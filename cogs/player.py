import discord
from discord.ext import commands

class Player(commands.Cog):
    players = []

    def __init__(self, bot):
        self.bot = bot
        self.members = [
            member.name for member in self.bot.get_all_members() if not member.bot
        ]

    def get_player(self):
        return self.__class__.players

    def set_player(self, player_list):
        self.__class__.players = player_list

    @commands.command()
    async def getm(self, ctx):
        """
        サーバに所属しているメンバ一覧
        """
        embed = discord.Embed(title="メンバー", description="{}".format(self.members))
        await ctx.send(embed=embed)

    @commands.command()
    async def getp(self, ctx):
        """
        参加メンバの確認
        """
        embed = discord.Embed(
            title="参加メンバー", description="{}".format(self.__class__.players)
        )
        await ctx.send(embed=embed)

    @commands.command()
    async def setp(self, ctx, *args):
        """
        参加メンバの登録
        """
        self.__class__.players = [
            self.members[int(args[i])] for i in range(0, len(args))
        ]
        embed = discord.Embed(
            title="参加メンバー", description="{}".format(self.__class__.players)
        )
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Player(bot))