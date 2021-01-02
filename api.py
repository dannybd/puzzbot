#! /usr/bin/python3

import configparser
import discord
import json
import logging
import os
import pymysql
import sys

from hashlib import md5

config = configparser.ConfigParser()
config.read("config.ini")

intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)

GUILD_ID = 790341470171168800
PUZZTECH_CHANNEL = 790387626531225611
STATUS_CHANNEL = 790348440890507285
PUZZLE_CATEGORY = 790343785804201984
SOLVED_PUZZLE_CATEGORY = 790348578018820096


@client.event
async def on_ready():
    logging.info("Connected as {0.user} and ready!".format(client))
    try:
        await gen_run()
    except Exception as e:
        logging.error(e, exc_info=e)
    finally:
        connection.close()
        await client.close()


async def gen_run():
    global guild, status_channel
    guild = client.get_guild(GUILD_ID)
    status_channel = client.get_channel(STATUS_CHANNEL)

    if command == "create" or command == "create_json":
        name, *topic = args
        topic = " ".join(topic)
        channel = await gen_create_channel(name, topic)
        invite = await channel.create_invite()
        print(
            json.dumps(
                {
                    "id": channel.id,
                    "name": channel.name,
                    "mention": channel.mention,
                    "url": invite.url,
                }
            )
        )
        return

    # DB Commands
    puzzle_name = " ".join(args)

    if command == "_new":
        return await gen_announce_new(puzzle_name)

    if command == "_solve":
        return await gen_announce_solve(puzzle_name)

    if command == "_attention":
        return await gen_announce_attention(puzzle_name)

    if command == "_round":
        round_name = puzzle_name
        return await gen_announce_round(round_name)

    # Helper methods
    if command == "stats":
        print("Server has", len(guild.members), "members, including bots")
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                   name
                FROM puzzle_view
                """,
            )
            rows = cursor.fetchall()
            print(
                "Puzzles ({0}):".format(len(rows)),
                [row["name"] for row in rows],
            )
        return

    raise Exception("command {0} not supported!".format(command))


@client.event
async def on_error(*args, **kwargs):
    connection.close()
    await client.close()


async def gen_announce_new(puzzle_name):
    puzzle, channel = get_puzzle_and_channel(puzzle_name)
    round_category = await gen_or_create_round_category(puzzle["round"])
    await channel.edit(
        category=round_category,
        position=0,
    )
    content = "**🚨 New Puzzle 🚨 _`{name}`_ ADDED!**".format(**puzzle)
    embed = build_puzzle_embed(puzzle)
    print("NEW:", puzzle, channel)
    message = await channel.send(content=content, embed=embed)
    await message.pin()
    await status_channel.send(content=content, embed=embed)


async def gen_announce_solve(puzzle_name):
    puzzle, channel = get_puzzle_and_channel(puzzle_name)
    await gen_archive_channel(puzzle, channel)
    return
    await channel.send(
        "**Puzzle solved!** Answer: ||`{answer}`||".format(**puzzle)
        + "\nChannel is now archived."
    )
    content = (
        "**🎉 Puzzle _`{name}`_ has been solved! 🥳**\n"
        + "(Answer: ||`{answer}`||)\n"
        + "Way to go team! 🎉"
    ).format(**puzzle)
    await status_channel.send(content=content)


async def gen_announce_attention(puzzle_name):
    puzzle, channel = get_puzzle_and_channel(puzzle_name)

    status = puzzle["status"]

    if status == "Needs eyes":
        prefix = "❗ "
        content = "**❗️ Puzzle _`{name}`_ NEEDS EYES! 👀**".format(**puzzle)
        embed = build_puzzle_embed(puzzle)
    elif status == "Critical":
        prefix = "⚠️  "
        content = "**🚨 Puzzle _`{name}`_ IS CRITICAL! ⚠️**".format(**puzzle)
        embed = build_puzzle_embed(puzzle)
    elif status == "Unnecessary":
        prefix = "🤷  "
        content = "**🤷 Puzzle _`{name}`_ is now UNNECESSARY! 🤷**".format(**puzzle)
        embed = None
    elif status == "Unnecessary":
        prefix = "☣️  "
        content = None
        embed = None

    if prefix:
        await channel.edit(name=prefix + channel.name)
    if content:
        await channel.send(content=content, embed=embed)
        await status_channel.send(content=content, embed=embed)


async def gen_announce_round(round_name):
    await gen_or_create_round_category(round_name)
    content = "🆕🔄 **New Round added! _`{0}`_**".format(round_name)
    embed = discord.Embed(
        color=get_round_embed_color(round_name),
        title="Round: _`{0}`_".format(round_name),
    )
    await status_channel.send(content=content, embed=embed)


async def gen_or_create_round_category(round_name, is_solved=False):
    category_name = ("🏁 Solved from: {0}" if is_solved else "🧩 {0}").format(round_name)
    existing_categories = [c for c in guild.categories if c.name == category_name]
    category = discord.utils.find(
        lambda category: len(category.channels) < 50,
        existing_categories,
    )
    if category:
        logging.info('Existing category "{0.name}" found'.format(category))
        return category

    if is_solved:
        # 🏁 Solved Puzzles: 🏁
        source_category = client.get_channel(790348578018820096)
    else:
        # 🧩 Puzzles below here: 🧩
        source_category = client.get_channel(790343785804201984)
    position = source_category.position + 1

    if existing_categories:
        # If this is an overflow category, position it just above the
        # other categories it belongs to
        position = min(category.position for category in existing_categories)

    logging.info("Creating new category: {0}".format(category_name))
    category = await source_category.clone(name=category_name)
    await category.edit(position=position)
    return category


def build_puzzle_embed(puzzle):
    embed = discord.Embed(
        color=get_round_embed_color(puzzle["round"]),
        title="Puzzle: _`{name}`_".format(**puzzle),
    )

    status = puzzle["status"]
    if status == "Needs eyes":
        embed.add_field(
            name="Status",
            value="❗️ {status} 👀".format(**puzzle),
            inline=False,
        )
    if status == "Critical":
        embed.add_field(
            name="Status",
            value="⚠️  {status} 🚨️".format(**puzzle),
            inline=False,
        )
    if status == "Unnecessary":
        embed.add_field(
            name="Status",
            value="🤷 {status} 🤷".format(**puzzle),
            inline=False,
        )
    if status == "Solved":
        embed.add_field(
            name="Status",
            value="✅ {status} 🥳".format(**puzzle),
            inline=True,
        )
        embed.add_field(
            name="Answer",
            value="||`{answer}`||".format(**puzzle),
            inline=True,
        )
    if status == "WTF":
        embed.add_field(
            name="Status",
            value="☣️  {status} ☣️".format(**puzzle),
            inline=False,
        )

    embed.add_field(name="Puzzle URL", value=puzzle["puzzle_uri"], inline=False)
    embed.add_field(name="Google Doc", value=puzzle["drive_uri"], inline=False)
    embed.add_field(
        name="Discord Channel", value="<#{channel_id}>".format(**puzzle), inline=True
    )
    embed.add_field(name="Round", value=puzzle["round"], inline=True)
    return embed


def get_round_embed_color(round):
    hash = md5(round.encode("utf-8")).hexdigest()
    hue = int(hash, 16) / 16 ** len(hash)
    return discord.Color.from_hsv(hue, 0.655, 1)


async def gen_create_channel(name, topic):
    category = client.get_channel(PUZZLE_CATEGORY)
    channel = await category.create_text_channel(
        name=name,
        position=1,
        reason='New puzzle: "{0}"'.format(name),
        topic=topic,
    )
    logging.info("Created #{0.name} puzzle channel".format(channel))
    return channel


async def gen_archive_channel(puzzle, channel):
    start_category = channel.category
    if start_category.name.startswith("🏁"):
        logging.warning("{0.name} ({0.id}) already solved".format(channel))
        return

    solved_category = await gen_or_create_round_category(
        round_name=puzzle["round"],
        is_solved=True,
    )
    await channel.edit(
        category=solved_category,
        position=0,
        reason='Puzzle "{0.name}" solved, archiving!'.format(channel),
    )
    logging.info("Archived #{0.name} puzzle channel".format(channel))

    if not start_category.channels:
        logging.info("Puzzle category {0.name} now empty, deleting".format(channel))
        await start_category.delete()


def get_channelx(channel_id):
    channel = None
    if isinstance(channel_id, int) or channel_id.isnumeric():
        channel = client.get_channel(int(channel_id))
    if channel == None:
        channel = discord.utils.get(client.get_all_channels(), name=channel_id)
    if channel == None:
        raise Exception("Channel ID {0} missing!".format(channel_id))
    return channel


def get_puzzle_and_channel(puzzle_name):
    puzzle = _get_puzzle_from_db(puzzle_name)
    if puzzle is None:
        raise Exception('Puzzle "{0}" not found'.format(puzzle_name))
    puzzle["drive_uri"] = (
        "https://wind-up-birds.org/puzzleboss/bin/doc.pl?pid={name}"
    ).format(**puzzle)
    return (puzzle, client.get_channel(int(puzzle["channel_id"])))


def _get_puzzle_from_db(puzzle_name):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
               name,
               round,
               puzzle_uri,
               slack_channel_id AS channel_id,
               status,
               answer
            FROM puzzle_view
            WHERE name = %s
            LIMIT 1
            """,
            (puzzle_name,),
        )
        return cursor.fetchone()


def get_db_connection():
    creds = config["puzzledb"]
    return pymysql.connect(
        host=creds["host"],
        port=creds.getint("port"),
        user=creds["user"].lower(),
        password=creds["passwd"],
        db=creds["db"],
        cursorclass=pymysql.cursors.DictCursor,
    )


if __name__ == "__main__":
    # Define logging levels
    loglevel = os.environ.get("LOGLEVEL", "INFO").upper()
    logging.basicConfig(
        format="%(asctime)s [%(process)d][%(name)s - %(levelname)s] - %(message)s",
        level=loglevel,
    )
    if loglevel == "INFO":
        logging.getLogger("discord").setLevel(logging.WARNING)

    args = sys.argv[1:]
    if len(args) == 0:
        print("Usage: create | message | _round | _new | _solve | _attention")
        sys.exit()
    command, *args = args
    logging.info("Starting! Command: {0}, Args: {1}".format(command, args))
    connection = get_db_connection()
    logging.info("Connected to DB! Starting Discord client...")
    client.run(config["discord"]["botsecret"])
    logging.info("Done, closing out")
