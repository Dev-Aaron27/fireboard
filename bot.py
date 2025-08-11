import discord
from discord.ext import commands
import aiohttp
import json
import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from threading import Thread
from datetime import datetime

# --- CONFIG ---
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1068275031106387968  # Fire Ads server ID

# Your categories (discord category channel IDs mapped to names)
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

OPTOUT_FILE = "optout.json"
ADS_FILE = "ads.json"

# --- Load opt-out list ---
if os.path.exists(OPTOUT_FILE):
    with open(OPTOUT_FILE, "r") as f:
        optout_list = json.load(f)
else:
    optout_list = []

# --- Load stored ads ---
if os.path.exists(ADS_FILE):
    with open(ADS_FILE, "r") as f:
        ads_data = json.load(f)
else:
    ads_data = []  # List of dicts representing ads


# --- Flask Webserver (backend API) ---
app = Flask(__name__)
CORS(app)  # Enable CORS for all origins (adjust as needed)

@app.route('/')
def home():
    return "Fire Board backend is running!"

@app.route('/api/ads', methods=['GET'])
def get_ads():
    # Optionally support query params for filtering, sorting here
    # For now, just return all ads sorted by timestamp descending
    sorted_ads = sorted(ads_data, key=lambda x: x["timestamp"], reverse=True)
    return jsonify(sorted_ads)

def run_flask():
    app.run(host="0.0.0.0", port=8080)

def start_flask_in_thread():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# --- Discord Bot ---
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"✅ Bot logged in as {bot.user}")


@bot.command()
async def optout(ctx):
    """User opts out from being tracked."""
    if ctx.author.id not in optout_list:
        optout_list.append(ctx.author.id)
        with open(OPTOUT_FILE, "w") as f:
            json.dump(optout_list, f)
        await ctx.send("✅ You have opted out of Fire Board tracking.")
    else:
        await ctx.send("❌ You are already opted out.")


@bot.command()
async def optin(ctx):
    """User opts back in to tracking."""
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
        return  # Only track messages in the Fire Ads server

    if message.author.id in optout_list:
        return  # User opted out

    if not message.content or not message.content.strip():
        return

    if not message.channel.category_id:
        return

    category_name = CATEGORY_MAP.get(message.channel.category_id)
    if not category_name:
        return  # Category not tracked

    # Try to find an invite link in the message content
    invite_url = None
    for word in message.content.split():
        if "discord.gg/" in word or "discord.com/invite/" in word:
            invite_url = word
            break

    # If no invite found, try create one for the channel (if possible)
    if not invite_url:
        try:
            invite = await message.channel.create_invite(max_age=86400, max_uses=0)
            invite_url = str(invite)
        except Exception:
            invite_url = None

    # Compose the ad data
    ad_entry = {
        "id": message.id,
        "server_name": message.guild.name,
        "category": category_name,
        "content": message.content,
        "invite": invite_url or "No invite",
        "timestamp": message.created_at.isoformat(),
        "author_id": message.author.id,
        "author_name": str(message.author),
        "channel_id": message.channel.id,
        "channel_name": message.channel.name
    }

    # Update or add this ad in ads_data (replace if same message ID exists)
    global ads_data
    ads_data = [ad for ad in ads_data if ad["id"] != message.id]  # Remove old if exists
    ads_data.append(ad_entry)

    # Save to file
    with open(ADS_FILE, "w") as f:
        json.dump(ads_data, f, indent=2)

    print(f"✅ Tracked ad from {message.author} in category {category_name}")

    await bot.process_commands(message)


if __name__ == "__main__":
    start_flask_in_thread()
    bot.run(TOKEN)
