"""
ASHBY COMMUNITY GUARDIAN — GOLD STANDARD v2.1 (Production Hardened)
Features:
  - Fixed Race Conditions (Async Locks)
  - Fixed Initialization Bug (Callback name)
  - Graceful Startup (No false watchdog alarms)
  - Configurable Bounds via Env Vars
  - Robust Session Management
"""

import os
import re
import time
import json
import gc
import asyncio
import discord
from discord.ext import commands, tasks
import aiohttp
from collections import deque
from dotenv import load_dotenv

# ─── CONFIGURATION (Load from .env) ───────────────────────────────────────────────
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
ASHBY_API_URL = os.getenv("ASHBY_API_URL", "https://your-url.onrender.com")
MOD_CHANNEL_NAME = os.getenv("MOD_CHANNEL_NAME", "mod-log")

# Viability Bounds (Hard Limits) - Can be overridden by Env Vars
MAX_API_FAILURES = int(os.getenv("MAX_API_FAILURES", 3))
WATCHDOG_TIMEOUT_SECONDS = float(os.getenv("WATCHDOG_TIMEOUT_SECONDS", 30.0))
MEMORY_THRESHOLD_PCT = float(os.getenv("MEMORY_THRESHOLD_PCT", 90.0))
CPU_THRESHOLD_PCT = float(os.getenv("CPU_THRESHOLD_PCT", 95.0))
ERROR_RATE_THRESHOLD = float(os.getenv("ERROR_RATE_THRESHOLD", 0.10))

# Safety Cage Parameters
CRITICAL_LIMIT = int(os.getenv("CRITICAL_LIMIT", 2))
RESET_WINDOW_SECONDS = int(os.getenv("RESET_WINDOW_SECONDS", 60))
STARTUP_GRACE_PERIOD = 60  # Seconds to ignore watchdog on boot

# Circuit Breaker Config
CIRCUIT_BREAKER_WINDOW_MINUTES = 5

# ─── MODULE 1: ASYNC WATCHDOG (Fixed) ───────────────────────────────────────

class AsyncWatchdog:
    def __init__(self, timeout, on_trigger_callback):
        self.timeout = timeout
        self.last_pulse = time.time()
        self.is_running = True
        self.callback = on_trigger_callback  # FIXED: Was 'callback', now uses param
        self.task = None
        self.is_ready = False  # Flag to ignore startup spikes

    def start(self):
        self.task = asyncio.create_task(self._monitor_loop())

    def pulse(self):
        self.last_pulse = time.time()

    async def stop(self):
        self.is_running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    async def _monitor_loop(self):
        while self.is_running:
            await asyncio.sleep(5)
            
            # Grace period: Don't alarm if we just started
            if not self.is_ready and time.time() - self.last_pulse < STARTUP_GRACE_PERIOD:
                continue
            
            self.is_ready = True  # Now we start checking
            
            if time.time() - self.last_pulse > self.timeout:
                print(f"[!!!] WATCHDOG: System HANGED (> {self.timeout}s). Triggering Shutdown.")
                try:
                    self.callback()
                except Exception as e:
                    print(f"[!!!] WATCHDOG: Callback failed: {e}")
                break

# ─── MODULE 2: DEAD MAN'S SWITCH (Thread Safe) ───────────────────────────────────────

class DeadManSwitch:
    def __init__(self):
        self.is_active = self._load_state()
        self.violation_count = 0
        self.threshold = CRITICAL_LIMIT
        self.lock = asyncio.Lock()  # For safe async updates
        self.keywords = ["free nitro", "click here", "scam", "phishing", "hack"]
        self._normalize_keywords()

    def _normalize_keywords(self):
        self.norm_keywords = []
        for kw in self.keywords:
            norm = kw.lower().replace(' ', '').replace('3','e').replace('1','i').replace('0','o').replace('@','a').replace('$','s')
            self.norm_keywords.append(norm)

    async def record_violation(self):
        async with self.lock:
            self.violation_count += 1
            if self.violation_count >= self.threshold:
                self._activate()

    async def reset_violations(self):
        async with self.lock:
            self.violation_count = 0

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
                json.dump({'is_active': self.is_active, 'timestamp': time.time()}, f)
        except IOError:
            print("⚠️ Warning: Could not save state file.")

    def _load_state(self):
        try:
            if not os.path.exists("dead_man_state.json"):
                return False
            with open("dead_man_state.json", 'r') as f:
                data = json.load(f)
                return data.get('is_active', False)
        except (json.JSONDecodeError, IOError, Exception):
            print("⚠️ Warning: State file corrupted. Resetting to Online.")
            return False

