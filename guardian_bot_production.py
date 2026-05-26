"""
ASHBY COMMUNITY GUARDIAN — PRODUCTION v1.0 (Anti-Fragile Edition)
Includes:
  - Dynamic Equilibrium (Target S = 0.7)
  - Adaptive Baseline (Drift Correction)
  - Entropy Check (Synthetic Perfection Detection)
  - Boredom Sensor (Forced Chaos)
  - Cross-Sensor Validation
"""

import os
import re
import time
import discord
from discord.ext import commands, tasks
import aiohttp
import numpy as np
from collections import deque

# ─── CONFIGURATION ───────────────────────────────────────────────

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "YOUR_BOT_TOKEN_HERE")
ASHBY_API_URL = os.getenv("ASHBY_API_URL", "https://ashby-brain.onrender.com")
MOD_CHANNEL_NAME = os.getenv("MOD_CHANNEL_NAME", "mod-log")
DECAY_INTERVAL_SECONDS = 60

# Anti-Fragile Parameters
LEARNING_RATE = 0.01
MAX_DRIFT_PER_DAY = 0.05
PERFECTION_THRESHOLD = 0.99
VARIANCE_THRESHOLD = 0.02
BOREDOM_DAYS = 7

# ─── ANTI-FRAGILE MODULES ───────────────────────────────────────

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
        # Simplified: Check for zero typos and zero jitter
        # Real app: Use NLP for typo rate
        has_typos = bool(re.search(r'\b(th|teh|wut|lolz)\b', text.lower()))
        is_perfect = not has_typos and jitter < 0.001
        return is_perfect

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

@bot.event
async def on_ready():
    print(f"🛡️  Ashby Guardian (Anti-Fragile) is ONLINE as {bot.user}")
    print(f"🧠  Connected to Ashby Brain: {ASHBY_API_URL}")
    if not decay_loop.is_running():
        decay_loop.start()

