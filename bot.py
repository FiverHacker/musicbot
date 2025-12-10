import discord
from discord.ext import commands
import yt_dlp
import asyncio

TOKEN = "ggg"

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


# --- YTDL CONFIG ---
ytdl_opts = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0'
}

FFMPEG_OPTIONS = {
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(ytdl_opts)


def search_song(query):
    info = ytdl.extract_info(query, download=False)
    if "entries" in info:
        info = info["entries"][0]
    return info


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


@bot.command()
async def join(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        await channel.connect()
        await ctx.send("Joined VC!")
    else:
        await ctx.send("You must be in a VC.")


@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("Left VC.")
    else:
        await ctx.send("I'm not in VC.")


@bot.command()
async def play(ctx, *, query):
    if not ctx.author.voice:
        return await ctx.send("Join a VC first!")

    vc = ctx.voice_client

    if not vc:
        vc = await ctx.author.voice.channel.connect()

    info = search_song(query)
    url = info["url"]
    title = info["title"]

    await ctx.send(f"🎵 Now playing: **{title}**")

    vc.play(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS))


@bot.command()
async def stop(ctx):
    if ctx.voice_client:
        ctx.voice_client.stop()
        await ctx.send("⛔ Music stopped.")


@bot.command()
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("⏸️ Paused.")


@bot.command()
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("▶️ Resumed.")


bot.run(TOKEN)

