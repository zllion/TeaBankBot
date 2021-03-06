import os
import logging
import random
import discord
from datetime import datetime
from discord.ext import commands
from dotenv import load_dotenv
from teabank import SQLBank

logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN_TEST')

extensions = (
    "cogs.bankcmd",
    "cogs.test",
    #"cogs.bet"
    )

intents = discord.Intents.default()
intents.members = True

class BankBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bank = SQLBank('TestBank','testbank.db')
        for extension in extensions:
            self.load_extension(extension)
        return

TeaBot = BankBot(command_prefix='¥',owner_id = 356096513828454411, intents = intents)

TeaBot.run(TOKEN)
