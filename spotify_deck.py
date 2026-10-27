#!/usr/bin/env python3
"""
Minimal Music & Video Deck Companion Service
===========================================
Supports:
  - 📺 YouTube / YouTube Music in Browser (Google Chrome & Safari)
  -  Apple Music (Native macOS Music.app)
  - 🎵 Spotify (Desktop App & Web API)
  - 🎮 Minimal Demo Mode
Streams track metadata, 68x68 RGB565 album art thumbnails, and progress timeline.
Matches the minimal Apple / iOS Lock Screen media player layout.
"""

import os
import sys
import re
import time
import json
import io
import threading
import argparse
import select
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

import serial
import serial.tools.list_ports
import requests
from PIL import Image, ImageDraw

try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    HAS_SPOTIPY = True
except ImportError:
    HAS_SPOTIPY = False

# Terminal raw input helper for interactive hotkeys
class TerminalInput:
    def __init__(self):
        self.old_settings = None
        self.active = False
        if sys.stdin.isatty():
            try:
                import termios
                import tty
                self.termios = termios
                self.tty = tty
                self.old_settings = termios.tcgetattr(sys.stdin)
                tty.setcbreak(sys.stdin.fileno())
                self.active = True
            except Exception:
                self.active = False

    def get_key(self) -> Optional[str]:
        if not self.active:
            return None
        r, _, _ = select.select([sys.stdin], [], [], 0)
        if r:
            return sys.stdin.read(1)
        return None

    def restore(self):
        if self.active and self.old_settings:
            try:
                self.termios.tcsetattr(sys.stdin, self.termios.TCSADRAIN, self.old_settings)
            except Exception:
                pass
            self.active = False


# Configuration paths
CONFIG_PATH = Path("config.json")
CACHE_DIR = Path(".cache_deck")
CACHE_DIR.mkdir(exist_ok=True)
ART_CACHE_DIR = CACHE_DIR / "art"
ART_CACHE_DIR.mkdir(exist_ok=True)

DEFAULT_PORT = "/dev/cu.usbserial-10"
BAUD_RATE = 115200
ART_SIZE = 68  # 68x68 pixels

# Demo playlist
DEMO_TRACKS = [
    {
        "id": "demo_company",
        "title": "Company",
        "artist": "Justin Bieber",
        "album": "Purpose",
        "duration_sec": 208,
        "bg_colors": [(45, 45, 48), (20, 20, 22)],
        "accent": (255, 255, 255),
    },
    {
        "id": "demo_blinding",
        "title": "Blinding Lights",
        "artist": "The Weeknd",
        "album": "After Hours",
        "duration_sec": 200,
        "bg_colors": [(160, 20, 35), (35, 10, 15)],
        "accent": (255, 220, 80),
    },
]


def load_config() -> Dict[str, Any]:
    """Load configuration from config.json or environment."""
    config = {
        "spotify_client_id": os.getenv("SPOTIPY_CLIENT_ID", ""),
        "spotify_client_secret": os.getenv("SPOTIPY_CLIENT_SECRET", ""),
        "spotify_redirect_uri": os.getenv("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
        "port": DEFAULT_PORT,
        "baud": BAUD_RATE,
        "player": "auto",
    }
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r") as f:
                saved = json.load(f)
                config.update(saved)
        except Exception as e:
            print(f"[Config] Error loading config.json: {e}")
    return config


def save_config(config: Dict[str, Any]):
    """Save config to config.json."""
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def find_serial_port(specified_port: Optional[str] = None) -> Optional[str]:
    """Find the ESP32 serial port."""
    if specified_port and os.path.exists(specified_port):
        return specified_port
    if os.path.exists(DEFAULT_PORT):
        return DEFAULT_PORT

    ports = serial.tools.list_ports.comports()
    for p in ports:
        device = p.device
        if any(tag in device.lower() for tag in ["usbserial", "wchusb", "slab", "cp210", "ch34"]):
            return device
    if ports:
        return ports[0].device
    return None


def sanitize_text(text: str) -> str:
    """Sanitize text to safe clean printable string for TFT_eSPI."""
    text = text.replace("–", "-").replace("—", "-").replace("“", '"').replace("”", '"').replace("’", "'")
    text = re.sub(r"[\t\r\n]", " ", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    return text.strip()


def image_to_rgb565(img: Image.Image) -> bytes:
    """Convert a PIL Image to 16-bit RGB565 big-endian byte array."""
    img = img.convert("RGB")
    if img.size != (ART_SIZE, ART_SIZE):
        img = img.resize((ART_SIZE, ART_SIZE), Image.Resampling.LANCZOS)

    raw = bytearray()
    pixels = img.load()
    for y in range(ART_SIZE):
        for x in range(ART_SIZE):
            r, g, b = pixels[x, y]
            r5 = (r >> 3) & 0x1F
            g6 = (g >> 2) & 0x3F
            b5 = (b >> 3) & 0x1F
            rgb565 = (r5 << 11) | (g6 << 5) | b5
            raw.append((rgb565 >> 8) & 0xFF)
            raw.append(rgb565 & 0xFF)
    return bytes(raw)


def generate_procedural_art(title: str, artist: str, bg_colors=None, accent=(255, 255, 255)) -> bytes:
    """Generate a sleek album art thumbnail when no image is available."""
    img = Image.new("RGB", (ART_SIZE, ART_SIZE), color=(30, 30, 35))
    draw = ImageDraw.Draw(img)

    if not bg_colors:
        h = sum(ord(c) for c in title) if title else 42
        c1 = ((h * 37) % 150 + 40, (h * 67) % 150 + 40, (h * 97) % 150 + 40)
        c2 = (c1[0] // 3, c1[1] // 3, c1[2] // 3)
        bg_colors = [c1, c2]

    c1, c2 = bg_colors[0], bg_colors[1]
    for y in range(ART_SIZE):
        t = y / float(ART_SIZE)
        r = int(c1[0] * (1 - t) + c2[0] * t)
        g = int(c1[1] * (1 - t) + c2[1] * t)
        b = int(c1[2] * (1 - t) + c2[2] * t)
        draw.line([(0, y), (ART_SIZE - 1, y)], fill=(r, g, b))

    cx, cy = ART_SIZE // 2, ART_SIZE // 2
    draw.ellipse([cx - 26, cy - 26, cx + 26, cy + 26], outline=(255, 255, 255, 30), width=1)
    draw.ellipse([cx - 18, cy - 18, cx + 18, cy + 18], outline=(0, 0, 0, 40), width=1)
    draw.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], fill=accent)
    draw.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=(20, 20, 22))

    initials = "".join([w[0] for w in title.split() if w][:2]).upper()
    if initials:
        draw.text((7, ART_SIZE - 17), initials, fill=(255, 255, 255))

    return image_to_rgb565(img)


