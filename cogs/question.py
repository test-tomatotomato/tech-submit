import asyncio
import io
import os
import random
import re
import shutil
import string
from pathlib import Path
from time import sleep
from typing import List, Optional, Tuple

import discord
import selenium.webdriver
from bs4 import BeautifulSoup
from discord.ext import commands
from PIL import Image
from selenium.webdriver import Chrome, ChromeOptions

from . import player

URL = "https://www.ap-siken.com/s/apkakomon.php"

options = ChromeOptions()
options.add_argument("--headless")
driver = Chrome(options=options)

driver.get(URL)
html = driver.page_source.encode("utf-8")
soup = BeautifulSoup(html, "lxml")

base_path = "PATH"
correct_dir = str(base_path / "image" / "correct")
incorrect_dir = str(base_path / "image" / "incorrect")


def click_by_name(name, order):
    driver.execute_script(
        "document.getElementsByName('" + name + "')['" + str(order) + "'].click();"
    )


def click_by_name_temp(name):
    driver.execute_script("document.getElementsByName('" + name + "').click();")


def generate_name(n):
    return "".join(random.choices(string.ascii_letters + string.digits, k=n))


def generate_nonce(n):
    return "".join(random.choices(string.digits, k=n))


def take_screenshot(filename):
    # File Name
    file_path = str(base_path / "image" / "{}.png".format(filename))
    # get width and height of the page
    w = driver.execute_script("return document.body.scrollWidth;")
    h = driver.execute_script("return document.body.scrollHeight;")
    # set window size
    driver.set_window_size(w, h)
    # Get Screen Shot
    driver.save_screenshot(file_path)
    return file_path


def get_full_screenshot_image(driver, reverse=False, driverss_contains_scrollbar=None):
    if driverss_contains_scrollbar is None:
        driverss_contains_scrollbar = isinstance(driver, selenium.webdriver.Chrome)
    # Scroll to the bottom of the page once
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    sleep(1)
    (
        scroll_height,
        document_client_width,
        document_client_height,
        inner_width,
        inner_height,
    ) = driver.execute_script(
        "return [document.body.scrollHeight, document.documentElement.clientWidth, document.documentElement.clientHeight, window.innerWidth, window.innerHeight]"
    )
    streams_to_be_closed = []  # type: List[io.BytesIO]
    images = []  # type: List[Tuple[Image.Image, int]]
    try:
        # open
        for y_coord in range(0, scroll_height, document_client_height):
            driver.execute_script("window.scrollTo(0, arguments[0]);", y_coord)
            stream = io.BytesIO(driver.get_screenshot_as_png())
            streams_to_be_closed.append(stream)
            img = Image.open(stream)
            # Image, y_coord
            images.append((img, min(y_coord, scroll_height - inner_height)))
        # load
        scale = float(img.size[0]) / (
            inner_width if driverss_contains_scrollbar else document_client_width
        )
        img_dst = Image.new(
            mode="RGBA",
            size=(int(document_client_width * scale), int(scroll_height * scale)),
        )
        for img, y_coord in reversed(images) if reverse else images:
            img_dst.paste(img, (0, int(y_coord * scale)))
        return img_dst
    finally:
        # close
        for stream in streams_to_be_closed:
            stream.close()
        for img, y_coord in images:
            img.close()


def field(te_flag, ma_flag, st_flag):
    # 出題設定を分野指定に移動
    driver.find_element_by_xpath('// *[ @ id = "tabs"] / ul / li[2] / a').click()
    # 全項目チェックをOFFにする
    driver.find_element_by_xpath('//*[@id="tab2"]/ul[1]/p/button[2]').click()
    # 分野指定について
    field = soup.find(attrs={"value": "te_all"})
    # name属性は他と重複しているため別途で数値を与える必要がある
    if te_flag == "on":
        # テクノロジ系の出題範囲を1-4に絞る
        for order in range(10, 14):
            # get("name")に与える数値は0から始まるのでマイナス１
            click_by_name(
                (soup.find(attrs={"value": "{}".format(order)})).get("name"), order - 1
            )
    if ma_flag == "on":
        click_by_name(field.get("name"), 1)
    if st_flag == "on":
        click_by_name(field.get("name"), 2)


