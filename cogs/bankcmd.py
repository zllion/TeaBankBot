import discord
import asyncio
import itertools
from discord.ext import commands

def check_admin_role(ctx):
    print(ctx.author.id,ctx.author.roles)
    return (ctx.author.id == ctx.bot.owner_id) or ('管理员' in [role.name for role in ctx.author.roles])

class bankcmd(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _toggle_number(self,n):
        amount = ['{:,}'.format(n),'{:.2e}'.format(n),]
        # English
        if n>=0 and n//(10**9) > 0 or n<0 and n//(10**9)<-1:
            amount.append('{:.2f}'.format(n/(10**9)).rstrip('0').rstrip('.')+'B')
        elif n>=0 and n//(10**6) > 0 or n<0 and n//(10**6)<-1:
            amount.append('{:.2f}'.format(n/(10**6)).rstrip('0').rstrip('.')+'M')
        elif n>=0 and n//(10**3) > 0 or n<0 and n//(10**3)<-1:
            amount.append('{:.2f}'.format(n/(10**3)).rstrip('0').rstrip('.')+'K')
        else:
            amount.append('{:,}'.format(n))
        # Chinese
        if n>=0 and n//(10**8) > 0 or n<0 and n//(10**8)<-1:
            amount.append('{:.2f}'.format(n/(10**8)).rstrip('0').rstrip('.')+'亿')
        elif n>=0 and n//(10**4) > 0 or n<0 and n//(10**4)<-1:
            amount.append('{:.2f}'.format(n/(10**4)).rstrip('0').rstrip('.')+'万')
        else:
            amount.append('{:,}'.format(n))
        #print(amount)
        return itertools.cycle(amount)

    async def _reply(self,ctx,premsg,*arg):
        user=ctx.message.author
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

    @commands.command(name='register',help='$register 新建账户')
    async def register(self,ctx):
        user=ctx.message.author
        try:
            self.bot.bank.CreateAccount(user.display_name,str(user.id))
        except ValueError as err:
            await ctx.send('```'+str(err)+'```')
        else:
            await ctx.send('```Congratulations! Your account is created!```')
        return

    @commands.command(name='deposit',help='$deposit n memo(Optional) 存钱进账户，游戏内需要存钱进军团钱包')
    async def deposit(self,ctx, n: int, memo = ''):
        user=ctx.message.author
        try:
            self.bot.bank.Deposit(n,user.display_name,str(user.id),memo)
        except ValueError as err:
            await ctx.send('```'+str(err)+'```')
        else:
            premsg = '```'+user.display_name+' has deposited {} isk```'
            await self._reply(ctx,premsg,n)

        return

    @commands.command(name='withdraw',help='$withdraw n memo(Optional) 从军团钱包取钱，@Toolman开钱包权限，建议攒笔大的一起提')
    async def withdraw(self,ctx, n: int, memo = ''):
        user=ctx.message.author
        try:
            self.bot.bank.Withdraw(n,user.display_name,str(user.id),memo)
        except ValueError as err:
            await ctx.send('```'+str(err)+'```')
        else:
            premsg = '```'+user.display_name+' has withdrawn {} isk```'
            await self._reply(ctx,premsg,n)
        return

    @commands.command(name='send',help='$send @username n memo(Optional) 转账,转账之前要先deposit')
    async def send(self,ctx: commands.Context, receiver: discord.User, n: int, memo=''):
        sender = ctx.message.author
        amount = self._toggle_number(n)
        premsg = '``` You will send '+receiver.display_name+' {} isk, press ✅ to confirm, ❌ to cancel.```'
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
            self.bot.bank.Transfer(n,sender.display_name,str(sender.id),receiver.display_name,str(receiver.id),memo)
        except ValueError as err:
            await ctx.send('```'+str(err)+'```')
        else:
            premsg = '```'+sender.display_name+' has sent '+receiver.display_name+' {} isk.```'
            await self._reply(ctx,premsg,n)
        return

    @commands.command(name='check',help='$check 查账户余额')
    async def check(self,ctx):
        user=ctx.message.author
        try:
            balance,pending = self.bot.bank.Check(user.display_name,str(user.id))
        except ValueError as err:
            await ctx.send('```'+str(err)+'```')
            return
        else:
            premsg = '```'+user.display_name + 'Account balance: {} isk, Pending: {} isk.```'
            await self._reply(ctx,premsg,balance,pending)

    @commands.command(name='record', help='$record n(Optional) 查询最近n笔交易')
    async def record(self,ctx,n=5):
        user=ctx.message.author
        try:
            data=self.bot.bank.PullTransactions(user.id,n)
        except ValueError as err:
            await ctx.send('```'+str(err)+'```')
        else:
            fields = {}
            fields['Receiver'] = [p[5] for p in data]
            maxl = max([len(str(p[2]))+len(str(p[2]))//3 for p in data])+1
            amount = [self._toggle_number(int(p[2])) for p in data]
            fields['Action'] = [data[i][3].ljust(8,'.')+next(amount[i]).rjust(maxl,'.')+' isk' for i in range(len(amount))]
            fields['Time'] = [p[1] for p in data]
            embed = discord.Embed(title = 'Record', description = 'Check recent {} records, 🔄 changes the number representation'.format(n))
            for key in fields:
                embed.add_field(name = key, value = '\n'.join(fields[key]))
            msg = await ctx.send(embed=embed)
            await msg.add_reaction('🔄')
            def check(reaction, user):
                return user == ctx.author and reaction.message == msg
            while True:
                try:
                    reaction, user = await self.bot.wait_for('reaction_add', timeout=600.0, check=check)
                except asyncio.TimeoutError:
                    break
                else:
                    if reaction.emoji == '🔄':
                        await reaction.remove(user)
                        fields['Action'] = [data[i][3].ljust(8,'.')+next(amount[i]).rjust(maxl,'.')+' isk' for i in range(len(amount))]
                        embed.set_field_at(1,name = 'Action', value = '\n'.join(fields['Action']))
                        await msg.edit(embed = embed)
                        continue

    @commands.command(name='recall', help='$record 取消上一笔存款或取款操作')
    async def recall(self,ctx):
        user=ctx.message.author
        try:
            data=self.bot.bank.PullTransactions(user.id,1)[0]
        except ValueError as err:
            await ctx.send('```'+str(err)+'```')
        else:
            if not data:
                await ctx.send('```No transaction found```')
            elif data[3] != 'deposit' and data[3] !='withdraw':
                await ctx.send('```Last transaction cannot be retracted.```')
            elif data[6] != 'pending':
                await ctx.send('```Last transaction has already been auditted.```')
            else:
                msg = await ctx.send('```Confirm recalling this transaction {} {} isk```'.format(data[3],data[2]))
                await msg.add_reaction('✅') # check mark
                await msg.add_reaction('❌') # cross
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
                            self.bot.bank.Deny(data[0],ctx.author.display_name)
                            await ctx.send('```Recalled```')
                            return
                        elif reaction.emoji == '❌':
                            await ctx.send('```Cancelled```')
                            return


    def _embed_edit(self,embed,fields,i,emoji):
        fields['Name'][i] = emoji + fields['Name'][i]
        value = '\n'.join(fields['Name'])
        embed.set_field_at(0,name = 'Name', value = value)
        return

    def _backup_to_gs(self):
        self.bot.bank.BackUpGS()
        return

    @commands.command(name='audit', help='$audit 审计，只有@管理员可以使用')
    @commands.check(check_admin_role)
    async def audit(self,ctx):
        user = ctx.author
        user_name = ctx.author.display_name
        pendings = self.bot.bank.GetPendings()[::-1]
        if pendings == []:
            await ctx.send('```No pending transactions```')
            self._backup_to_gs()
            return
        fields = {}
        fields['Name'] = [p[4] for p in pendings]
        maxl = max([len(str(p[2]))+len(str(p[2]))//3 for p in pendings])+1
        amount = [self._toggle_number(int(p[2])) for p in pendings]
        fields['Action'] = [pendings[i][3].ljust(8,'.')+next(amount[i]).rjust(maxl,'.')+' isk' for i in range(len(amount))]
        fields['Time'] = [p[1] for p in pendings]
        embed = discord.Embed(title = 'Audit process', description = '👍 will approve all. \n✅ will approve next. \n❌ will deny next.\
        \n⏸️ will skip next. \nMay take some time to interact with the database.')
        for key in fields:
            value = '\n'.join(fields[key])
            embed.add_field(name = key, value = value)
        msg = await ctx.send(embed=embed)
        await msg.add_reaction('👍')
        await msg.add_reaction('✅') # check mark
        await msg.add_reaction('❌') # cross
        await msg.add_reaction('⏸️') # stop
        await msg.add_reaction('🔄')
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
                    self.bot.bank.Approve(pendings[i][0],user_name)
                    await reaction.remove(user)
                    self._embed_edit(embed,fields,i,reaction.emoji)
                    await msg.edit(embed = embed)
                elif reaction.emoji == '❌':
                    self.bot.bank.Deny(pendings[i][0],user_name)
                    await reaction.remove(user)
                    self._embed_edit(embed,fields,i,reaction.emoji)
                    await msg.edit(embed = embed)
                elif reaction.emoji == '👍':
                    while i < l:
                        self.bot.bank.Approve(pendings[i][0],user_name)
                        self._embed_edit(embed,fields,i,'✅')
                        await msg.edit(embed = embed)
                        i += 1
                    await reaction.remove(user)
                elif reaction.emoji == '⏸️':
                    await reaction.remove(user)
                    self._embed_edit(embed,fields,i,reaction.emoji)
                    await msg.edit(embed = embed)
                elif reaction.emoji == '🔄':
                    await reaction.remove(user)
                    fields['Action'] = [pendings[i][3].ljust(8,'.')+next(amount[i]).rjust(maxl,'.')+' isk' for i in range(len(amount))]
                    embed.set_field_at(1,name = 'Action', value ='\n'.join(fields['Action']))
                    await msg.edit(embed = embed)
                    continue
                else:
                    continue
                i += 1
        self.bot.bank.conn.commit()
        self._backup_to_gs()
        return



def setup(bot):
    bot.add_cog(bankcmd(bot))
