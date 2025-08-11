import discord
from discord.ext import commands
import aiohttp
import os
import threading
from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import certifi
import json

# --- Backend Setup ---

app = Flask(__name__)
CORS(app, origins=["https://fireboard.infy.uk"])  # Adjust your frontend URL

# MongoDB setup with certifi to handle TLS CA certificates properly
MONGO_URI = "mongodb+srv://admin:KabjFL6qQ9Ya8W39@cluster0.0xzfpwa.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
mongo_client = MongoClient(MONGO_URI, tls=True, tlsCAFile=certifi.where())

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
            print("No data received in POST")
            return jsonify({"error": "No data sent"}), 400

        print(f"Received ad data: {data}")

        # Validate required fields (optional but recommended)
        required_fields = ["author_id", "timestamp", "content", "server_name", "category"]
        missing = [field for field in required_fields if field not in data]
        if missing:
            print(f"Missing fields in POST data: {missing}")
            return jsonify({"error": f"Missing fields: {missing}"}), 400

        try:
            # Check for duplicate by author_id + timestamp
            exists = ads_collection.find_one({
                "author_id": data.get("author_id"),
                "timestamp": data.get("timestamp")
            })
            if exists:
                print("Duplicate ad, not inserting.")
                return jsonify({"status": "duplicate"}), 200

            # Insert new ad
            result = ads_collection.insert_one(data)
            print(f"Inserted ad with ID: {result.inserted_id}")
            return jsonify({"status": "success"}), 200
        except Exception as e:
            print(f"Error inserting ad: {e}")
            return jsonify({"error": "Database insert failed"}), 500

    else:  # GET
        try:
            ads = list(ads_collection.find({}, {'_id': False}))
            print(f"Fetched {len(ads)} ads from DB")
            return jsonify(ads), 200
        except Exception as e:
            print(f"Error fetching ads: {e}")
            return jsonify({"error": "Database fetch failed"}), 500


def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# --- Discord Bot Setup ---

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1068275031106387968  # Your Fire Ads server ID

# Make sure BACKEND_URL is reachable from bot
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8080/api/ads")

OPTOUT_FILE = "optout.json"

CATEGORY_MAP = {
    1275488682618392699: "Premium",
    1280616873305571463: "Partners",
    1392814387454283838: "Everything",
    1396951878691983510: "Discord",
    1396951925353611264: "2h",
    139695197207422564: "6h",
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
    # Ignore bots, DMs, wrong guild, opted-out users, empty messages, or channels without category
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
        print(f"Category ID {message.channel.category_id} not in CATEGORY_MAP, ignoring message.")
        await bot.process_commands(message)
        return

    # Extract invite URL if present in message
    invite_url = None
    for word in message.content.split():
        if "discord.gg" in word or "discord.com/invite" in word:
            invite_url = word
            break

    # If no invite URL in content, create a temporary invite
    if not invite_url:
        try:
            invite = await message.channel.create_invite(max_age=86400, max_uses=0, unique=True)
            invite_url = str(invite)
        except Exception as e:
            print(f"Failed to create invite: {e}")
            invite_url = None

    payload = {
        "server_name": message.guild.name,
        "category": category_name,
        "content": message.content,
        "invite": invite_url or "No invite",
        "timestamp": message.created_at.isoformat(),
        "author_id": message.author.id
    }

    print(f"Sending ad payload: {payload}")

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(BACKEND_URL, json=payload) as resp:
                text = await resp.text()
                if resp.status == 200:
                    print(f"✅ Successfully sent ad from {message.author} in {category_name}")
                else:
                    print(f"⚠️ Failed to send ad: HTTP {resp.status}, Response: {text}")
        except Exception as e:
            print(f"❌ Exception sending ad: {e}")

    await bot.process_commands(message)


if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    bot.run(TOKEN)