def create_dir(players):
    for player in players:
        if not Path(base_path / "image" / player / "correct").exists():
            Path(base_path / "image" / player / "correct").mkdir(
                parents=True, exist_ok=True
            )
            print("player: {} correct".format(player))
        else:
            print("player: {} correct is already exsists".format(player))
        if not Path(base_path / "image" / player / "incorrect").exists():
            Path(base_path / "image" / player / "incorrect").mkdir(
                parents=True, exist_ok=True
            )
            print("player: {} incorrect".format(player))
        else:
            print("player: {} incorrect is already exsists".format(player))


def option(cal_flag):
    # 出題オプション
    option = soup.find(attrs={"value": "random"})
    # 計算問題について
    if cal_flag == "on":
        click_by_name(option.get("name"), 6)
    elif cal_flag == "off":
        click_by_name(option.get("name"), 5)
    # 問題をランダム
    click_by_name(option.get("name"), 3)
    # 解説ないのは出題しない
    click_by_name(option.get("name"), 4)
    # 開催年度について
    filter = soup.find(attrs={"value": "timesFilter"})
    click_by_name(filter.get("name"), 0)
    year = soup.find(attrs={"value": "01_aki"})
    # 平成28年度以降を対象にする
    click_by_name(year.get("name"), 30)
    click_by_name(year.get("name"), 31)
    click_by_name(year.get("name"), 32)
    click_by_name(year.get("name"), 33)
    click_by_name(year.get("name"), 34)
    click_by_name(year.get("name"), 35)
    click_by_name(year.get("name"), 36)
    click_by_name(year.get("name"), 37)