def download_album_art(url: str, track_id: str, crop_square=False) -> Optional[bytes]:
    """Download album art from web URL, resize to 68x68, and convert to RGB565."""
    cache_file = ART_CACHE_DIR / f"{track_id}_68.raw"
    if cache_file.exists():
        try:
            return cache_file.read_bytes()
        except Exception:
            pass

    try:
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        resp = requests.get(url, headers=headers, timeout=4)
        if resp.status_code == 200:
            img = Image.open(io.BytesIO(resp.content))
            if crop_square:
                w, h = img.size
                min_dim = min(w, h)
                left = (w - min_dim) // 2
                top = (h - min_dim) // 2
                img = img.crop((left, top, left + min_dim, top + min_dim))
            rgb565_bytes = image_to_rgb565(img)
            cache_file.write_bytes(rgb565_bytes)
            return rgb565_bytes
    except Exception as e:
        print(f"[Art] Failed to download {url}: {e}")
    return None


class BrowserYouTubeClient:
    """Browser YouTube / YouTube Music provider (Google Chrome & Safari)."""

    warned_js = False
    last_video_id = ""
    cached_meta: Dict[str, Tuple[str, str]] = {}
    
    # Accurate timeline & playback tracking
    current_pos = 0.0
    last_tick_time = time.time()
    is_playing_state = True

    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        if not url:
            return None
        match = re.search(r"[?&]v=([a-zA-Z0-9_-]{11})", url)
        if match:
            return match.group(1)
        match = re.search(r"youtu\.be/([a-zA-Z0-9_-]{11})", url)
        if match:
            return match.group(1)
        return None

    @classmethod
    def get_instant_oembed_meta(cls, video_id: str) -> Tuple[str, str]:
        """Fetch song name and artist instantly in 0.1s via oEmbed API."""
        if video_id in cls.cached_meta:
            return cls.cached_meta[video_id]

        url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        try:
            r = requests.get(url, timeout=2.0)
            if r.status_code == 200:
                d = r.json()
                raw_title = d.get("title", "")
                author = d.get("author_name", "YouTube")
                
                # Clean noise tags like (Official Video), [4K], etc.
                cleaned = re.sub(r"[\(\[][^\)\]]*(?:Official|Music|Video|Audio|Lyric|HD|4K|Remaster|with)[^\)\]]*[\)\]]", "", raw_title, flags=re.IGNORECASE).strip()
                cleaned = re.sub(r"\s*\|\s*.*$", "", cleaned).strip()

                if " - " in cleaned:
                    p1, p2 = cleaned.split(" - ", 1)
                    artist = p1.strip()
                    song = p2.strip()
                elif " by " in cleaned.lower():
                    parts = re.split(r"\s+by\s+", cleaned, flags=re.IGNORECASE, maxsplit=1)
                    song, artist = parts[0].strip(), parts[1].strip()
                else:
                    song = cleaned.strip()
                    artist = author.strip()

                meta = (song or "YouTube", artist or "Playing")
                cls.cached_meta[video_id] = meta
                return meta
        except Exception:
            pass

        return ("YouTube Track", "Playing")

    @classmethod
    def get_playback_state(cls) -> Optional[Dict[str, Any]]:
        state = cls._query_chrome()
        if state:
            return state

        state = cls._query_safari()
        if state:
            return state

        return None

    @classmethod
    def _query_chrome(cls) -> Optional[Dict[str, Any]]:
        # AppleScript prioritizing the user's active front tab
        script = """
        tell application "System Events"
            set isChrome to (name of processes) contains "Google Chrome"
        end tell
        if not isChrome then return "NOT_RUNNING"

        tell application "Google Chrome"
            -- 1. Check active tab of front window first
            try
                set curTab to active tab of front window
                set curUrl to (URL of curTab as string)
                if curUrl contains "youtube.com/watch" or curUrl contains "youtu.be/" then
                    set curTitle to (title of curTab as string)
                    try
                        set jsCmd to "(() => { const v = document.querySelector('video'); if (!v) return 'NO_VIDEO'; return [v.paused ? 'PAUSED' : 'PLAYING', Math.floor(v.currentTime), Math.floor(v.duration || 0)].join('||'); })()"
                        set jsRes to (execute curTab javascript jsCmd)
                        return "OK||" & jsRes & "||" & curTitle & "||" & curUrl
                    on error
                        return "NO_JS||" & curTitle & "||" & curUrl
                    end try
                end if
            end try

            -- 2. Scan all windows for YouTube
            repeat with w in windows
                repeat with t in tabs of w
                    set tUrl to (URL of t as string)
                    if tUrl contains "youtube.com/watch" or tUrl contains "youtu.be/" then
                        set tTitle to (title of t as string)
                        try
                            set jsCmd to "(() => { const v = document.querySelector('video'); if (!v) return 'NO_VIDEO'; return [v.paused ? 'PAUSED' : 'PLAYING', Math.floor(v.currentTime), Math.floor(v.duration || 0)].join('||'); })()"
                            set jsRes to (execute t javascript jsCmd)
                            return "OK||" & jsRes & "||" & tTitle & "||" & tUrl
                        on error
                            return "NO_JS||" & tTitle & "||" & tUrl
                        end try
                    end if
                end repeat
            end repeat
            return "NOT_FOUND"
        end tell
        """
        try:
            out = subprocess.check_output(["osascript", "-e", script], stderr=subprocess.DEVNULL).decode().strip()
            if not out or out in ("NOT_RUNNING", "NOT_FOUND"):
                return None

            now = time.time()
            dt = now - cls.last_tick_time
            cls.last_tick_time = now

            if out.startswith("OK||"):
                # JavaScript enabled: 100% exact timeline & pause state
                parts = out.split("||")
                if len(parts) >= 6:
                    _, state_str, pos_s, dur_s, raw_title, url = parts[:6]
                    is_playing = (state_str.upper() == "PLAYING")
                    pos = int(pos_s) if pos_s.isdigit() else 0
                    dur = int(dur_s) if dur_s.isdigit() else 240
                    video_id = cls.extract_video_id(url) or "yt_unknown"

                    # Get instant metadata via oEmbed
                    song, artist = cls.get_instant_oembed_meta(video_id)

                    cls.last_video_id = video_id
                    cls.current_pos = float(pos)
                    cls.is_playing_state = is_playing

                    return {
                        "source": "YouTube (Chrome)",
                        "id": f"yt_{video_id}",
                        "title": song,
                        "artist": artist,
                        "album": "YouTube",
                        "duration_sec": dur if dur > 0 else 240,
                        "progress_sec": pos,
                        "is_playing": is_playing,
                        "video_id": video_id,
                        "art_url": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                        "crop_art": True,
                    }

            elif out.startswith("NO_JS||"):
                # JavaScript disabled in Chrome: use instant oEmbed + smooth local timer
                parts = out.split("||")
                if len(parts) >= 3:
                    _, raw_title, url = parts[:3]
                    video_id = cls.extract_video_id(url) or "yt_unknown"

                    song, artist = cls.get_instant_oembed_meta(video_id)

                    # Smooth local timer (fixes the stuck timeline bug)
                    if video_id != cls.last_video_id:
                        cls.last_video_id = video_id
                        cls.current_pos = 0.0
                    else:
                        if cls.is_playing_state:
                            cls.current_pos += dt

                    pos = int(cls.current_pos)

                    if not cls.warned_js:
                        print("\n[ACTION REQUIRED FOR EXACT PAUSE / TIMELINE]")
                        print("  👉 In Google Chrome: View > Developer > Allow JavaScript from Apple Events\n")
                        cls.warned_js = True

                    return {
                        "source": "YouTube (Chrome)",
                        "id": f"yt_{video_id}",
                        "title": song,
                        "artist": artist,
                        "album": "YouTube",
                        "duration_sec": 240,
                        "progress_sec": pos,
                        "is_playing": cls.is_playing_state,
                        "video_id": video_id,
                        "art_url": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                        "crop_art": True,
                    }
        except Exception:
            return None
        return None

    @classmethod
    def _query_safari(cls) -> Optional[Dict[str, Any]]:
        script = """
        tell application "System Events"
            set isSafari to (name of processes) contains "Safari"
        end tell
        if not isSafari then return "NOT_RUNNING"

        tell application "Safari"
            repeat with w in windows
                repeat with t in tabs of w
                    set tUrl to (URL of t as string)
                    if tUrl contains "youtube.com/watch" or tUrl contains "youtu.be/" then
                        set tTitle to (name of t as string)
                        try
                            set jsCmd to "(() => { const v = document.querySelector('video'); if (!v) return 'NO_VIDEO'; return [v.paused ? 'PAUSED' : 'PLAYING', Math.floor(v.currentTime), Math.floor(v.duration || 0)].join('||'); })()"
                            set jsRes to (do JavaScript jsCmd in t)
                            return "OK||" & jsRes & "||" & tTitle & "||" & tUrl
                        on error
                            return "NO_JS||" & tTitle & "||" & tUrl
                        end try
                    end if
                end repeat
            end repeat
            return "NOT_FOUND"
        end tell
        """
        try:
            out = subprocess.check_output(["osascript", "-e", script], stderr=subprocess.DEVNULL).decode().strip()
            if not out or out in ("NOT_RUNNING", "NOT_FOUND"):
                return None

            now = time.time()
            dt = now - cls.last_tick_time
            cls.last_tick_time = now

            if out.startswith("OK||"):
                parts = out.split("||")
                if len(parts) >= 6:
                    _, state_str, pos_s, dur_s, raw_title, url = parts[:6]
                    is_playing = (state_str.upper() == "PLAYING")
                    pos = int(pos_s) if pos_s.isdigit() else 0
                    dur = int(dur_s) if dur_s.isdigit() else 240
                    video_id = cls.extract_video_id(url) or "yt_unknown"
                    song, artist = cls.get_instant_oembed_meta(video_id)

                    return {
                        "source": "YouTube (Safari)",
                        "id": f"yt_{video_id}",
                        "title": song,
                        "artist": artist,
                        "album": "YouTube",
                        "duration_sec": dur if dur > 0 else 240,
                        "progress_sec": pos,
                        "is_playing": is_playing,
                        "video_id": video_id,
                        "art_url": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                        "crop_art": True,
                    }
        except Exception:
            return None
        return None

    @classmethod
    def play_pause(cls):
        """Toggle play/pause in YouTube video."""
        cls.is_playing_state = not cls.is_playing_state

        # Method 1: JavaScript in Chrome
        script_chrome_js = """
        tell application "Google Chrome"
            repeat with w in windows
                repeat with t in tabs of w
                    if URL of t contains "youtube.com/watch" then
                        try
                            execute t javascript "(() => { const v = document.querySelector('video'); if (v) v.paused ? v.play() : v.pause(); })()"
                            return "OK"
                        end try
                    end if
                end repeat
            end repeat
        end tell
        """
        try:
            res = subprocess.check_output(["osascript", "-e", script_chrome_js], stderr=subprocess.DEVNULL).decode().strip()
            if res == "OK":
                return
        except Exception:
            pass

        # Method 2: Keystroke "k" (Universal YouTube shortcut)
        script_keystroke = """
        tell application "Google Chrome" to activate
        tell application "System Events"
            tell process "Google Chrome"
                keystroke "k"
            end tell
        end tell
        """
        try:
            subprocess.run(["osascript", "-e", script_keystroke], stderr=subprocess.DEVNULL)
        except Exception:
            pass

    @classmethod
    def next_track(cls):
        """Skip to next video."""
        cls.current_pos = 0.0
        script = """
        tell application "Google Chrome" to activate
        tell application "System Events"
            tell process "Google Chrome"
                keystroke "N" using {shift down}
            end tell
        end tell
        """
        try:
            subprocess.run(["osascript", "-e", script], stderr=subprocess.DEVNULL)
        except Exception:
            pass

    @classmethod
    def prev_track(cls):
        """Jump back or previous video."""
        script = """
        tell application "Google Chrome" to activate
        tell application "System Events"
            tell process "Google Chrome"
                keystroke "j"
            end tell
        end tell
        """
        try:
            subprocess.run(["osascript", "-e", script], stderr=subprocess.DEVNULL)
        except Exception:
            pass


