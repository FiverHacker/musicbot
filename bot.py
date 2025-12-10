import discord
from discord.ext import commands
import asyncio
import os
import shutil
import re
from dotenv import load_dotenv
try:
    import spotipy
    from spotipy.oauth2 import SpotifyClientCredentials
    SPOTIFY_AVAILABLE = True
except ImportError:
    SPOTIFY_AVAILABLE = False
    print("ERROR: spotipy is required! Install with: pip install spotipy")
    raise

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    raise ValueError("DISCORD_TOKEN environment variable is not set. Please create a .env file with your Discord bot token.")

# Debug: Check if token looks valid (should be ~59 characters for Discord bot tokens)
if TOKEN and (len(TOKEN) < 50 or TOKEN == "your_discord_bot_token_here"):
    print("WARNING: Token appears to be invalid or still set to placeholder value!")
    print("Please update your .env file with a valid Discord bot token.")
    print("Token length:", len(TOKEN) if TOKEN else 0)

# Spotify configuration (required)
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')

if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
    raise ValueError("SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set in .env file!")

# Initialize Spotify client
spotify = None
if SPOTIFY_AVAILABLE and SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET:
    try:
        client_credentials_manager = SpotifyClientCredentials(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET
        )
        spotify = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
        print("✓ Spotify API connected")
    except Exception as e:
        print(f"ERROR: Could not connect to Spotify API: {e}")
        raise
else:
    raise ValueError("Spotify credentials are required!")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Sync slash commands tree
tree = bot.tree

# Check if ffmpeg is available
FFMPEG_PATH = shutil.which('ffmpeg')
if not FFMPEG_PATH:
    print("WARNING: ffmpeg is not installed or not in PATH!")
    print("Please install ffmpeg to use the music bot:")
    print("  Ubuntu/Debian: sudo apt-get update && sudo apt-get install -y ffmpeg")
    print("  CentOS/RHEL: sudo yum install ffmpeg")
    print("  Or download from: https://ffmpeg.org/download.html")
    print("\nThe bot will still start, but music commands will not work until ffmpeg is installed.")
else:
    print(f"✓ ffmpeg found at: {FFMPEG_PATH}")

FFMPEG_OPTIONS = {
    'options': '-vn',
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
}

# Queue system - stores tracks per guild
queues = {}
current_track = {}  # Current playing track per guild
player_message = {}  # Player embed message per guild
player_channel = {}  # Channel for player messages per guild


def is_spotify_url(url):
    """Check if the given string is a Spotify URL"""
    spotify_pattern = r'(?:https?://)?(?:open|play)\.spotify\.com/(?:track|album|playlist|artist)/([a-zA-Z0-9]+)'
    return bool(re.match(spotify_pattern, url.strip()))