# コグとして用いるクラスを定義。
class Question(commands.Cog):

    # TestCogクラスのコンストラクタ。Botを受取り、インスタンス変数として保持。
    def __init__(self, bot):
        self.bot = bot
        self.question_number = 1
        self.choice = {}
        self.players = []
        self.te_flag = "off"
        self.ma_flag = "off"
        self.st_flag = "off"

    @commands.command()
    async def set_field(self, ctx, te_flag, ma_flag, st_flag):
        """
        on/off: [テクノロジ系] [マネジメント系] [ストラテジー系]
        """
        embed = discord.Embed(
            title="設定状況",
            description="テクノロジ系: {}, マネジメント系: {}, ストラテジ系: {}".format(
                te_flag, ma_flag, st_flag
            ),
        )
        field(te_flag, ma_flag, st_flag)
        await ctx.send(embed=embed)

    @commands.command()
    async def set_option(self, ctx, cal_flag):
        """
        on/off: [計算問題]
        """
        embed = discord.Embed(title="設定状況", description="計算問題: {}".format(cal_flag))
        option(cal_flag)
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.content == "ただいま":
            pass

            # 参加者登録
            self.combination = {}
            members = [
                member.name for member in self.bot.get_all_members() if not member.bot
            ]
            embed = discord.Embed(
                title="参加者を登録して",
                description="{}".format(members),
                color=discord.Colour.gold(),
            )
            regist_player = await message.channel.send(embed=embed)
            for counter in range(len(members)):
                reac_code = chr(ord("\U0001f470") + counter)
                self.combination[members[counter]] = reac_code
                await regist_player.add_reaction(reac_code)
            await regist_player.add_reaction("\U0001f44c")

            # 分野選択
            embed = discord.Embed(
                title="今日はどれ？", description="テクノロジ系, マネジメント系, ストラテジ系"
            )
            select_field = await message.channel.send(embed=embed)
            await select_field.add_reaction("\U0001f480")
            await select_field.add_reaction("\U0001f481")
            await select_field.add_reaction("\U0001f482")
            await select_field.add_reaction("\U0001f451")

            # 計算選択
            embed = discord.Embed(title="計算問題は？", description="やる、やらない")
            select_field = await message.channel.send(embed=embed)
            await select_field.add_reaction("\U0001f499")
            await select_field.add_reaction("\U0001f49a")
            await select_field.add_reaction("\U0001f49d")
        if message.content == "山":
            await message.channel.send("川")

    # 誰からリアクションがきていて、それを通知するだけ
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        emoji = str(reaction.emoji)
        channel_id = reaction.message.channel.id
        channel = self.bot.get_channel(channel_id)
        if user.bot:
            pass
        elif emoji == "👍":
            if self.nonce == int(reaction.message.nonce):
                embed = discord.Embed(
                    title="{}さんの確認が終了しました".format(user.name),
                    color=discord.Colour.gold(),
                )
                await channel.send(embed=embed)
        elif emoji == "👑":
            for selected_emoji in reaction.message.reactions:
                if selected_emoji.count == 2:
                    print("selected emoji: {}".format(selected_emoji))
                    if selected_emoji.emoji == "💀":
                        self.te_flag = "on"
                    if selected_emoji.emoji == "💁":
                        self.ma_flag = "on"
                    if selected_emoji.emoji == "💂":
                        self.st_flag = "on"
            field(self.te_flag, self.ma_flag, self.st_flag)
            embed = discord.Embed(
                title="設定状況",
                description="テクノロジ系: {}, マネジメント系: {}, ストラテジ系: {}".format(
                    self.te_flag, self.ma_flag, self.st_flag
                ),
            )
            await channel.send(embed=embed)

        elif emoji == "💝":
            for selected_emoji in reaction.message.reactions:
                if selected_emoji.count == 2:
                    print("selected emoji: {}".format(selected_emoji))
                    if selected_emoji.emoji == "💚":
                        cal_flag = "off"
                    if selected_emoji.emoji == "💙":
                        cal_flag = "on"
            option(cal_flag)
            embed = discord.Embed(title="設定状況", description="計算問題: {}".format(cal_flag))
            await channel.send(embed=embed)
        elif emoji == "👌":
            selected_player = []
            for selected_emoji in reaction.message.reactions:
                if selected_emoji.count == 2:
                    for k, v in self.combination.items():
                        if v == selected_emoji.emoji:
                            selected_player.append(k)
            print("selected player: {}".format(selected_player))
            player.Player(self.bot).set_player(selected_player)
            embed = discord.Embed(title="参加者", description="{}".format(selected_player))
            await channel.send(embed=embed)
        else:
            print("該当なし")
            print("user: {}".format(user))
            print("emoji: {}".format(emoji))

    @commands.command()
    async def incorrect(self, ctx, name):
        """
        display_name: 正解した問題について
        """
        embed = discord.Embed(
            title="{}の不正解した問題".format(name),
            color=discord.Color.from_rgb(255, 192, 203),
        )
        await ctx.send(embed=embed)

        incorrect_dir = Path(base_path / "image" / name / "incorrect")
        self.players = player.Player(self.bot).get_player()

        if len(self.players) == 0:
            await ctx.send("参加者登録をして")
        else:
            # 不正解問題
            incorrect_files_path = [
                x
                for x in incorrect_dir.glob("**/*")
                if re.search("^(?!.*ans).*$", str(x))
            ]
            random.shuffle(incorrect_files_path)
            embed = discord.Embed(
                title="全部で{}問".format(len(incorrect_files_path)),
                color=discord.Color.from_rgb(255, 192, 203),
            )
            await ctx.send(embed=embed)

            def check_ans(reaction, user):
                emoji = str(reaction.emoji)
                # デフォルトでbotにリアクションをつけるようにしたのでbotのリアクションは無視するようにする
                if (user.bot == False) and (user.name in self.players):
                    if emoji == "🇦":
                        self.choice[user.name] = "ア"
                    elif emoji == "🇧":
                        self.choice[user.name] = "イ"
                    elif emoji == "🇨":
                        self.choice[user.name] = "ウ"
                    elif emoji == "🇩":
                        self.choice[user.name] = "エ"
                    print("{}さんの回答終わり: {}".format(user.name, self.choice[user.name]))

                return len(self.choice) == len(self.players)

            def check(reaction, user):
                # デフォルトでbotにリアクションをつけるようにしたのでbotのリアクションは無視するようにする
                if not user.bot:
                    emoji = str(reaction.emoji)
                    print("user: {}".format(user))
                    print("emoji: {}".format(emoji))
                    print("reaction count: {}".format(reaction.count))
                    print("len(self.players): {}".format(len(self.players)))
                    print("reaction message nonce: {}".format(reaction.message.nonce))
                    print("self nonce: {}".format(self.nonce))
                    return (self.nonce == int(reaction.message.nonce)) and (
                        reaction.count == len(self.players) + 1
                    )

            for i in range(len(incorrect_files_path)):
                choised_file_path = incorrect_files_path[i]
                choised_file = choised_file_path.stem

                # 正解問題の答え
                choised_file_pair_path = [
                    x
                    for x in incorrect_dir.glob("**/*")
                    if re.search(choised_file + ".*ans", str(x))
                ]

                embed = discord.Embed(title="問題を表示〜")
                await ctx.send(embed=embed)
                self.nonce = int(generate_nonce(18))
                incorrect_pic = discord.File(str(choised_file_path))
                incorrect = await ctx.send(file=incorrect_pic, nonce=self.nonce)
                await incorrect.add_reaction("👍")

                await self.bot.wait_for("reaction_add", check=check)
                await asyncio.sleep(1)

                embed = discord.Embed(
                    title="答えを入力して！",
                    description="A. ア   B. イ   C.ウ   D.エ",
                    color=discord.Colour.gold(),
                )
                thinking = await ctx.send(embed=embed)
                await thinking.add_reaction("🇦")
                await thinking.add_reaction("🇧")
                await thinking.add_reaction("🇨")
                await thinking.add_reaction("🇩")

                # メンバーの回答待ち
                await self.bot.wait_for("reaction_add", check=check_ans)

                # 答えを初期化
                self.choice = {}
                # 答えを文章で表示
                embed = discord.Embed(title="答えだよ", color=discord.Colour.green())
                await ctx.send(embed=embed)

                self.nonce = int(generate_nonce(18))
                incorrect_pair_pic = discord.File(str(choised_file_pair_path[0]))
                incorrect_pair = await ctx.send(
                    file=incorrect_pair_pic, nonce=self.nonce
                )
                await incorrect_pair.add_reaction("👍")

                await self.bot.wait_for("reaction_add", check=check)
                await asyncio.sleep(1)

            embed = discord.Embed(
                title="全部終わり", color=discord.Color.from_rgb(255, 192, 203)
            )
            await ctx.send(embed=embed)

    @commands.command()
    async def correct(self, ctx, name):
        """
        display_name: 正解した問題について
        """
        embed = discord.Embed(
            title="{}の正解した問題".format(name),
            color=discord.Color.from_rgb(255, 192, 203),
        )
        await ctx.send(embed=embed)

        correct_dir = Path(base_path / "image" / name / "correct")
        self.players = player.Player(self.bot).get_player()

        if len(self.players) == 0:
            await ctx.send("参加者登録をして")
        else:
            # 正解問題
            correct_files_path = [
                x
                for x in correct_dir.glob("**/*")
                if re.search("^(?!.*ans).*$", str(x))
            ]
            random.shuffle(correct_files_path)
            embed = discord.Embed(
                title="全部で{}問".format(len(correct_files_path)),
                color=discord.Color.from_rgb(255, 192, 203),
            )
            await ctx.send(embed=embed)

            def check_ans(reaction, user):
                emoji = str(reaction.emoji)
                # デフォルトでbotにリアクションをつけるようにしたのでbotのリアクションは無視するようにする
                if (user.bot == False) and (user.name in self.players):
                    if emoji == "🇦":
                        self.choice[user.name] = "ア"
                    elif emoji == "🇧":
                        self.choice[user.name] = "イ"
                    elif emoji == "🇨":
                        self.choice[user.name] = "ウ"
                    elif emoji == "🇩":
                        self.choice[user.name] = "エ"
                    print("{}さんの回答終わり: {}".format(user.name, self.choice[user.name]))

                return len(self.choice) == len(self.players)

            def check(reaction, user):
                # デフォルトでbotにリアクションをつけるようにしたのでbotのリアクションは無視するようにする
                if not user.bot:
                    emoji = str(reaction.emoji)
                    print("user: {}".format(user))
                    print("emoji: {}".format(emoji))
                    print("reaction count: {}".format(reaction.count))
                    print("len(self.players): {}".format(len(self.players)))
                    print("reaction message nonce: {}".format(reaction.message.nonce))
                    print("self nonce: {}".format(self.nonce))
                    return (self.nonce == int(reaction.message.nonce)) and (
                        reaction.count == len(self.players) + 1
                    )

            for i in range(len(correct_files_path)):
                choised_file_path = correct_files_path[i]
                choised_file = choised_file_path.stem

                # 正解問題の答え
                choised_file_pair_path = [
                    x
                    for x in correct_dir.glob("**/*")
                    if re.search(choised_file + ".*ans", str(x))
                ]

                embed = discord.Embed(title="問題を表示")
                await ctx.send(embed=embed)
                self.nonce = int(generate_nonce(18))
                correct_pic = discord.File(str(choised_file_path))
                correct = await ctx.send(file=correct_pic, nonce=self.nonce)
                await correct.add_reaction("👍")

                await self.bot.wait_for("reaction_add", check=check)
                await asyncio.sleep(1)

                embed = discord.Embed(
                    title="答えを入力して",
                    description="A. ア   B. イ   C.ウ   D.エ",
                    color=discord.Colour.gold(),
                )
                thinking = await ctx.send(embed=embed)
                await thinking.add_reaction("🇦")
                await thinking.add_reaction("🇧")
                await thinking.add_reaction("🇨")
                await thinking.add_reaction("🇩")

                # メンバーの回答待ち
                await self.bot.wait_for("reaction_add", check=check_ans)

                # 答えを初期化
                self.choice = {}
                # 答えを文章で表示
                embed = discord.Embed(title="答えだよ", color=discord.Colour.green())
                await ctx.send(embed=embed)

                self.nonce = int(generate_nonce(18))
                correct_pair_pic = discord.File(str(choised_file_pair_path[0]))
                correct_pair = await ctx.send(file=correct_pair_pic, nonce=self.nonce)
                await correct_pair.add_reaction("👍")

                await self.bot.wait_for("reaction_add", check=check)
                await asyncio.sleep(1)

            embed = discord.Embed(
                title="全部終わった", color=discord.Color.from_rgb(255, 192, 203)
            )
            await ctx.send(embed=embed)

    @commands.command()
    async def start(self, ctx):
        def check(reaction, user):
            # デフォルトでbotにリアクションをつけるようにしたのでbotのリアクションは無視するようにする
            if not user.bot:
                emoji = str(reaction.emoji)
                print("user: {}".format(user))
                print("emoji: {}".format(emoji))
                print("reaction count: {}".format(reaction.count))
                print("len(self.players): {}".format(len(self.players)))
                print("reaction message nonce: {}".format(reaction.message.nonce))
                print("self nonce: {}".format(self.nonce))
                return (self.nonce == int(reaction.message.nonce)) and (
                    reaction.count == len(self.players) + 1
                )

        def check_ans(reaction, user):
            emoji = str(reaction.emoji)
            # デフォルトでbotにリアクションをつけるようにしたのでbotのリアクションは無視するようにする
            if (user.bot == False) and (user.name in self.players):
                if emoji == "🇦":
                    self.choice[user.name] = "ア"
                elif emoji == "🇧":
                    self.choice[user.name] = "イ"
                elif emoji == "🇨":
                    self.choice[user.name] = "ウ"
                elif emoji == "🇩":
                    self.choice[user.name] = "エ"
                print("{}さんの回答終わり: {}".format(user.name, self.choice[user.name]))

            return len(self.choice) == len(self.players)

        # playerクラスで弄ったplayer変数を参照する
        self.players = player.Player(self.bot).get_player()

        if len(self.players) == 0:
            await ctx.send("参加者登録をして")

        else:
            # 参加者のディレクトリ作成
            create_dir(self.players)
            # 参加者にメンションを送る
            for join_player in self.players:
                for member in self.bot.get_all_members():
                    if join_player == member.name:
                        content = "{} {}".format(member.mention, "始まるよ")
                        await ctx.send(content)

            # 問題画像用意
            random_name = generate_name(10)
            ques_name = "{}_{}".format(self.question_number, random_name)

            embed = discord.Embed(title="問題を表示")
            await ctx.send(embed=embed)

            driver.find_element_by_xpath('//*[@id="tabs"]/ul/li[2]/a').click()
            driver.find_element_by_xpath(
                '//*[@id="main_contents"]/section/input'
            ).click()
            ques_path = take_screenshot(ques_name)
            self.nonce = int(generate_nonce(18))
            question = await ctx.send(file=discord.File(ques_path), nonce=self.nonce)
            # リアクションしやすい用にbotがデフォルトで押す
            await question.add_reaction("👍")

            while True:

                # 回答の準備待ち
                print("===========check===================")
                await self.bot.change_presence(activity=discord.Game("シンキングタイム"))
                await self.bot.wait_for("reaction_add", check=check)
                print("===========check===================")

                print("===========回答準備===================")
                print("全員の回答準備が終了しました")
                print("===========回答準備===================")
                await asyncio.sleep(1)

                embed = discord.Embed(
                    title="答えを入力して！",
                    description="A. ア   B. イ   C.ウ   D.エ",
                    color=discord.Colour.gold(),
                )
                thinking = await ctx.send(embed=embed)
                await thinking.add_reaction("🇦")
                await thinking.add_reaction("🇧")
                await thinking.add_reaction("🇨")
                await thinking.add_reaction("🇩")

                # メンバーの回答待ち
                print("===========check_ans===================")
                await self.bot.change_presence(activity=discord.Game("回答受付中"))
                await self.bot.wait_for("reaction_add", check=check_ans)
                print("===========check_ans===================")
                print("===========回答終了===================")
                print("全員の回答が終了しました")
                print("===========回答終了===================")

                # 答えの画像を表示
                driver.find_element_by_xpath('//*[@id="qPage"]/div[1]/div[1]/a').click()
                ans_web = (driver.find_element_by_class_name("answer")).text
                ans_name = "{}_{}_ans".format(self.question_number, random_name)
                ans_path = str(base_path / "image" / "{}.png".format(ans_name))
                get_full_screenshot_image(driver).save(ans_path)

                self.nonce = int(generate_nonce(18))
                answer = await ctx.send(file=discord.File(ans_path), nonce=self.nonce)
                await answer.add_reaction("👍")

                for name, ans_user in self.choice.items():
                    if ans_web == ans_user:
                        embed = discord.Embed(
                            description="{}さんは正解です！".format(name),
                            color=discord.Colour.green(),
                        )
                        await ctx.send(embed=embed)
                        shutil.copy(
                            ques_path, str(Path(base_path / "image" / name / "correct"))
                        )
                        shutil.copy(
                            ans_path, str(Path(base_path / "image" / name / "correct"))
                        )
                    else:
                        embed = discord.Embed(
                            description="{}さんは不正解です！".format(name),
                            color=discord.Colour.green(),
                        )
                        await ctx.send(embed=embed)
                        shutil.copy(
                            ques_path,
                            str(Path(base_path / "image" / name / "incorrect")),
                        )
                        shutil.copy(
                            ans_path,
                            str(Path(base_path / "image" / name / "incorrect")),
                        )

                os.remove(ques_path)
                os.remove(ans_path)

                # 答えを初期化
                self.choice = {}
                await asyncio.sleep(1)

                # 答えを文章で表示
                embed = discord.Embed(
                    title="答えは{}です".format(ans_web), color=discord.Colour.green()
                )
                await ctx.send(embed=embed)

                # 復習待ち
                print("===========check===================")
                await self.bot.change_presence(activity=discord.Game("復習中"))
                await self.bot.wait_for("reaction_add", check=check)
                print("===========check===================")
                print("===========答え確認終了===================")
                print("全員の答え確認が終了しました")
                print("===========答え確認終了===================")
                await asyncio.sleep(1)

                # 2問目以降の準備
                self.question_number += 1
                random_name = generate_name(10)
                ques_name = "{}_{}".format(self.question_number, random_name)

                # 2問目以降の通知
                embed = discord.Embed(
                    title="次は{}番目の問題".format(self.question_number),
                    description="問題を表示します",
                )
                await ctx.send(embed=embed)

                # 2問目以降の出題
                driver.find_element_by_xpath(
                    '//*[@id="main_contents"]/section/input'
                ).click()
                ques_path = take_screenshot(ques_name)
                self.nonce = int(generate_nonce(18))
                question = await ctx.send(
                    file=discord.File(ques_path), nonce=self.nonce
                )
                await question.add_reaction("👍")


# Bot本体側からコグを読み込む際に呼び出される関数。
def setup(bot):
    # TestCogにBotを渡してインスタンス化し、Botにコグとして登録する。
    bot.add_cog(Question(bot))