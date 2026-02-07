import discord
import asyncio
import itertools
import sqlite3
from tabulate import tabulate
from discord.ext import commands

from src.services.bank_service import BankService
from src.repositories.account_repo import AccountRepository
from src.repositories.transaction_repo import TransactionRepository
from src.models.exceptions import BankError


def check_admin_role(ctx):
    print(ctx.author.id, ctx.author.roles)
    return (ctx.author.id == ctx.bot.owner_id) or ('管理员' in [role.name for role in ctx.author.roles])


class bankcmd(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Initialize BankService with repositories and settings
        settings = bot.settings

        # Create database connection
        db_path = settings.test_db_path if settings.is_test else settings.prod_db_path
        conn = sqlite3.connect(db_path)

        # Initialize repositories
        account_repo = AccountRepository(conn)
        transaction_repo = TransactionRepository(conn)

        # Create tables if they don't exist
        account_repo.create_table()
        transaction_repo.create_table()

        # Initialize BankService with business rule parameters from settings
        self.bank_service = BankService(
            account_repo=account_repo,
            transaction_repo=transaction_repo,
            min_amount=1,
            max_amount=settings.max_deposit_amount,
            min_balance=settings.min_balance,
        )

        # Store connection for backup operations
        self._conn = conn

    def _toggle_number(self, n):
        amount = ['{:,}'.format(n), '{:.2e}'.format(n), ]
        # English
        if n >= 0 and n//(10**9) > 0 or n < 0 and n//(10**9) < -1:
            amount.append('{:.2f}'.format(
                n/(10**9)).rstrip('0').rstrip('.')+'B')
        elif n >= 0 and n//(10**6) > 0 or n < 0 and n//(10**6) < -1:
            amount.append('{:.2f}'.format(
                n/(10**6)).rstrip('0').rstrip('.')+'M')
        elif n >= 0 and n//(10**3) > 0 or n < 0 and n//(10**3) < -1:
            amount.append('{:.2f}'.format(
                n/(10**3)).rstrip('0').rstrip('.')+'K')
        else:
            amount.append('{:,}'.format(n))
        # Chinese
        if n >= 0 and n//(10**8) > 0 or n < 0 and n//(10**8) < -1:
            amount.append('{:.2f}'.format(
                n/(10**8)).rstrip('0').rstrip('.')+'亿')
        elif n >= 0 and n//(10**4) > 0 or n < 0 and n//(10**4) < -1:
            amount.append('{:.2f}'.format(
                n/(10**4)).rstrip('0').rstrip('.')+'万')
        else:
            amount.append('{:,}'.format(n))
        #print(amount)
        return itertools.cycle(amount)

    async def _reply(self, ctx, premsg, *arg):
        user = ctx.message.author
        amount = [self._toggle_number(n) for n in arg]
        s = [next(n) for n in amount]
        msg = await ctx.send(premsg.format(*s))
        await msg.add_reaction('🔄')

        def check(reaction, user):
            return not user.bot and reaction.message == msg
        while True:
            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=3600.0, check=check)
            except asyncio.TimeoutError:
                break
            else:
                if reaction.emoji == '🔄':
                    await reaction.remove(user)
                    s = [next(n) for n in amount]
                    await msg.edit(content=premsg.format(*s))

    @commands.command(name='register', help='$register 新建账户')
    async def register(self, ctx):
        user = ctx.message.author
        try:
            self.bank_service.create_account(str(user.id), user.display_name)
        except BankError as err:
            await ctx.send('```'+str(err)+'```')
        else:
            await ctx.send('```Congratulations! Your account is created!```')
        return

    @commands.command(name='deposit', help='$deposit n memo(Optional) 存钱进账户，游戏内需要存钱进军团钱包')
    async def deposit(self, ctx, n: int, *args):
        user = ctx.message.author
        memo = (' '.join(args)).lstrip('<').rstrip('>')
        try:
            self.bank_service.deposit(str(user.id), n, memo)
        except BankError as err:
            await ctx.send('```'+str(err)+'```')
        else:
            premsg = '```'+user.display_name+' has deposited {} isk```'
            await self._reply(ctx, premsg, n)
        return

    @commands.command(name='withdraw', help='$withdraw n memo(Optional) 从军团钱包取钱，@Toolman开钱包权限，建议攒笔大的一起提')
    async def withdraw(self, ctx, n: int, *args):
        user = ctx.message.author
        memo = (' '.join(args)).lstrip('<').rstrip('>')
        try:
            self.bank_service.withdraw(str(user.id), n, memo)
        except BankError as err:
            await ctx.send('```'+str(err)+'```')
        else:
            premsg = '```'+user.display_name+' has withdrawn {} isk```'
            await self._reply(ctx, premsg, n)
        return

    @commands.command(name='send', help='$send @username n memo(Optional) 转账,转账之前要先deposit')
    async def send(self, ctx: commands.Context, receiver: discord.User, n: int, *args):
        sender = ctx.message.author
        amount = self._toggle_number(n)
        memo = (' '.join(args)).lstrip('<').rstrip('>')
        premsg = '``` You will send '+receiver.display_name + \
            ' {} isk, press ✅ to confirm, ❌ to cancel.```'
        msg = await ctx.send(premsg.format(next(amount)))
        await msg.add_reaction('🔄')
        await msg.add_reaction('✅')
        await msg.add_reaction('❌')

        def check(reaction, user):
            return not user.bot and reaction.message == msg
        while True:
            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=600.0, check=check)
            except asyncio.TimeoutError:
                await ctx.send('Time out')
                return
            else:
                if reaction.emoji == '🔄':
                    await reaction.remove(user)
                    await msg.edit(content=premsg.format(next(amount)))
                    continue
                elif reaction.emoji == '✅':
                    break
                elif reaction.emoji == '❌':
                    await ctx.send('Action canceled!')
                    return
        try:
            self.bank_service.transfer(str(sender.id), str(receiver.id), n, memo)
        except BankError as err:
            await ctx.send('```'+str(err)+'```')
        else:
            premsg = '```'+sender.display_name+' has sent ' + \
                receiver.display_name+' {} isk.```'
            await self._reply(ctx, premsg, n)
        return

    @commands.command(name='request', help='$request n memo(Optional) 向军团会计索取费用，通常用于与会计好交易，当铺，制造，或赎回基金')
    async def request(self, ctx, n: int, *args):
        user = ctx.message.author
        memo = (' '.join(args)).lstrip('<').rstrip('>')
        try:
            self.bank_service.request(str(user.id), n, memo)
        except BankError as err:
            await ctx.send('```'+str(err)+'```')
        else:
            premsg = '```'+user.display_name+' has requested {} isk```'
            await self._reply(ctx, premsg, n)
        return

    @commands.command(name='donate', help='$donate n memo(optional) 从个人账户向军团账户捐赠/转账，用于与会计号交易或者购买基金')
    async def donate(self, ctx, n: int, *args):
        user = ctx.message.author
        memo = (' '.join(args)).lstrip('<').rstrip('>')
        try:
            self.bank_service.donate(str(user.id), n, memo)
        except BankError as err:
            await ctx.send('```'+str(err)+'```')
        else:
            premsg = '```'+user.display_name+' has donated {} isk```'
            await self._reply(ctx, premsg, n)
        return

    @commands.command(name='check', help='$check 查账户余额')
    async def check(self, ctx):
        user = ctx.message.author
        try:
            balance, pending = self.bank_service.get_balance(str(user.id))
        except BankError as err:
            await ctx.send('```'+str(err)+'```')
            return
        else:
            premsg = '```'+user.display_name + 'Account balance: {} isk, Pending: {} isk.```'
            await self._reply(ctx, premsg, balance, pending)

    @commands.command(name='record', help='$record n(Optional) 查询最近n笔交易')
    async def record(self, ctx, n=5):
        user = ctx.message.author
        try:
            transactions = self.bank_service.pull_transactions(str(user.id), n)
        except BankError as err:
            await ctx.send('```'+str(err)+'```')
        else:
            if not transactions:
                await ctx.send('```No transactions found```')
                return

            amount = [self._toggle_number(int(txn.amount)) for txn in transactions]
            datadict = {
                'Transaction ID': [txn.id for txn in transactions],
                'Time': [txn.time.strftime('%Y%m%d') for txn in transactions],
                'Amount': [next(amount[i]) for i in range(len(transactions))],
                'Type': [txn.type for txn in transactions],
                'Sender': [txn.sender_account for txn in transactions],
                'Receiver': [txn.receiver_account for txn in transactions],
                'Status': [txn.status for txn in transactions],
                'Memo': [txn.memo for txn in transactions]
            }
            header = ['Type', 'Amount', 'Sender', 'Receiver', 'Memo']
            content = tabulate(
                [header] + [[datadict[h][i] for h in header] for i in range(len(transactions))],
                headers="firstrow",
                stralign='right',
                numalign='right'
            )
            msg = await ctx.send('```'+content+'```')
            await msg.add_reaction('🔄')

            def check(reaction, user):
                return user == ctx.author and reaction.message == msg
            while True:
                try:
                    reaction, user = await self.bot.wait_for('reaction_add', timeout=1800.0, check=check)
                except asyncio.TimeoutError:
                    break
                else:
                    if reaction.emoji == '🔄':
                        await reaction.remove(user)
                        datadict['Amount'] = [next(amount[i]) for i in range(len(transactions))]
                        content = tabulate(
                            [header] + [[datadict[h][i] for h in header] for i in range(len(transactions))],
                            headers="firstrow",
                            stralign='right',
                            numalign='right'
                        )
                        await msg.edit(content='```'+content+'```')
                        continue

    @commands.command(name='recall', help='$recall 取消上一笔存款或取款操作')
    async def recall(self, ctx):
        user = ctx.message.author
        try:
            transactions = self.bank_service.pull_transactions(str(user.id), 1)
            if not transactions:
                await ctx.send('```No transaction found```')
                return

            data = transactions[0]
            if data.type not in ['deposit', 'withdraw', 'donate', 'request']:
                await ctx.send('```Last transaction cannot be retracted.```')
            elif data.status != 'pending':
                await ctx.send('```Last transaction has already been auditted.```')
            else:
                msg = await ctx.send('```Confirm recalling this transaction {} {} isk```'.format(data.type, data.amount))
                await msg.add_reaction('✅')  # check mark
                await msg.add_reaction('❌')  # cross

                def check(reaction, user):
                    return user == ctx.author and reaction.message == msg
                while True:
                    try:
                        reaction, user = await self.bot.wait_for('reaction_add', timeout=600.0, check=check)
                    except asyncio.TimeoutError:
                        await ctx.send('time out')
                        return
                    else:
                        if reaction.emoji == '✅':
                            self.bank_service.deny_transaction(data.id, ctx.author.display_name)
                            await ctx.send('```Recalled```')
                            return
                        elif reaction.emoji == '❌':
                            await ctx.send('```Cancelled```')
                            return
        except BankError as err:
            await ctx.send('```'+str(err)+'```')

    def _embed_edit(self, embed, fields, i, emoji):
        fields['Name'][i] = emoji + fields['Name'][i]
        value = '\n'.join(fields['Name'])
        embed.set_field_at(0, name='Name', value=value)
        return

    def _backup_to_gs(self):
        # TODO: Implement Google Sheets backup
        # self.bot.bank.BackUpGS()
        return

    @commands.command(name='audit', help='$audit 审计，只有@管理员可以使用')
    @commands.check(check_admin_role)
    async def audit(self, ctx):
        settings = self.bot.settings
        max_output = settings.audit_max_output
        user = ctx.author
        user_name = ctx.author.display_name
        pendings = self.bank_service.get_pending_transactions(max_output)

        if not pendings:
            await ctx.send('```No pending transactions```')
            self._backup_to_gs()
            return

        fields = {}
        fields['Name'] = [p.receiver_account for p in pendings]
        maxl = max([len(str(p.amount))+len(str(p.amount))//3 for p in pendings])+1
        amount = [self._toggle_number(int(p.amount)) for p in pendings]
        fields['Action'] = [pendings[i].type.ljust(
            8, '.')+next(amount[i]).rjust(maxl, '.')+' isk' for i in range(len(amount))]
        fields['Time'] = [p.time.strftime('%Y%m%d') for p in pendings]
        embed = discord.Embed(title='Audit process', description=f'👍 will approve all. \n✅ will approve next. \n❌ will deny next.\
        \n⏸️ will skip next. \nMay take some time to interact with the database.\nMaximum output is {max_output}')
        for key in fields:
            value = '\n'.join(fields[key])
            embed.add_field(name=key, value=value)
        msg = await ctx.send(embed=embed)
        await asyncio.gather(
            msg.add_reaction('👍'),
            msg.add_reaction('✅'),
            msg.add_reaction('❌'),
            msg.add_reaction('⏸️'),
            msg.add_reaction('🔄')
        )
        l = len(pendings)
        i = 0

        def check(reaction, user):
            return user == ctx.author and reaction.message == msg
        while i < l:
            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=600.0, check=check)
            except asyncio.TimeoutError:
                await ctx.send('time out')
                break
            else:
                if reaction.emoji == '✅':
                    self.bank_service.approve_transaction(pendings[i].id, user_name)
                    await reaction.remove(user)
                    self._embed_edit(embed, fields, i, reaction.emoji)
                    await msg.edit(embed=embed)
                elif reaction.emoji == '❌':
                    self.bank_service.deny_transaction(pendings[i].id, user_name)
                    await reaction.remove(user)
                    self._embed_edit(embed, fields, i, reaction.emoji)
                    await msg.edit(embed=embed)
                elif reaction.emoji == '👍':
                    while i < l:
                        self.bank_service.approve_transaction(pendings[i].id, user_name)
                        self._embed_edit(embed, fields, i, '✅')
                        await msg.edit(embed=embed)
                        i += 1
                    await reaction.remove(user)
                elif reaction.emoji == '⏸️':
                    await reaction.remove(user)
                    self._embed_edit(embed, fields, i, reaction.emoji)
                    await msg.edit(embed=embed)
                elif reaction.emoji == '🔄':
                    await reaction.remove(user)
                    fields['Action'] = [pendings[i].type.ljust(
                        8, '.')+next(amount[i]).rjust(maxl, '.')+' isk' for i in range(len(amount))]
                    embed.set_field_at(
                        1, name='Action', value='\n'.join(fields['Action']))
                    await msg.edit(embed=embed)
                    continue
                else:
                    continue
                i += 1
        self._conn.commit()
        self._backup_to_gs()
        return

    @commands.command(name='admin-send', help='$admin-send n memo(Optional) 会计号向成员账号转账，只有管理员可以使用')
    @commands.check(check_admin_role)
    async def admin_send(self, ctx: commands.Context, receiver: discord.User, n: int, *args):
        operator = ctx.message.author
        memo = (' '.join(args)).lstrip('<').rstrip('>')
        amount = self._toggle_number(n)
        premsg = '``` Corp will send '+receiver.display_name + \
            ' {} isk, press ✅ to confirm, ❌ to cancel.```'
        msg = await ctx.send(premsg.format(next(amount)))
        await msg.add_reaction('🔄')
        await msg.add_reaction('✅')
        await msg.add_reaction('❌')

        def check(reaction, user):
            return not user.bot and reaction.message == msg
        while True:
            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=600.0, check=check)
            except asyncio.TimeoutError:
                await ctx.send('Time out')
                return
            else:
                if reaction.emoji == '🔄':
                    await reaction.remove(user)
                    await msg.edit(content=premsg.format(next(amount)))
                    continue
                elif reaction.emoji == '✅':
                    break
                elif reaction.emoji == '❌':
                    await ctx.send('Action canceled!')
                    return
        try:
            # TODO: Implement admin_send in BankService
            # For now, we'll use transfer as a workaround
            self.bank_service.transfer(str(operator.id), str(receiver.id), n, memo)
        except BankError as err:
            await ctx.send('```'+str(err)+'```')
        else:
            premsg = '```Corp has sent '+receiver.display_name+' {} isk.```'
            await self._reply(ctx, premsg, n)
        return


def setup(bot):
    bot.add_cog(bankcmd(bot))
    print('bankcmd is loaded')
