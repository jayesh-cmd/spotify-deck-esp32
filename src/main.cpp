#include <Arduino.h>
#include <TFT_eSPI.h>

// -------------------------------------------------------------
// SPOTIFY DECK - MINIMAL APPLE/IOS STYLE (ROBUST & FAST)
// Clean, elegant, distraction-free Now Playing widget
// Matches the minimal Apple Music / iOS Lock Screen layout
// -------------------------------------------------------------

TFT_eSPI tft = TFT_eSPI();

// Hardware Push Button Pins
#define PIN_BOOT_BTN   0   // On-board BOOT button: Play / Pause toggle
#define PIN_BTN_NEXT   13  // Next track
#define PIN_BTN_PREV   14  // Prev track
#define PIN_BTN_PLAY   27  // Play / Pause

// Apple / iOS Dark Palette (RGB565)
#define COLOR_BG            0x2124  // #202024 Deep Charcoal / Slate
#define COLOR_CARD_BG       0x2945  // #2C2C30 Card
#define COLOR_TEXT_WHITE    0xFFFF  // Crisp White
#define COLOR_TEXT_MUTED    0x8C71  // #8E8E93 iOS Secondary Grey
#define COLOR_BAR_BG        0x39E7  // #3A3A3C Progress bar background
#define COLOR_BAR_FILL      0xE71C  // #E5E5EA Bright Silver / White

// Layout (Landscape 160 x 128)
#define SCREEN_W 160
#define SCREEN_H 128

// Artwork Position & Size
#define ART_SIZE 68
#define ART_X 8
#define ART_Y 30
#define ART_RADIUS 6

// Right Content Column
#define RIGHT_X 84
#define RIGHT_W (SCREEN_W - RIGHT_X - 6) // ~70 px
#define RIGHT_CX (RIGHT_X + RIGHT_W / 2) // ~119 px

// Track State
struct TrackState {
  String title = "Not Playing";
  String artist = "Waiting";
  String album = "";
  int durationSec = 240;
  int progressSec = 0;
  bool isPlaying = false;
  bool hasArt = false;
  uint32_t lastLocalTick = 0;
} track;

// Button debounce
unsigned long lastBootPress = 0;
unsigned long lastNextPress = 0;
unsigned long lastPrevPress = 0;
unsigned long lastPlayPress = 0;
const unsigned long DEBOUNCE_MS = 300;

// Marquee scroll
int titleScrollOffset = 0;
unsigned long lastScrollTime = 0;
int scrollPauseCount = 0;
const int TITLE_WINDOW_CHARS = 9;

// Clip the 4 corners of the album art to make it smoothly rounded
void roundArtworkCorners() {
  int x = ART_X;
  int y = ART_Y;
  int s = ART_SIZE;
  int r = ART_RADIUS;

  // Corner 1: Top-Left
  tft.fillRect(x, y, r, 1, COLOR_BG);
  tft.fillRect(x, y + 1, r - 1, 1, COLOR_BG);
  tft.fillRect(x, y + 2, r - 2, 1, COLOR_BG);
  tft.fillRect(x, y + 3, r - 3, 1, COLOR_BG);

  // Corner 2: Top-Right
  tft.fillRect(x + s - r, y, r, 1, COLOR_BG);
  tft.fillRect(x + s - r + 1, y + 1, r - 1, 1, COLOR_BG);
  tft.fillRect(x + s - r + 2, y + 2, r - 2, 1, COLOR_BG);
  tft.fillRect(x + s - r + 3, y + 3, r - 3, 1, COLOR_BG);

  // Corner 3: Bottom-Left
  tft.fillRect(x, y + s - 1, r, 1, COLOR_BG);
  tft.fillRect(x, y + s - 2, r - 1, 1, COLOR_BG);
  tft.fillRect(x, y + s - 3, r - 2, 1, COLOR_BG);
  tft.fillRect(x, y + s - 4, r - 3, 1, COLOR_BG);

  // Corner 4: Bottom-Right
  tft.fillRect(x + s - r, y + s - 1, r, 1, COLOR_BG);
  tft.fillRect(x + s - r + 1, y + s - 2, r - 1, 1, COLOR_BG);
  tft.fillRect(x + s - r + 2, y + s - 3, r - 2, 1, COLOR_BG);
  tft.fillRect(x + s - r + 3, y + s - 4, r - 3, 1, COLOR_BG);
}