def get_spotify_track_info(query, limit=1):
    """
    Get Spotify track information from URL or search query.
    Returns dict with 'preview_url', 'title', 'artist', 'duration', 'full_url', 'is_preview'
    If limit > 1, returns list of tracks
    """
    try:
        # Check if it's a Spotify URL
        if is_spotify_url(query):
            match = re.search(r'spotify\.com/(track|album|playlist|artist)/([a-zA-Z0-9]+)', query)
            if not match:
                return None if limit == 1 else []
            
            url_type = match.group(1)
            spotify_id = match.group(2)
            
            if url_type == 'track':
                track = spotify.track(spotify_id)
                result = {
                    'preview_url': track.get('preview_url'),
                    'title': track['name'],
                    'artist': ', '.join([artist['name'] for artist in track['artists']]),
                    'duration': track['duration_ms'] // 1000,
                    'full_url': track['external_urls']['spotify'],
                    'is_preview': track.get('preview_url') is not None,
                    'album': track['album']['name'],
                    'image': track['album']['images'][0]['url'] if track['album']['images'] else None
                }
                return result if limit == 1 else [result]
            elif url_type == 'album':
                album = spotify.album(spotify_id)
                tracks = []
                for track_item in album['tracks']['items'][:limit]:
                    full_track = spotify.track(track_item['id'])
                    tracks.append({
                        'preview_url': full_track.get('preview_url'),
                        'title': full_track['name'],
                        'artist': ', '.join([artist['name'] for artist in full_track['artists']]),
                        'duration': full_track['duration_ms'] // 1000,
                        'full_url': full_track['external_urls']['spotify'],
                        'is_preview': full_track.get('preview_url') is not None,
                        'album': full_track['album']['name'],
                        'image': full_track['album']['images'][0]['url'] if full_track['album']['images'] else None
                    })
                return tracks[0] if limit == 1 and tracks else tracks
            elif url_type == 'playlist':
                playlist = spotify.playlist(spotify_id)
                tracks = []
                for item in playlist['tracks']['items'][:limit]:
                    track = item['track']
                    if track:
                        full_track = spotify.track(track['id'])
                        tracks.append({
                            'preview_url': full_track.get('preview_url'),
                            'title': full_track['name'],
                            'artist': ', '.join([artist['name'] for artist in full_track['artists']]),
                            'duration': full_track['duration_ms'] // 1000,
                            'full_url': full_track['external_urls']['spotify'],
                            'is_preview': full_track.get('preview_url') is not None,
                            'album': full_track['album']['name'],
                            'image': full_track['album']['images'][0]['url'] if full_track['album']['images'] else None
                        })
                return tracks[0] if limit == 1 and tracks else tracks
        else:
            # Search for track
            results = spotify.search(q=query, type='track', limit=limit)
            tracks = []
            for track in results['tracks']['items']:
                tracks.append({
                    'preview_url': track.get('preview_url'),
                    'title': track['name'],
                    'artist': ', '.join([artist['name'] for artist in track['artists']]),
                    'duration': track['duration_ms'] // 1000,
                    'full_url': track['external_urls']['spotify'],
                    'is_preview': track.get('preview_url') is not None,
                    'album': track['album']['name'],
                    'image': track['album']['images'][0]['url'] if track['album']['images'] else None
                })
            return tracks[0] if limit == 1 and tracks else tracks
        
        return None if limit == 1 else []
        
    except Exception as e:
        print(f"Error getting Spotify track info: {e}")
        return None if limit == 1 else []


def format_duration(seconds):
    """Format duration in seconds to MM:SS or HH:MM:SS"""
    mins, secs = divmod(seconds, 60)
    if mins >= 60:
        hours, mins = divmod(mins, 60)
        return f"{int(hours)}:{int(mins):02d}:{int(secs):02d}"
    return f"{int(mins)}:{int(secs):02d}"


