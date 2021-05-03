import discord
import asyncio
from discord.ext import commands
from gspread.exceptions import CellNotFound

def check_audit_role(ctx):
    #print(ctx.author.id,ctx.bot.owner_id,ctx.author.roles)
    return (ctx.author.id == ctx.bot.owner_id) or ('管理员' in [role.name for role in ctx.author.roles])

class bankcmd(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='register',help='$register 新建账户')
    async def register(self,ctx):
        user=ctx.message.author
        try:
            self.bot.bank.CreateAccount(user.display_name,str(user.id))
        except ValueError as err:
            await ctx.send(err)
        else:
            await ctx.send('Congratulations! Your account is created!')
        return

    @commands.command(name='deposit',help='$deposit n 存钱进账户，游戏内需要存钱进军团钱包')
    async def deposit(self,ctx, n: int):
        user=ctx.message.author
        try:
            self.bot.bank.Deposit(n,user.display_name,str(user.id))
            await ctx.send(user.display_name+' has deposited '+'{:,}'.format(n)+' isk.')
        except ValueError as err:
            await ctx.send(err)
        return

    @commands.command(name='withdraw',help='$withdraw n 从军团钱包取钱，@Toolman开钱包权限，建议攒笔大的一起提')
    async def withdraw(self,ctx, n: int):
        user=ctx.message.author
        try:
            self.bot.bank.Withdraw(n,user.display_name,str(user.id))
            await ctx.send(user.display_name+' has withdrawn '+'{:,}'.format(n)+' isk.')
        except ValueError as err:
            await ctx.send(err)
        return

    @commands.command(name='send',help='$send @username n <memo> 转账,转账之前要先deposit')
    async def send(self,ctx: commands.Context, receiver: discord.User, n: int, memo=''):
        sender = ctx.message.author
        try:
            self.bot.bank.Transfer(n,sender.display_name,str(sender.id),receiver.display_name,str(receiver.id),memo)
            await ctx.send(sender.display_name+' has sent '+receiver.display_name+' {:,}'.format(n)+' isk.')
        except ValueError as err:
            await ctx.send(err)
        return

    @commands.command(name='check',help='$check 查账户余额')
    async def check(self,ctx):
        user=ctx.message.author
        try:
            balance,pending = self.bot.bank.Check(user.display_name,str(user.id))
        except ValueError as err:
            await ctx.send(err)
            return
        await ctx.send(user.display_name + 'Account balance: '+'{:,}'.format(balance)+'; pending: '+'{:,}'.format(pending))

    def _embed_edit(self,embed,fields,i,emoji):
        fields['Name'][i] = emoji + fields['Name'][i]
        value = '\n'.join(fields['Name'])
        embed.set_field_at(0,name = 'Name', value = value)
        return

    def _backup_to_gs(self):
        self.bot.bank.BackUpGS()
        return

    @commands.command(name='audit', help='$audit 审计，只有@管理员可以使用')
    @commands.check(check_audit_role)
    async def audit(self,ctx):
        user = ctx.author
        user_name = ctx.author.display_name
        pendings = self.bot.bank.GetPendings()
        if pendings == []:
            await ctx.send('No pending transactions')
            self._backup_to_gs()
            return
        fields = {}
        fields['Name'] = [p[4] for p in pendings]
        fields['Type'] = [p[3] for p in pendings]
        fields['Amount'] = ['{:,}'.format(int(p[2])) for p in pendings]
        fields['Time'] = [p[1] for p in pendings]
        embed = discord.Embed(title = 'Audit process', description = '👍 will approve all, ✅ will approve next, ❌ will deny next.\
        \n May take some time to interact with the database.')
        for key in fields:
            embed.add_field(name = key, value = '\n'.join(fields[key]))
        msg = await ctx.send(embed=embed)
        await msg.add_reaction('👍')
        await msg.add_reaction('✅') # check mark
        await msg.add_reaction('❌') # cross
        l = len(pendings)
        i = 0
        def check(reaction, user):
            return user == ctx.author and reaction.message == msg
        while i < l:
            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=3600.0, check=check)
            except asyncio.TimeoutError:
                await ctx.send('time out')
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
                i += 1
        self.bot.bank.conn.commit()
        self._backup_to_gs()
        return



def setup(bot):
    bot.add_cog(bankcmd(bot))