class AppleMusicClient:
    """macOS Native Apple Music (Music.app) Provider via AppleScript."""

    @staticmethod
    def is_running() -> bool:
        cmd = 'tell application "System Events" to (name of processes) contains "Music"'
        try:
            out = subprocess.check_output(["osascript", "-e", cmd], stderr=subprocess.DEVNULL).decode().strip()
            return out == "true"
        except Exception:
            return False

    @staticmethod
    def get_playback_state() -> Optional[Dict[str, Any]]:
        if not AppleMusicClient.is_running():
            return None

        script = """
        tell application "Music"
            try
                set pState to (player state as string)
                if pState is "stopped" then
                    return "STOPPED"
                end if
                set tName to name of current track
                set tArtist to artist of current track
                set tAlbum to album of current track
                set tDur to duration of current track
                set tPos to player position
                return tName & "||" & tArtist & "||" & tAlbum & "||" & tDur & "||" & tPos & "||" & pState
            on error
                return "ERROR"
            end try
        end tell
        """
        try:
            out = subprocess.check_output(["osascript", "-e", script], stderr=subprocess.DEVNULL).decode().strip()
            if not out or out in ("STOPPED", "ERROR"):
                return None

            parts = out.split("||")
            if len(parts) >= 6:
                title, artist, album, dur_s, pos_s, state_s = parts[:6]
                is_playing = (state_s.lower() == "playing")
                dur = int(float(dur_s)) if dur_s else 0
                pos = int(float(pos_s)) if pos_s else 0
                track_id = f"am_{title}_{artist}_{album}".replace(" ", "_").replace("/", "_")
                return {
                    "source": "Apple Music",
                    "id": track_id,
                    "title": title,
                    "artist": artist,
                    "album": album,
                    "duration_sec": dur,
                    "progress_sec": pos,
                    "is_playing": is_playing,
                    "art_url": None,
                }
        except Exception:
            return None
        return None

    @staticmethod
    def get_artwork(track_id: str) -> Optional[bytes]:
        cache_file = ART_CACHE_DIR / f"{track_id}_68.raw"
        if cache_file.exists():
            try:
                return cache_file.read_bytes()
            except Exception:
                pass

        temp_art = CACHE_DIR / "temp_am_art.raw"
        posix_path = str(temp_art.resolve())
        script = f"""
        tell application "Music"
            try
                if (count of artworks of current track) > 0 then
                    set artData to raw data of artwork 1 of current track
                    set fRef to open for access (POSIX file "{posix_path}") with write permission
                    set eof fRef to 0
                    write artData to fRef
                    close access fRef
                    return "OK"
                end if
            on error
                try
                    close access (POSIX file "{posix_path}")
                end try
                return "ERROR"
            end try
            return "NO_ART"
        end tell
        """
        try:
            res = subprocess.check_output(["osascript", "-e", script], stderr=subprocess.DEVNULL).decode().strip()
            if res == "OK" and temp_art.exists():
                data = temp_art.read_bytes()
                jpg_idx = data.find(b"\xff\xd8")
                png_idx = data.find(b"\x89PNG")
                img = None
                if jpg_idx != -1:
                    img = Image.open(io.BytesIO(data[jpg_idx:]))
                elif png_idx != -1:
                    img = Image.open(io.BytesIO(data[png_idx:]))
                else:
                    try:
                        img = Image.open(io.BytesIO(data))
                    except Exception:
                        img = None

                if img:
                    rgb565_bytes = image_to_rgb565(img)
                    cache_file.write_bytes(rgb565_bytes)
                    return rgb565_bytes
        except Exception as e:
            print(f"[Apple Music Art] {e}")
        return None

    @staticmethod
    def play_pause():
        subprocess.run(["osascript", "-e", 'tell application "Music" to playpause'], stderr=subprocess.DEVNULL)

    @staticmethod
    def next_track():
        subprocess.run(["osascript", "-e", 'tell application "Music" to next track'], stderr=subprocess.DEVNULL)

    @staticmethod
    def prev_track():
        subprocess.run(["osascript", "-e", 'tell application "Music" to previous track'], stderr=subprocess.DEVNULL)


