""" Puzzboss-only commands """
import aiohttp
from common import plural
from db import REST, SQL
import discord
from discord.ext import commands
from discord.ext.commands import guild_only, has_any_role, MemberConverter, errors
import json
import logging
import re
from urllib.parse import quote_plus, urlencode
import typing

from discord_info import *


def print_user(user: discord.Member):
    username = str(user)
    if user.display_name != username:
        return f"{user.display_name} ({username})"
    return username


class Puzzboss(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @has_any_role("RoleVerifier", "Puzzleboss", "Puzztech")
    @guild_only()
    @commands.command(name="onboard")
    async def onboard(self, ctx, member: discord.Member):
        """Sends a onboarding message to a new member"""
        await member.send(
            (
                """
Welcome to **{team_name}!** Here's how to get started.

1. Make a Puzzleboss account (https://{team_domain}/account), accessing that page with username `{registration_username}` and password `{registration_password}`. (This account lets our team coordinate who is solving what, generate common spreadsheets, and more.)
2. Ping @RoleVerifier on the Discord server with your {team_domain} username, so we can link the two 🔗

**How the Discord server works:**
* We make text channels for each puzzle 🧩
  * This results in a lot of channels, but you can use Ctrl+K to quickly navigate between them!
* We have voice channel "tables" where people work together, both on-campus and remote 🗣
  * Because we rely so heavily on voice chats, please make sure you know how to join and [use Push-to-Talk in Discord Voice Chats](https://steemit.com/tutorial/@lenadr/how-to-set-up-voice-to-talk-in-discord)!
* We've got a trusty bot, puzzbot (that's me!), which helps us connect puzzle channels to the table VCs where people are solving 🤖
* puzzbot's got a lot of commands, but you don't have to learn any more than maybe 3 of them to participate 🙂

Learn more here: https://{team_domain}/wiki/index.php/Hunting_in_Discord:_A_Guide

Thanks, and happy hunting! 🕵️‍♀️🧩
        """
            ).format(**self.bot.hunt_config)
        )
        await ctx.send(
            "Welcome aboard, {}! Check your DMs for instructions on how to set up your account to hunt with us 🙂".format(
                member.mention
            )
        )

    @onboard.error
    async def onboard_error(self, ctx, error):
        if isinstance(error, errors.MissingRequiredArgument):
            await ctx.send("Usage: `!onboard [Discord display name]`\n")
            return
        if isinstance(error, errors.CheckFailure):
            await ctx.send(
                "Sorry, only folks with the @RoleVerifier role can use this command. "
                + "Ping them and they should be able to help you."
            )
            return
        if (
            isinstance(error, errors.CommandInvokeError)
            and "Cannot send messages to this user" in error.text
        ):
            await ctx.send(
                "Sorry, we cannot DM this user! Please allow DMs and then retry."
            )
        await ctx.send("Error! Something went wrong, please ping @dannybd.")
        raise error

    @has_any_role("RoleVerifier", "Puzzleboss", "Puzztech")
    @guild_only()
    @commands.command(name="whois", aliases=["lookup"])
    async def whois(
        self,
        ctx,
        member: typing.Optional[discord.Member],
        *,
        query: typing.Optional[str],
    ):
        """Looks up a user in Discord and Puzzleboss. (Regex supported)"""
        response = ""
        discord_result = ""
        if member:
            discord_result = self._lookup_discord_user(member)
            response += f"{discord_result}\n\n"
            query = member.display_name

        if not query:
            await ctx.send(response)
            return

        response += "Checking Puzzleboss accounts... "
        try:
            regex = re.compile(query, re.IGNORECASE)
        except Exception as e:
            regex = re.compile(r"^$")
        query = query.lower()

        def solver_matches(name, fullname, discord_name, **kwargs):
            if query in name.lower():
                return True
            if regex.search(name):
                return True
            if query in fullname.lower():
                return True
            if regex.search(fullname):
                return True
            if not discord_name:
                return False
            if query in discord_name.lower():
                return True
            if regex.search(discord_name):
                return True
            return False

        solvers = SQL.get_all_solvers()
        results = []
        for solver in solvers:
            if solver_matches(**solver):
                solver_tag = "`{name} ({fullname})`".format(**solver)
                if solver["discord_name"]:
                    solver_tag += " [Discord user `{}`]".format(solver["discord_name"])
                results.append(solver_tag)

        if not results:
            if query in ["john galt", "johngalt"]:
                await ctx.send(
                    """
```
PART I

NON-CONTRADICTION

CHAPTER I
THE THEME

"Who is John Galt?"
The light was ebbing, and Eddie Willers could not distinguish the bum's face. The bum had said it simply, without expression. But from the sunset far at the end of the street, yellow glints caught his eyes, and the eyes looked straight at Eddie Willers, mocking and still-as if the question had been addressed to the causeless uneasiness within him.
"Why did you say that?" asked Eddie Willers, his voice tense.
The bum leaned against the side of the doorway; a wedge of broken glass behind him reflected the metal yellow of the sky.
"Why does it bother you?" he asked.
"It doesn't," snapped Eddie Willers.
He reached hastily into his pocket. The bum had stopped him and asked for a dime, then had gone on talking, as if to kill that moment and postpone the problem of the next. Pleas for dimes were so frequent in the streets these days that it was not necessary to listen to explanations, and he had no desire to hear the details of this bum's particular despair.
"Go get your cup of coffee," he said, handing the dime to the shadow that had no face.
"Thank you, sir," said the voice, without interest, and the face leaned forward for a moment. The face was wind-browned, cut by lines of weariness and cynical resignation; the eyes were intelligent. Eddie Willers walked on, wondering why he always felt it at this time of day, this sense of dread without reason. No, he thought, not dread, there's nothing to fear: just an immense, diffused apprehension, with no source or object. He had become accustomed to the feeling, but he could find no explanation for it; yet the bum had spoken as if he knew that Eddie felt it, as if he thought that one should feel it, and more: as if he knew the reason.
```
                    """
                )
                return
            response += "0 results found in Puzzleboss for that query."
        elif len(results) == 1:
            response += "1 match found:\n\n{}".format(results[0])
        else:
            response += "{} matches found:\n\n{}".format(
                len(results), "\n".join(results)
            )
        try:
            await ctx.send(response)
        except:
            response = f"{discord_result}\n\nChecking Puzzleboss accounts... Error! 😔\n"
            response += (
                "Sorry, too many matches ({}) found to display in Discord. "
                + "Please narrow your query."
            ).format(len(results))
            await ctx.send(response)

    def _lookup_discord_user(self, member: discord.Member):
        member_tag = "Discord user `{0}`".format(print_user(member))
        if member.bot:
            return f"{member_tag} is a bot, like me :)"
        solver = SQL.select_one(
            """
            SELECT
                name,
                fullname
            FROM solver_view
            WHERE chat_uid = %s
            ORDER BY id DESC
            LIMIT 1
            """,
            (member.id,),
        )
        if not solver:
            return f"{member_tag} does not seem to be verified yet!"
        return ("{0} is Puzzleboss user `{1} ({2})`").format(
            member_tag, solver["name"], solver["fullname"]
        )

    @has_any_role("Beta Boss", "Puzzleboss", "Puzztech")
    @guild_only()
    @commands.command()
    async def usurp(self, ctx):
        await self.newpuzzboss(ctx, ctx.author)

    @has_any_role("Beta Boss", "Puzzleboss", "Puzztech")
    @guild_only()
    @commands.command()
    async def newpuzzboss(self, ctx, newboss: typing.Optional[discord.Member]):
        """[puzzboss only] Designates a new person as Puzzleboss"""
        puzzboss_role = ctx.guild.get_role(PUZZBOSS_ROLE)
        current_puzzbosses = puzzboss_role.members
        if not newboss:
            newboss = ctx.author
        if newboss in current_puzzbosses:
            await ctx.send("{0.mention} is already Puzzleboss!".format(newboss))
            return
        betaboss_role = ctx.guild.get_role(BETABOSS_ROLE)
        puzztech_role = ctx.guild.get_role(PUZZTECH_ROLE)
        if betaboss_role not in newboss.roles and puzztech_role not in newboss.roles:
            await ctx.send("{0.mention} should be a Beta Boss first!".format(newboss))
            return
        for puzzboss in puzzboss_role.members:
            await puzzboss.remove_roles(puzzboss_role)
        await newboss.add_roles(puzzboss_role)
        await ctx.send(
            (
                "{0.mention} has anointed {1} as the new {2.mention}! "
                + "Use {2.mention} to get their attention."
            ).format(
                ctx.author,
                newboss.mention if newboss != ctx.author else "themself",
                puzzboss_role,
            )
        )

    @has_any_role("Puzzleboss", "Puzztech")
    @commands.command()
    async def reload(self, ctx):
        """[puzztech only] Reload hunt config from DB"""
        self.bot.hunt_config = SQL.get_hunt_config()
        await ctx.reply("Updated puzzcord's hunt config from DB.")

    @has_any_role("Puzzleboss", "Puzztech")
    @commands.command(aliases=["defer", "redirectto"])
    async def deferto(self, ctx, *, target_channel: discord.TextChannel):
        """[puzzboss only] Defer a puzzle channel to another channel"""
        logging.info(
            "{0.command}: Deferring {0.channel} to channel: {1}".format(
                ctx, target_channel
            )
        )
        if ctx.channel == target_channel:
            await ctx.message.reply("You cannot defer to its own channel!")
            return
        member_role = ctx.guild.get_role(HUNT_MEMBER_ROLE)
        await ctx.channel.set_permissions(member_role, read_messages=False)
        this_puzzle = SQL.get_puzzle_for_channel(ctx.channel)
        target_puzzle = SQL.get_puzzle_for_channel(target_channel)
        SQL.update(
            ctx,
            """
            UPDATE puzzle
            SET
                comments = %s,
                chat_channel_link = %s,
                drive_id = %s,
                drive_uri = %s
            WHERE id = %s AND name = %s
            """,
            (
                f"<<<REDIRECTED>>> to #{target_channel}",
                target_puzzle["chat_channel_link"],
                target_puzzle["drive_id"],
                target_puzzle["drive_uri"],
                this_puzzle["id"],
                this_puzzle["name"],
            ),
        )
        await target_channel.send(
            "**Heads up:** Puzzle [`{name}`](<{puzzle_uri}>) now points to this channel!".format(
                **this_puzzle
            )
        )
        await ctx.send(
            f"# DO NOT USE THIS CHANNEL!\nGo to {target_channel.mention} instead"
        )
        await ctx.channel.edit(name="⛔️-" + ctx.channel.name)
        if ctx.channel.category.name.startswith("🏁"):
            await ctx.channel.delete(reason="Redirected channel cleanup")

    @has_any_role("Beta Boss", "Puzzleboss", "Puzztech")
    @commands.command()
    async def newround(self, ctx, *, round_name: str):
        """[puzzboss only] Creates a new round"""
        logging.info("{0.command}: Creating a new round: {1}".format(ctx, round_name))
        response = await REST.post("/rounds/", {"name": "{0}".format(round_name)})
        status = response.status
        if status == 200:
            await ctx.send("Round created!")
            return
        if status == 500:
            await ctx.send("Error. This is likely because the round already exists.")
            return
        await ctx.send("Error. Something weird happened, try the PB UI directly.")

    @has_any_role("Beta Boss", "Puzzleboss", "Puzztech")
    @commands.command()
    async def solvedround(self, ctx, *, round_name: typing.Optional[str]):
        """[puzzboss only] Marks a round as solved"""
        if not round_name:
            puzzle = SQL.get_puzzle_for_channel(ctx.channel)
            if not puzzle:
                await ctx.send("Incorrect usage: please specify round name")
                return
            round_name = puzzle["round_name"]
        logging.info(
            "{0.command}: Marking a round as solved: {1}".format(ctx, round_name)
        )
        SQL.update(
            ctx,
            """
            UPDATE round
            SET round_uri = '#solved'
            WHERE name = %s
            """,
            (round_name,),
        )
        await ctx.send("You solved the meta(s)!! 🎉 🥳")
        return

    @solvedround.error
    async def solvedround_error(self, ctx, error):
        puzzboss_role = ctx.guild.get_role(PUZZBOSS_ROLE)
        if isinstance(error, errors.MissingAnyRole):
            await ctx.send(
                (
                    "Only {0.mention} can mark a round as solved. "
                    + "I've just pinged them; they should be here soon "
                    + "to confirm. (You don't need to ping them again.)"
                ).format(puzzboss_role)
            )
            return
        if isinstance(error, errors.MissingRequiredArgument):
            await ctx.send("Usage: `!solvedround RoundName`\n")
            return
        await ctx.send(
            (
                "Error! Something went wrong, possibly because "
                + "you didn't match the round name exactly. "
                + "Otherwise, please ping @dannybd, "
                + "who can mark this solved behind the scenes."
            ).format(puzzboss_role)
        )

    @has_any_role("Beta Boss", "Puzzleboss", "Puzztech")
    @guild_only()
    @commands.command(aliases=["solve", "submit", "SOLVED"])
    async def solved(
        self, ctx, channel: typing.Optional[discord.TextChannel], *, answer: str
    ):
        """[puzzboss only] Mark a puzzle as solved and archive its channel"""
        logging.info(
            "{0.command}: {0.author.name} is marking a puzzle as solved".format(ctx)
        )
        apply_to_self = channel is None
        if apply_to_self:
            channel = ctx.channel
        puzzle = SQL.get_puzzle_for_channel(channel)
        if not puzzle:
            await ctx.send(
                "Error: Could not find a puzzle for channel {0.mention}".format(channel)
            )
            await ctx.message.delete()
            return
        response = await REST.post(
            "/puzzles/{id}/answer".format(**puzzle), {"answer": answer.upper()}
        )
        if apply_to_self:
            await ctx.message.delete()

    @solved.error
    async def solved_error(self, ctx, error):
        puzzboss_role = ctx.guild.get_role(PUZZBOSS_ROLE)
        if isinstance(error, errors.MissingAnyRole):
            await ctx.send(
                (
                    "Only {0.mention} can mark a puzzle as solved. "
                    + "I've just pinged them; they should be here soon "
                    + "to confirm. (You don't need to ping them again.)"
                ).format(puzzboss_role)
            )
            return
        if isinstance(error, errors.MissingRequiredArgument):
            await ctx.send(
                "Usage: `!solved ANSWER`\n"
                + "If you're calling this from a different channel, "
                + "add the mention in there, like "
                + "`!solved #easypuzzle ANSWER`"
            )
            return
        await ctx.send(
            (
                "Error! Something went wrong, please ping @dannybd. "
                + "In the meantime {0.mention} should use the "
                + "web Puzzleboss interface to mark this as solved."
            ).format(puzzboss_role)
        )

    @has_any_role("Beta Boss", "Puzzleboss", "Puzztech")
    @guild_only()
    @commands.command(aliases=["unsolve"])
    async def unsolved(self, ctx, channel: typing.Optional[discord.TextChannel]):
        """[puzzboss only] Fix a puzzle accidentally marked as solved"""
        logging.info(
            "{0.command}: {0.author.name} is marking a puzzle as unsolved".format(ctx)
        )
        apply_to_self = channel is None
        if apply_to_self:
            channel = ctx.channel
        puzzle = SQL.get_puzzle_for_channel(channel)
        if not puzzle:
            await ctx.send(
                "Error: Could not find a puzzle for channel {0.mention}".format(channel)
            )
            return
        await ctx.send("Trying to restore...")
        SQL.update(
            ctx,
            """
            UPDATE puzzle
            SET answer = NULL, status = 'Being worked'
            WHERE id = %s AND name = %s
            """,
            (puzzle["id"], puzzle["name"]),
        )

        category_name = "🧩 {0}".format(puzzle["round_name"])
        existing_categories = [
            c for c in ctx.guild.categories if c.name == category_name
        ]
        category = discord.utils.find(
            lambda category: len(category.channels) < 50,
            existing_categories,
        )
        if not category:
            await ctx.send("ERROR: Could not move channel automatically.")
            return

        await channel.edit(
            category=category,
            position=0,
            reason='Puzzle "{0.name}" NOT solved, unarchiving!'.format(channel),
        )

        await ctx.send("Success! Moved this back.")
        logging.info("{0.command}: succeeded!".format(ctx))

    @has_any_role("RoleVerifier", "Beta Boss", "Puzzleboss", "Puzztech")
    @guild_only()
    @commands.command()
    async def duplicates(self, ctx):
        """Try to find duplicate guild members"""
        visitor_role = ctx.guild.get_role(VISITOR_ROLE)
        members = [
            member
            for member in ctx.guild.members
            if not member.bot and visitor_role not in member.roles
        ]
        member_names = [member.name for member in members]

        dupe_members = [
            member for member in members if member_names.count(member.name) > 1
        ]
        dupe_members = sorted(dupe_members, key=lambda member: member.name)
        if not dupe_members:
            await ctx.send("Looks like all obvious duplicates have been cleared!")
            return

        member_role = ctx.guild.get_role(HUNT_MEMBER_ROLE)
        lines = [
            "Joined {0.joined_at:%Y-%m-%d %H:%M}: {1}{2}".format(
                member,
                print_user(member),
                "  [Team Member]" if member_role in member.roles else "",
            )
            for member in dupe_members
        ]
        await ctx.send(
            f"Potential dupe members ({len(lines)}):\n"
            + "```\n"
            + "\n".join(lines)
            + "\n```"
        )

    @has_any_role("RoleVerifier", "Beta Boss", "Puzzleboss", "Puzztech")
    @guild_only()
    @commands.command()
    async def unmatched(self, ctx):
        """Unmatched Puzzleboss accounts w/o Discord accounts yet"""
        unmatched_users = SQL.select_all(
            """
            SELECT
                name,
                fullname
            FROM solver_view
            WHERE
                chat_uid IS NULL
                AND name <> 'puzzleboss'
            ORDER BY id DESC
            """,
        )

        if not unmatched_users:
            await ctx.send("Looks like all PB accounts are matched, nice!")
            return

        await ctx.send(
            f"Puzzleboss accounts without matching Discord accounts ({len(unmatched_users)}):\n```"
            + "\n".join(
                [
                    user["name"] + " (" + user["fullname"] + ")"
                    for user in unmatched_users
                ]
            )
            + "\n```"
        )

    @has_any_role("RoleVerifier", "Beta Boss", "Puzzleboss", "Puzztech")
    @guild_only()
    @commands.command()
    async def unverified(self, ctx):
        """Lists not-yet-verified team members"""
        rows = SQL.select_all(
            """
            SELECT
                DISTINCT chat_uid
            FROM solver_view
            WHERE chat_uid IS NOT NULL
            """,
        )
        verified_discord_ids = [int(row["chat_uid"]) for row in rows]
        visitor_role = ctx.guild.get_role(VISITOR_ROLE)
        unverified_users = [
            member
            for member in ctx.guild.members
            if visitor_role not in member.roles
            and member.id not in verified_discord_ids
            and not member.bot
        ]
        unverified_users = sorted(unverified_users, key=lambda member: member.joined_at)
        if not unverified_users:
            await ctx.send(
                "Looks like all team members are verified, nice!\n\n"
                + "(If this is unexpected, try adding the Team Member "
                + "role to someone first.)"
            )
            return
        member_role = ctx.guild.get_role(HUNT_MEMBER_ROLE)
        unverified_other = [
            "Joined {0.joined_at:%Y-%m-%d %H:%M}: {1}".format(
                member, print_user(member)
            )
            for member in unverified_users
            if member_role not in member.roles
        ]
        if unverified_other:
            unverified_other = (
                "Folks needing verification ({0}):\n```\n{1}\n```".format(
                    len(unverified_other), "\n".join(unverified_other)
                )
            )
        else:
            unverified_other = ""

        unverified_members = [
            "Joined {0.joined_at:%Y-%m-%d %H:%M}: {1}".format(
                member, print_user(member)
            )
            for member in unverified_users
            if member_role in member.roles
        ]
        if unverified_members:
            unverified_members = "Folks needing verification, but already have the Member role ({0}):\n```\n{1}\n```".format(
                len(unverified_members), "\n".join(unverified_members)
            )
        else:
            unverified_members = ""

        rows = SQL.select_all(
            """
            SELECT
                id,
                name,
                fullname
            FROM solver_view
            WHERE
                chat_uid IS NULL
                AND id > 320
            ORDER BY id DESC
            LIMIT 10
            """,
        )
        unverified_new_accounts = [
            f"{row['name']} ({row['fullname']}, ID {row['id']})" for row in rows
        ]
        if unverified_new_accounts:
            unverified_new_accounts = (
                "\nRecent Puzzleboss accounts needing Discord users:\n```{0}```".format(
                    "\n".join(unverified_new_accounts)
                )
            )
        else:
            unverified_new_accounts = ""

        rows = SQL.select_all(
            """
            SELECT
                username,
                fullname
            FROM newuser
            """,
        )
        accounts_being_registered = [
            f"{row['username']} ({row['fullname']})" for row in rows
        ]
        if accounts_being_registered:
            accounts_being_registered = "\nPuzzleboss accounts pending confirmation before creation/reset:\n```{0}```".format(
                "\n".join(accounts_being_registered)
            )
        else:
            accounts_being_registered = ""

        await ctx.send(
            unverified_other
            + unverified_members
            + unverified_new_accounts
            + accounts_being_registered
        )

    @has_any_role("RoleVerifier", "Beta Boss", "Puzzleboss", "Puzztech")
    @guild_only()
    @commands.command()
    async def verify(
        self, ctx, member: typing.Union[discord.Member, str], *, username: str
    ):
        """Verifies a team member with their email
        Usage: !verify @member username[@importanthuntpoll.org]
        """
        if not isinstance(member, discord.Member) and " " in username:
            # Let's perform some surgery, and stitch the actual member name
            # back together.
            parts = username.split()
            username = parts[-1]
            member = " ".join([member] + parts[:-1])
            try:
                converter = MemberConverter()
                member = await converter.convert(ctx, member)
            except:
                pass

        if not isinstance(member, discord.Member):
            await ctx.send(
                (
                    "Sorry, the Discord name has to be _exact_, "
                    + "otherwise I'll fail. `{}` isn't recognizable to me "
                    + "as a known Discord name.\n\n"
                    + "TIP: If their display name has spaces or symbols in it, "
                    + 'wrap the name in quotes: `!verify "foo bar" FooBar`'
                ).format(member)
            )
            return
        username = username.replace("@" + self.bot.team_domain, "")
        logging.info(
            "{0.command}: Marking user {1.display_name} as PB user {2}".format(
                ctx, member, username
            )
        )
        solver = SQL.select_one(
            """
            SELECT
                id,
                name,
                fullname
            FROM solver_view
            WHERE name LIKE %s
            LIMIT 1
            """,
            (username,),
        )
        if not solver:
            pending_solver = SQL.select_one(
                """
                SELECT
                    username
                FROM newuser
                WHERE username LIKE %s
                LIMIT 1
                """,
                (username,),
            )
            if pending_solver:
                await ctx.send(
                    (
                        "Error: {0} has started registration but has not yet "
                        + "confirmed their email! Check your spam folder as well, "
                        + "click the confirmation link, then come back here to let us know."
                    ).format(username)
                )
                return
            await ctx.send(
                "Error: Couldn't find a {0}@{1}, please try again.".format(
                    username, self.bot.team_domain
                )
            )
            return
        logging.info("{0.command}: Found solver {1}".format(ctx, solver["fullname"]))
        print(solver["id"])
        SQL.update(
            ctx,
            """
            UPDATE solver
            SET chat_uid = %s, chat_name = %s
            WHERE id = %s
            """,
            (
                str(member.id),
                str(member),
                solver["id"],
            ),
        )
        member_role = ctx.guild.get_role(HUNT_MEMBER_ROLE)
        if member_role not in member.roles:
            logging.info("{0.command}: Adding member role!".format(ctx))
            await member.add_roles(member_role)
        await ctx.send(
            "**{0.display_name}** is now verified as **{1}**!".format(
                member, solver["name"]
            )
        )

    @verify.error
    async def verify_error(self, ctx, error):
        if isinstance(error, errors.MissingRequiredArgument):
            await ctx.send(
                "Usage: `!verify [Discord display name] [Puzzleboss username]`\n"
                + "If the person's display name has spaces or weird symbols "
                + "in it, try wrapping it in quotes, like\n"
                + '`!verify "Fancy Name" FancyPerson`'
            )
            return
        if isinstance(error, errors.CheckFailure):
            await ctx.send(
                "Sorry, only folks with the @RoleVerifier role can use this command. "
                + "Ping them and they should be able to help you."
            )
            return
        await ctx.send(
            "Error! Something went wrong, please ping @dannybd. "
            + "In the meantime it should be safe to just add this person "
            + "to the server by giving them the Team Member role."
        )
        raise error

    @has_any_role("Puzztech")
    @guild_only()
    @commands.command(name="relinkdoc", aliases=["linkdoc"])
    async def relinkdoc(
        self,
        ctx,
        channel: typing.Optional[discord.TextChannel],
        *,
        sheet_hash: str,
    ):
        """[puzztech only] Emergency relinking of a puzzle to an existing sheet"""
        channel = channel or ctx.channel
        puzzle = SQL.get_puzzle_for_channel(channel)
        await ctx.send(
            "Relinking sheet `{}` to `{name}`...".format(sheet_hash, **puzzle)
        )
        response = await REST.post(
            "/puzzles/{id}/drive_id".format(**puzzle),
            {"drive_id": sheet_hash},
        )
        if response.status != 200:
            await ctx.send("Error setting drive_id!")
            return

        response = await REST.post(
            "/puzzles/{id}/drive_uri".format(**puzzle),
            {
                "drive_uri": f"https://docs.google.com/spreadsheets/d/{sheet_hash}/edit?usp=drivesdk"
            },
        )
        if response.status != 200:
            await ctx.send("Error setting drive_uri!")
            return

        await ctx.send("Done. Please run: `!puz {name}`".format(**puzzle))

    @has_any_role("Beta Boss", "Puzzleboss", "Puzztech")
    @guild_only()
    @commands.command()
    async def sync(self, ctx):
        """[experimental] Pull updates from Hunt website we don't have in Puzzleboss yet"""
        config = self.bot.hunt_config
        url = config.get("scrape_url", None)
        if not url:
            await ctx.send("No url")
            return
        cookie = config.get("scrape_cookie", None)
        if not cookie:
            await ctx.send("No cookie")
        headers = {
            "accept": "text/html",
            "cache-control": "max-age=0",
            "cookie": cookie,
            "user-agent": "Puzzleboss v0.1 HuntTeam:"
            + config.get("team_name", "Unknown"),
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    await ctx.send(f"Scrape error code {response.status}")
                    return
                result = await response.text()
        if "window.initialAllPuzzlesState = " not in result:
            await ctx.send("Data not found in scrape")
            return
        result = result.split("window.initialAllPuzzlesState = ", 1)[1]
        result = result.split("</script>", 1)[0]
        try:
            data = json.loads(result)
        except JSONDecodeError as _:
            await ctx.send("Cannot parse JSON")
            return
        db_puzzles = SQL.get_all_puzzles()
        discrepancies = []
        puzzles_to_buy = []
        currency = data.get("currency", 0)
        rounds = data.get("rounds", [])
        rounds.append(
            {
                "title": "StrayLeads",
                "puzzles": data.get("stray", []),
            }
        )
        for round in rounds:
            round_name = round.get("title", "?")
            for puzzle in round.get("puzzles", []):
                slug = puzzle.get("slug", "")
                name = puzzle.get("title", "")
                if not slug or not name:
                    continue
                if puzzle.get("state", "?") != "unlocked":
                    if currency:
                        puzzles_to_buy.append(
                            f"* {name} in `{round_name}` (_{puzzle.get('desc', '')}_)"
                        )
                    continue
                puzzle_uri = "https://www.two-pi-noir.agency/puzzles/" + quote_plus(
                    slug
                )
                db_puzzle = None
                for p in db_puzzles:
                    if p["puzzle_uri"] == puzzle_uri:
                        db_puzzle = p
                        break
                if not db_puzzle:
                    add_puzzle_params = {
                        "puzzurl": puzzle_uri,
                        "puzzid": name,
                        "roundname": round_name.replace(" ", ""),
                    }
                    add_puzzle_url = (
                        "https://importanthuntpoll.org/pb/addpuzzle.php?"
                        + urlencode(add_puzzle_params)
                    )
                    discrepancies.append(
                        f"* **New puzzle:** [{name}]({puzzle_uri}) "
                        f"in round `{round_name}` needs to be added! "
                        f"Click [here]({add_puzzle_url}) to add."
                    )
                    continue
                answer = puzzle.get("answer", None)
                if answer:
                    answer = answer.replace(" ", "")
                if not answer:
                    answer = None
                db_answer = db_puzzle["answer"]
                if db_answer:
                    db_answer = db_answer.replace(" ", "")
                if not db_answer:
                    db_answer = None
                channel = f"<#{db_puzzle['channel_id']}>"
                if answer == db_answer:
                    continue
                elif answer and not db_answer:
                    discrepancies.append(
                        f"* **Solved!** {channel} needs answer `{answer}`"
                    )
                elif not answer and db_answer:
                    discrepancies.append(
                        f"* Mis-labeled! {channel} lists answer `{db_answer}` "
                        f"but is not marked as solved on the Hunt website"
                    )
                else:
                    discrepancies.append(
                        f"* Mis-labeled! {channel} lists answer `{db_answer}` "
                        f"but the Hunt website says `{answer}`"
                    )
        discrepancies = "\n".join(discrepancies)
        puzzles_to_buy = "\n".join(puzzles_to_buy)

        async def send_chunks(message):
            if len(message) < 2000:
                await ctx.send(message)
                return
            chunks = []
            chunk = ""
            first_line = True
            for line in message.split("\n"):
                if not first_line:
                    line = "\n" + line
                first_line = False
                if len(line) >= 2000:
                    chunk += line[: (2000 - len(chunk))]
                    chunks.append(chunk)
                    chunk = line[2000:]
                    continue
                if len(chunk) + len(line) >= 2000:
                    chunks.append(chunk)
                    chunk = ""
                chunk += line
            if chunk:
                chunks.append(chunk)
            for chunk in chunks:
                await ctx.send(chunk)

        if not discrepancies and not puzzles_to_buy:
            await ctx.send("Hunt website and Puzzleboss appear to be in sync :)")
        elif not discrepancies and puzzles_to_buy:
            await send_chunks(
                f"No discrepancies found, but we have {currency} keys "
                f"we can use on some puzzles:\n{puzzles_to_buy}"
            )
        elif discrepancies and not puzzles_to_buy:
            await send_chunks(f"Discrepancies found:\n{discrepancies}")
        else:
            await send_chunks(
                f"Discrepancies found:\n{discrepancies}\n\n"
                f"We also have {plural(currency, 'key')} we can use on some puzzles:\n"
                f"{puzzles_to_buy}"
            )


async def setup(bot):
    cog = Puzzboss(bot)
    await bot.add_cog(cog)