def create_player_embed(track_info, is_playing=True, queue_length=0):
    """Create a Discord embed for the music player"""
    embed = discord.Embed(
        title="🎵 Now Playing" if is_playing else "⏸️ Paused",
        color=0x1DB954 if is_playing else 0x808080,
        timestamp=discord.utils.utcnow()
    )
    
    embed.add_field(
        name="Track",
        value=f"[{track_info['title']}]({track_info['full_url']})",
        inline=False
    )
    
    embed.add_field(
        name="Artist",
        value=track_info['artist'],
        inline=True
    )
    
    embed.add_field(
        name="Duration",
        value=format_duration(track_info['duration']),
        inline=True
    )
    
    if track_info.get('album'):
        embed.add_field(
            name="Album",
            value=track_info['album'],
            inline=True
        )
    
    if track_info.get('image'):
        embed.set_thumbnail(url=track_info['image'])
    
    if track_info['is_preview']:
        embed.set_footer(text="⚠️ 30-second preview • Full track on Spotify")
    else:
        embed.set_footer(text="Spotify")
    
    if queue_length > 0:
        embed.add_field(
            name="Queue",
            value=f"{queue_length} track(s) in queue",
            inline=False
        )
    
    return embed


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await tree.sync()
        print(f"✓ Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"Error syncing commands: {e}")


@tree.command(name="join", description="Join your voice channel")
async def join(interaction: discord.Interaction):
    if interaction.user.voice:
        channel = interaction.user.voice.channel
        await channel.connect()
        await interaction.response.send_message("Joined VC!")
    else:
        await interaction.response.send_message("You must be in a VC.")


@tree.command(name="leave", description="Leave the voice channel")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("Left VC.")
    else:
        await interaction.response.send_message("I'm not in VC.")


async def play_next(guild_id, vc):
    """Play the next track in the queue"""
    if guild_id not in queues or len(queues[guild_id]) == 0:
        current_track[guild_id] = None
        return
    
    if not vc:
        return
    
    track_info = queues[guild_id].pop(0)
    current_track[guild_id] = track_info
    
    if not track_info['preview_url']:
        # Skip tracks without preview
        await play_next(guild_id, vc)
        return
    
    # Update player embed
    embed = create_player_embed(track_info, is_playing=True, queue_length=len(queues[guild_id]))
    if guild_id in player_message and player_message[guild_id]:
        try:
            await player_message[guild_id].edit(embed=embed)
        except:
            pass
    elif guild_id in player_channel and player_channel[guild_id]:
        try:
            channel = player_channel[guild_id]
            player_msg = await channel.send(embed=embed)
            player_message[guild_id] = player_msg
        except:
            pass
    
    def after_playing(error):
        if error:
            print(f"Error in playback: {error}")
        # Play next in queue
        asyncio.create_task(play_next(guild_id, vc))
    
    try:
        source = discord.FFmpegPCMAudio(track_info['preview_url'], executable=FFMPEG_PATH, **FFMPEG_OPTIONS)
        vc.play(source, after=after_playing)
    except Exception as e:
        print(f"Error playing: {e}")
        asyncio.create_task(play_next(guild_id, vc))


@tree.command(name="play", description="Play a song from Spotify")
async def play(interaction: discord.Interaction, query: str):
    if not interaction.user.voice:
        return await interaction.response.send_message("Join a VC first!")

    if not FFMPEG_PATH:
        return await interaction.response.send_message("❌ **Error:** ffmpeg is not installed. Please install ffmpeg to use music commands.\n"
                             "Install with: `sudo apt-get install -y ffmpeg` (Ubuntu/Debian)")

    if not spotify:
        return await interaction.response.send_message("❌ **Error:** Spotify API not connected. Check your credentials.")

    await interaction.response.defer()

    try:
        vc = interaction.guild.voice_client
        guild_id = interaction.guild.id

        if not vc:
            vc = await interaction.user.voice.channel.connect()

        # Initialize queue if needed
        if guild_id not in queues:
            queues[guild_id] = []

        await interaction.followup.send("🔍 Searching Spotify...")
        
        # Get track info from Spotify
        track_info = await asyncio.to_thread(get_spotify_track_info, query, limit=1)
        
        if not track_info:
            return await interaction.followup.send("❌ **Error:** Could not find track on Spotify. Try a different search or Spotify URL.")
        
        if not track_info['preview_url']:
            return await interaction.followup.send(f"❌ **Error:** No preview available for this track.\n\n"
                                f"**Track:** {track_info['title']} by {track_info['artist']}\n"
                                f"**Spotify Link:** {track_info['full_url']}\n\n"
                                f"*Note: Some tracks don't have preview URLs available. Try a different track.*")
        
        # If something is playing, add to queue
        if vc.is_playing() or vc.is_paused():
            queues[guild_id].append(track_info)
            embed = discord.Embed(
                title="✅ Added to Queue",
                description=f"[{track_info['title']}]({track_info['full_url']}) by **{track_info['artist']}**",
                color=0x1DB954
            )
            embed.add_field(name="Position in Queue", value=f"#{len(queues[guild_id])}", inline=True)
            embed.add_field(name="Duration", value=format_duration(track_info['duration']), inline=True)
            if track_info.get('image'):
                embed.set_thumbnail(url=track_info['image'])
            return await interaction.followup.send(embed=embed)
        
        # Play immediately
        current_track[guild_id] = track_info
        
        # Create and send player embed
        embed = create_player_embed(track_info, is_playing=True, queue_length=len(queues[guild_id]))
        player_msg = await interaction.followup.send(embed=embed)
        player_message[guild_id] = player_msg
        player_channel[guild_id] = interaction.channel

        def after_playing(error):
            if error:
                error_str = str(error)
                print(f"Error in playback: {error_str}")
            # Play next in queue
            asyncio.create_task(play_next(guild_id, vc))

        # Play from Spotify preview URL
        try:
            source = discord.FFmpegPCMAudio(track_info['preview_url'], executable=FFMPEG_PATH, **FFMPEG_OPTIONS)
            vc.play(source, after=after_playing)
        except Exception as play_error:
            await interaction.followup.send(f"❌ **Error playing audio:** {str(play_error)}")
            raise play_error
        
    except discord.errors.ClientException as e:
        if "ffmpeg was not found" in str(e):
            await interaction.followup.send("❌ **Error:** ffmpeg is not installed. Please install ffmpeg to use music commands.")
        else:
            await interaction.followup.send(f"❌ **Error:** {str(e)}")
    except Exception as e:
        await interaction.followup.send(f"❌ **Error:** {str(e)}")


@tree.command(name="search", description="Search for songs on Spotify")
async def search(interaction: discord.Interaction, query: str):
    """Search for songs on Spotify"""
    if not spotify:
        return await interaction.response.send_message("❌ **Error:** Spotify API not connected. Check your credentials.")
    
    await interaction.response.defer()
    
    try:
        await interaction.followup.send("🔍 Searching Spotify...")
        
        # Search for tracks
        tracks = await asyncio.to_thread(get_spotify_track_info, query, limit=10)
        
        if not tracks or len(tracks) == 0:
            return await interaction.followup.send("❌ **Error:** No tracks found. Try a different search.")
        
        # Create embed with search results
        embed = discord.Embed(
            title="🔍 Search Results",
            description=f"Found {len(tracks)} result(s) for: **{query}**",
            color=0x1DB954
        )
        
        results_text = ""
        for i, track in enumerate(tracks[:10], 1):
            duration = format_duration(track['duration'])
            preview_status = "✅" if track['preview_url'] else "❌"
            results_text += f"{i}. {preview_status} **{track['title']}** - {track['artist']} ({duration})\n"
            results_text += f"   [Listen on Spotify]({track['full_url']})\n\n"
        
        embed.description = results_text[:4096]  # Discord embed limit
        embed.set_footer(text="Use /play <song name> to play")
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"❌ **Error:** {str(e)}")