class SpotifyWebClient:
    """Spotify Web API Provider using spotipy."""

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.sp: Optional[spotipy.Spotify] = None
        self._init_spotify()

    def _init_spotify(self):
        scope = "user-read-playback-state user-modify-playback-state user-read-currently-playing"
        auth_manager = SpotifyOAuth(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            scope=scope,
            cache_path=str(CACHE_DIR / ".spotify_token"),
            open_browser=True,
        )
        self.sp = spotipy.Spotify(auth_manager=auth_manager)

    def get_playback_state(self) -> Optional[Dict[str, Any]]:
        if not self.sp:
            return None
        try:
            curr = self.sp.current_playback()
            if not curr or not curr.get("item"):
                return None

            item = curr["item"]
            track_id = item.get("id", "unknown")
            title = item.get("name", "Unknown Track")
            artist = ", ".join([a["name"] for a in item.get("artists", [])]) or "Unknown Artist"
            album = item.get("album", {}).get("name", "Unknown Album")
            duration_sec = int(item.get("duration_ms", 0) / 1000)
            progress_sec = int(curr.get("progress_ms", 0) / 1000)
            is_playing = bool(curr.get("is_playing", False))

            art_url = None
            images = item.get("album", {}).get("images", [])
            if images:
                art_url = images[-1]["url"] if len(images) > 1 else images[0]["url"]

            return {
                "source": "Spotify",
                "id": track_id,
                "title": title,
                "artist": artist,
                "album": album,
                "duration_sec": duration_sec,
                "progress_sec": progress_sec,
                "is_playing": is_playing,
                "art_url": art_url,
            }
        except Exception:
            return None

    def play_pause(self, current_playing: bool):
        try:
            if current_playing:
                self.sp.pause_playback()
            else:
                self.sp.start_playback()
        except Exception as e:
            print(f"[Spotify API] Play/Pause error: {e}")

    def next_track(self):
        try:
            self.sp.next_track()
        except Exception as e:
            print(f"[Spotify API] Next error: {e}")

    def prev_track(self):
        try:
            self.sp.previous_track()
        except Exception as e:
            print(f"[Spotify API] Prev error: {e}")


