# 🎵 Spotify Deck

A tiny physical Now Playing display — ESP32 + TFT screen styled like the iOS Lock Screen widget. Shows song title, artist, album art, and a live progress bar. Works with Spotify, YouTube, Apple Music, and a demo mode.

**Platform support:** macOS (full) · Windows (Chrome/Edge + Spotify) · Linux (playerctl/MPRIS)

---

## 🧰 Hardware

| Part | Detail |
|------|--------|
| ESP32 Dev Board | Any standard 30/38-pin board |
| ST7735 TFT | 1.8" 160×128 SPI display |
| Jumper Wires | Male-to-female dupont wires |
| USB Cable | Data-capable Micro-USB |
| Battery *(optional)* | LiPo 3.7V + TP4056 module for wireless use |

---

## 🔌 Wiring

| Display Pin | ESP32 GPIO |
|-------------|-----------|
| VCC | 3.3V |
| GND | GND |
| CS | GPIO 5 |
| RST | GPIO 4 |
| DC / A0 | GPIO 2 |
| SDA / MOSI | GPIO 23 |
| SCK | GPIO 18 |
| LED | 3.3V |

**Optional buttons** (connect to GND, internal pull-ups active):

| GPIO | Action |
|------|--------|
| 0 (BOOT) | Play / Pause |
| 13 | Next track |
| 14 | Previous track |
| 27 | Play / Pause |

---

## 💻 Setup

### 1. Flash ESP32

Open in **VS Code + PlatformIO**, connect ESP32, click **Upload**. `platformio.ini` handles everything automatically.

### 2. Install Python deps

```bash
pip install -r requirements.txt
```

Extra for **Windows** (YouTube/Spotify detection):
```bash
pip install pywin32 pyautogui
```

Extra for **Linux** (universal MPRIS detection):
```bash
sudo apt install playerctl   # or: sudo pacman -S playerctl
```

### 3. Run

```bash
python3 spotify_deck.py
```

The ESP32 port is **auto-detected** — no config needed. If it picks the wrong port:
```bash
python3 spotify_deck.py --port /dev/ttyUSB0   # Linux/macOS
python3 spotify_deck.py --port COM3            # Windows
```

---

## 🎮 Usage

| Command | What it does |
|---------|-------------|
| `python3 spotify_deck.py` | Auto-detect what's playing |
| `--player youtube` | Force YouTube |
| `--player spotify` | Force Spotify |
| `--player apple` | Force Apple Music (macOS only) |
| `--demo` | Offline demo mode |
| `--setup` | Configure Spotify Web API credentials |

**Keyboard shortcuts while running:** `Space` play/pause · `n` next · `p` prev · `q` quit

---

## 🎵 Spotify Web API (Optional)

Only needed for controlling Spotify on **phone / browser / speakers**. Desktop app works automatically.

1. Create an app at [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
2. Set Redirect URI → `http://127.0.0.1:8888/callback`
3. Run `python3 spotify_deck.py --setup` and enter your credentials

---

## 🌐 YouTube Exact Timeline (macOS only)

In **Chrome:** View → Developer → ✅ Allow JavaScript from Apple Events  
In **Safari:** Develop → ✅ Allow JavaScript from Apple Events

Without this, playback time is estimated locally.

---

## 🛠️ Troubleshooting

| Problem | Fix |
|---------|-----|
| Port not found | Use `--port` to specify manually |
| Blank screen | Check wiring pins against `platformio.ini` |
| No art showing | Needs internet for Spotify/YouTube art |
| Linux not detecting | Run `playerctl status` to verify playerctl works |
| Windows YouTube missing | Install `pywin32`, open YouTube in Chrome/Edge |