@tree.command(name="queue", description="Show the current queue")
async def queue(interaction: discord.Interaction):
    """Show the current queue"""
    guild_id = interaction.guild.id
    
    if guild_id not in queues or len(queues[guild_id]) == 0:
        return await interaction.response.send_message("📭 **Queue is empty!**")
    
    embed = discord.Embed(
        title="📋 Music Queue",
        color=0x1DB954
    )
    
    queue_list = ""
    for i, track in enumerate(queues[guild_id][:10], 1):
        duration = format_duration(track['duration'])
        queue_list += f"{i}. **{track['title']}** - {track['artist']} ({duration})\n"
    
    if len(queues[guild_id]) > 10:
        queue_list += f"\n... and {len(queues[guild_id]) - 10} more"
    
    embed.description = queue_list
    embed.set_footer(text=f"Total: {len(queues[guild_id])} track(s) in queue")
    
    await interaction.response.send_message(embed=embed)


@tree.command(name="nowplaying", description="Show the currently playing track")
async def nowplaying(interaction: discord.Interaction):
    """Show the currently playing track"""
    guild_id = interaction.guild.id
    
    if guild_id not in current_track or current_track[guild_id] is None:
        return await interaction.response.send_message("❌ **Nothing is currently playing!**")
    
    track_info = current_track[guild_id]
    vc = interaction.guild.voice_client
    is_playing = vc and vc.is_playing() and not vc.is_paused()
    queue_length = len(queues[guild_id]) if guild_id in queues else 0
    
    embed = create_player_embed(track_info, is_playing=is_playing, queue_length=queue_length)
    await interaction.response.send_message(embed=embed)


