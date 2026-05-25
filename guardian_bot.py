"""
ASHBY COMMUNITY GUARDIAN — Discord Bot v1.0
Wraps the Ashby-Vira Brain API to provide intelligent community moderation.

Requirements:
  pip install discord.py aiohttp

Usage:
  1. Set DISCORD_TOKEN and ASHBY_API_URL environment variables
  2. python guardian_bot.py
"""

import os
import re
import time
import discord
from discord.ext import commands, tasks
import aiohttp

# ─── Configuration ───────────────────────────────────────────────

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "YOUR_BOT_TOKEN_HERE")
ASHBY_API_URL = os.getenv("ASHBY_API_URL", "https://ashby-brain.onrender.com")
MOD_CHANNEL_NAME = os.getenv("MOD_CHANNEL_NAME", "mod-log")
DECAY_INTERVAL_SECONDS = 60
MIN_TRUST_SCORE = 0.3
DEFAULT_TRUST_SCORE = 0.5
MODERATOR_TRUST = 0.9
ADMIN_TRUST = 1.0

# ─── Severity Patterns ──────────────────────────────────────────

SEVERITY_RULES = [
    {
        "patterns": [
            r"(?i)(free\s+nitro|discord\s+gift|steam\s+giveaway)",
            r"(?i)(click\s+here\s+for\s+free|claim\s+your\s+reward)",
            r"(?i)\b(bit\.ly|tinyurl|grabify)\b.*\b(free|gift|reward)\b",
        ],
        "severity": "critical",
        "type": "bug",
        "label": "🚨 Scam/Phishing"
    },
    {
        "patterns": [
            r"(?i)\b(kys|kill\s+yourself)\b",
            r"(?i)\b(idiot|moron|stupid)\b.*\b(you\b|you're)\b",
        ],
        "severity": "high",
        "type": "bug",
        "label": "🔴 Toxicity"
    },
    {
        "patterns": [
            r"(.{10,})\1{3,}",
            r"(?i)buy\s+(crypto|coin|token|nft)",
            r"@everyone\s+.*\b(http|https|www)\b",
        ],
        "severity": "medium",
        "type": "bug",
        "label": "🟡 Spam"
    },
    {
        "patterns": [],
        "severity": "low",
        "type": "general_feedback",
        "label": "⚪ Noise"
    },
]

# ─── Trust Score Calculator ─────────────────────────────────────

def calculate_trust_score(member: discord.Member) -> float:
    if member.guild_permissions.administrator:
        return ADMIN_TRUST
    mod_role_names = ["moderator", "admin", "mod", "staff", "helper"]
    for role in member.roles:
        if any(name in role.name.lower() for name in mod_role_names):
            return MODERATOR_TRUST
    account_age_days = (time.time() - member.created_at.timestamp()) / 86400
    if account_age_days > 365:
        return 0.8
    elif account_age_days > 30:
        return DEFAULT_TRUST_SCORE
    else:
        return MIN_TRUST_SCORE

# ─── Severity Evaluator ─────────────────────────────────────────

def evaluate_message(content: str) -> dict:
    for rule in SEVERITY_RULES:
        for pattern in rule["patterns"]:
            if re.search(pattern, content):
                return {
                    "severity": rule["severity"],
                    "type": rule["type"],
                    "label": rule["label"],
                    "matched_pattern": pattern
                }
    return {
        "severity": "low",
        "type": "general_feedback",
        "label": "✅ Safe",
        "matched_pattern": None
    }

# ─── The Bot ────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!ashby ", intents=intents)
bot.ashby_session = None

@bot.event
async def on_ready():
    print(f"🛡️  Ashby Community Guardian is ONLINE as {bot.user}")
    print(f"🧠  Connected to Ashby Brain: {ASHBY_API_URL}")
    print(f"📡 Monitoring {len(bot.guilds)} server(s)")
    if not decay_loop.is_running():
        decay_loop.start()

