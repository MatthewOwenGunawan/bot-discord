import discord
from discord.ext import commands, tasks 
from discord import app_commands 
from discord.ui import Button, View
import random
import yt_dlp
import asyncio
import os
import psycopg2
from datetime import datetime, timedelta

intents = discord.Intents.default()
intents.voice_states = True 
bot = commands.Bot(command_prefix='!', intents=intents)

ytdl_format_options = {'format': 'bestaudio/best', 'noplaylist': 'True'}
ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}
ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

LOTTERY_TICKET_PRICE = 1000
BASE_JACKPOT = 60000 
lottery_players = []
lottery_channels = set()

DATABASE_URL = os.environ.get('DATABASE_URL')
conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True 
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS warga (
                user_id BIGINT PRIMARY KEY,
                credits BIGINT DEFAULT 0,
                last_hourly TIMESTAMP,
                last_weekly TIMESTAMP
            )''')

c.execute('ALTER TABLE warga ADD COLUMN IF NOT EXISTS last_daily TIMESTAMP')
c.execute('ALTER TABLE warga ADD COLUMN IF NOT EXISTS last_work TIMESTAMP')
c.execute('ALTER TABLE warga ADD COLUMN IF NOT EXISTS last_beg TIMESTAMP')
c.execute('ALTER TABLE warga ADD COLUMN IF NOT EXISTS last_steal TIMESTAMP')

def get_user(user_id):
    c.execute("SELECT credits, last_hourly, last_weekly, last_daily, last_work, last_beg, last_steal FROM warga WHERE user_id = %s", (user_id,))
    result = c.fetchone()
    if result is None:
        c.execute("INSERT INTO warga (user_id, credits) VALUES (%s, 0)", (user_id,))
        return (0, None, None, None, None, None, None)
    return result

def update_credits(user_id, amount):
    c.execute("UPDATE warga SET credits = credits + %s WHERE user_id = %s", (amount, user_id))
    
def update_cooldown(user_id, column):
    now = datetime.now()
    c.execute(f"UPDATE warga SET {column} = %s WHERE user_id = %s", (now, user_id))

def check_cooldown(last_time, delta):
    if not last_time: return True, None
    if isinstance(last_time, str): 
        last_time = datetime.fromisoformat(last_time)
    now = datetime.now()
    if now >= last_time + delta:
        return True, None
    return False, (last_time + delta) - now

def get_rank(credits):
    if credits < 10000: return "🧳 Immigrant"
    elif credits < 35000: return "🏙️ Citizen"
    elif credits < 100000: return "🪖 Private"
    elif credits < 250000: return "🎖️ Lance Corporal"
    elif credits < 500000: return "🏅 Corporal"
    elif credits < 1000000: return "🥉 Sergeant"
    elif credits < 2000000: return "🥈 Sergeant First Class"
    elif credits < 3500000: return "🥇 Sergeant Major"
    elif credits < 5000000: return "🔰 Second Lieutenant"
    elif credits < 7500000: return "🛡️ Lieutenant"
    elif credits < 10000000: return "⚔️ Captain"
    elif credits < 15000000: return "🦅 Major"
    elif credits < 20000000: return "🦁 Lieutenant Colonel"
    elif credits < 27500000: return "🐅 Colonel"
    elif credits < 35000000: return "⭐ Brigadier General"
    elif credits < 45000000: return "⭐⭐ Major General"
    elif credits < 60000000: return "⭐⭐⭐ Lieutenant General"
    elif credits < 80000000: return "⭐⭐⭐⭐ General"
    elif credits < 100000000: return "✨ Grand General"
    elif credits < 150000000: return "👑 Supreme Leader"
    else: return "🔱 Emperor 👑"

def check_rank_change(old_credits, new_credits):
    old_rank = get_rank(old_credits)
    new_rank = get_rank(new_credits)
    if old_rank != new_rank:
        if new_credits > old_credits:
            return f"\n🎖️ **PROMOTION!** Your rank has increased to **{new_rank}**!"
        else:
            return f"\n🚨 **DEMOTION!** Your rank has decreased to **{new_rank}**!"
    return ""

@bot.event
async def on_ready():
    if not lottery_draw.is_running():
        lottery_draw.start()
    try:
        synced = await bot.tree.sync()
        print(f'Bot {bot.user} is now online!')
        print(f'Successfully synced {len(synced)} slash commands.')
    except Exception as e:
        print(f'Failed to sync commands: {e}')

@tasks.loop(hours=1)
async def lottery_draw():
    global lottery_players, lottery_channels
    if not lottery_players: return 
    
    winner_id = random.choice(lottery_players)
    total_tickets = len(lottery_players)
    prize_pool = BASE_JACKPOT + (total_tickets * LOTTERY_TICKET_PRICE)
    
    user_data = get_user(winner_id)
    old_credits = user_data[0]
    update_credits(winner_id, prize_pool)
    notification = check_rank_change(old_credits, old_credits + prize_pool)
    
    for ch_id in lottery_channels:
        try:
            channel = bot.get_channel(ch_id)
            if channel:
                embed = discord.Embed(title="🎟️ LOTTERY DRAW RESULTS! 🎟️", color=discord.Color.gold())
                embed.description = (
                    f"The 1-hour wait is over! The State has drawn the lucky ticket.\n\n"
                    f"👑 **Grand Winner:** <@{winner_id}>\n"
                    f"💰 **Jackpot Won:** **{prize_pool:,} SC**\n"
                    f"🎟️ **Total Tickets Sold:** {total_tickets} tickets\n"
                    f"{notification}"
                )
                embed.set_footer(text=f"The jackpot has reset to {BASE_JACKPOT:,} SC. Buy a new ticket with /lotre!")
                await channel.send(embed=embed)
        except Exception: pass
            
    lottery_players.clear()
    lottery_channels.clear()

@bot.tree.command(name='profileinfo', description='Check User Profile')
async def profileinfo(interaction: discord.Interaction, member: discord.Member = None):
    target_user = member or interaction.user
    user_id = target_user.id
    user_data = get_user(user_id)
    credits = user_data[0]
    rank = get_rank(credits)

    embed = discord.Embed(title="🪪 USER ID CARD", color=discord.Color.dark_red())
    embed.set_thumbnail(url=target_user.display_avatar.url)
    embed.add_field(name="Username", value=f"**{target_user.display_name}**", inline=False)
    embed.add_field(name="Social Credit", value=f"🪙 **{credits:,} SC**", inline=False)
    embed.add_field(name="Server Rank", value=f"**{rank}**", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='wanted', description='Create a Bounty Wanted Poster of yourself!')
async def wanted(interaction: discord.Interaction, member: discord.Member = None):
    target_user = member or interaction.user
    user_data = get_user(target_user.id)
    credits = user_data[0]
    rank = get_rank(credits)

    embed = discord.Embed(title="☠️ WANTED DEAD OR ALIVE ☠️", color=discord.Color.dark_orange())
    embed.set_image(url=target_user.display_avatar.url)
    embed.description = f"### **{target_user.display_name.upper()}**\n\n**Threat Level:** {rank}\n**Bounty Reward:** 🪙 **{credits:,} SC**\n\n*Approach with extreme caution.*"
    embed.set_footer(text="Property of the Government")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='rankinfo', description='See Social Credit requirements for each position')
async def rankinfo(interaction: discord.Interaction):
    embed = discord.Embed(title="🎖️ Server rank requirements", color=discord.Color.gold())
    rank_list = (
        "**0 - 9,999 SC** : 🧳 Immigrant\n"
        "**10,000 - 34,999 SC** : 🏙️ Citizen\n"
        "**35,000 - 99,999 SC** : 🪖 Private\n"
        "**100,000 - 249,999 SC** : 🎖️ Lance Corporal\n"
        "**250,000 - 499,999 SC** : 🏅 Corporal\n"
        "**500,000 - 999,999 SC** : 🥉 Sergeant\n"
        "**1,000,000 - 1,999,999 SC** : 🥈 Sergeant First Class\n"
        "**2,000,000 - 3,499,999 SC** : 🥇 Sergeant Major\n"
        "**3,500,000 - 4,999,999 SC** : 🔰 Second Lieutenant\n"
        "**5,000,000 - 7,499,999 SC** : 🛡️ Lieutenant\n"
        "**7,500,000 - 9,999,999 SC** : ⚔️ Captain\n"
        "**10,000,000 - 14,999,999 SC** : 🦅 Major\n"
        "**15,000,000 - 19,999,999 SC** : 🦁 Lieutenant Colonel\n"
        "**20,000,000 - 27,499,999 SC** : 🐅 Colonel\n"
        "**27,500,000 - 34,999,999 SC** : ⭐ Brigadier General\n"
        "**35,000,000 - 44,999,999 SC** : ⭐⭐ Major General\n"
        "**45,000,000 - 59,999,999 SC** : ⭐⭐⭐ Lieutenant General\n"
        "**60,000,000 - 79,999,999 SC** : ⭐⭐⭐⭐ General\n"
        "**80,000,000 - 99,999,999 SC** : ✨ Grand General\n"
        "**100,000,000 - 149,999,999 SC** : 👑 Supreme Leader\n"
        "**150,000,000+ SC** : 🔱 Emperor 👑"
    )
    embed.description = rank_list
    embed.set_footer(text="Collect SCs via /work, /daily, or play in Casino!")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='leaderboard', description='View the Top 10 citizens with the highest Social Credit')
async def leaderboard(interaction: discord.Interaction):
    await interaction.response.defer()
    c.execute("SELECT user_id, MAX(credits) FROM warga GROUP BY user_id ORDER BY MAX(credits) DESC LIMIT 10")
    top_users = c.fetchall()
    
    if not top_users:
        return await interaction.followup.send("No citizen data found in the government database yet.")
        
    embed = discord.Embed(title="🏆 Social Credit Leaderboard 🏆", description="**Top 10 Most Influential Citizens:**\n\n", color=discord.Color.gold())
    board_text = ""
    for index, (user_id, credits) in enumerate(top_users, start=1):
        try:
            user = interaction.guild.get_member(user_id) or await bot.fetch_user(user_id)
            username = user.display_name
        except Exception:
            username = f"Unknown Citizen ({user_id})"
            
        rank = get_rank(credits)
        if index == 1: medal = "🥇"
        elif index == 2: medal = "🥈"
        elif index == 3: medal = "🥉"
        else: medal = f"**{index}.**"
            
        board_text += f"{medal} **{username}**\n├ Rank: {rank}\n└ 🪙 **{credits:,} SC**\n\n"
        
    embed.description += board_text
    embed.set_footer(text="Keep working and playing in the casino to increase your Social Credit!")
    await interaction.followup.send(embed=embed)

@bot.tree.command(name='give', description='Give Social Credit to another citizen')
async def give(interaction: discord.Interaction, member: discord.Member, amount: int):
    if amount <= 0: return await interaction.response.send_message("Invalid amount!", ephemeral=True)
    if member.id == interaction.user.id: return await interaction.response.send_message("You can't give money to yourself!", ephemeral=True)
    
    user_data = get_user(interaction.user.id)
    if user_data[0] < amount: return await interaction.response.send_message("You don't have enough Social Credit!", ephemeral=True)
    
    get_user(member.id) 
    update_credits(interaction.user.id, -amount)
    update_credits(member.id, amount)
    
    await interaction.response.send_message(f"💸 **SUCCESS!** You transferred **{amount:,} SC** to {member.mention}.")

@bot.tree.command(name='steal', description='Steal Social Credit from another citizen (Cooldown: 15m)')
async def steal(interaction: discord.Interaction, member: discord.Member):
    if member.id == interaction.user.id: return await interaction.response.send_message("You can't steal from yourself!", ephemeral=True)
    if member.bot: return await interaction.response.send_message("You can't steal from a bot!", ephemeral=True)
    
    user_id = interaction.user.id
    user_data = get_user(user_id)
    last_steal = user_data[6] 
    
    ready, remaining = check_cooldown(last_steal, timedelta(minutes=15))
    if not ready:
        mins, secs = int(remaining.total_seconds() // 60), int(remaining.total_seconds() % 60)
        return await interaction.response.send_message(f"⏳ Cops are patrolling! Wait **{mins}m {secs}s** before stealing again.", ephemeral=True)

    target_data = get_user(member.id)
    if target_data[0] < 500:
        return await interaction.response.send_message(f"Target is too poor (Under 500 SC). Have some mercy!", ephemeral=True)

    update_cooldown(user_id, 'last_steal')
    
    if random.random() < 0.40:
        percentage = random.uniform(0.01, 0.05) 
        stolen = int(target_data[0] * percentage)
        if stolen > 50000: stolen = 50000 
        
        update_credits(member.id, -stolen)
        update_credits(user_id, stolen)
        await interaction.response.send_message(f"🥷 **HEIST SUCCESSFUL!** You successfully stole **{stolen:,} SC** from {member.mention}'s wallet!")
    else:
        fine = 1000
        if user_data[0] < fine: fine = user_data[0] 
        update_credits(user_id, -fine)
        await interaction.response.send_message(f"🚨 **CAUGHT BY THE POLICE!** You failed to steal from {member.mention} and paid a fine of **{fine:,} SC**.")

@bot.tree.command(name='beg', description='Beg for some spare change (Cooldown: 15s)')
async def beg(interaction: discord.Interaction):
    user_id = interaction.user.id
    user_data = get_user(user_id)
    old_credits, last_beg = user_data[0], user_data[5]
    
    ready, remaining = check_cooldown(last_beg, timedelta(seconds=15))
    if not ready:
        return await interaction.response.send_message(f"⏳ Please wait **{int(remaining.total_seconds())} seconds** before begging again.", ephemeral=True)

    reward = random.randint(500, 750) 
    update_credits(user_id, reward)
    update_cooldown(user_id, 'last_beg')
    
    notification = check_rank_change(old_credits, old_credits + reward)
    await interaction.response.send_message(f"🥺 Someone felt pity and gave you **{reward:,} SC**!{notification}")

@bot.tree.command(name='work', description='Work to earn Social Credit (Cooldown: 60s)')
async def work(interaction: discord.Interaction):
    user_id = interaction.user.id
    user_data = get_user(user_id)
    old_credits, last_work = user_data[0], user_data[4]
    
    ready, remaining = check_cooldown(last_work, timedelta(seconds=60))
    if not ready:
        return await interaction.response.send_message(f"⏳ You are exhausted. Rest for **{int(remaining.total_seconds())} seconds**.", ephemeral=True)

    reward = random.randint(1500, 3000) 
    update_credits(user_id, reward)
    update_cooldown(user_id, 'last_work')
    
    notification = check_rank_change(old_credits, old_credits + reward)
    await interaction.response.send_message(f"🛠️ You worked hard and earned **{reward:,} SC**!{notification}")

@bot.tree.command(name='hourly', description='Claim your hourly allowance (Cooldown: 1h)')
async def hourly(interaction: discord.Interaction):
    user_id = interaction.user.id
    user_data = get_user(user_id)
    old_credits, last_hourly = user_data[0], user_data[1]
    
    ready, remaining = check_cooldown(last_hourly, timedelta(hours=1))
    if not ready:
        minutes = int(remaining.total_seconds() // 60)
        return await interaction.response.send_message(f"⏳ Please wait **{minutes} minutes** for your next hourly claim.", ephemeral=True)

    reward = random.randint(5000, 7500) 
    update_credits(user_id, reward)
    update_cooldown(user_id, 'last_hourly')
    
    notification = check_rank_change(old_credits, old_credits + reward)
    await interaction.response.send_message(f"⏱️ Hourly allowance claimed! You received **{reward:,} SC**.{notification}")

@bot.tree.command(name='daily', description='Claim your daily allowance (Cooldown: 24h)')
async def daily(interaction: discord.Interaction):
    user_id = interaction.user.id
    user_data = get_user(user_id)
    old_credits, last_daily = user_data[0], user_data[3]
    
    ready, remaining = check_cooldown(last_daily, timedelta(hours=24))
    if not ready:
        hours, mins = int(remaining.total_seconds() // 3600), int((remaining.total_seconds() % 3600) // 60)
        return await interaction.response.send_message(f"⏳ Daily claim available in **{hours}h {mins}m**.", ephemeral=True)

    reward = random.randint(30000, 50000) 
    update_credits(user_id, reward)
    update_cooldown(user_id, 'last_daily')
    
    notification = check_rank_change(old_credits, old_credits + reward)
    await interaction.response.send_message(f"☀️ Daily allowance claimed! You received a hefty **{reward:,} SC**.{notification}")

@bot.tree.command(name='weekly', description='Claim your weekly salary (Cooldown: 7d)')
async def weekly(interaction: discord.Interaction):
    user_id = interaction.user.id
    user_data = get_user(user_id)
    old_credits, last_weekly = user_data[0], user_data[2]
    
    ready, remaining = check_cooldown(last_weekly, timedelta(days=7))
    if not ready:
        hours = int((remaining.total_seconds() % 86400) // 3600)
        return await interaction.response.send_message(f"⏳ Weekly salary available in **{remaining.days} days, {hours} hours**.", ephemeral=True)

    reward = random.randint(450000, 650000) 
    update_credits(user_id, reward)
    update_cooldown(user_id, 'last_weekly')
    
    notification = check_rank_change(old_credits, old_credits + reward)
    await interaction.response.send_message(f"📅 Your MASSIVE weekly salary of **{reward:,} SC** has been transferred!{notification}")


@bot.tree.command(name='lotre', description=f'Buy lottery tickets ({LOTTERY_TICKET_PRICE:,} SC/ticket). Win the GRAND JACKPOT!')
async def lotre(interaction: discord.Interaction, amount: int = 1):
    if amount <= 0:
        return await interaction.response.send_message("You must buy at least 1 ticket!", ephemeral=True)
        
    user_id = interaction.user.id
    user_data = get_user(user_id)
    old_credits = user_data[0]
    total_cost = amount * LOTTERY_TICKET_PRICE
    
    if old_credits < total_cost:
        return await interaction.response.send_message(f"You don't have enough balance! You need **{total_cost:,} SC** to buy {amount} tickets.", ephemeral=True)
        
    update_credits(user_id, -total_cost)
    
    global lottery_players, lottery_channels
    lottery_players.extend([user_id] * amount)
    lottery_channels.add(interaction.channel.id) 
    
    current_pool = BASE_JACKPOT + (len(lottery_players) * LOTTERY_TICKET_PRICE)
    user_ticket_count = lottery_players.count(user_id)
    total_sold = len(lottery_players)
    win_chance = (user_ticket_count / total_sold) * 100
    
    embed = discord.Embed(title="🎟️ TICKET PURCHASED!", color=discord.Color.green())
    embed.description = (
        f"You successfully bought **{amount:,}** lottery tickets for **{total_cost:,} SC**!\n\n"
        f"💸 **Current Prize Pool:** **{current_pool:,} SC**\n"
        f"📈 **Your Win Chance:** {win_chance:.1f}% ({user_ticket_count} of {total_sold} tickets)\n\n"
        f"⏱️ *The winner will be drawn automatically every hour.*"
    )
    
    notification = check_rank_change(old_credits, old_credits - total_cost)
    if notification: 
        embed.set_footer(text=notification.replace("\n", "").replace("*", ""))
        
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name='plinko', description='Play Plinko! Drop a ball and win up to 10x your bet!')
async def plinko(interaction: discord.Interaction, bet: int):
    user_id = interaction.user.id
    user_data = get_user(user_id)
    old_credits = user_data[0]
    
    if bet <= 0 or old_credits < bet:
        return await interaction.response.send_message("Invalid bet / Not enough balance!", ephemeral=True)
        
    update_credits(user_id, -bet)
    
    embed = discord.Embed(title="🔵 PLINKO 🔵", color=discord.Color.blue())
    embed.description = f"Dropping ball for **{bet:,} SC**...\n\n| . . . . . 🔴 . . . . . |"
    await interaction.response.send_message(embed=embed)
    
    for _ in range(2):
        await asyncio.sleep(0.5)
        spaces = " . " * random.randint(1, 8)
        embed.description = f"Dropping ball for **{bet:,} SC**...\n\n|{spaces}🔴{spaces}|"
        await interaction.edit_original_response(embed=embed)
        
    await asyncio.sleep(0.5)
    
    multipliers = [0.2, 0.5, 1.0, 1.5, 2.0, 5.0, 10.0]
    weights = [35, 25, 15, 10, 8, 5, 2] 
    mult = random.choices(multipliers, weights=weights)[0]
    
    win = int(bet * mult)
    update_credits(user_id, win)
    
    if mult >= 2.0:
        color, msg = discord.Color.green(), f"🎉 **AMAZING!** You hit a huge multiplier!"
    elif mult >= 1.0:
        color, msg = discord.Color.gold(), f"👌 **NOT BAD!** You made a safe drop."
    else:
        color, msg = discord.Color.red(), f"📉 **OUCH!** The ball fell in a bad spot."
        
    embed.color = color
    notification = check_rank_change(old_credits, old_credits - bet + win)
    embed.description = f"{msg}\n\n[ **{mult}x** ]\n\n💸 Payout: **{win:,} SC**"
    if notification: embed.set_footer(text=notification.replace("\n", "").replace("*", ""))
    await interaction.edit_original_response(embed=embed)


class HorseRaceJoinView(View):
    def __init__(self, host_id, bet):
        super().__init__(timeout=30) 
        self.players = [host_id]
        self.bet = bet

    @discord.ui.button(label="Join Race", style=discord.ButtonStyle.primary, emoji="🏇")
    async def join_btn(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id in self.players:
            return await interaction.response.send_message("You are already in the race!", ephemeral=True)
        if len(self.players) >= 3: 
            return await interaction.response.send_message("The race is already full (Max 3)! ", ephemeral=True)
            
        user_data = get_user(interaction.user.id)
        if user_data[0] < self.bet:
            return await interaction.response.send_message("You don't have enough SC to match the bet!", ephemeral=True)
            
        self.players.append(interaction.user.id)
        update_credits(interaction.user.id, -self.bet) 
        
        await interaction.response.send_message(f"You joined the race! (-{self.bet:,} SC)", ephemeral=True)
        
        embed = interaction.message.embeds[0]
        mentions = "\n".join([f"- <@{p}>" for p in self.players])
        embed.description = f"**Bet:** {self.bet:,} SC\n**Players:** {len(self.players)}/3\n\n{mentions}\n\n*Waiting 30 seconds for others to join...*"
        await interaction.message.edit(embed=embed, view=self)
        
        if len(self.players) >= 3:
            self.stop() 

@bot.tree.command(name='horserace', description='Start a multiplayer Horse Race! (Max 3 players)')
async def horserace(interaction: discord.Interaction, bet: int):
    user_id = interaction.user.id
    user_data = get_user(user_id)
    
    if bet <= 0 or user_data[0] < bet:
        return await interaction.response.send_message("Invalid bet / Not enough balance!", ephemeral=True)
        
    update_credits(user_id, -bet) 
    
    view = HorseRaceJoinView(user_id, bet)
    embed = discord.Embed(title="🏁 MULTIPLAYER HORSE RACE 🏁", color=discord.Color.green())
    embed.description = f"**Bet:** {bet:,} SC\n**Players:** 1/3\n\n- <@{user_id}>\n\n*Waiting 30 seconds for others to join...*"
    await interaction.response.send_message(embed=embed, view=view)
    
    await view.wait() 
    
    if len(view.players) < 2:
        update_credits(user_id, bet)
        embed.description = "Race cancelled! You need at least 2 players to race. Your bet has been refunded."
        embed.color = discord.Color.red()
        return await interaction.edit_original_response(embed=embed, view=None)
        
    track_length = 20
    positions = {p: 0 for p in view.players}
    horses = ["🐎", "🏇", "🦄"]
    
    embed.title = "🏁 THE RACE HAS STARTED! 🏁"
    embed.color = discord.Color.orange()
    await interaction.edit_original_response(embed=embed, view=None)
    
    winner = None
    while not winner:
        await asyncio.sleep(1.5) 
        desc = ""
        for i, p in enumerate(view.players):
            positions[p] += random.randint(1, 4) 
            if positions[p] >= track_length:
                positions[p] = track_length
                if not winner: winner = p 
                
            track = "・" * positions[p] + horses[i] + "・" * (track_length - positions[p])
            desc += f"<@{p}>\n|{track}|\n\n"
            
        embed.description = desc
        await interaction.edit_original_response(embed=embed)
        
    prize = bet * len(view.players)
    update_credits(winner, prize)
    
    win_embed = discord.Embed(title="🏆 RACE OVER! 🏆", color=discord.Color.gold())
    win_embed.description = f"🎉 <@{winner}>'s horse dashed to the finish line and won **{prize:,} SC**!"
    await interaction.followup.send(embed=win_embed)


def calculate_cards(cards):
    total, aces = 0, 0
    for card in cards:
        val = card[0]
        if type(val) == int: total += val
        elif val in ['J', 'Q', 'K']: total += 10
        elif val == 'A':
            total += 11
            aces += 1
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total

class BlackjackView(View):
    def __init__(self, user_id, bet, old_credits):
        super().__init__(timeout=120) 
        self.user_id = user_id
        self.original_bet = bet 
        self.bet = bet
        self.old_credits = old_credits
        self.setup_game()

    def setup_game(self):
        self.bet = self.original_bet
        suits = ['♠️', '♥️', '♣️', '♦️']
        values = [2, 3, 4, 5, 6, 7, 8, 9, 10, 'J', 'Q', 'K', 'A']
        self.deck = [(v, s) for v in values for s in suits] * 4 
        random.shuffle(self.deck)
        
        self.player = [self.deck.pop(), self.deck.pop()]
        self.dealer = [self.deck.pop(), self.deck.pop()]

        self.clear_items()
        
        self.hit_btn = Button(label="Hit", style=discord.ButtonStyle.primary, emoji="🃏")
        self.hit_btn.callback = self.hit
        self.add_item(self.hit_btn)
        
        self.stand_btn = Button(label="Stand", style=discord.ButtonStyle.secondary, emoji="🖐️")
        self.stand_btn.callback = self.stand
        self.add_item(self.stand_btn)
        
        self.double_btn = Button(label="Double", style=discord.ButtonStyle.success, emoji="💸")
        self.double_btn.callback = self.double
        self.add_item(self.double_btn)
        
        self.surrender_btn = Button(label="Surrender", style=discord.ButtonStyle.danger, emoji="🏳️")
        self.surrender_btn.callback = self.surrender
        self.add_item(self.surrender_btn)

    def generate_embed(self, game_over=False):
        p_total = calculate_cards(self.player)
        d_total = calculate_cards(self.dealer)
        
        embed = discord.Embed(color=0x2b2d31) 
        def format_hand(hand): return " ".join([f"` {c[0]}{c[1]} `" for c in hand])
            
        p_hand_str = format_hand(self.player)
        
        if game_over:
            d_hand_str = format_hand(self.dealer)
            embed.add_field(name="🤵 Dealer's Hand", value=f"**{d_total}** | {d_hand_str}", inline=False)
        else:
            embed.add_field(name="🤵 Dealer's Hand", value=f"**{calculate_cards([self.dealer[0]])}** | ` {self.dealer[0][0]}{self.dealer[0][1]} ` ` ❓ `", inline=False)
            
        embed.add_field(name="👤 Your Hand", value=f"**{p_total}** | {p_hand_str}", inline=False)
        return embed, p_total, d_total

    async def end_game(self, interaction: discord.Interaction, embed: discord.Embed):
        self.clear_items()
        
        deal_btn = Button(label="Deal Again", style=discord.ButtonStyle.primary, emoji="🔁")
        deal_btn.callback = self.deal_again
        self.add_item(deal_btn)
        
        stop_btn = Button(label="Stop", style=discord.ButtonStyle.secondary, emoji="🛑")
        stop_btn.callback = self.stop_game
        self.add_item(stop_btn)
        await interaction.response.edit_message(embed=embed, view=self)

    async def hit(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id: return
        if len(self.children) > 2:
            for item in self.children:
                if item.label in ["Double", "Surrender"]: item.disabled = True

        self.player.append(self.deck.pop())
        embed, p_total, d_total = self.generate_embed()
        
        if p_total > 21:
            notification = check_rank_change(self.old_credits, self.old_credits - self.bet)
            embed.color = discord.Color.red()
            embed.description = f"💥 **BUST!** You went over 21.\n📉 **Loss:** -{self.bet:,} SC{notification}"
            await self.end_game(interaction, embed)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    async def stand(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id: return
        await self.evaluate_game(interaction)

    async def double(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id: return
        user_data = get_user(self.user_id)
        if user_data[0] < self.bet: return await interaction.response.send_message("You don't have enough balance to double down!", ephemeral=True)

        update_credits(self.user_id, -self.bet)
        self.bet *= 2
        
        self.player.append(self.deck.pop())
        p_total = calculate_cards(self.player)
        
        if p_total > 21:
            embed, p_total, d_total = self.generate_embed(game_over=True)
            notification = check_rank_change(self.old_credits, self.old_credits - self.bet)
            embed.color = discord.Color.red()
            embed.description = f"💥 **BUST!** You doubled and lost.\n📉 **Loss:** -{self.bet:,} SC{notification}"
            await self.end_game(interaction, embed)
        else:
            await self.evaluate_game(interaction)

    async def surrender(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id: return
        refund = int(self.bet / 2)
        update_credits(self.user_id, refund)
        embed, _, _ = self.generate_embed(game_over=True)
        notification = check_rank_change(self.old_credits, self.old_credits - (self.bet - refund))
        embed.color = discord.Color.orange()
        embed.description = f"🏳️ **SURRENDERED!** You forfeit the game.\n↩️ **Returned:** {refund:,} SC (Lost {self.bet - refund:,} SC){notification}"
        await self.end_game(interaction, embed)

    async def evaluate_game(self, interaction: discord.Interaction):
        p_total = calculate_cards(self.player)
        d_total = calculate_cards(self.dealer)
        
        while d_total < 17:
            self.dealer.append(self.deck.pop())
            d_total = calculate_cards(self.dealer)

        embed, p_total, d_total = self.generate_embed(game_over=True)
        
        if p_total == 21 and len(self.player) == 2 and not (d_total == 21 and len(self.dealer) == 2):
            profit = int(self.bet * 1.5)
            win = self.bet + profit
            update_credits(self.user_id, win)
            notification = check_rank_change(self.old_credits, self.old_credits + profit)
            embed.color = discord.Color.magenta()
            embed.description = f"🌟 **BLACKJACK!** 🌟\n🟢 **Profit:** +{profit:,} SC\n*(Total Payout: {win:,} SC)*{notification}"
            
        elif d_total > 21 or p_total > d_total:
            profit = self.bet
            win = self.bet + profit
            update_credits(self.user_id, win)
            notification = check_rank_change(self.old_credits, self.old_credits + profit)
            embed.color = discord.Color.green()
            embed.description = f"🎉 **YOU WIN!**\n🟢 **Profit:** +{profit:,} SC\n*(Total Payout: {win:,} SC)*{notification}"
            
        elif p_total == d_total:
            update_credits(self.user_id, self.bet)
            embed.color = discord.Color.gold()
            embed.description = f"🤝 **PUSH! (TIE)**\n↩️ **Returned:** {self.bet:,} SC"
            
        else:
            notification = check_rank_change(self.old_credits, self.old_credits - self.bet)
            embed.color = discord.Color.red()
            embed.description = f"📉 **YOU LOSE!** Dealer wins.\n🔴 **Loss:** -{self.bet:,} SC{notification}"
            
        await self.end_game(interaction, embed)

    async def deal_again(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id: return
        user_data = get_user(self.user_id)
        if user_data[0] < self.original_bet: return await interaction.response.send_message("You don't have enough Social Credit to play again!", ephemeral=True)
        update_credits(self.user_id, -self.original_bet)
        self.old_credits = user_data[0]
        self.setup_game()
        embed, _, _ = self.generate_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def stop_game(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id: return
        self.clear_items()
        await interaction.response.edit_message(view=self)

@bot.tree.command(name='blackjack', description='Play Blackjack 21 against the Casino Dealer')
async def blackjack(interaction: discord.Interaction, bet: int):
    user_id = interaction.user.id
    user_data = get_user(user_id)
    if bet <= 0 or user_data[0] < bet: return await interaction.response.send_message("Invalid bet / Not enough balance!", ephemeral=True)
        
    update_credits(user_id, -bet) 
    view = BlackjackView(user_id, bet, user_data[0])
    embed, _, _ = view.generate_embed()
    if calculate_cards(view.player) == 21: await view.evaluate_game(interaction)
    else: await interaction.response.send_message(embed=embed, view=view)


class SlotView(View):
    def __init__(self, user_id, bet):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.bet = bet

    async def spin_animation(self, interaction: discord.Interaction, is_first_time=False):
        user_data = get_user(self.user_id)
        old_credits = user_data[0]
        
        if old_credits < self.bet:
            msg = "You don't have enough Social Credit to play!"
            if is_first_time: await interaction.response.send_message(msg, ephemeral=True)
            else: await interaction.response.send_message(msg, ephemeral=True)
            return

        update_credits(self.user_id, -self.bet)
        emojis = ['🍒', '🍊', '🍇', '🔔', '💎', '7️⃣']
        
        embed = discord.Embed(color=discord.Color.blurple())
        embed.description = f"## 🎰 [ ❓ | ❓ | ❓ ] 🎰\n\n🔄 **Spinning...**\n👛 **wallet:** {old_credits - self.bet:,} SC"
        if is_first_time: await interaction.response.send_message(embed=embed, view=self)
        else: await interaction.response.edit_message(embed=embed, view=self)

        for _ in range(3):
            await asyncio.sleep(0.5) 
            temp_result = [random.choice(emojis) for _ in range(3)]
            embed.description = f"## 🎰 [ {temp_result[0]} | {temp_result[1]} | {temp_result[2]} ] 🎰\n\n🔄 **Spinning...**\n👛 **wallet:** {old_credits - self.bet:,} SC"
            await interaction.edit_original_response(embed=embed, view=self)

        await asyncio.sleep(0.5)
        result = [random.choice(emojis) for _ in range(3)]
        
        win_amount = 0
        multiplier = 0.0
        if result[0] == result[1] == result[2]:
            win_amount = self.bet * 15 
            multiplier = 15.0
        elif result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
            win_amount = int(self.bet * 2) 
            multiplier = 2.0
            
        if win_amount > 0:
            update_credits(self.user_id, win_amount)
            new_credits = old_credits - self.bet + win_amount
            color, profit_str = discord.Color.green(), f"🟢 **Profit:** +{win_amount - self.bet:,} SC (Payout {multiplier}x)"
        else:
            new_credits = old_credits - self.bet
            color, profit_str = discord.Color.red(), f"🔴 **Loss:** -{self.bet:,} SC"

        notification = check_rank_change(old_credits, new_credits)
        embed.color = color
        embed.description = f"## 🎰 [ {result[0]} | {result[1]} | {result[2]} ] 🎰\n\n{profit_str}\n👛 **wallet:** {new_credits:,} SC"
        if notification: embed.set_footer(text=notification.replace("\n", "").replace("*", ""))
        else: embed.remove_footer()
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="again?", style=discord.ButtonStyle.primary, emoji="🔁")
    async def btn_again(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id: return
        await self.spin_animation(interaction, is_first_time=False)

    @discord.ui.button(label="stop", style=discord.ButtonStyle.secondary, emoji="🛑")
    async def btn_stop(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id: return
        for child in self.children: child.disabled = True
        await interaction.response.edit_message(view=self)

@bot.tree.command(name='slot', description='Play the Slot Machine. Win BIG on a jackpot!')
async def slot(interaction: discord.Interaction, bet: int):
    if bet <= 0: return await interaction.response.send_message("Invalid bet amount!", ephemeral=True)
    view = SlotView(interaction.user.id, bet)
    await view.spin_animation(interaction, is_first_time=True)

class MinesTile(Button):
    def __init__(self, x, y):
        super().__init__(style=discord.ButtonStyle.secondary, label="⬛", row=x)
        self.is_mine = False
        self.x, self.y = x, y

    async def callback(self, interaction: discord.Interaction):
        view: MinesView = self.view
        if interaction.user.id != view.user_id: return
        
        if self.is_mine:
            for child in view.children:
                child.disabled = True
                if isinstance(child, MinesTile) and child.is_mine:
                    child.label = "💥"
                    child.style = discord.ButtonStyle.danger
            self.style = discord.ButtonStyle.danger
            notification = check_rank_change(view.old_credits, view.old_credits - view.bet)
            embed = discord.Embed(title="💣 BOMB HIT!", description=f"You lost!\n🔴 **Loss:** -{view.bet:,} SC{notification}", color=discord.Color.red())
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            self.disabled, self.style, self.label = True, discord.ButtonStyle.success, "💎"
            view.safe_clicks += 1
            view.multiplier *= (view.total_tiles - view.safe_clicks + 1) / (view.total_tiles - view.mines_count - view.safe_clicks + 1)
            embed = discord.Embed(title="⛏️ Casino Mines", description=f"Bet: **{view.bet:,} SC**\nMines: **{view.mines_count}**\n\nCurrent Profit: **x{view.multiplier:.2f}** (Payout: {(int(view.bet * view.multiplier)):,} SC)", color=discord.Color.blue())
            await interaction.response.edit_message(embed=embed, view=view)

class MinesView(View):
    def __init__(self, user_id, bet, mines_count, old_credits):
        super().__init__(timeout=120)
        self.user_id, self.bet, self.mines_count, self.old_credits = user_id, bet, mines_count, old_credits
        self.multiplier, self.safe_clicks, self.total_tiles = 1.0, 0, 20 
        
        tiles = []
        for x in range(4):
            for y in range(5):
                tile = MinesTile(x, y)
                tiles.append(tile)
                self.add_item(tile)
                
        for idx in random.sample(range(20), mines_count): tiles[idx].is_mine = True
            
        self.cashout_btn = Button(style=discord.ButtonStyle.primary, label="💰 CASHOUT (STOP)", row=4)
        self.cashout_btn.callback = self.cashout_callback
        self.add_item(self.cashout_btn)

    async def cashout_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id: return
        for child in self.children: child.disabled = True
        
        win = int(self.bet * self.multiplier)
        update_credits(self.user_id, win)
        
        notification = check_rank_change(self.old_credits, self.old_credits - self.bet + win)
        embed = discord.Embed(title="💸 CASHOUT SUCCESSFUL!", description=f"You safely withdrew!\n🟢 **Profit:** +{win - self.bet:,} SC (Payout {self.multiplier:.2f}x){notification}", color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=self)

@bot.tree.command(name='mines', description='Play Mines. Avoid the bombs and cashout your winnings!')
async def mines(interaction: discord.Interaction, bet: int, mines_count: int):
    user_id = interaction.user.id
    user_data = get_user(user_id)
    if bet <= 0 or user_data[0] < bet: return await interaction.response.send_message("Invalid bet / Not enough balance!", ephemeral=True)
    if mines_count < 1 or mines_count > 19: return await interaction.response.send_message("The number of mines must be between 1 and 19!", ephemeral=True)

    update_credits(user_id, -bet) 
    view = MinesView(user_id, bet, mines_count, user_data[0])
    embed = discord.Embed(title="⛏️ Casino Mines", description=f"Bet: **{bet:,} SC**\nMines: **{mines_count}**\n\nClick the tiles to find diamonds. Beware of bombs!", color=discord.Color.blue())
    await interaction.response.send_message(embed=embed, view=view)

async def play_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    if not current: return []
    def search_yt(query):
        with yt_dlp.YoutubeDL({'extract_flat': True, 'quiet': True}) as ydl: return ydl.extract_info(f"ytsearch5:{query}", download=False).get('entries', [])

    try: entries = await asyncio.get_event_loop().run_in_executor(None, search_yt, current)
    except Exception: return []

    return [app_commands.Choice(name=f"{e.get('title')} - {e.get('uploader')} (youtube)"[:100], value=e.get('url')) for e in entries]

@bot.tree.command(name='play', description='Play a song from a YouTube link or search query')
@app_commands.autocomplete(query=play_autocomplete) 
async def play(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    if not interaction.user.voice: return await interaction.followup.send("You must join a Voice Channel first!")
    
    try: voice_client = await interaction.user.voice.channel.connect()
    except discord.ClientException: voice_client = interaction.guild.voice_client
    try:
        search_query = query if query.startswith(('http://', 'https://')) else f"ytsearch1:{query}"
        data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(search_query, download=False))
        if 'entries' in data: data = data['entries'][0]
        voice_client.play(discord.FFmpegPCMAudio(data['url'], **ffmpeg_options))
        await interaction.followup.send(f"🎶 Now playing: **{data.get('title', 'Song')}**")
    except Exception:
        await interaction.followup.send("Oops, failed to load the song. Try another link or search term!")

@bot.tree.command(name='stop', description='Stop the song and kick the bot out')
async def stop(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("I'm leaving the Voice Channel! 👋")
    else:
        await interaction.response.send_message("I'm not currently in a Voice Channel.")

@bot.tree.command(name='ship', description='Check the love compatibility between two members!')
async def ship_user(interaction: discord.Interaction, user1: discord.Member, user2: discord.Member):
    random.seed(user1.id + user2.id)
    match_percentage = random.randint(0, 100)
    random.seed()
    if match_percentage >= 90: status = "A match made in heaven! 💍❤️"
    elif match_percentage >= 70: status = "Perfect match! 🥰"
    elif match_percentage >= 40: status = "Needs a little extra effort! 👀"
    else: status = "Better off just as friends. 😅"

    embed = discord.Embed(title="💖 Love Meter 💖", description=f"Compatibility between **{user1.display_name}** & **{user2.display_name}**", color=discord.Color.pink())
    embed.add_field(name="Result:", value=f"**{match_percentage}%**\n*{status}*", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='ship_name', description='Check love compatibility (type any names)!')
async def ship_name(interaction: discord.Interaction, name1: str, name2: str):
    random.seed("".join(sorted([name1.lower(), name2.lower()])))
    match_percentage = random.randint(0, 100)
    random.seed()
    if match_percentage >= 90: status = "A match made in heaven! 💍❤️"
    elif match_percentage >= 70: status = "Perfect match! 🥰"
    elif match_percentage >= 40: status = "Needs a little extra effort! 👀"
    else: status = "Better off just as friends. 😅"
    embed = discord.Embed(title="💖 Love Meter (Custom) 💖", description=f"Compatibility between **{name1}** & **{name2}**", color=discord.Color.purple())
    embed.add_field(name="Result:", value=f"**{match_percentage}%**\n*{status}*", inline=False)
    await interaction.response.send_message(embed=embed)

TOKEN = os.environ.get('DISCORD_TOKEN')
if TOKEN is None:
    print("ERROR: DISCORD_TOKEN environment variable not set. Please add it to your Render dashboard.")
else:
    bot.run(TOKEN)