class SpotifyAppleScriptClient:
    """macOS Local Spotify Desktop App Provider via osascript."""

    @staticmethod
    def is_running() -> bool:
        cmd = 'tell application "System Events" to (name of processes) contains "Spotify"'
        try:
            out = subprocess.check_output(["osascript", "-e", cmd], stderr=subprocess.DEVNULL).decode().strip()
            return out == "true"
        except Exception:
            return False

    @staticmethod
    def get_playback_state() -> Optional[Dict[str, Any]]:
        if not SpotifyAppleScriptClient.is_running():
            return None

        script = """
        tell application "Spotify"
            if player state is stopped then
                return "STOPPED"
            end if
            set tName to name of current track
            set tArtist to artist of current track
            set tAlbum to album of current track
            set tDur to (duration of current track) / 1000
            set tPos to player position
            set tState to (player state as string)
            set tArt to artwork url of current track
            return tName & "||" & tArtist & "||" & tAlbum & "||" & tDur & "||" & tPos & "||" & tState & "||" & tArt
        end tell
        """
        try:
            out = subprocess.check_output(["osascript", "-e", script], stderr=subprocess.DEVNULL).decode().strip()
            if not out or out == "STOPPED":
                return None

            parts = out.split("||")
            if len(parts) >= 7:
                title, artist, album, dur_s, pos_s, state_s, art_url = parts[:7]
                is_playing = (state_s.lower() == "playing")
                dur = int(float(dur_s)) if dur_s else 0
                pos = int(float(pos_s)) if pos_s else 0
                track_id = f"sp_{title}_{artist}"
                return {
                    "source": "Spotify",
                    "id": track_id,
                    "title": title,
                    "artist": artist,
                    "album": album,
                    "duration_sec": dur,
                    "progress_sec": pos,
                    "is_playing": is_playing,
                    "art_url": art_url if art_url.startswith("http") else None,
                }
        except Exception:
            return None
        return None

    @staticmethod
    def play_pause():
        subprocess.run(["osascript", "-e", 'tell application "Spotify" to playpause'], stderr=subprocess.DEVNULL)

    @staticmethod
    def next_track():
        subprocess.run(["osascript", "-e", 'tell application "Spotify" to next track'], stderr=subprocess.DEVNULL)

    @staticmethod
    def prev_track():
        subprocess.run(["osascript", "-e", 'tell application "Spotify" to previous track'], stderr=subprocess.DEVNULL)