@tree.command(name="skip", description="Skip the current track")
async def skip(interaction: discord.Interaction):
    """Skip the current track"""
    vc = interaction.guild.voice_client
    if vc:
        guild_id = interaction.guild.id
        if vc.is_playing() or vc.is_paused():
            vc.stop()
            await interaction.response.send_message("⏭️ **Skipped!**")
            # Play next track
            await play_next(guild_id, vc)
        else:
            await interaction.response.send_message("❌ **Nothing is playing!**")
    else:
        await interaction.response.send_message("❌ **Not connected to a voice channel!**")


@tree.command(name="clear", description="Clear the queue")
async def clear(interaction: discord.Interaction):
    """Clear the queue"""
    guild_id = interaction.guild.id
    
    if guild_id in queues:
        queue_length = len(queues[guild_id])
        queues[guild_id] = []
        await interaction.response.send_message(f"🗑️ **Cleared {queue_length} track(s) from queue!**")
    else:
        await interaction.response.send_message("📭 **Queue is already empty!**")


@tree.command(name="stop", description="Stop playback and clear queue")
async def stop(interaction: discord.Interaction):
    """Stop playback and clear queue"""
    guild_id = interaction.guild.id
    vc = interaction.guild.voice_client
    
    if vc:
        vc.stop()
        if guild_id in queues:
            queues[guild_id] = []
        if guild_id in current_track:
            current_track[guild_id] = None
        await interaction.response.send_message("⛔ **Music stopped and queue cleared!**")
    else:
        await interaction.response.send_message("❌ **Not connected to a voice channel!**")


@tree.command(name="pause", description="Pause the current track")
async def pause(interaction: discord.Interaction):
    """Pause the current track"""
    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        vc.pause()
        guild_id = interaction.guild.id
        if guild_id in current_track and current_track[guild_id]:
            track_info = current_track[guild_id]
            queue_length = len(queues[guild_id]) if guild_id in queues else 0
            embed = create_player_embed(track_info, is_playing=False, queue_length=queue_length)
            if guild_id in player_message and player_message[guild_id]:
                try:
                    await player_message[guild_id].edit(embed=embed)
                except:
                    pass
        await interaction.response.send_message("⏸️ **Paused!**")
    else:
        await interaction.response.send_message("❌ **Nothing is playing!**")


@tree.command(name="resume", description="Resume the current track")
async def resume(interaction: discord.Interaction):
    """Resume the current track"""
    vc = interaction.guild.voice_client
    if vc and vc.is_paused():
        vc.resume()
        guild_id = interaction.guild.id
        if guild_id in current_track and current_track[guild_id]:
            track_info = current_track[guild_id]
            queue_length = len(queues[guild_id]) if guild_id in queues else 0
            embed = create_player_embed(track_info, is_playing=True, queue_length=queue_length)
            if guild_id in player_message and player_message[guild_id]:
                try:
                    await player_message[guild_id].edit(embed=embed)
                except:
                    pass
        await interaction.response.send_message("▶️ **Resumed!**")
    else:
        await interaction.response.send_message("❌ **Nothing is paused!**")


bot.run(TOKEN)