# ─── MODULE 3: TWO-KEY RESET ───────────────────────────────────────

class AdminResetManager:
    def __init__(self):
        self.votes = set()
        self.start_time = 0
        self.window = RESET_WINDOW_SECONDS
        self.lock = asyncio.Lock()

    async def initiate(self, admin_id):
        async with self.lock:
            now = time.time()
            if now - self.start_time > self.window:
                self.votes = set()
                self.start_time = now
            self.votes.add(admin_id)
            if len(self.votes) >= 2:
                self.votes = set()
                return True
            return False

# ─── THE BOT ────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!ashby ", intents=intents)
bot.ashby_session = None
bot.state_lock = asyncio.Lock() # Global lock for api_failure_count

# Global Instances
dead_man = DeadManSwitch()
reset_mgr = AdminResetManager()
api_failure_count = 0
watchdog = None

def emergency_shutdown():
    dead_man._activate()

@bot.event
async def on_ready():
    global watchdog
    print(f"🛡️  Ashby Guardian v2.1 (Cybernetic) is ONLINE as {bot.user}")
    print(f"🧠  Connected to Ashby Brain: {ASHBY_API_URL}")
    print(f"⚙️  Viability Bounds: API_Failures={MAX_API_FAILURES}, Watchdog={WATCHDOG_TIMEOUT_SECONDS}s")
    
    # Initialize Watchdog with startup grace
    watchdog = AsyncWatchdog(WATCHDOG_TIMEOUT_SECONDS, emergency_shutdown)
    watchdog.start()
    
    if not viability_check_loop.is_running(): viability_check_loop.start()
    if not cleanup_task.is_running(): cleanup_task.start()

# SURVIVAL PATCH 1: Daily Garbage Collection
@tasks.loop(hours=24)
async def cleanup_task():
    gc.collect()
    print("🧹 Daily Cleanup: Memory garbage collected.")