class DemoProvider:
    """Interactive offline demo mode featuring Purpose - Company."""

    def __init__(self):
        self.track_idx = 0
        self.progress = 6
        self.is_playing = True
        self.last_tick = time.time()

    def get_playback_state(self) -> Dict[str, Any]:
        now = time.time()
        if self.is_playing:
            dt = now - self.last_tick
            self.progress += int(dt)
        self.last_tick = now

        track = DEMO_TRACKS[self.track_idx]
        if self.progress >= track["duration_sec"]:
            self.next_track()
            track = DEMO_TRACKS[self.track_idx]

        return {
            "source": "Demo Player",
            "id": track["id"],
            "title": track["title"],
            "artist": track["artist"],
            "album": track["album"],
            "duration_sec": track["duration_sec"],
            "progress_sec": self.progress,
            "is_playing": self.is_playing,
            "art_url": None,
            "bg_colors": track["bg_colors"],
            "accent": track["accent"],
        }

    def play_pause(self):
        self.is_playing = not self.is_playing
        self.last_tick = time.time()

    def next_track(self):
        self.track_idx = (self.track_idx + 1) % len(DEMO_TRACKS)
        self.progress = 0
        self.last_tick = time.time()

    def prev_track(self):
        self.track_idx = (self.track_idx - 1) % len(DEMO_TRACKS)
        self.progress = 0
        self.last_tick = time.time()


class ESP32Bridge:
    """Handles communication with the ESP32 over Serial."""

    def __init__(self, port: str, baud: int = BAUD_RATE):
        self.port = port
        self.baud = baud
        self.ser: Optional[serial.Serial] = None
        self.lock = threading.Lock()
        self.on_button_callback = None
        self.running = False
        self.reader_thread = None

    def connect(self) -> bool:
        """Establish serial connection."""
        try:
            print(f"[Serial] Connecting to {self.port} at {self.baud} baud...")
            self.ser = serial.Serial(self.port, self.baud, timeout=0.1)
            time.sleep(1.2)
            self.running = True
            self.reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
            self.reader_thread.start()
            print("[Serial] Connected successfully!")
            return True
        except Exception as e:
            print(f"[Serial] Connection error: {e}")
            self.ser = None
            return False

    def close(self):
        """Close connection."""
        self.running = False
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None

    def send_track_info(self, title: str, artist: str, album: str, duration_sec: int,
                        progress_sec: int, is_playing: bool, has_art: bool):
        """Send track metadata to ESP32."""
        with self.lock:
            if not self.ser or not self.ser.is_open:
                return
            clean_title = sanitize_text(title)
            clean_artist = sanitize_text(artist)
            clean_album = sanitize_text(album)
            cmd = f"T:{clean_title}\t{clean_artist}\t{clean_album}\t{duration_sec}\t{progress_sec}\t{1 if is_playing else 0}\t{1 if has_art else 0}\n"
            try:
                self.ser.write(cmd.encode("utf-8", errors="ignore"))
                self.ser.flush()
            except Exception as e:
                print(f"[Serial] Error sending track info: {e}")

    def send_progress(self, progress_sec: int, is_playing: bool):
        """Send lightweight progress update to ESP32."""
        with self.lock:
            if not self.ser or not self.ser.is_open:
                return
            cmd = f"P:{progress_sec}\t{1 if is_playing else 0}\n"
            try:
                self.ser.write(cmd.encode("utf-8", errors="ignore"))
                self.ser.flush()
            except Exception as e:
                print(f"[Serial] Error sending progress: {e}")

    def send_artwork(self, raw_bytes: bytes):
        """Stream 68x68 RGB565 thumbnail to ESP32 with safe pacing."""
        with self.lock:
            if not self.ser or not self.ser.is_open:
                return
            header = f"A:{ART_SIZE},{ART_SIZE},{len(raw_bytes)}\n"
            try:
                self.ser.write(header.encode("utf-8"))
                self.ser.flush()
                time.sleep(0.06)

                chunk_size = 128
                for i in range(0, len(raw_bytes), chunk_size):
                    chunk = raw_bytes[i:i + chunk_size]
                    self.ser.write(chunk)
                    self.ser.flush()
                    time.sleep(0.012)
            except Exception as e:
                print(f"[Serial] Error sending artwork: {e}")

    def _reader_loop(self):
        """Background thread listening for incoming button events from ESP32."""
        while self.running:
            try:
                if self.ser and self.ser.is_open:
                    line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                    if line:
                        if line.startswith("BTN:") and self.on_button_callback:
                            action = line.split(":", 1)[1]
                            self.on_button_callback(action)
                        elif line == "SPOTIFY_DECK_READY":
                            print("\n[ESP32] Screen reports READY!")
                else:
                    time.sleep(0.2)
            except Exception:
                time.sleep(0.1)


