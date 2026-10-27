#  Minimal Media Deck (YouTube, Apple Music & Spotify)
### Powered by ESP32 & ST7735 160×128 SPI TFT

A sleek, distraction-free desktop media player companion designed to look like the **Apple / iOS Lock Screen Now Playing widget**.

---

## ✨ Supported Players

- **📺 YouTube & YouTube Music in Browser (Chrome & Safari)**:
  - Detects active YouTube video/song tabs automatically.
  - Automatically fetches the video's official thumbnail, center-crops to square, and streams to your screen in RGB565!
  - Displays video title and artist cleanly.
- ** Apple Music**:
  - Native macOS `Music.app` zero-config integration with library artwork.
- **🎵 Spotify**:
  - Supports Spotify Desktop and Spotify Web API (phone, browser, speakers).
- **🎮 Minimal Demo Mode**:
  - Instant offline demo with sample tracks.

---

## 🛠️ Hardware Wiring (ST7735 160×128 SPI TFT)

| Display Pin | ESP32 GPIO | Description |
| :--- | :--- | :--- |
| **VCC** | `3.3V` / `5V` | Display Power |
| **GND** | `GND` | Ground |
| **CS** | `GPIO 5` | SPI Chip Select |
| **RST** | `GPIO 4` | Display Reset |
| **DC / A0** | `GPIO 2` | Data / Command Select |
| **SDA / MOSI**| `GPIO 23` | SPI MOSI Data |
| **SCK** | `GPIO 18` | SPI Clock |
| **LED** | `3.3V` | Backlight Anode |

---

## 🚀 How to Run

### 1. Start the Companion Service
```bash
python3 spotify_deck.py
```
It will automatically connect to your ESP32 on `/dev/cu.usbserial-10` and start monitoring your open YouTube tabs!

### 2. (Recommended) Enable Exact YouTube Timeline & Button Control
To allow the script to read the exact video seconds (`0:06 / -3:22`) and pause/resume YouTube with your ESP32 **BOOT button**:
- In **Google Chrome**: from the top menu, click **View → Developer → Allow JavaScript from Apple Events** (one-time setup).
- In **Safari**: from the top menu, click **Develop → Allow JavaScript from Apple Events**.

### 3. Switch Players Anytime
- Prioritize YouTube:
  ```bash
  python3 spotify_deck.py --player youtube
  ```
- Prioritize Apple Music:
  ```bash
  python3 spotify_deck.py --player apple
  ```
- Prioritize Spotify:
  ```bash
  python3 spotify_deck.py --player spotify
  ```