// Draw default sleek placeholder art
void drawDefaultArtwork() {
  tft.fillRoundRect(ART_X, ART_Y, ART_SIZE, ART_SIZE, ART_RADIUS, COLOR_CARD_BG);
  
  int cx = ART_X + ART_SIZE / 2;
  int cy = ART_Y + ART_SIZE / 2;
  tft.fillCircle(cx, cy, 24, 0x18C3);
  tft.drawCircle(cx, cy, 24, 0x31E7);
  tft.drawCircle(cx, cy, 16, 0x2124);
  tft.fillCircle(cx, cy, 7, 0x8C71);
  tft.fillCircle(cx, cy, 2, TFT_BLACK);
}

// Draw top-right subtle icons (Speaker & Bluetooth)
void drawTopIcons() {
  tft.fillRect(RIGHT_X, 10, RIGHT_W + 4, 12, COLOR_BG);

  int sx = 134;
  int sy = 12;
  tft.fillRect(sx, sy + 2, 3, 4, COLOR_TEXT_MUTED);
  tft.fillTriangle(sx + 3, sy + 2, sx + 3, sy + 5, sx + 6, sy + 1, COLOR_TEXT_MUTED);
  tft.fillTriangle(sx + 3, sy + 5, sx + 6, sy + 1, sx + 6, sy + 6, COLOR_TEXT_MUTED);
  tft.drawPixel(sx + 8, sy + 2, COLOR_TEXT_MUTED);
  tft.drawPixel(sx + 8, sy + 3, COLOR_TEXT_MUTED);
  tft.drawPixel(sx + 8, sy + 4, COLOR_TEXT_MUTED);
  tft.drawPixel(sx + 8, sy + 5, COLOR_TEXT_MUTED);
  tft.drawPixel(sx + 10, sy + 1, COLOR_TEXT_MUTED);
  tft.drawPixel(sx + 10, sy + 6, COLOR_TEXT_MUTED);

  int bx = 149;
  int by = 11;
  tft.drawLine(bx + 2, by, bx + 2, by + 8, COLOR_TEXT_MUTED);
  tft.drawLine(bx + 2, by, bx + 5, by + 2, COLOR_TEXT_MUTED);
  tft.drawLine(bx + 5, by + 2, bx, by + 6, COLOR_TEXT_MUTED);
  tft.drawLine(bx + 2, by + 8, bx + 5, by + 6, COLOR_TEXT_MUTED);
  tft.drawLine(bx + 5, by + 6, bx, by + 2, COLOR_TEXT_MUTED);
}

// Draw Song Title (clean, centered, with marquee scrolling if long)
void drawTrackTitle() {
  String fullTitle = track.title;
  String displayTitle = fullTitle;

  if (fullTitle.length() > TITLE_WINDOW_CHARS) {
    int maxOffset = fullTitle.length() - TITLE_WINDOW_CHARS;
    int curOffset = min(titleScrollOffset, maxOffset);
    displayTitle = fullTitle.substring(curOffset, curOffset + TITLE_WINDOW_CHARS);
  }

  tft.fillRect(RIGHT_X, 28, RIGHT_W + 6, 18, COLOR_BG);
  tft.setTextColor(COLOR_TEXT_WHITE, COLOR_BG);
  
  int tw = tft.textWidth(displayTitle, 2);
  int tx = RIGHT_CX - (tw / 2);
  if (tx < RIGHT_X) tx = RIGHT_X;
  tft.drawString(displayTitle, tx, 28, 2);
}

