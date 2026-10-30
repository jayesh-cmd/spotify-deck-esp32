# 🎵 Spotify Deck

A physical media player companion that displays what's currently playing on a tiny TFT screen — styled just like the **Apple iOS Lock Screen Now Playing widget**. Plug in your ESP32, run the Python script, and your screen shows the song title, artist, album art, progress bar, and playback controls in real time.

Supports **Spotify**, **YouTube / YouTube Music**, **Apple Music**, and a built-in **Demo Mode**.

---

## 🖥️ Platform Support

| Platform | YouTube | Spotify Desktop | Apple Music | Spotify Web API |
|----------|---------|----------------|-------------|-----------------|
| **macOS** | ✅ Chrome & Safari (AppleScript) | ✅ Full metadata | ✅ Full + artwork | ✅ |
| **Windows** | ✅ Chrome & Edge (window title) | ✅ Window title | ❌ not available | ✅ |
| **Linux** | ✅ via `playerctl` + MPRIS | ✅ via `playerctl` | ❌ not available | ✅ |

---

## 📸 What It Looks Like

```
┌──────────────────────────────────┐
│  🔊  🔵                          │  ← Speaker & Bluetooth icons
│  ┌────────┐   Blinding Lig       │  ← Song title (scrolls if long)
│  │ 🎵 Art │   The Weeknd         │  ← Artist name
│  │        │                      │
│  │        │    ◀◀  ⏸  ▶▶         │  ← Media controls
│  └────────┘                      │
│              ████░░░░  0:45/-2:55│  ← Progress bar + time
└──────────────────────────────────┘
```

---

## 🧰 Hardware You Need

| Component | Details |
|-----------|---------|
| **ESP32 Dev Board** | Any standard ESP32 (38-pin or 30-pin) |
| **ST7735 TFT Display** | 1.8" 160×128 pixel SPI TFT screen |
| **Jumper Wires** | Male-to-female dupont wires for connecting display to ESP32 |
| **USB Cable** | Micro-USB (to flash firmware and power the ESP32) |
| **Battery** *(optional)* | LiPo battery + TP4056 charging module for portable/wireless use |

---

## 🔌 Wiring — How to Connect the Display

Connect the **ST7735 TFT display** to your **ESP32** using jumper wires:

| Display Pin | Connect to ESP32 | What it does |
|-------------|-----------------|--------------|
| **VCC** | `3.3V` or `5V` | Powers the display |
| **GND** | `GND` | Ground / common reference |
| **CS** | `GPIO 5` | SPI Chip Select |
| **RST** | `GPIO 4` | Display Reset |
| **DC / A0** | `GPIO 2` | Data vs. Command signal |
| **SDA / MOSI** | `GPIO 23` | SPI data line (sends pixel data) |
| **SCK** | `GPIO 18` | SPI clock |
| **LED** | `3.3V` | Backlight — keeps screen lit |

> **Tip:** Use different colored jumper wires for VCC (red), GND (black), and signal lines to avoid wiring mistakes.

### Optional Buttons

You can wire physical push buttons for hardware media control:

| Button | GPIO Pin | Action |
|--------|----------|--------|
| On-board BOOT button | `GPIO 0` | Play / Pause |
| External button | `GPIO 13` | Next track |
| External button | `GPIO 14` | Previous track |
| External button | `GPIO 27` | Play / Pause (duplicate) |

All button pins use the ESP32's internal pull-up resistors — connect one side to the GPIO pin and the other side to `GND`.

---

## 🔋 Using a Battery (Optional)

To make the deck portable (no USB cable needed during use):

1. Connect a **LiPo battery** (3.7V, 500mAh or larger) to a **TP4056 charging module**.
2. Connect the TP4056 output (`B+` / `B-`) to the ESP32's `VIN` and `GND` pins.
3. Charge via the TP4056's USB port. The ESP32 and display will run off the battery.

> ⚠️ Do **not** connect 5V USB and a raw LiPo at the same time without a proper power management circuit. Use the `VIN` pin (not `3.3V`) when powering from battery.

---

## 💻 Software Setup

### Step 1 — Flash the ESP32 Firmware

The ESP32 firmware is in [`src/main.cpp`](src/main.cpp). Use **PlatformIO** to build and upload it.