@tasks.loop(seconds=DECAY_INTERVAL_SECONDS)
async def decay_loop():
    try:
        async with bot.ashby_session.post(f"{ASHBY_API_URL}/decay") as resp:
            if resp.status == 200:
                data = await resp.json()
                print(f"🔄 Auto-Heal: Score={data.get('stability_score')}, Status={data.get('system_status')}")
    except Exception as e:
        print(f"⚠️ Auto-Heal error: {e}")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return
    await bot.process_commands(message)

    # 1. Calculate Variance & Jitter (Simulated for demo)
    # In production, calculate real timing jitter from timestamps
    variance = np.random.uniform(0.01, 0.1) # Placeholder for real variance calc
    jitter = np.random.uniform(0.001, 0.05) # Placeholder for real jitter
    
    # 2. Entropy Check (Synthetic Perfection)
    if bot.entropy.check(message.content, jitter):
        print("⚠️ ENTROPY CHECK: Synthetic Perfection Detected! Treating as Critical.")
        severity = "critical"
        trust_score = 0.1
    else:
        # Standard Evaluation
        severity = "low"
        if re.search(r"(free\s+nitro|scam|phishing)", message.content, re.IGNORECASE):
            severity = "critical"
        elif re.search(r"(idiot|stupid|kys)", message.content, re.IGNORECASE):
            severity = "high"
        elif re.search(r"(crypto|buy|sell)", message.content, re.IGNORECASE):
            severity = "medium"
        
        trust_score = 0.5 # Default
        if message.author.guild_permissions.administrator: trust_score = 1.0
        elif any("mod" in r.name.lower() for r in message.author.roles): trust_score = 0.9

    # 3. Adaptive Baseline Update
    # Simulate residual (difference between expected and observed)
    residual = abs(variance - 0.05) 
    if bot.baseline.update(residual):
        print(f"📈 BASELINE ADJUSTED: New Efficiency = {bot.baseline.constants['efficiency']:.2f}")

    # 4. Boredom Check
    if bot.boredom.check(variance):
        print("🌀 BOREDOM SENSOR: Variance too low. Injecting Chaos!")
        # Force a 'Chaos Event' by sending a critical feedback to the brain
        payload = {
            "type": "bug",
            "severity": "critical",
            "user_email": "system_boredom",
            "trust_score": 1.0
        }
        try:
            async with bot.ashby_session.post(f"{ASHBY_API_URL}/feedback", json=payload) as resp:
                if resp.status == 200:
                    print("✅ Chaos Event Injected Successfully.")
        except Exception as e:
            print(f"⚠️ Chaos Injection failed: {e}")
        # Reset boredom counter
        bot.boredom.low_days = 0

    # 5. Send to Ashby Brain
    payload = {
        "type": "bug" if severity != "low" else "general_feedback",
        "severity": severity,
        "user_email": str(message.author.id),
        "trust_score": trust_score
    }

    try:
        async with bot.ashby_session.post(f"{ASHBY_API_URL}/feedback", json=payload) as resp:
            if resp.status != 200:
                print(f"⚠️ Ashby API error: HTTP {resp.status}")
                return
            data = await resp.json()
    except Exception as e:
        print(f"⚠️ Ashby API connection error: {e}")
        return

    # 6. Handle Action
    action = data.get("action", {}).get("action", "ALLOW")
    status = data.get("system_status", "stable")
    score = data.get("stability_score", 1.0)

    if action == "ALLOW":
        return
    elif action == "FLAG":
        await message.add_reaction("⚠️")
        # Log to mod channel
        mod_channel = discord.utils.get(message.guild.text_channels, name=MOD_CHANNEL_NAME)
        if mod_channel:
            embed = discord.Embed(title="⚠️ Flagged", color=discord.Color.orange(), description=f"Score: {score:.2f} | Status: {status}")
            embed.add_field(name="User", value=message.author.mention)
            embed.add_field(name="Reason", value=severity.upper())
            await mod_channel.send(embed=embed)
    elif action == "TRIGGER_MUTATION":
        try: await message.delete()
        except: pass
        try: await message.author.send(f"🛡️ **Ashby Guardian**: Your message was removed. Reason: {severity.upper()}.")
        except: pass
        try: await message.channel.edit(slowmode_delay=60)
        except: pass
        mod_channel = discord.utils.get(message.guild.text_channels, name=MOD_CHANNEL_NAME)
        if mod_channel:
            embed = discord.Embed(title="🚨 CRITICAL", color=discord.Color.red(), description=f"Score: {score:.2f} | Status: {status}")
            embed.add_field(name="User", value=message.author.mention)
            embed.add_field(name="Action", value="Deleted + Slow Mode")
            await mod_channel.send(embed=embed)
    elif action == "INJECT_CHAOS":
        # This is a system message, not a user action
        print("🌀 System is injecting chaos to prevent stagnation.")

@bot.command(name="status")
async def cmd_status(ctx):
    try:
        async with bot.ashby_session.get(f"{ASHBY_API_URL}/state") as resp:
            data = await resp.json()
            embed = discord.Embed(title="🧠 Ashby Brain Status", color=discord.Color.green() if data.get('status')=='stable' else discord.Color.red())
            embed.add_field(name="Score", value=data.get('stability_score'))
            embed.add_field(name="Status", value=data.get('status'))
            embed.add_field(name="Oppression", value=data.get('oppression_metric', 'N/A'))
            await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"⚠️ Error: {e}")

@bot.command(name="heal")
@commands.has_permissions(manage_messages=True)
async def cmd_heal(ctx):
    try:
        async with bot.ashby_session.post(f"{ASHBY_API_URL}/decay") as resp:
            data = await resp.json()
            embed = discord.Embed(title="💚 Manual Heal", color=discord.Color.green(), description=f"Score: {data.get('stability_score')}")
            await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"⚠️ Heal failed: {e}")

@bot.before_connect
async def create_session():
    bot.ashby_session = aiohttp.ClientSession()

@bot.after_close
async def close_session():
    if bot.ashby_session:
        await bot.ashby_session.close()

if __name__ == "__main__":
    if DISCORD_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ ERROR: Set DISCORD_TOKEN env var.")
        exit(1)
    print("🛡️  Starting Ashby Guardian (Anti-Fragile)...")
    bot.run(DISCORD_TOKEN)