// Draw Artist Name (clean, centered, muted grey)
void drawArtist() {
  tft.fillRect(RIGHT_X, 48, RIGHT_W + 6, 14, COLOR_BG);
  tft.setTextColor(COLOR_TEXT_MUTED, COLOR_BG);

  String displayArtist = track.artist;
  if (displayArtist.length() > 14) {
    displayArtist = displayArtist.substring(0, 13) + "..";
  }

  int tw = tft.textWidth(displayArtist, 1);
  int tx = RIGHT_CX - (tw / 2);
  if (tx < RIGHT_X) tx = RIGHT_X;
  tft.drawString(displayArtist, tx, 49, 1);
}

// Draw Media Controls: <<  || (or >)  >>
void drawControls() {
  int cy = 73;
  tft.fillRect(RIGHT_X, cy - 10, RIGHT_W + 6, 20, COLOR_BG);

  // 1. Rewind / Prev (<<)
  int px = 94;
  tft.fillTriangle(px + 4, cy - 5, px + 4, cy + 5, px, cy, COLOR_TEXT_WHITE);
  tft.fillTriangle(px + 9, cy - 5, px + 9, cy + 5, px + 5, cy, COLOR_TEXT_WHITE);

  // 2. Play / Pause
  int cx = RIGHT_CX;
  if (track.isPlaying) {
    // Two vertical bars || (Playing state -> show pause icon)
    tft.fillRoundRect(cx - 4, cy - 7, 3, 14, 1, COLOR_TEXT_WHITE);
    tft.fillRoundRect(cx + 2, cy - 7, 3, 14, 1, COLOR_TEXT_WHITE);
  } else {
    // Solid right play triangle > (Paused state -> show play icon)
    tft.fillTriangle(cx - 3, cy - 7, cx - 3, cy + 7, cx + 6, cy, COLOR_TEXT_WHITE);
  }

  // 3. Fast-forward / Next (>>)
  int nx = 140;
  tft.fillTriangle(nx, cy - 5, nx, cy + 5, nx + 4, cy, COLOR_TEXT_WHITE);
  tft.fillTriangle(nx + 5, cy - 5, nx + 5, cy + 5, nx + 9, cy, COLOR_TEXT_WHITE);
}

// Format seconds into M:SS or -M:SS
String formatTime(int sec, bool negative = false) {
  if (sec < 0) sec = 0;
  int m = sec / 60;
  int s = sec % 60;
  char buf[10];
  if (negative) {
    snprintf(buf, sizeof(buf), "-%d:%02d", m, s);
  } else {
    snprintf(buf, sizeof(buf), "%d:%02d", m, s);
  }
  return String(buf);
}

// Draw Progress Bar and Timers (Elapsed & -Remaining)
void drawProgress() {
  int barX = RIGHT_X + 2;
  int barY = 96;
  int barW = RIGHT_W - 4; // ~66 px
  int barH = 3;

  // Background track
  tft.fillRoundRect(barX, barY, barW, barH, 1, COLOR_BAR_BG);

  // Filled progress
  if (track.durationSec > 0) {
    int fillW = (track.progressSec * barW) / track.durationSec;
    if (fillW > barW) fillW = barW;
    if (fillW > 0) {
      tft.fillRoundRect(barX, barY, fillW, barH, 1, COLOR_BAR_FILL);
    }
  }

  // Timestamps under bar
  tft.fillRect(barX - 2, 103, barW + 6, 12, COLOR_BG);
  tft.setTextColor(COLOR_TEXT_MUTED, COLOR_BG);

  // Left: 0:06 (elapsed)
  tft.drawString(formatTime(track.progressSec), barX, 104, 1);

  // Right: -3:22 (remaining)
  int remainSec = track.durationSec - track.progressSec;
  if (remainSec < 0) remainSec = 0;
  String remStr = formatTime(remainSec, true);
  int rw = tft.textWidth(remStr, 1);
  tft.drawString(remStr, barX + barW - rw, 104, 1);
}

// Render complete initial UI
void renderFullUI() {
  tft.fillScreen(COLOR_BG);
  if (!track.hasArt) {
    drawDefaultArtwork();
  }
  drawTopIcons();
  titleScrollOffset = 0;
  scrollPauseCount = 0;
  drawTrackTitle();
  drawArtist();
  drawControls();
  drawProgress();
}