# SURVIVAL PATCH 2: Viability Bound Checker (Thread Safe)
@tasks.loop(seconds=30)
async def viability_check_loop():
    global api_failure_count
    
    try:
        async with bot.ashby_session.get(f"{ASHBY_API_URL}/health", timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                data = await resp.json()
                severity = data.get('overall_severity', 'HEALTHY')
                violated = data.get('violated_bounds', [])
                
                if severity != 'HEALTHY':
                    print(f"⚠️ VIOLATION DETECTED: Severity={severity}, Violated={violated}")
                    if severity in ['CRITICAL', 'FROZEN']:
                        await dead_man.record_violation()
                    elif severity == 'WARNING':
                        print(f"ℹ️ Warning: {violated}")
                else:
                    # Recover gradually
                    async with dead_man.lock:
                        if dead_man.violation_count > 0:
                            dead_man.violation_count -= 1
                    
                watchdog.pulse()
                
            else:
                # Non-200 response
                async with bot.state_lock:
                    api_failure_count += 1
                    count = api_failure_count
                
                if count >= MAX_API_FAILURES:
                    print(f"🚨 CIRCUIT BREAKER TRIPPED: {count} failures.")
                    await dead_man.record_violation()
                else:
                    print(f"⚠️ API returned {resp.status}. Failures: {count}/{MAX_API_FAILURES}")
                    
    except asyncio.TimeoutError:
        print("⚠️ Viability Check: API Timeout")
        async with bot.state_lock:
            api_failure_count += 1
    except Exception as e:
        print(f"⚠️ Viability Check: {e}")
        async with bot.state_lock:
            api_failure_count += 1

# SURVIVAL PATCH 3: API Call Helper (Thread Safe)
async def call_ashby_api(endpoint, payload=None, method="POST"):
    global api_failure_count
    
    try:
        url = f"{ASHBY_API_URL}{endpoint}"
        if method == "GET":
            async with bot.ashby_session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                status = resp.status
                response_data = await resp.json() if status == 200 else None
        else:
            async with bot.ashby_session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                status = resp.status
                response_data = await resp.json() if status == 200 else None

        if status != 200 or response_data is None:
            async with bot.state_lock:
                api_failure_count += 1
                count = api_failure_count
            
            if count >= MAX_API_FAILURES:
                print(f"🚨 CIRCUIT BREAKER: Entering Offline Mode.")
            return None
        
        # Reset count on success
        async with bot.state_lock:
            api_failure_count = 0
        
        return response_data

    except Exception as e:
        async with bot.state_lock:
            api_failure_count += 1
            count = api_failure_count
        
        if count >= MAX_API_FAILURES:
            print(f"🚨 CIRCUIT BREAKER: Connection lost ({count}). Entering Offline Mode.")
        return None

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return
    
    if watchdog:
        watchdog.pulse()

    # SAFETY CAGE LAYER 1
    if dead_man.is_active:
        if dead_man.apply_hard_rules(message.content) == "BLOCK":
            try:
                await message.delete()
                await message.author.send("🚨 **SYSTEM FAILURE**: AI is offline. Strict safety mode active.")
            except Exception:
                pass
            return

    await bot.process_commands(message)

# Commands

@bot.command(name="status")
async def cmd_status(ctx):
    async with bot.state_lock:
        if api_failure_count >= MAX_API_FAILURES:
            await ctx.send("⚠️ System in Offline Mode (Circuit Breaker Active).")
            return
    
    data = await call_ashby_api("/health", method="GET")
    if data:
        severity = data.get('overall_severity', 'UNKNOWN')
        violated = data.get('violated_bounds', [])
        embed_color = discord.Color.green() if severity == 'HEALTHY' else discord.Color.red()
        
        embed = discord.Embed(title="🧠 Viability Status", color=embed_color)
        embed.add_field(name="Overall Severity", value=severity)
        embed.add_field(name="Violated Bounds", value=", ".join(violated) if violated else "None")
        embed.add_field(name="Dead Man Switch", value="Active" if dead_man.is_active else "Inactive")
        
        await ctx.send(embed=embed)
    else:
        await ctx.send("⚠️ Could not fetch status.")

@bot.command(name="heal")
@commands.has_permissions(manage_messages=True)
async def cmd_heal(ctx):
    async with bot.state_lock:
        if api_failure_count >= MAX_API_FAILURES:
            await ctx.send("⚠️ System in Offline Mode.")
            return
    
    data = await call_ashby_api("/decay_cycle")
    if data:
        await ctx.send(f"💚 Manual Heal Triggered. Response: {data.get('status', 'unknown')}")
    else:
        await ctx.send("⚠️ Heal command failed.")

@bot.command(name="reset")
@commands.has_permissions(administrator=True)
async def cmd_reset(ctx):
    if dead_man.is_active:
        success = await reset_mgr.initiate(ctx.author.id)
        if success:
            dead_man.is_active = False
            await dead_man.reset_violations()
            dead_man._save_state()
            async with bot.state_lock:
                api_failure_count = 0
            await ctx.send("✅ **TWO-KEY RESET SUCCESSFUL**: System Re-initialized.")
        else:
            await ctx.send(f"⏳ **RESET INITIATED (1/2)**: Waiting for 2nd admin within {RESET_WINDOW_SECONDS}s.")
    else:
        await ctx.send("System is already online.")

@bot.event
async def on_close():
    """Cleanup on shutdown."""
    if watchdog:
        await watchdog.stop()
    if bot.ashby_session and not bot.ashby_session.closed:
        await bot.ashby_session.close()
    gc.collect()

async def setup_hook():
    bot.ashby_session = aiohttp.ClientSession()
    print("🔌 HTTP Session established.")

bot.setup_hook = setup_hook

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ ERROR: DISCORD_TOKEN missing in .env")
        exit(1)
    
    try:
        print("🛡️  Starting Ashby Guardian v2.1 (Production Hardened)...")
        bot.run(DISCORD_TOKEN)
    except discord.errors.LoginFailure:
        print("\n🚨 CRITICAL: Login Failed! Token invalid/expired.")
        print("➡️  ACTION: Go to Discord Developer Portal -> Reset Token -> Update .env")
        exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected Error: {e}")
        print("➡️  ACTION: Check logs and restart.")
        exit(1)
