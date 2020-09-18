from discord.ext import commands

class Hobby(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def quit(self, ctx):
        await ctx.send("帰ります")
        await self.bot.close()

    @commands.command()
    async def ping(self, ctx):
        await ctx.send("pong!")


def setup(bot):
    bot.add_cog(Hobby(bot))