// Receive raw 68x68 RGB565 thumbnail over serial
void receiveArtwork(int width, int height, int totalBytes) {
  tft.setAddrWindow(ART_X, ART_Y, width, height);

  const int CHUNK_SIZE = 128;
  uint8_t buf[CHUNK_SIZE];
  int bytesRead = 0;
  unsigned long startWait = millis();

  while (bytesRead < totalBytes && (millis() - startWait < 3000)) {
    if (Serial.available()) {
      int toRead = min((int)Serial.available(), totalBytes - bytesRead);
      if (toRead > CHUNK_SIZE) toRead = CHUNK_SIZE;
      int r = Serial.readBytes((char*)buf, toRead);
      if (r > 0) {
        bytesRead += r;
        tft.pushColors((uint16_t*)buf, r / 2, true); // true = swap big-endian
        startWait = millis();
      }
    } else {
      delay(2);
    }
  }

  track.hasArt = (bytesRead >= totalBytes);
  if (track.hasArt) {
    roundArtworkCorners();
  } else {
    drawDefaultArtwork();
  }
}

// Process incoming line commands from Python
void processCommand(String line) {
  line.trim();
  if (line.length() == 0) return;

  // Track info: T:<title>\t<artist>\t<album>\t<durationSec>\t<progressSec>\t<isPlaying>\t<hasArt>
  if (line.startsWith("T:")) {
    String payload = line.substring(2);
    int idx0 = payload.indexOf('\t');
    int idx1 = payload.indexOf('\t', idx0 + 1);
    int idx2 = payload.indexOf('\t', idx1 + 1);
    int idx3 = payload.indexOf('\t', idx2 + 1);
    int idx4 = payload.indexOf('\t', idx3 + 1);
    int idx5 = payload.indexOf('\t', idx4 + 1);

    if (idx0 != -1 && idx1 != -1 && idx2 != -1) {
      String newTitle = payload.substring(0, idx0);
      String newArtist = payload.substring(idx0 + 1, idx1);
      String newAlbum = payload.substring(idx1 + 1, idx2);
      
      int dur = 240, prog = 0;
      bool playing = true, art = false;
      
      if (idx3 != -1) dur = payload.substring(idx2 + 1, idx3).toInt();
      if (idx4 != -1) prog = payload.substring(idx3 + 1, idx4).toInt();
      if (idx5 != -1) {
        playing = (payload.substring(idx4 + 1, idx5) == "1");
        art = (payload.substring(idx5 + 1) == "1");
      }

      bool trackChanged = (newTitle != track.title || newArtist != track.artist);
      bool stateChanged = (playing != track.isPlaying);

      track.title = newTitle;
      track.artist = newArtist;
      track.album = newAlbum;
      track.durationSec = dur > 0 ? dur : 240;
      track.progressSec = prog;
      track.isPlaying = playing;
      track.hasArt = art;
      track.lastLocalTick = millis();

      if (trackChanged) {
        if (!track.hasArt) {
          drawDefaultArtwork();
        }
        titleScrollOffset = 0;
        scrollPauseCount = 0;
        drawTrackTitle();
        drawArtist();
        drawControls();
        drawProgress();
      } else {
        if (stateChanged) drawControls();
        drawProgress();
      }
    }
  }
  // Progress heartbeat: P:<progressSec>\t<isPlaying>
  else if (line.startsWith("P:")) {
    String payload = line.substring(2);
    int tab = payload.indexOf('\t');
    if (tab != -1) {
      track.progressSec = payload.substring(0, tab).toInt();
      bool playing = (payload.substring(tab + 1) == "1");
      bool stateChanged = (playing != track.isPlaying);
      track.isPlaying = playing;
      track.lastLocalTick = millis();
      if (stateChanged) drawControls();
      drawProgress();
    }
  }
  // Artwork Header: A:<width>,<height>,<bytes>
  else if (line.startsWith("A:")) {
    String payload = line.substring(2);
    int comma1 = payload.indexOf(',');
    int comma2 = payload.indexOf(',', comma1 + 1);
    if (comma1 != -1 && comma2 != -1) {
      int w = payload.substring(0, comma1).toInt();
      int h = payload.substring(comma1 + 1, comma2).toInt();
      int bytes = payload.substring(comma2 + 1).toInt();
      receiveArtwork(w, h, bytes);
    }
  }
}

