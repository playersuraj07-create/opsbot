# =========================
# OPSBOT – CORE STABLE (OPTION A LOCKED)
# =========================

import discord
from discord.ext import commands, tasks
from discord.utils import get
import os, asyncio, time, re, json, random
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# ---------- ENV ----------
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN missing")

# ---------- PATHS ----------
BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
ANALYTICS = os.path.join(DATA, "analytics")
STATE_FILE = os.path.join(DATA, "state.json")

PATHS = {
    "badwords": os.path.join(DATA, "moderation", "badwords.txt"),
    "messages": os.path.join(ANALYTICS, "messages.json"),
    "warnings": os.path.join(ANALYTICS, "warnings.json"),
    "actions": os.path.join(ANALYTICS, "actions.json"),
}

# ---------- FILE SAFETY ----------
def ensure(path, default):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default, f)

os.makedirs(ANALYTICS, exist_ok=True)
ensure(PATHS["messages"], {})
ensure(PATHS["warnings"], {})
ensure(PATHS["actions"], {})
ensure(STATE_FILE, {
    "auto_greet": True,
    "auto_question": True,
    "silence_breaker": True
})

# ---------- UTIL ----------
def read_lines(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [x.strip() for x in f if x.strip()]

def normalize(txt):
    return re.sub(r"[^a-z]", "", txt.lower())

def log_json(path, key, value=1):
    with open(path, "r+", encoding="utf-8") as f:
        data = json.load(f)
        data[key] = data.get(key, 0) + value
        f.seek(0)
        json.dump(data, f, indent=2)
        f.truncate()

def log_action(name):
    with open(PATHS["actions"], "r+", encoding="utf-8") as f:
        data = json.load(f)
        data.append({"action": name, "time": datetime.utcnow().isoformat()})
        f.seek(0)
        json.dump(data, f, indent=2)
        f.truncate()

def time_block():
    h = datetime.now().hour
    if 5 <= h < 12: return "morning"
    if 12 <= h < 17: return "afternoon"
    if 17 <= h < 21: return "evening"
    return "night"

async def auto_delete(msg, delay):
    await asyncio.sleep(delay)
    try: await msg.delete()
    except: pass

# ---------- BOT ----------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ---------- MODERATION CONFIG ----------
MAX_REPEAT = 3
FLOOD_TIME = 6
MAX_MSGS = 5
MAX_WARNINGS = 2
TIMEOUT_MINUTES = 10

user_cache = {}
user_warnings = {}
hello_wait = {}

BADWORDS = set(normalize(w) for w in read_lines(PATHS["badwords"]))

# ---------- WARN ----------
async def warn(member, channel, reason):
    guild = member.guild
    modlog = get(guild.text_channels, name="mod-logs")

    user_warnings[member.id] = user_warnings.get(member.id, 0) + 1
    count = user_warnings[member.id]

    msg = await channel.send(
        f"⚠️ {member.mention} Warning {count}/{MAX_WARNINGS}\nReason: **{reason}**"
    )
    asyncio.create_task(auto_delete(msg, 120))

    if modlog:
        await modlog.send(
            f"⚠️ WARNING\nUser: {member}\nReason: {reason}\nCount: {count}"
        )

    log_json(PATHS["warnings"], reason)

    if count >= MAX_WARNINGS:
        until = datetime.now(timezone.utc) + timedelta(minutes=TIMEOUT_MINUTES)
        await member.timeout(until, reason="Repeated violations")
        if modlog:
            await modlog.send(f"⏳ TIMEOUT → {member} ({TIMEOUT_MINUTES}m)")

# ---------- MESSAGE LISTENER ----------
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    await bot.process_commands(message)

    if message.channel.name != "general":
        return

    uid = message.author.id
    now = time.time()
    text = message.content
    norm = normalize(text)

    log_json(PATHS["messages"], str(uid))

    # ---- BAD WORDS ----
    for bad in BADWORDS:
        if bad and bad in norm:
            await message.delete()
            await warn(message.author, message.channel, "Abusive language")
            return

    # ---- SPAM ----
    cache = user_cache.get(uid, [])
    cache.append((text, now))
    cache = [c for c in cache if now - c[1] <= FLOOD_TIME]
    user_cache[uid] = cache

    if len(cache) > MAX_MSGS:
        await message.delete()
        await warn(message.author, message.channel, "Flood spam")
        return

    same = [c for c in cache if c[0].lower() == text.lower()]
    if len(same) >= MAX_REPEAT:
        await message.delete()
        await warn(message.author, message.channel, "Repeated spam")
        return

    # ---- HI / HELLO AUTO REPLY ----
    if norm in ("hi", "hello"):
        if uid not in hello_wait:
            hello_wait[uid] = now
            await asyncio.sleep(15)
            if hello_wait.get(uid) == now:
                reply = random.choice([
                    "👋 Hey! Looks like no one is online right now.",
                    "🤖 OPSBOT here — community seems quiet!",
                    "👀 Hello! Feel free to start a topic."
                ])
                sent = await message.channel.send(reply)
                asyncio.create_task(auto_delete(sent, 300))
                del hello_wait[uid]

# ---------- SILENCE BREAKER ----------
@tasks.loop(minutes=5)
async def silence_breaker():
    with open(STATE_FILE) as f:
        state = json.load(f)
    if not state.get("silence_breaker"):
        return

    for g in bot.guilds:
        ch = get(g.text_channels, name="general")
        if not ch or not ch.last_message:
            continue

        diff = datetime.now(timezone.utc) - ch.last_message.created_at
        mins = random.randint(90,120) if time_block()=="night" else random.randint(20,40)

        if diff >= timedelta(minutes=mins):
            msg = await ch.send("💬 Silence breaker — say something!")
            log_action("silence_break")
            asyncio.create_task(auto_delete(msg, 600))

# ---------- READY ----------
@bot.event
async def on_ready():
    print(f"OPSBOT CORE READY: {bot.user}")
    silence_breaker.start()

bot.run(TOKEN)
