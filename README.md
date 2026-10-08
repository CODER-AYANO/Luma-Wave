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