// Check push buttons silently
void checkButtons() {
  unsigned long now = millis();

  // 1. BOOT Button (GPIO 0, active LOW) -> Play/Pause
  if (digitalRead(PIN_BOOT_BTN) == LOW) {
    if (now - lastBootPress > DEBOUNCE_MS) {
      lastBootPress = now;
      Serial.println("BTN:PLAYPAUSE");
      track.isPlaying = !track.isPlaying;
      drawControls();
    }
  }

  // 2. Next Button (GPIO 13, active LOW)
  if (digitalRead(PIN_BTN_NEXT) == LOW) {
    if (now - lastNextPress > DEBOUNCE_MS) {
      lastNextPress = now;
      Serial.println("BTN:NEXT");
    }
  }

  // 3. Prev Button (GPIO 14, active LOW)
  if (digitalRead(PIN_BTN_PREV) == LOW) {
    if (now - lastPrevPress > DEBOUNCE_MS) {
      lastPrevPress = now;
      Serial.println("BTN:PREV");
    }
  }

  // 4. External Play Button (GPIO 27, active LOW)
  if (digitalRead(PIN_BTN_PLAY) == LOW) {
    if (now - lastPlayPress > DEBOUNCE_MS) {
      lastPlayPress = now;
      Serial.println("BTN:PLAYPAUSE");
      track.isPlaying = !track.isPlaying;
      drawControls();
    }
  }
}

void setup() {
  // Expand RX buffer to 2048 bytes to prevent UART FIFO overflow during artwork stream
  Serial.setRxBufferSize(2048);
  Serial.begin(115200);
  Serial.setTimeout(100);

  // Configure button pins with internal pullups
  pinMode(PIN_BOOT_BTN, INPUT_PULLUP);
  pinMode(PIN_BTN_NEXT, INPUT_PULLUP);
  pinMode(PIN_BTN_PREV, INPUT_PULLUP);
  pinMode(PIN_BTN_PLAY, INPUT_PULLUP);

  // Initialize display
  tft.init();
  tft.setRotation(3); // Landscape 160x128
  
  // Render minimal clean standby screen
  renderFullUI();

  // Announce ready
  Serial.println("SPOTIFY_DECK_READY");
}

void loop() {
  // 1. Incoming Serial data
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    processCommand(line);
  }

  // 2. Silent Hardware Button checks
  checkButtons();

  // 3. Smooth Marquee scrolling for long titles
  if (track.isPlaying && track.title.length() > TITLE_WINDOW_CHARS) {
    unsigned long now = millis();
    if (now - lastScrollTime >= 350) {
      lastScrollTime = now;
      int maxOffset = track.title.length() - TITLE_WINDOW_CHARS;
      
      if (titleScrollOffset == 0 && scrollPauseCount < 4) {
        scrollPauseCount++;
      } else if (titleScrollOffset >= maxOffset && scrollPauseCount < 8) {
        scrollPauseCount++;
      } else {
        titleScrollOffset++;
        if (titleScrollOffset > maxOffset) {
          titleScrollOffset = 0;
          scrollPauseCount = 0;
        }
        drawTrackTitle();
      }
    }
  }

  // 4. Local timeline interpolation (ticks progress every 1s when playing)
  if (track.isPlaying) {
    unsigned long now = millis();
    if (now - track.lastLocalTick >= 1000) {
      track.lastLocalTick = now;
      if (track.progressSec < track.durationSec) {
        track.progressSec++;
        drawProgress();
      }
    }
  }

  delay(20);
}
