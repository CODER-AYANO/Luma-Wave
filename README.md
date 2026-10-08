# 🎵 Wallpaper Visualizer

A lightweight Windows desktop audio visualizer that reacts to system audio and displays a smooth mirrored spectrum over your wallpaper.

The visualizer captures system audio using WASAPI loopback, processes it with a real-time FFT, and renders animated bars using PySide6.

## ✨ Features

- 🎵 Real-time system audio visualization
- 🪞 Mirrored left and right spectrum
- 🎨 Wallpaper-derived gradient colors
- ⚡ Smooth FFT-based animation
- 🖥️ Transparent desktop overlay
- 🖱️ Click-through overlay
- 🔊 WASAPI loopback audio capture
- 📊 Logarithmic frequency distribution
- 🎚️ Smooth attack and decay animation
- 🖼️ Automatically extracts colors from the current wallpaper
- 🔄 Refresh wallpaper colors from the system tray
- 🚀 Optional Start with Windows support
- 📦 Standalone Windows executable available through GitHub Releases

---

## 🖥️ Preview

The visualizer sits near the bottom of the desktop and reacts to whatever audio is currently playing.

The left and right sides are exact mirrors of the same audio spectrum, with a gap in the center.

<img width="1919" height="1199" alt="Screenshot 2026-10-08 211824" src="https://github.com/user-attachments/assets/90464b2f-908b-4b51-80f7-835c6a141a90" />
<img width="1919" height="1199" alt="Screenshot 2026-10-08 211813" src="https://github.com/user-attachments/assets/7ee02144-fc27-431b-9b6e-ba5bd3e31d0e" />
<img width="1919" height="1199" alt="Screenshot 2026-10-08 211758" src="https://github.com/user-attachments/assets/c545510e-980c-4012-a40f-263ad62be0cd" />
<img width="1919" height="1199" alt="Screenshot 2026-10-08 211745" src="https://github.com/user-attachments/assets/70a39eaf-aaaf-4c73-9527-8427482f2fde" />
<img width="1919" height="1198" alt="Screenshot 2026-10-08 211726" src="https://github.com/user-attachments/assets/74d5ef5f-d51d-4b5a-bb93-76df00e617fc" />

---

## 🛠️ Tech Stack

- **Python**
- **PySide6** — transparent GUI and rendering
- **NumPy** — FFT and audio processing
- **PyAudioWPatch** — WASAPI loopback audio capture
- **Pillow** — wallpaper color extraction
- **pywin32** — Windows API integration

---

## 📋 Requirements

- Windows 10 / Windows 11
- Python 3.10+
- A Windows audio output device
- WASAPI-compatible audio playback

---

# 🚀 Installation

## Download the executable

The easiest way to use Wallpaper Visualizer is to download the latest Windows executable from the GitHub Releases page.

Download:

```text
WallpaperVisualizer.exe