def format_time_str(sec: int) -> str:
    m = sec // 60
    s = sec % 60
    return f"{m:02d}:{s:02d}"


def run_deck(args):
    """Main companion runner."""
    config = load_config()

    port = args.port or config.get("port")
    port = find_serial_port(port)
    if not port:
        print("[Error] No ESP32 serial port found! Please plug in your ESP32 with USB cable.")
        sys.exit(1)

    print(f"\n=======================================================")
    print(f"  📺  MINIMAL DECK: YOUTUBE, APPLE MUSIC & SPOTIFY  📺")
    print(f"=======================================================")
    print(f" ESP32 Port     : {port}")
    print(f" Baud Rate      : {BAUD_RATE}")

    bridge = ESP32Bridge(port, BAUD_RATE)
    if not bridge.connect():
        print(f"[Error] Failed to open serial port {port}. Is another program using it?")
        sys.exit(1)

    spotify_web_client = None
    if config.get("spotify_client_id") and config.get("spotify_client_secret") and HAS_SPOTIPY:
        try:
            spotify_web_client = SpotifyWebClient(
                config["spotify_client_id"],
                config["spotify_client_secret"],
                config["spotify_redirect_uri"]
            )
        except Exception:
            pass

    demo_client = DemoProvider()
    forced_player = args.player.lower() if args.player else config.get("player", "auto")

    current_track_id = None
    last_art_track_id = None
    active_source = "None"
    last_sent_state = None

    def trigger_action(action: str):
        if "YouTube" in active_source:
            if action == "PLAYPAUSE":
                BrowserYouTubeClient.play_pause()
            elif action == "NEXT":
                BrowserYouTubeClient.next_track()
            elif action == "PREV":
                BrowserYouTubeClient.prev_track()
        elif active_source == "Apple Music":
            if action == "PLAYPAUSE":
                AppleMusicClient.play_pause()
            elif action == "NEXT":
                AppleMusicClient.next_track()
            elif action == "PREV":
                AppleMusicClient.prev_track()
        elif active_source == "Spotify (Desktop)":
            if action == "PLAYPAUSE":
                SpotifyAppleScriptClient.play_pause()
            elif action == "NEXT":
                SpotifyAppleScriptClient.next_track()
            elif action == "PREV":
                SpotifyAppleScriptClient.prev_track()
        elif active_source == "Spotify (Web)" and spotify_web_client:
            state = spotify_web_client.get_playback_state()
            is_p = state["is_playing"] if state else False
            if action == "PLAYPAUSE":
                spotify_web_client.play_pause(is_p)
            elif action == "NEXT":
                spotify_web_client.next_track()
            elif action == "PREV":
                spotify_web_client.prev_track()
        elif active_source == "Demo Player":
            if action == "PLAYPAUSE":
                demo_client.play_pause()
            elif action == "NEXT":
                demo_client.next_track()
            elif action == "PREV":
                demo_client.prev_track()

    bridge.on_button_callback = lambda act: (print(f"\n[Deck Event] 🔘 ESP32 Button: {act}"), trigger_action(act))

    print("-------------------------------------------------------")
    print(" 🚀 Deck is LIVE! Monitoring YouTube (Chrome/Safari), Apple Music & Spotify...")
    print(" Controls: [Space] Play/Pause | [n] Next | [p] Prev | [q] Quit")
    print("-------------------------------------------------------\n")

    term_input = TerminalInput()

    try:
        while True:
            key = term_input.get_key()
            if key:
                if key == " ":
                    print("\n[Action] Play/Pause toggled")
                    trigger_action("PLAYPAUSE")
                elif key.lower() == "n":
                    print("\n[Action] Next track")
                    trigger_action("NEXT")
                elif key.lower() == "p":
                    print("\n[Action] Previous track")
                    trigger_action("PREV")
                elif key.lower() == "q":
                    print("\n[Action] Quit requested")
                    break

            state = None

            if args.demo:
                state = demo_client.get_playback_state()
                active_source = "Demo Player"
            elif forced_player == "youtube":
                state = BrowserYouTubeClient.get_playback_state()
                if state:
                    active_source = state["source"]
            elif forced_player == "apple":
                state = AppleMusicClient.get_playback_state()
                if state:
                    active_source = "Apple Music"
            elif forced_player == "spotify":
                if SpotifyAppleScriptClient.is_running():
                    state = SpotifyAppleScriptClient.get_playback_state()
                    if state:
                        active_source = "Spotify (Desktop)"
                if not state and spotify_web_client:
                    state = spotify_web_client.get_playback_state()
                    if state:
                        active_source = "Spotify (Web)"
            else:
                yt_state = BrowserYouTubeClient.get_playback_state()
                if yt_state:
                    state = yt_state
                    active_source = yt_state["source"]

                if not state and AppleMusicClient.is_running():
                    st = AppleMusicClient.get_playback_state()
                    if st and st.get("is_playing"):
                        state = st
                        active_source = "Apple Music"

                if not state and SpotifyAppleScriptClient.is_running():
                    st = SpotifyAppleScriptClient.get_playback_state()
                    if st and st.get("is_playing"):
                        state = st
                        active_source = "Spotify (Desktop)"

                if not state and spotify_web_client:
                    st = spotify_web_client.get_playback_state()
                    if st and st.get("is_playing"):
                        state = st
                        active_source = "Spotify (Web)"

                if not state and AppleMusicClient.is_running():
                    st = AppleMusicClient.get_playback_state()
                    if st:
                        state = st
                        active_source = "Apple Music"

                if not state:
                    state = demo_client.get_playback_state()
                    active_source = "Demo Player"

            if not state:
                time.sleep(0.3)
                continue

            track_id = state["id"]
            title = state["title"]
            artist = state["artist"]
            album = state["album"]
            dur = state["duration_sec"]
            prog = state["progress_sec"]
            is_playing = state["is_playing"]
            art_url = state.get("art_url")
            crop_art = state.get("crop_art", False)

            track_changed = (track_id != current_track_id)
            state_changed = (is_playing != last_sent_state)

            if track_changed:
                current_track_id = track_id
                last_sent_state = is_playing
                print(f"\n[{active_source}] 🎵 '{title}' - {artist} ({format_time_str(dur)})")

                art_bytes = None
                if active_source == "Apple Music":
                    art_bytes = AppleMusicClient.get_artwork(track_id)
                elif art_url:
                    art_bytes = download_album_art(art_url, track_id, crop_square=crop_art)

                if not art_bytes:
                    bg = state.get("bg_colors")
                    acc = state.get("accent", (255, 255, 255))
                    art_bytes = generate_procedural_art(title, artist, bg_colors=bg, accent=acc)

                has_art = art_bytes is not None

                # Send Track Metadata
                bridge.send_track_info(title, artist, album, dur, prog, is_playing, has_art)
                time.sleep(0.12)

                # Send Artwork
                if has_art and track_id != last_art_track_id:
                    print(f"[Art] 🎨 Streaming 68x68 thumbnail to display ({len(art_bytes)} bytes)...")
                    bridge.send_artwork(art_bytes)
                    last_art_track_id = track_id
            else:
                last_sent_state = is_playing
                bridge.send_progress(prog, is_playing)

            # Live terminal status line
            state_sym = "▶" if is_playing else "⏸"
            rem_s = dur - prog
            if rem_s < 0:
                rem_s = 0
            time_str = f"{format_time_str(prog)} / -{format_time_str(rem_s)}"
            sys.stdout.write(f"\r[{active_source[:16]}] {state_sym} {title[:16]} - {artist[:14]} | {time_str}   ")
            sys.stdout.flush()

            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n[Exit] Stopping Deck Companion...")
    finally:
        term_input.restore()
        bridge.close()
        print("[Exit] Done.")