@tasks.loop(seconds=DECAY_INTERVAL_SECONDS)
async def decay_loop():
    try:
        async with bot.ashby_session.post(f"{ASHBY_API_URL}/decay") as resp:
            if resp.status == 200:
                data = await resp.json()
                score = data.get("stability_score", "?")
                status = data.get("system_status", "?")
                print(f"🔄 Auto-Heal: Score={score}, Status={status}")
            else:
                print(f"⚠️ Auto-Heal failed: HTTP {resp.status}")
    except Exception as e:
        print(f"⚠️ Auto-Heal error: {e}")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return
    await bot.process_commands(message)

    evaluation = evaluate_message(message.content)
    if evaluation["severity"] == "low" and evaluation["matched_pattern"] is None:
        return

    trust_score = calculate_trust_score(message.author)

    payload = {
        "type": evaluation["type"],
        "severity": evaluation["severity"],
        "user_email": str(message.author.id),
        "trust_score": trust_score
    }

    try:
        async with bot.ashby_session.post(
            f"{ASHBY_API_URL}/feedback",
            json=payload
        ) as resp:
            if resp.status != 200:
                print(f"⚠️ Ashby API error: HTTP {resp.status}")
                return
            data = await resp.json()
    except Exception as e:
        print(f"⚠️ Ashby API connection error: {e}")
        return

    action_data = data.get("action", {})
    action = action_data.get("action", "ALLOW")
    stability_score = data.get("stability_score", 1.0)
    system_status = data.get("system_status", "stable")

    await handle_action(
        message=message,
        action=action,
        evaluation=evaluation,
        stability_score=stability_score,
        system_status=system_status,
        trust_score=trust_score
    )

async def handle_action(message, action, evaluation, stability_score, system_status, trust_score):
    mod_channel = discord.utils.get(message.guild.text_channels, name=MOD_CHANNEL_NAME)

    if action == "ALLOW":
        return

    elif action == "FLAG":
        if mod_channel:
            embed = discord.Embed(
                title="⚠️ Flagged Message",
                color=discord.Color.orange(),
                description=f"**System Status:** {system_status.upper()} (Score: {stability_score:.2f})"
            )
            embed.add_field(name="User", value=message.author.mention, inline=True)
            embed.add_field(name="Trust", value=f"{trust_score:.1f}", inline=True)
            embed.add_field(name="Detection", value=evaluation["label"], inline=True)
            embed.add_field(name="Content", value=message.content[:200] or "*empty*", inline=False)
            embed.add_field(name="Jump", value=f"[View Message]({message.jump_url})", inline=False)
            await mod_channel.send(embed=embed)
        try:
            await message.add_reaction("⚠️")
        except:
            pass

    elif action == "TRIGGER_MUTATION":
        try:
            await message.delete()
            deleted = True
        except:
            deleted = False
        try:
            await message.author.send(
                f"🛡️ **Ashby Guardian**: Your message was removed because it matched "
                f"a **{evaluation['label']}** pattern. The community health score is "
                f"currently **{stability_score:.2f}** ({system_status}). "
                f"Please follow the community guidelines."
            )
        except:
            pass
        try:
            await message.channel.edit(slowmode_delay=60)
        except:
            pass
        if mod_channel:
            embed = discord.Embed(
                title="🚨 CRITICAL — Mutation Triggered",
                color=discord.Color.red(),
                description=f"**Stability Score:** {stability_score:.2f} — **{system_status.upper()}**"
            )
            embed.add_field(name="User", value=message.author.mention, inline=True)
            embed.add_field(name="Trust", value=f"{trust_score:.1f}", inline=True)
            embed.add_field(name="Detection", value=evaluation["label"], inline=True)
            embed.add_field(name="Message Deleted", value="✅ Yes" if deleted else "❌ No", inline=True)
            embed.add_field(name="Slow Mode", value="Enabled (60s)", inline=True)
            embed.add_field(name="Content", value=message.content[:200] or "*empty*", inline=False)
            await mod_channel.send(embed=embed)

    elif action == "ALERT_HUMAN":
        if mod_channel:
            embed = discord.Embed(
                title="🧊 FROZEN — Human Intervention Required",
                color=discord.Color.dark_red(),
                description=(
                    f"The Ashby Brain is **FROZEN** (Score: {stability_score:.2f}). "
                    f"A mutation was blocked by the Vira Validator. "
                    f"Manual review is required before the system can recover."
                )
            )
            embed.add_field(name="Action Needed", value="Use `!ashby heal` to manually recover the system.", inline=False)
            await mod_channel.send(embed=embed)

