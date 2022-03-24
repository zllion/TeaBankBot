import discord
import asyncio
from discord.ext import commands
# from discord_ui import Button, View

def check_audit_role(ctx):
    #print(ctx.author.id,ctx.bot.owner_id,ctx.author.roles)
    return (ctx.author.id == ctx.bot.owner_id) or ('管理员' in ctx.author.roles)

class test(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='test',help='')
    async def test(self,ctx):
        user = ctx.author
        #message = await ctx.send('```Please explain the bug```')
        embed = discord.Embed(title = 'Audit process', description = '\N{THUMBS UP SIGN} will approve all, \U00002705 will approve next, \U0000274C will deny next')
        embed.add_field(name = 'test name', value = 'test value \n test value',inline = False)
        embed.add_field(name = 'test name', value = 'test value',inline = True)
        embed.add_field(name = 'test name', value = 'test value',inline = True)
        message = await ctx.send(embed = embed)
        # thumb = await message.add_reaction('\N{THUMBS UP SIGN}')
        check = await message.add_reaction('✅') # check mark
        cross = await message.add_reaction('❌') # cross
        def check(reaction, user):
            return user == ctx.author and reaction.message == message
        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=3600.0, check=check)
        except asyncio.TimeoutError:
            await ctx.send('time out')
        else:
            if reaction.emoji == '✅' or reaction.emoji == '❌':
                embed.set_field_at(0,name = 'test name', value = reaction.emoji +' test value \n test value', inline = False)
                await message.edit(embed = embed)
                await reaction.remove(user)
        return

    @commands.command(name='thumb')
    async def thumb(self,ctx):
        message = ctx.message
        channel = message.channel
        # button = Button(label="test", style=discord.ButtonStyle.green, emoji='👍')
        m = await channel.send('Send me that 👍 reaction, mate')
        react1 = await m.add_reaction('👍')
        react2 = await m.add_reaction('👎')
        # view = View()
        # view.add_item(button)
        # await ctx.send('Hi', view=view)
        def check(reaction, user):
            return user == message.author and (str(reaction.emoji) == '👍' or str(reaction.emoji) == '👎')
        for i in range(10):
            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=3600.0, check=check)
            except asyncio.TimeoutError:
                await channel.send('👎')
            else:
                if reaction.emoji == '👍':
                    await channel.send('👍')
                else:
                    await reaction.remove(user)

    @commands.command(name='userinfo')
    async def userinfo(self,ctx: commands.Context, user: discord.User):
        user_id = user.id
        username = user.display_name
        await ctx.send(f'User found: {user_id} -- {username}\n{avatar}')

    @commands.command(name='ping')
    async def ping(self,ctx):
        channel = self.bot.get_channel(852038266529513482)
        await channel.send('!!!')
        print(channel.guild,channel.name)

    async def simp_send(self,msg):
        channel = self.bot.get_channel(854718183385595914)
        await channel.send(msg)
        print("sent")



def setup(bot):
    bot.add_cog(test(bot))
    print('test loaded')