def setup_wizard():
    """Interactive wizard to configure Spotify Web API credentials."""
    print("\n=======================================================")
    print("  🔑  SPOTIFY DEVELOPER SETUP WIZARD")
    print("=======================================================")
    print("Note: YouTube & Apple Music require NO setup! They work automatically.")
    print("For Spotify Web API across all devices:")
    print("1. Go to: https://developer.spotify.com/dashboard")
    print("2. Redirect URI: http://127.0.0.1:8888/callback")
    print("-------------------------------------------------------\n")

    client_id = input("Enter Spotify Client ID (or press Enter to skip): ").strip()
    client_secret = input("Enter Spotify Client Secret: ").strip() if client_id else ""

    if client_id and client_secret:
        config = load_config()
        config["spotify_client_id"] = client_id
        config["spotify_client_secret"] = client_secret
        save_config(config)
        print(f"\n[Success] Saved Spotify credentials to config.json!\n")
    else:
        print("\n[Notice] Using zero-config YouTube / Apple Music / Spotify Desktop Mode.")


def main():
    parser = argparse.ArgumentParser(description="Minimal Media Deck ESP32 Companion (YouTube, Apple Music, Spotify)")
    parser.add_argument("--demo", action="store_true", help="Run minimal demo simulation mode")
    parser.add_argument("--player", type=str, default="auto", choices=["auto", "youtube", "apple", "spotify"], help="Player source: auto, youtube, apple, spotify")
    parser.add_argument("--port", type=str, default=None, help="Serial port of ESP32 (e.g. /dev/cu.usbserial-10)")
    parser.add_argument("--setup", action="store_true", help="Configure Spotify Web API credentials")
    args = parser.parse_args()

    if args.setup:
        setup_wizard()
    else:
        run_deck(args)


if __name__ == "__main__":
    main()
