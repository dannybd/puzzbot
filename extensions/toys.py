""" Contains some fun commands that aren't that useful """


import discord
from discord.ext import commands
from discord.ext.commands import guild_only
from common import plural


class Toys(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(hidden=True)
    async def huntyet(self, ctx):
        """Is it hunt yet?"""
        now = self.bot.now()
        timeleft = self.bot.hunt_begins - now
        if timeleft.days < 0:
            if now > self.bot.hunt_ends:
                await ctx.send("Nope 😢 see y'all next year")
                return
            await ctx.send("Yes! 🎉")
            return

        left = [
            plural(timeleft.days, "day"),
            plural(timeleft.seconds // 3600, "hour"),
            plural(timeleft.seconds // 60 % 60, "minute"),
            plural(timeleft.seconds % 60, "second"),
        ]
        await ctx.send("No! " + ", ".join(left))

    @commands.command()
    async def zwsp(self, ctx):
        """Helper for getting a Zero Width Space"""
        await ctx.send(
            "Here is a [zero-width space](<https://en.wikipedia.org/wiki/Zero-width_space>) "
            + "(ZWSP, U+200B): ```​``` "
            + "You can also copy one [here](<https://zerowidthspace.me/>)."
        )

    @commands.Cog.listener("on_message")
    async def fun_replies(self, message):
        if message.author == self.bot.user:
            return
        content = message.content.lower()
        channel = message.channel
        if "50/50" in content:
            await channel.send("Roll up your sleeves!")
            return
        if "thanks obama" in content:
            await channel.send("You're welcome!")
            return
        if "org chart" in content:
            await channel.send("We had a plan, and we executed the plan.")
            return
        if "football" in content:
            await channel.send("Football?  Really?")
            return
        if content.startswith("!backsolv"):
            message = await channel.send(
                "It's only backsolving if it comes from the region of "
                + "actually understanding all the meta constraints, "
                + "otherwise it's just sparkling guessing."
            )
            await message.add_reaction("✨")
            await message.add_reaction("🔙")
            await message.add_reaction("🏁")

    @commands.command(hidden=True)
    async def hooray(self, ctx):
        await ctx.send("🥳🎉🎊✨")


async def setup(bot):
    cog = Toys(bot)
    await bot.add_cog(cog)
