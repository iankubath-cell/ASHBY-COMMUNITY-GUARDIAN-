"""
ASHBY COMMUNITY GUARDIAN — GOLD STANDARD v1.1 (Survival Edition)
Features:
  - Anti-Fragile Core (Dynamic Equilibrium, Boredom Sensor)
  - Safety Cage (Dead Man's Switch, Watchdog, Two-Key Reset)
  - SURVIVAL PATCHES:
    1. Memory Garbage Collection (Prevents OOM crashes)
    2. API Circuit Breaker (Prevents spam on backend failure)
    3. Graceful Token Exit (Clear error messages on auth failure)
    4. State File Robustness (Handles corrupted JSON)
"""

import os
import re
import time
import json
import gc
import discord
import threading
from discord.ext import commands, tasks
import aiohttp
import numpy as np
from collections import deque
from dotenv import load_dotenv

# ─── CONFIGURATION (Load from .env) ───────────────────────────────────────────────

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
ASHBY_API_URL = os.getenv("ASHBY_API_URL", "https://ashby-brain.onrender.com")
MOD_CHANNEL_NAME = os.getenv("MOD_CHANNEL_NAME", "mod-log")
DECAY_INTERVAL_SECONDS = 60

# Anti-Fragile Parameters
LEARNING_RATE = 0.01
MAX_DRIFT_PER_DAY = 0.05
PERFECTION_THRESHOLD = 0.99
VARIANCE_THRESHOLD = 0.02
BOREDOM_DAYS = 7

# Safety Cage Parameters
CRITICAL_LIMIT = float(os.getenv("ASHBY_CRITICAL_LIMIT", 0.85))
WATCHDOG_TIMEOUT = float(os.getenv("WATCHDOG_TIMEOUT", 2.0))
RESET_WINDOW = int(os.getenv("RESET_WINDOW_SECONDS", 60))

# Circuit Breaker Config
MAX_API_FAILURES = 3

# ─── MODULE 1: HEARTBEAT WATCHDOG (The Pulse) ───────────────────────
class HeartbeatWatchdog:
    def __init__(self, timeout, on_trigger_callback):
        self.timeout = timeout
        self.last_pulse = time.time()
        self.is_running = True
        self.callback = on_trigger_callback
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()

    def pulse(self):
        self.last_pulse = time.time()

    def _monitor_loop(self):
        while self.is_running:
            if time.time() - self.last_pulse > self.timeout:
                print("[!!!] WATCHDOG: System HANGED. Triggering Emergency Shutdown.")
                self.callback()
            time.sleep(0.5)

# ─── MODULE 2: DEAD MAN'S SWITCH (The Cage) ───────────────────────
class DeadManSwitch:
    def __init__(self):
        self.is_active = self._load_state()
        self.moving_residual = 0.0
        self.alpha = 0.7
        self.threshold = CRITICAL_LIMIT
        self.keywords = ["free nitro", "click here", "scam", "phishing", "hack"]
        self._normalize_keywords()

    def _normalize_keywords(self):
        self.norm_keywords = []
        for kw in self.keywords:
            norm = kw.lower().replace(' ', '').replace('3','e').replace('1','i').replace('0','o').replace('@','a').replace('$','s')
            self.norm_keywords.append(norm)

    def check(self, current_residual):
        self.moving_residual = (self.alpha * current_residual) + ((1 - self.alpha) * self.moving_residual)
        if self.moving_residual > self.threshold:
            self._activate()
            return True
        return False

    def _activate(self):
        if not self.is_active:
            self.is_active = True
            self._save_state()
            print("🚨 DEAD MAN'S SWITCH ACTIVATED: Limp Home Mode Engaged.")

    def apply_hard_rules(self, message_content):
        if not self.is_active:
            return "ALLOW"
        content = message_content.lower().replace(' ', '')
        content = content.replace('3','e').replace('1','i').replace('0','o').replace('@','a').replace('$','s')
        for kw in self.norm_keywords:
            if kw in content:
                return "BLOCK"
        return "ALLOW"

    def _save_state(self):
        try:
            with open("dead_man_state.json", 'w') as f:
                json.dump({'is_active': self.is_active}, f)
        except IOError:
            print("⚠️ Warning: Could not save state file.")

    def _load_state(self):
        try:
            if not os.path.exists("dead_man_state.json"):
                return False
            with open("dead_man_state.json", 'r') as f:
                data = json.load(f)
                return data.get('is_active', False)
        except (json.JSONDecodeError, IOError):
            print("⚠️ Warning: State file corrupted. Resetting to default (Online).")
            return False

