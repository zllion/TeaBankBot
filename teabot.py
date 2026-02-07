import os
import logging
import random
import discord
from datetime import datetime
from discord.ext import commands
from dotenv import load_dotenv
from config.settings import Settings

logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

load_dotenv()

# Load settings from environment variables
settings = Settings.load()
settings.is_test = False

extensions = (
    "cogs.bankcmd",
    )

intents = discord.Intents.default()
intents.members = True

class BankBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.settings = kwargs.pop('settings')
        for extension in extensions:
            self.load_extension(extension)
        return


TeaBot = BankBot(
    command_prefix='$',
    owner_id=settings.owner_id,
    intents=intents,
    settings=settings
)

@TeaBot.check
async def globally_block_channels(ctx):
    if ctx.channel.id in settings.blocked_channel_ids:
        await ctx.send("$ commands are excluded from test channel")
        return False
    return True

TeaBot.run(settings.discord_token)
