import discord
from discord.ext import commands
import aiohttp
import os
import threading
from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

# --- Backend Setup ---

app = Flask(__name__)
CORS(app, origins=["https://fireboard.infy.uk"])  # Adjust your frontend URL

# MongoDB setup
MONGO_URI = "mongodb+srv://admin:KabjFL6qQ9Ya8W39@cluster0.0xzfpwa.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
mongo_client = MongoClient(MONGO_URI)

try:
    mongo_client.admin.command('ping')
    print("✅ Connected to MongoDB")
except ConnectionFailure:
    print("❌ Failed to connect to MongoDB")

db = mongo_client["fireboard"]
ads_collection = db["ads"]

@app.route("/")
def home():
    return "Fire Board backend running"

@app.route("/api/ads", methods=["GET", "POST"])
def ads_route():
    if request.method == "POST":
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data sent"}), 400

        # Deduplication: check if ad with same author_id and timestamp exists
        exists = ads_collection.find_one({
            "author_id": data.get("author_id"),
            "timestamp": data.get("timestamp")
        })
        if not exists:
            ads_collection.insert_one(data)
            return jsonify({"status": "success"}), 200
        else:
            return jsonify({"status": "duplicate"}), 200

    else:  # GET
        ads = list(ads_collection.find({}, {'_id': False}))
        return jsonify(ads), 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# --- Discord Bot Setup ---

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1068275031106387968  # Your Fire Ads server ID
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8080/api/ads")

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

# Load optout list or start empty
import json
if os.path.exists(OPTOUT_FILE):
    try:
        with open(OPTOUT_FILE, "r") as f:
            optout_list = json.load(f)
    except Exception:
        optout_list = []
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
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if message.guild is None or message.guild.id != GUILD_ID:
        return
    if message.author.id in optout_list:
        return
    if not message.content.strip():
        return
    if not message.channel.category_id:
        return

    category_name = CATEGORY_MAP.get(message.channel.category_id)
    if not category_name:
        return

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
                    print(f"⚠️ Failed to send ad: {resp.status}")
        except Exception as e:
            print(f"❌ Error sending ad: {e}")

    await bot.process_commands(message)

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    bot.run(TOKEN)