1. Install [VS Code](https://code.visualstudio.com/) + the [PlatformIO extension](https://platformio.org/install/ide?install=vscode).
2. Open this project folder in VS Code.
3. PlatformIO will auto-read [`platformio.ini`](platformio.ini) and install the `TFT_eSPI` library.
4. Connect your ESP32 via USB and click **Upload** (→ button in the PlatformIO toolbar).
5. The display should light up with the standby screen once flashed.

---

### Step 2 — Install Python Dependencies

The easiest way — install everything from `requirements.txt`:

```bash
pip install -r requirements.txt
```

Or install the core packages manually:

```bash
pip install pyserial requests pillow spotipy
```

#### Platform-specific extras

**Windows** — needed for Chrome/Edge YouTube detection and Spotify media key control:
```bash
pip install pywin32 pyautogui
```

**Linux** — install `playerctl` for universal MPRIS media detection (works with Spotify, Chrome, VLC, etc.):
```bash
# Debian / Ubuntu
sudo apt install playerctl

# Arch Linux
sudo pacman -S playerctl
```

---

### Step 3 — Configure (Optional)

If you want to use the **Spotify Web API** (for controlling Spotify on your phone, browser, or smart speaker), copy the example config and fill in your credentials:

```bash
cp config.example.json config.json
```

Then edit `config.json`:

```json
{
  "spotify_client_id": "YOUR_CLIENT_ID",
  "spotify_client_secret": "YOUR_CLIENT_SECRET",
  "spotify_redirect_uri": "http://127.0.0.1:8888/callback"
}
```

Or use the interactive wizard:

```bash
python3 spotify_deck.py --setup
```

> For the **Spotify Desktop app on macOS or Windows**, no config is needed — it works automatically.

---

### Step 4 — Run the Companion Script

Plug in your ESP32 and run:

```bash
python3 spotify_deck.py
```

The script will:
- **Auto-detect** the ESP32's serial port (scans for known ESP32 USB-serial chip IDs — no hardcoded port)
- Connect and wait for the `SPOTIFY_DECK_READY` signal from the board
- Start monitoring your currently playing music and push updates to the screen
- **Auto-reconnect** if the USB cable is unplugged and re-plugged mid-session

---

## 🎮 How to Use It

### Auto Mode (Recommended)

```bash
python3 spotify_deck.py
```

The script automatically detects what's playing. Priority order by platform:

**macOS:**
1. YouTube / YouTube Music (Chrome or Safari)
2. Apple Music (native app)
3. Spotify Desktop
4. Spotify Web API
5. Built-in Demo Mode

**Windows:**
1. YouTube (Chrome or Edge — reads window title)
2. Spotify Desktop (reads window title)
3. Spotify Web API
4. Built-in Demo Mode

**Linux:**
1. Any MPRIS-compatible player via `playerctl` (Spotify, VLC, Rhythmbox, Chrome + browser-mpris2, etc.)
2. Spotify Web API
3. Built-in Demo Mode

---

### Force a Specific Player

```bash
# YouTube only
python3 spotify_deck.py --player youtube

# Apple Music only (macOS)
python3 spotify_deck.py --player apple

# Spotify only
python3 spotify_deck.py --player spotify
```

### Run Demo Mode (No music app needed)

```bash
python3 spotify_deck.py --demo
```

Plays through sample tracks offline — great for testing your setup without any music app.

### Specify a Serial Port Manually

The script auto-detects your ESP32 port. If it picks the wrong one, override it:

```bash
# macOS / Linux
python3 spotify_deck.py --port /dev/ttyUSB0

# Windows
python3 spotify_deck.py --port COM3
```

### Keyboard Shortcuts (while the script is running)

| Key | Action |
|-----|--------|
| `Space` | Play / Pause |
| `n` | Next track |
| `p` | Previous track |
| `q` | Quit |

---

## 🎵 Setting Up Spotify Web API (Optional)

> You only need this if you want to control Spotify on **other devices** (phone, smart speaker, etc.).
> For the **Spotify Desktop app**, it works automatically with zero config on both macOS and Windows.

1. Go to [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) and create a new app.
2. Set the Redirect URI to: `http://127.0.0.1:8888/callback`
3. Run the setup wizard:

```bash
python3 spotify_deck.py --setup
```

4. Enter your **Client ID** and **Client Secret** when prompted. They are saved to `config.json`.
5. On first run, a browser window will open for you to log in to Spotify and authorize the app.

---

## 🌐 YouTube — Enable Exact Timeline (macOS Only, One-Time Setup)

On macOS, by default, YouTube playback timing is estimated locally. For **exact pause detection and accurate seek position**:

**Google Chrome:**
> Menu → View → Developer → ✅ Allow JavaScript from Apple Events

**Safari:**
> Menu → Develop → ✅ Allow JavaScript from Apple Events

This lets the script read the precise video timestamp directly from the browser tab.

> **Windows / Linux:** Exact timeline is not available via window title detection. The progress bar uses local time estimation from when the video was detected.

---

## ⚙️ How It Works (Under the Hood)

```
Your Computer                     ESP32 + TFT Display
──────────────                    ────────────────────
Python Script                     main.cpp firmware
     │                                    │
     │  Reads from:                       │
     │  • macOS  → AppleScript           │
     │  • Windows→ win32gui + title       │
     │  • Linux  → playerctl (MPRIS)      │
     │                                    │
     │──── Serial USB ─────────────────▶  │
     │   T: title\tartist\t...            │  Updates song info
     │   A: 68,68,9248 + raw bytes        │  Streams album art
     │   P: progressSec\tisPlaying        │  Heartbeat every 0.5s
     │                                    │
     │◀────────────────────────────────── │
         BTN:PLAYPAUSE / NEXT / PREV        Button press events
```

1. **Python script** polls your music app every 0.5 seconds.
2. When the track changes, it downloads the album art, converts it to **68×68 px RGB565** (the raw pixel format the TFT understands), and streams it byte-by-byte over USB serial.
3. Every 0.5 seconds, it sends a lightweight `P:` progress heartbeat.
4. The **ESP32 firmware** parses these serial commands and updates only the parts of the screen that changed — no full screen redraws.
5. If a button is pressed on the ESP32, it sends `BTN:NEXT` / `BTN:PREV` / `BTN:PLAYPAUSE` back to the Python script, which then controls the music app.
6. If the **USB cable is unplugged**, the script detects the disconnect and automatically tries to reconnect with exponential back-off (3s → 6s → 12s → 30s).

---

## 📁 Project Structure

```
spotify-deck/
├── src/
│   └── main.cpp            # ESP32 firmware (C++ / Arduino)
├── platformio.ini          # PlatformIO build config (TFT pins, library)
├── spotify_deck.py         # Python companion script (runs on your computer)
├── requirements.txt        # Python dependencies
├── config.example.json     # Config template — copy to config.json and fill in
├── config.json             # Your credentials (gitignored, auto-created)
└── .cache_deck/            # Auto-created — caches downloaded album art
```

---

## 🛠️ Troubleshooting

| Problem | Fix |
|---------|-----|
| `No ESP32 serial port found` | Make sure the USB cable is data-capable (not charge-only). Try a different port. Pass `--port` manually if needed. |
| Screen stays blank / white | Check your wiring, especially DC, CS, and RST pins. Verify `platformio.ini` pin numbers match your wiring. |
| Album art doesn't show | You need an internet connection for YouTube/Spotify art. Apple Music art loads from local library. |
| Spotify not detected (macOS) | Make sure Spotify Desktop is open and playing. For Web API, run `--setup` first. |
| Spotify not detected (Windows) | Window title detection only works when a track is actively playing. Use Web API (`--setup`) for full control. |
| YouTube timeline is stuck (macOS) | Enable "Allow JavaScript from Apple Events" in Chrome/Safari (see above). |
| YouTube not detected (Windows) | Make sure Chrome or Edge has a YouTube tab open. Install `pywin32`: `pip install pywin32`. |
| Linux: nothing detected | Install `playerctl` and make sure your player supports MPRIS. Test with `playerctl status` in a terminal. |
| Script crashes on USB disconnect | Update to the latest version — auto-reconnect is now built in. |
| Wrong serial port auto-detected | Pass the port manually: `python3 spotify_deck.py --port /dev/ttyUSB0` (Linux) or `--port COM3` (Windows). |
| Apple Music on Windows/Linux | Apple Music is macOS-only. Use Spotify or YouTube instead. |

---

## 📦 Dependencies Summary

| Tool / Package | Platform | Notes |
|----------------|----------|-------|
| PlatformIO | All | For flashing ESP32 firmware |
| TFT_eSPI | ESP32 | Auto-installed via PlatformIO |
| Python 3.8+ | All | Required |
| `pyserial` | All | Serial communication with ESP32 |
| `requests` | All | Downloads album art from internet |
| `Pillow` | All | Converts images to RGB565 for TFT |
| `spotipy` | All | Spotify Web API *(optional)* |
| `pywin32` | Windows | Chrome/Edge YouTube detection *(optional but recommended)* |
| `pyautogui` | Windows/Linux | Playback control keystrokes *(optional)* |
| `playerctl` | Linux | MPRIS media detection (install via package manager) |