# ─── Admin Commands ─────────────────────────────────────────────

@bot.command(name="status")
async def cmd_status(ctx):
    try:
        async with bot.ashby_session.get(f"{ASHBY_API_URL}/state") as resp:
            data = await resp.json()
            score = data.get("stability_score", "?")
            status = data.get("status", "?")
            cycles = data.get("cycles_to_stable", "?")
            noise = data.get("noise_ignored", "?")
            embed = discord.Embed(
                title="🧠 Ashby Brain Status",
                color=discord.Color.green() if status == "stable" else
                      discord.Color.orange() if status == "warning" else
                      discord.Color.red(),
                description=f"**{status.upper()}** — Score: {score}"
            )
            embed.add_field(name="Cycles to Stable", value=cycles, inline=True)
            embed.add_field(name="Noise Ignored", value=noise, inline=True)
            await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"⚠️ Error connecting to Ashby Brain: {e}")

@bot.command(name="heal")
@commands.has_permissions(manage_messages=True)
async def cmd_heal(ctx):
    try:
        async with bot.ashby_session.post(f"{ASHBY_API_URL}/decay") as resp:
            data = await resp.json()
            score = data.get("stability_score", "?")
            status = data.get("system_status", "?")
            embed = discord.Embed(
                title="💚 Manual Heal Applied",
                color=discord.Color.green(),
                description=f"Score: {score} — Status: {status.upper()}"
            )
            await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"⚠️ Heal failed: {e}")

@bot.command(name="reset")
@commands.has_permissions(administrator=True)
async def cmd_reset(ctx):
    try:
        for _ in range(10):
            async with bot.ashby_session.post(f"{ASHBY_API_URL}/decay") as resp:
                data = await resp.json()
        score = data.get("stability_score", "?")
        status = data.get("system_status", "?")
        embed = discord.Embed(
            title="🔄 System Reset Complete",
            color=discord.Color.green(),
            description=f"Score: {score} — Status: {status.upper()}"
        )
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"⚠️ Reset failed: {e}")

@bot.command(name="trust")
async def cmd_trust(ctx, member: discord.Member = None):
    target = member or ctx.author
    trust = calculate_trust_score(target)
    await ctx.send(f"🔐 Trust score for {target.mention}: **{trust:.1f}**")

# ─── Startup ────────────────────────────────────────────────────

@bot.before_connect
async def create_session():
    bot.ashby_session = aiohttp.ClientSession()

@bot.after_close
async def close_session():
    if bot.ashby_session:
        await bot.ashby_session.close()

if __name__ == "__main__":
    if DISCORD_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ ERROR: Set your DISCORD_TOKEN environment variable.")
        print("   export DISCORD_TOKEN=your_token_here")
        exit(1)
    print("🛡️  Starting Ashby Community Guardian...")
    print(f"🧠  Ashby Brain: {ASHBY_API_URL}")
    print(f"📋  Mod Channel: #{MOD_CHANNEL_NAME}")
    print(f"🔄  Auto-Heal: Every {DECAY_INTERVAL_SECONDS}s")
    print("─" * 40)
    bot.run(DISCORD_TOKEN)
