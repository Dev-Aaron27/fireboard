import discord
from discord.ext import commands
import aiohttp
import json
import os
from flask import Flask
from threading import Thread
from flask_cors import CORS

# ----- Keep-alive web server -----
app = Flask(__name__)
CORS(app, origins=["https://fireboard.infy.uk"])  # Allow your frontend domain

@app.route('/')
def home():
    return "Fire Board bot is running!"

def run_webserver():
    # Use port 8080 (adjust if your hosting requires a different port)
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_webserver)
    t.daemon = True  # So it exits when main program exits
    t.start()

# ----- Discord bot setup -----
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1068275031106387968  # Fire Ads server ID
BACKEND_URL = "https://fireboard-5npd.onrender.com/api/ads"  # Your backend endpoint
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

# Load opt-out list
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
    """Stop your ads from being tracked."""
    if ctx.author.id not in optout_list:
        optout_list.append(ctx.author.id)
        with open(OPTOUT_FILE, "w") as f:
            json.dump(optout_list, f)
        await ctx.send("✅ You have opted out of Fire Board tracking.")
    else:
        await ctx.send("❌ You are already opted out.")

@bot.command()
async def optin(ctx):
    """Resume tracking your ads."""
    if ctx.author.id in optout_list:
        optout_list.remove(ctx.author.id)
        with open(OPTOUT_FILE, "w") as f:
            json.dump(optout_list, f)
        await ctx.send("✅ You have opted back in to Fire Board tracking.")
    else:
        await ctx.send("❌ You are already opted in.")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if message.guild is None:
        return
    if message.guild.id != GUILD_ID:
        return
    if message.author.id in optout_list:
        return  # Skip tracking for opted-out users

    if not message.content.strip():
        return

    if not message.channel.category_id:
        return

    category_name = CATEGORY_MAP.get(message.channel.category_id)
    if not category_name:
        return

    # Get invite link from message or create one
    invite_url = None
    if "discord.gg" in message.content or "discord.com/invite" in message.content:
        for word in message.content.split():
            if "discord.gg" in word or "discord.com/invite" in word:
                invite_url = word
                break
    else:
        try:
            invite = await message.channel.create_invite(max_age=86400, max_uses=0)
            invite_url = str(invite)
        except:
            invite_url = "No invite"

    payload = {
        "server_name": message.guild.name,
        "category": category_name,
        "content": message.content,
        "invite": invite_url,
        "timestamp": str(message.created_at),
        "author_id": message.author.id
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(BACKEND_URL, json=payload) as resp:
                if resp.status == 200:
                    print(f"✅ Sent ad from {message.author} in {category_name}")
                else:
                    print(f"⚠️ Failed to send ad: {resp.status}")
        except Exception as e:
            print(f"❌ Error sending ad: {e}")

    await bot.process_commands(message)

if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