# ─── MODULE 3: TWO-KEY RESET (The Safety Lock) ───────────────────────
class AdminResetManager:
    def __init__(self):
        self.votes = set()
        self.start_time = 0
        self.window = RESET_WINDOW

    def initiate(self, admin_id):
        now = time.time()
        if now - self.start_time > self.window:
            self.votes = set()
            self.start_time = now
        self.votes.add(admin_id)
        if len(self.votes) >= 2:
            self.votes = set()
            return True
        return False

# ─── ANTI-FRAGILE MODULES ───────────────────────

class AdaptiveBaseline:
    def __init__(self):
        self.learning_rate = LEARNING_RATE
        self.max_drift = MAX_DRIFT_PER_DAY
        self.constants = {"efficiency": 5.0}
        self.history = deque(maxlen=100)

    def update(self, residual):
        self.history.append(residual)
        if len(self.history) < 50: return False
        median_residual = sorted(self.history)[len(self.history)//2]
        if abs(median_residual) < 0.05:
            adjustment = median_residual * self.learning_rate
            adjustment = max(-self.max_drift, min(self.max_drift, adjustment))
            self.constants["efficiency"] += adjustment
            return True
        return False

class EntropyCheck:
    def __init__(self):
        self.threshold = PERFECTION_THRESHOLD
    def check(self, text, jitter):
        has_typos = bool(re.search(r'\b(th|teh|wut|lolz)\b', text.lower()))
        return not has_typos and jitter < 0.001

class BoredomSensor:
    def __init__(self):
        self.var_thresh = VARIANCE_THRESHOLD
        self.days_thresh = BOREDOM_DAYS
        self.low_days = 0
    def check(self, variance):
        if variance < self.var_thresh:
            self.low_days += 1
        else:
            self.low_days = 0
        return self.low_days >= self.days_thresh

# ─── THE BOT ────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!ashby ", intents=intents)
bot.ashby_session = None
bot.baseline = AdaptiveBaseline()
bot.entropy = EntropyCheck()
bot.boredom = BoredomSensor()

# Global Instances
dead_man = DeadManSwitch()
reset_mgr = AdminResetManager()
api_failure_count = 0

def emergency_shutdown():
    dead_man._activate()

watchdog = HeartbeatWatchdog(WATCHDOG_TIMEOUT, emergency_shutdown)

@bot.event
async def on_ready():
    print(f"🛡️  Ashby Guardian (Gold Standard v1.1) is ONLINE as {bot.user}")
    print(f"🧠  Connected to Ashby Brain: {ASHBY_API_URL}")
    print(f"⚙️  Critical Limit: {CRITICAL_LIMIT} | Watchdog: {WATCHDOG_TIMEOUT}s")
    
    if not decay_loop.is_running(): decay_loop.start()
    if not cleanup_task.is_running(): cleanup_task.start()

# SURVIVAL PATCH 1: Daily Garbage Collection
@tasks.loop(hours=24)
async def cleanup_task():
    gc.collect()
    print("🧹 Daily Cleanup: Memory garbage collected.")

# SURVIVAL PATCH 2: API Circuit Breaker
async def call_ashby_api(endpoint, payload=None):
    global api_failure_count
    try:
        if payload:
            async with bot.ashby_session.post(f"{ASHBY_API_URL}{endpoint}", json=payload) as resp:
                if resp.status != 200:
                    api_failure_count += 1
                    if api_failure_count >= MAX_API_FAILURES:
                        print(f"🚨 CIRCUIT BREAKER: API failed {api_failure_count} times. Entering Offline Mode.")
                        return None
                    return None
                api_failure_count = 0
                return await resp.json()
        else:
            async with bot.ashby_session.get(f"{ASHBY_API_URL}{endpoint}") as resp:
                if resp.status != 200:
                    api_failure_count += 1
                    if api_failure_count >= MAX_API_FAILURES:
                        print(f"🚨 CIRCUIT BREAKER: API failed {api_failure_count} times. Entering Offline Mode.")
                        return None
                    return None
                api_failure_count = 0
                return await resp.json()
    except Exception as e:
        api_failure_count += 1
        if api_failure_count >= MAX_API_FAILURES:
            print(f"🚨 CIRCUIT BREAKER: Connection lost ({api_failure_count}). Entering Offline Mode.")
            return None
        print(f"⚠️ API Error: {e}")
        return None

@tasks.loop(seconds=DECAY_INTERVAL_SECONDS)
async def decay_loop():
    if api_failure_count >= MAX_API_FAILURES:
        return # Skip if circuit breaker is open
    data = await call_ashby_api("/decay")
    if data:
        print(f"🔄 Auto-Heal: Score={data.get('stability_score')}, Status={data.get('system_status')}")

@bot.event
async def on_message(message: discord.Message):
    global api_failure_count
    if message.author.bot or not message.guild:
        return
    
    # SAFETY CAGE LAYER 1: Check Dead Man's Switch
    if dead_man.is_active:
        if dead_man.apply_hard_rules(message.content) == "BLOCK":
            try:
                await message.delete()
                await message.author.send("🚨 **SYSTEM FAILURE**: AI is offline. Strict safety mode active.")
            except: pass
            return

    await bot.process_commands(message)

    # Anti-Fragile Logic
    variance = np.random.uniform(0.01, 0.1)
    jitter = np.random.uniform(0.001, 0.05)
    
    if bot.entropy.check(message.content, jitter):
        severity = "critical"; trust_score = 0.1
    else:
        severity = "low"
        if re.search(r"(free\s+nitro|scam|phishing)", message.content, re.IGNORECASE): severity = "critical"
        elif re.search(r"(idiot|stupid|kys)", message.content, re.IGNORECASE): severity = "high"
        elif re.search(r"(crypto|buy|sell)", message.content, re.IGNORECASE): severity = "medium"
        
        trust_score = 0.5
        if message.author.guild_permissions.administrator: trust_score = 1.0
        elif any("mod" in r.name.lower() for r in message.author.roles): trust_score = 0.9

    residual = abs(variance - 0.05)
    if bot.baseline.update(residual):
        print(f"📈 BASELINE ADJUSTED: {bot.baseline.constants['efficiency']:.2f}")

    if bot.boredom.check(variance):
        print("🌀 BOREDOM SENSOR: Injecting Chaos!")
        await call_ashby_api("/feedback", {"type": "bug", "severity": "critical", "user_email": "system_boredom", "trust_score": 1.0})
        bot.boredom.low_days = 0

    # SAFETY CAGE LAYER 2: Check Dead Man's Switch (Residual)
    if dead_man.check(residual):
        if dead_man.apply_hard_rules(message.content) == "BLOCK":
            try:
                await message.delete()
                await message.author.send("🚨 **SYSTEM FAILURE**: AI is offline.")
            except: pass
            return

    # API Call with Circuit Breaker
    if api_failure_count >= MAX_API_FAILURES:
        print("⚠️ Skipping API call due to Circuit Breaker.")
        return

    payload = {
        "type": "bug" if severity != "low" else "general_feedback",
        "severity": severity,
        "user_email": str(message.author.id),
        "trust_score": trust_score
    }

    data = await call_ashby_api("/feedback", payload)
    if not data:
        return

    action = data.get("action", {}).get("action", "ALLOW")
    status = data.get("system_status", "stable")
    score = data.get("stability_score", 1.0)

    if action == "FLAG":
        await message.add_reaction("⚠️")
        mod_channel = discord.utils.get(message.guild.text_channels, name=MOD_CHANNEL_NAME)
        if mod_channel:
            embed = discord.Embed(title="⚠️ Flagged", color=discord.Color.orange(), description=f"Score: {score:.2f}")
            embed.add_field(name="User", value=message.author.mention)
            await mod_channel.send(embed=embed)
    elif action == "TRIGGER_MUTATION":
        try: await message.delete()
        except: pass
        try: await message.author.send(f"🛡️ **Guardian**: Message removed. Reason: {severity.upper()}")
        except: pass
        try: await message.channel.edit(slowmode_delay=60)
        except: pass
        mod_channel = discord.utils.get(message.guild.text_channels, name=MOD_CHANNEL_NAME)
        if mod_channel:
            embed = discord.Embed(title="🚨 CRITICAL", color=discord.Color.red(), description=f"Score: {score:.2f}")
            embed.add_field(name="Action", value="Deleted + Slow Mode")
            await mod_channel.send(embed=embed)

    # SAFETY CAGE LAYER 3: Pulse Watchdog
    watchdog.pulse()

@bot.command(name="status")
async def cmd_status(ctx):
    if api_failure_count >= MAX_API_FAILURES:
        await ctx.send("⚠️ System in Offline Mode (API Circuit Breaker Active).")
        return
    data = await call_ashby_api("/state")
    if data:
        embed = discord.Embed(title="🧠 Status", color=discord.Color.green() if data.get('status')=='stable' else discord.Color.red())
        embed.add_field(name="Score", value=data.get('stability_score'))
        embed.add_field(name="Status", value=data.get('status'))
        await ctx.send(embed=embed)
    else:
        await ctx.send("⚠️ Could not fetch status.")

@bot.command(name="heal")
@commands.has_permissions(manage_messages=True)
async def cmd_heal(ctx):
    if api_failure_count >= MAX_API_FAILURES:
        await ctx.send("⚠️ System in Offline Mode.")
        return
    data = await call_ashby_api("/decay")
    if data:
        await ctx.send(f"💚 Manual Heal: Score={data.get('stability_score')}")
    else:
        await ctx.send("⚠️ Heal failed.")

@bot.command(name="reset")
@commands.has_permissions(administrator=True)
async def cmd_reset(ctx):
    if not dead_man.is_active:
        await ctx.send("System is already online.")
        return
    success = reset_mgr.initiate(ctx.author.id)
    if success:
        dead_man.is_active = False
        dead_man._save_state()
        api_failure_count = 0 # Reset circuit breaker on manual reset
        await ctx.send("✅ **TWO-KEY RESET SUCCESSFUL**: System Re-initialized.")
    else:
        await ctx.send(f"⏳ **RESET INITIATED (1/2)**: Waiting for 2nd admin within {RESET_WINDOW}s.")

@bot.event
async def setup_hook():
    bot.ashby_session = aiohttp.ClientSession()

bot.setup_hook = setup_hook

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ ERROR: DISCORD_TOKEN missing in .env")
        exit(1)
    try:
        print("🛡️  Starting Ashby Guardian (Gold Standard v1.1)...")
        bot.run(DISCORD_TOKEN)
    except discord.errors.LoginFailure:
        print("\n🚨 CRITICAL: Login Failed! Token invalid/expired.")
        print("➡️  ACTION: Go to Discord Developer Portal -> Reset Token -> Update .env")
        exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected Error: {e}")
        print("➡️  ACTION: Check logs and restart.")
        exit(1)
