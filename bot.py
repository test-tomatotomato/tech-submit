import discord
from discord.ext import commands

import cogs.hobby as hobby
import cogs.player as player
import cogs.question as question

TOKEN = XXX

client = commands.Bot(command_prefix="$")

# テスト部屋
# CHANNEL_ID = XXXX

#  本番部屋
CHANNEL_ID = XXXXX


@client.event
async def on_ready():
    print("-----")
    print(client.user.name)
    print(client.user.id)
    print(discord.__version__)
    print("-----")
    channel = client.get_channel(CHANNEL_ID)
    try:
        question.setup(client)
        player.setup(client)
        hobby.setup(client)
        await channel.send("ただいま")
    except discord.errors.ClientException as e:
        print(e)
        await channel.send("またね")
        await client.close()

client.run(TOKEN)
