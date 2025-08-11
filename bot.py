import discord
from discord.ext import commands
import aiohttp
import json
import os
import threading
from flask import Flask
from flask_cors import CORS

# Backend settings
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8080/api/ads")

# Discord bot settings
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1068275031106387968  # Fire Ads server ID

# Opt-out storage file
OPTOUT_FILE = "optout.json"

CATEGORY_MAP = {
    1275488682618392699: "Premium",
    1280616873305571463: "Partners",
    1392814387454283838: "Everything",
    1396951878691983510: "Discord",
    1396951925353611264: "2h",
    1396951972074225664: "6h",
    1392810834648105083: "Socials",
    1396952374081355786: "Looking For",
    1280616481998246012: "Level 15",
    1280616462125498449: "Level 10",
    1392808339125174282: "Level 5"
}

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Load or create opt-out list
if os.path.exists(OPTOUT_FILE):
    with open(OPTOUT_FILE, "r") as f:
        optout_list = json.load(f)
else:
    optout_list = []

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

@bot.command()
async def optout(ctx):
    if ctx.author.id not in optout_list:
        optout_list.append(ctx.author.id)
        with open(OPTOUT_FILE, "w") as f:
            json.dump(optout_list, f)
        await ctx.send("✅ You have opted out of Fire Board tracking.")
    else:
        await ctx.send("❌ You are already opted out.")

@bot.command()
async def optin(ctx):
    if ctx.author.id in optout_list:
        optout_list.remove(ctx.author.id)
        with open(OPTOUT_FILE, "w") as f:
            json.dump(optout_list, f)
        await ctx.send("✅ You have opted back in to Fire Board tracking.")
    else:
        await ctx.send("❌ You are already opted in.")

@bot.event
async def on_message(message):
    if message.author.bot:
        return  # Ignore bots
    if message.guild is None or message.guild.id != GUILD_ID:
        return  # Only track in Fire Ads server
    if message.author.id in optout_list:
        return  # Skip opted out users
    if not message.content.strip():
        return  # Ignore empty messages
    if not message.channel.category_id:
        return  # Ignore if no category

    category_name = CATEGORY_MAP.get(message.channel.category_id)
    if not category_name:
        return  # Ignore if category not tracked

    # Extract invite URL from message content if present
    invite_url = None
    for word in message.content.split():
        if "discord.gg" in word or "discord.com/invite" in word:
            invite_url = word
            break
    if invite_url is None:
        # Try to create invite if not present in content
        try:
            invite = await message.channel.create_invite(max_age=86400, max_uses=0)
            invite_url = str(invite)
        except Exception:
            invite_url = "No invite"

    payload = {
        "server_name": message.guild.name,
        "category": category_name,
        "content": message.content,
        "invite": invite_url,
        "timestamp": message.created_at.isoformat(),
        "author_id": message.author.id
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(BACKEND_URL, json=payload) as resp:
                if resp.status == 200:
                    print(f"✅ Sent ad from {message.author} in {category_name}")
                else:
                    print(f"⚠️ Failed to send ad: HTTP {resp.status}")
        except Exception as e:
            print(f"❌ Error sending ad: {e}")

    await bot.process_commands(message)


if __name__ == "__main__":
    bot.run(TOKEN)
