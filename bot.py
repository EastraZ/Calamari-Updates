import re
import json
import aiohttp
import discord
from discord.ext import tasks, commands

# === Load config ===
with open("config.json", "r") as f:
    cfg = json.load(f)

TOKEN = cfg["token"]
CHANNEL_ID = int(cfg["channel_id"])

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

PATCH_SOURCES = {
    "Rust": "https://steamdb.info/app/252490/patchnotes/",
    "Apex Legends": "https://steamdb.info/app/1172470/patchnotes/",
    "Rainbow Six Siege": "https://steamdb.info/app/359550/patchnotes/",
    "Fortnite": "https://www.fortnite.com/news"
}

last_seen = {k: None for k in PATCH_SOURCES.keys()}


def make_compact_embed(game: str, title: str, url: str):
    embed = discord.Embed(
        title=title,
        url=url,
        color=discord.Color.red()
    )
    embed.set_author(name=f"{game} patch")
    embed.set_thumbnail(url="attachment://Calamari-diagonal.png")
    return embed


def make_startup_embed():
    embed = discord.Embed(
        title="✅ Patch Bot Online",
        description="Monitoring Rust, Apex Legends, Rainbow Six Siege, and Fortnite.",
        color=discord.Color.red()
    )
    embed.set_thumbnail(url="attachment://Calamari-diagonal.png")
    return embed


async def fetch_text(session: aiohttp.ClientSession, url: str):
    async with session.get(url, timeout=30) as resp:
        if resp.status != 200:
            return None
        return await resp.text()


def parse_steamdb(html: str):
    m = re.search(r'href="(/changelist/(\d+)[^"]*)"', html)
    if not m:
        return None, None
    path = m.group(1)
    cl_num = m.group(2)
    return f"Changelist {cl_num}", "https://steamdb.info" + path


def parse_fortnite(html: str):
    m = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']', html, re.I)
    if m:
        return m.group(1)
    m2 = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
    return m2.group(1).strip() if m2 else None


async def fetch_latest(session, game, url):
    text = await fetch_text(session, url)
    if not text:
        return None, None
    if "steamdb.info" in url:
        return parse_steamdb(text)
    if "fortnite.com" in url:
        t = parse_fortnite(text)
        return (t, url) if t else (None, None)
    return None, None


@tasks.loop(minutes=3)
async def check_patches():
    await bot.wait_until_ready()
    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        print("Channel not found.")
        return
    async with aiohttp.ClientSession() as session:
        for game, url in PATCH_SOURCES.items():
            try:
                title, link = await fetch_latest(session, game, url)
                if not title:
                    continue
                if last_seen[game] is None:
                    last_seen[game] = title
                    continue
                if title != last_seen[game]:
                    last_seen[game] = title
                    embed = make_compact_embed(game, title, link or url)
                    file = discord.File("Calamari-diagonal.png", filename="Calamari-diagonal.png")
                    await channel.send(embed=embed, file=file)
                    print(f"Sent {game}: {title}")
            except Exception as e:
                print(f"Error {game}: {e}")


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")

    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        embed = make_startup_embed()
        file = discord.File("Calamari-diagonal.png", filename="Calamari-diagonal.png")
        # Send “I’m online” message
        asyncio.create_task(channel.send(embed=embed, file=file))

    if not check_patches.is_running():
        check_patches.start()


if __name__ == "__main__":
    bot.run(TOKEN)
