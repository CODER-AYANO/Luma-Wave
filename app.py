import sys
import os
import ctypes
import winreg

import numpy as np
from PIL import Image

import pyaudiowpatch as pyaudio

from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QPainter, QPainterPath, QColor, QBrush, QIcon, QPixmap, QAction
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QSystemTrayIcon,
    QMenu,
    QMessageBox,
)

import win32gui
import win32con
import win32api


# =============================================================
# Configuration
# =============================================================

APP_NAME = "WallpaperVisualizer"
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"

# Visualizer layout
BAR_WIDTH = 10
BAR_GAP = 6

CENTER_GAP = 300

MAX_BAR_HEIGHT = 200

FPS_INTERVAL = 16

# Audio
FFT_SIZE = 2048
AUDIO_BUFFER_SIZE = 4096

SILENCE_THRESHOLD = 0.002

# Animation
ATTACK_SPEED = 0.45
DECAY_SPEED = 0.14

CORNER_RADIUS = 5


# =============================================================
# Windows Startup Manager
# =============================================================

class StartupManager:

    @staticmethod
    def get_app_path():
        if getattr(sys, "frozen", False):
            return f'"{sys.executable}"'

        return f'"{sys.executable}" "{os.path.abspath(__file__)}"'

    @classmethod
    def is_startup_enabled(cls):
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                REG_PATH,
                0,
                winreg.KEY_READ
            )

            winreg.QueryValueEx(key, APP_NAME)
            winreg.CloseKey(key)

            return True

        except FileNotFoundError:
            return False

        except Exception:
            return False

    @classmethod
    def set_startup(cls, enable: bool):

        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                REG_PATH,
                0,
                winreg.KEY_WRITE
            )

            if enable:

                winreg.SetValueEx(
                    key,
                    APP_NAME,
                    0,
                    winreg.REG_SZ,
                    cls.get_app_path()
                )

            else:

                try:
                    winreg.DeleteValue(key, APP_NAME)

                except FileNotFoundError:
                    pass

            winreg.CloseKey(key)

            return True

        except Exception as e:

            print(f"Startup registry error: {e}")

            return False


# =============================================================
# Wallpaper Color Extraction
# =============================================================

class WallpaperColorExtractor:

    @staticmethod
    def get_wallpaper_path():

        try:

            buffer = ctypes.create_unicode_buffer(512)

            ctypes.windll.user32.SystemParametersInfoW(
                win32con.SPI_GETDESKWALLPAPER,
                len(buffer),
                buffer,
                0
            )

            path = buffer.value

            if path and os.path.exists(path):
                return path

        except Exception:
            pass

        # Windows transcoded wallpaper fallback
        appdata = os.environ.get("APPDATA", "")

        fallback = os.path.join(
            appdata,
            r"Microsoft\Windows\Themes\TranscodedWallpaper"
        )

        if os.path.exists(fallback):
            return fallback

        return None

    @classmethod
    def extract_palette(cls, image_path, count=5):

        default_palette = [
            QColor(120, 160, 215),
            QColor(220, 140, 100),
            QColor(180, 120, 200),
            QColor(100, 200, 220),
            QColor(160, 210, 160),
        ]

        if not image_path or not os.path.exists(image_path):
            return default_palette

        try:

            img = Image.open(image_path).convert("RGB")

            width, height = img.size

            # Focus on the lower portion of the wallpaper
            img = img.crop(
                (
                    0,
                    int(height * 0.35),
                    width,
                    height
                )
            )

            img.thumbnail((160, 160))

            quantized = img.quantize(
                colors=24,
                method=Image.Quantize.MEDIANCUT
            ).convert("RGB")

            colors = quantized.getcolors(maxcolors=256)

            if not colors:
                return default_palette

            vibrant = []

            for _, (r, g, b) in sorted(
                colors,
                reverse=True,
                key=lambda x: x[0]
            ):

                maximum = max(r, g, b)
                minimum = min(r, g, b)

                saturation = (
                    (maximum - minimum) /
                    (maximum + 1e-5)
                )

                brightness = (r + g + b) / 3.0

                if (
                    35 < brightness < 235
                    and saturation > 0.12
                ):
                    vibrant.append(QColor(r, g, b))

                if len(vibrant) >= count:
                    break

            if len(vibrant) >= 2:
                return vibrant

        except Exception as e:

            print(f"Wallpaper color error: {e}")

        return default_palette


# =============================================================
# Main Visualizer
# =============================================================

class WallpaperVisualizer(QWidget):

    def __init__(self):

        super().__init__()

        # -----------------------------------------------------
        # State
        # -----------------------------------------------------

        self.last_wallpaper = None

        self.palette = []

        self.bar_colors = []

        # Computed dynamically in update_taskbar_position
        self.bars_per_side = 52

        self.values = np.zeros(
            self.bars_per_side,
            dtype=np.float32
        )

        self.target_values = np.zeros(
            self.bars_per_side,
            dtype=np.float32
        )

        self.opacity = 0.0

        self.is_silent = True

        # Audio sample storage
        self.audio_buffer = np.zeros(
            FFT_SIZE * 2,
            dtype=np.float32
        )

        self.audio_lock = False

        self.stream = None

        # -----------------------------------------------------
        # Window
        # -----------------------------------------------------

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )

        self.setAttribute(
            Qt.WA_TranslucentBackground,
            True
        )

        self.setAttribute(
            Qt.WA_ShowWithoutActivating,
            True
        )

        # -----------------------------------------------------
        # Setup
        # -----------------------------------------------------

        self.init_clickthrough()

        self.refresh_wallpaper_colors()

        self.init_audio()

        self.update_taskbar_position()

        # -----------------------------------------------------
        # Rendering timer
        # -----------------------------------------------------

        self.render_timer = QTimer(self)

        self.render_timer.timeout.connect(
            self.update_frame
        )

        self.render_timer.start(FPS_INTERVAL)

        # -----------------------------------------------------
        # System polling
        # -----------------------------------------------------

        self.poll_timer = QTimer(self)

        self.poll_timer.timeout.connect(
            self.poll_system_state
        )

        self.poll_timer.start(2000)


    # =========================================================
    # Window setup
    # =========================================================

    def init_clickthrough(self):

        hwnd = int(self.winId())

        extended_style = win32gui.GetWindowLong(
            hwnd,
            win32con.GWL_EXSTYLE
        )

        win32gui.SetWindowLong(
            hwnd,
            win32con.GWL_EXSTYLE,
            extended_style
            | win32con.WS_EX_TRANSPARENT
            | win32con.WS_EX_LAYERED
            | win32con.WS_EX_TOOLWINDOW
        )


    # =========================================================
    # Wallpaper
    # =========================================================

    def refresh_wallpaper_colors(self):

        wall_path = (
            WallpaperColorExtractor
            .get_wallpaper_path()
        )

        if (
            wall_path != self.last_wallpaper
            or not self.palette
        ):

            self.last_wallpaper = wall_path

            self.palette = (
                WallpaperColorExtractor
                .extract_palette(
                    wall_path,
                    count=5
                )
            )

            self.generate_bar_gradient()


    def generate_bar_gradient(self):

        self.bar_colors = []

        if not self.palette:
            return

        color_count = len(self.palette)

        for i in range(self.bars_per_side):

            position = (
                i / max(1, self.bars_per_side - 1)
            ) * (color_count - 1)

            index = int(position)

            fraction = position - index

            c1 = self.palette[
                min(index, color_count - 1)
            ]

            c2 = self.palette[
                min(index + 1, color_count - 1)
            ]

            r = int(
                c1.red()
                + (c2.red() - c1.red())
                * fraction
            )

            g = int(
                c1.green()
                + (c2.green() - c1.green())
                * fraction
            )

            b = int(
                c1.blue()
                + (c2.blue() - c1.blue())
                * fraction
            )

            self.bar_colors.append(
                QColor(r, g, b)
            )


    # =========================================================
    # Position
    # =========================================================

    def update_taskbar_position(self):

        try:

            monitor = win32api.MonitorFromPoint(
                (0, 0),
                win32con.MONITOR_DEFAULTTONEAREST
            )

            monitor_info = win32api.GetMonitorInfo(monitor)

            monitor_rect = monitor_info["Monitor"]
            work_area = monitor_info["Work"]

            screen_width = (
                monitor_rect[2] - monitor_rect[0]
            )

            # Dynamically compute bar count to
            # fill the full screen width.
            # Each side mirrors the other, so
            # total bars = 2 * bars_per_side.
            new_bars = int(
                (screen_width - CENTER_GAP + BAR_GAP)
                / (2 * (BAR_WIDTH + BAR_GAP))
            )

            new_bars = max(new_bars, 10)

            if new_bars != self.bars_per_side:

                self.bars_per_side = new_bars

                self.values = np.zeros(
                    self.bars_per_side,
                    dtype=np.float32
                )

                self.target_values = np.zeros(
                    self.bars_per_side,
                    dtype=np.float32
                )

                self.generate_bar_gradient()

            side_width = (
                self.bars_per_side * BAR_WIDTH
                + (self.bars_per_side - 1) * BAR_GAP
            )

            total_width = side_width * 2 + CENTER_GAP

            x_pos = (
                monitor_rect[0]
                + (screen_width - total_width) // 2
            )

            # Sit flush on top of the taskbar
            y_pos = (
                work_area[3]
                - MAX_BAR_HEIGHT
            )

            self.setGeometry(
                x_pos,
                y_pos,
                total_width,
                MAX_BAR_HEIGHT
            )

        except Exception as e:

            print(
                f"Positioning error: {e}"
            )


    # =========================================================
    # Audio
    # =========================================================

    def init_audio(self):

        try:

            self.p = pyaudio.PyAudio()

            wasapi_info = (
                self.p.get_host_api_info_by_type(
                    pyaudio.paWASAPI
                )
            )

            default_device = (
                self.p.get_device_info_by_index(
                    wasapi_info[
                        "defaultOutputDevice"
                    ]
                )
            )

            # Find WASAPI loopback device
            if not default_device.get(
                "isLoopbackDevice",
                False
            ):

                loopback_device = None

                for device in (
                    self.p
                    .get_loopback_device_info_generator()
                ):

                    if (
                        default_device["name"]
                        in device["name"]
                    ):

                        loopback_device = device
                        break

                if loopback_device is None:

                    raise RuntimeError(
                        "Could not find WASAPI loopback device."
                    )

                default_device = loopback_device

            self.audio_channels = int(
                default_device[
                    "maxInputChannels"
                ]
            )

            self.sample_rate = int(
                default_device[
                    "defaultSampleRate"
                ]
            )

            print(
                "Audio device:",
                default_device["name"]
            )

            print(
                "Channels:",
                self.audio_channels
            )

            print(
                "Sample rate:",
                self.sample_rate
            )

            # -------------------------------------------------
            # Audio callback ONLY captures data.
            # No FFT here.
            # -------------------------------------------------

            self.stream = self.p.open(
                format=pyaudio.paFloat32,

                channels=self.audio_channels,

                rate=self.sample_rate,

                input=True,

                input_device_index=(
                    default_device["index"]
                ),

                frames_per_buffer=AUDIO_BUFFER_SIZE,

                stream_callback=self.audio_callback
            )

            self.stream.start_stream()

            print("WASAPI loopback started.")

        except Exception as e:

            print(
                f"Audio initialization failed: {e}"
            )

            self.stream = None


    def audio_callback(
        self,
        in_data,
        frame_count,
        time_info,
        status
    ):

        try:

            audio = np.frombuffer(
                in_data,
                dtype=np.float32
            )

            if len(audio) == 0:
                return (
                    None,
                    pyaudio.paContinue
                )

            # -------------------------------------------------
            # Stereo/interleaved → mono
            # -------------------------------------------------

            channels = max(
                1,
                self.audio_channels
            )

            usable_length = (
                len(audio) // channels
            ) * channels

            audio = audio[
                :usable_length
            ]

            if channels > 1:

                audio = audio.reshape(
                    -1,
                    channels
                ).mean(axis=1)

            # -------------------------------------------------
            # Keep only the latest samples
            # -------------------------------------------------

            if len(audio) >= len(
                self.audio_buffer
            ):

                self.audio_buffer[:] = (
                    audio[-len(self.audio_buffer):]
                )

            else:

                self.audio_buffer = np.roll(
                    self.audio_buffer,
                    -len(audio)
                )

                self.audio_buffer[
                    -len(audio):
                ] = audio

        except Exception as e:

            print(
                f"Audio callback error: {e}"
            )

        return (
            None,
            pyaudio.paContinue
        )


    # =========================================================
    # FFT
    # =========================================================

    def process_audio(self):

        audio = self.audio_buffer.copy()

        if len(audio) < FFT_SIZE:
            return

        # Remove DC offset
        audio -= np.mean(audio)

        rms = np.sqrt(
            np.mean(audio * audio)
        )

        if rms < SILENCE_THRESHOLD:

            self.is_silent = True

            self.target_values.fill(0)

            return

        self.is_silent = False

        # -----------------------------------------------------
        # Window function
        # -----------------------------------------------------

        samples = audio[-FFT_SIZE:]

        window = np.hanning(
            FFT_SIZE
        )

        samples = samples * window

        # -----------------------------------------------------
        # FFT
        # -----------------------------------------------------

        spectrum = np.abs(
            np.fft.rfft(samples)
        )

        spectrum /= FFT_SIZE

        # Ignore DC
        spectrum[:2] = 0

        # -----------------------------------------------------
        # Logarithmic frequency distribution
        # -----------------------------------------------------

        frequencies = np.linspace(
            0,
            self.sample_rate / 2,
            len(spectrum)
        )

        min_frequency = 30
        max_frequency = min(
            self.sample_rate / 2,
            16000
        )

        edges = np.geomspace(
            min_frequency,
            max_frequency,
            self.bars_per_side + 1
        )

        result = np.zeros(
            self.bars_per_side,
            dtype=np.float32
        )

        for i in range(self.bars_per_side):

            low = edges[i]
            high = edges[i + 1]

            mask = (
                (frequencies >= low)
                & (frequencies < high)
            )

            if np.any(mask):

                result[i] = np.mean(
                    spectrum[mask]
                )

        # -----------------------------------------------------
        # Compress dynamic range
        # -----------------------------------------------------

        result = np.log1p(
            result * 100
        )

        # Normalize based on a stable reference
        result = np.clip(
            result / 1.8,
            0.0,
            1.0
        )

        # Slight bass emphasis
        bass_curve = np.linspace(
            1.15,
            0.9,
            self.bars_per_side
        )

        result *= bass_curve

        result = np.clip(
            result,
            0.0,
            1.0
        )

        self.target_values = result


    # =========================================================
    # Animation
    # =========================================================

    def update_frame(self):

        # FFT happens on the Qt thread,
        # NOT inside the audio callback.
        self.process_audio()

        if self.is_silent:

            self.opacity = max(
                0.0,
                self.opacity - 0.06
            )

        else:

            self.opacity = min(
                1.0,
                self.opacity + 0.12
            )

        # -----------------------------------------------------
        # Smooth bar animation
        # -----------------------------------------------------

        difference = (
            self.target_values
            - self.values
        )

        rising = difference > 0

        self.values[rising] += (
            difference[rising]
            * ATTACK_SPEED
        )

        self.values[~rising] += (
            difference[~rising]
            * DECAY_SPEED
        )

        self.values = np.clip(
            self.values,
            0.0,
            1.0
        )

        self.update()


    # =========================================================
    # Painting
    # =========================================================

    def paintEvent(self, event):

        if self.opacity <= 0.001:
            return

        painter = QPainter(self)

        painter.setRenderHint(
            QPainter.Antialiasing,
            True
        )

        painter.setPen(Qt.NoPen)

        height = self.height()

        side_width = (
            self.bars_per_side * BAR_WIDTH
            + (self.bars_per_side - 1) * BAR_GAP
        )

        total_width = side_width * 2 + CENTER_GAP

        start_x = (
            self.width() - total_width
        ) / 2

        # ---------------------------------------------------------
        # LEFT + RIGHT MIRRORED VISUALIZER
        # ---------------------------------------------------------

        for i in range(self.bars_per_side):

            value = float(
                self.values[i]
            )

            bar_height = int(
                value * (MAX_BAR_HEIGHT - 10)
            )

            if bar_height < 3:
                bar_height = 3

            # -------------------------------------------------
            # LEFT
            # -------------------------------------------------

            left_x = (
                start_x
                + i * (BAR_WIDTH + BAR_GAP)
            )

            left_y = (
                height - bar_height
            )

            # -------------------------------------------------
            # RIGHT
            # -------------------------------------------------

            right_x = (
                start_x
                + side_width
                + CENTER_GAP
                + (
                    self.bars_per_side
                    - 1
                    - i
                ) * (BAR_WIDTH + BAR_GAP)
            )

            right_y = (
                height - bar_height
            )

            # -------------------------------------------------
            # Color
            # -------------------------------------------------

            if i < len(self.bar_colors):

                color = QColor(
                    self.bar_colors[i]
                )

            else:

                color = QColor(
                    160,
                    180,
                    220
                )

            color.setAlphaF(
                0.85 * self.opacity
            )

            painter.setBrush(
                QBrush(color)
            )

            # LEFT BAR
            path = QPainterPath()
            path.moveTo(left_x, left_y + bar_height)
            path.lineTo(left_x, left_y + CORNER_RADIUS)
            path.quadTo(
                left_x, left_y,
                left_x + CORNER_RADIUS, left_y
            )
            path.lineTo(
                left_x + BAR_WIDTH - CORNER_RADIUS,
                left_y
            )
            path.quadTo(
                left_x + BAR_WIDTH, left_y,
                left_x + BAR_WIDTH,
                left_y + CORNER_RADIUS
            )
            path.lineTo(
                left_x + BAR_WIDTH,
                left_y + bar_height
            )
            path.closeSubpath()
            painter.drawPath(path)

            # RIGHT BAR
            path = QPainterPath()
            path.moveTo(right_x, right_y + bar_height)
            path.lineTo(right_x, right_y + CORNER_RADIUS)
            path.quadTo(
                right_x, right_y,
                right_x + CORNER_RADIUS, right_y
            )
            path.lineTo(
                right_x + BAR_WIDTH - CORNER_RADIUS,
                right_y
            )
            path.quadTo(
                right_x + BAR_WIDTH, right_y,
                right_x + BAR_WIDTH,
                right_y + CORNER_RADIUS
            )
            path.lineTo(
                right_x + BAR_WIDTH,
                right_y + bar_height
            )
            path.closeSubpath()
            painter.drawPath(path)

        painter.end()


    # =========================================================
    # Polling
    # =========================================================

    def poll_system_state(self):

        self.update_taskbar_position()

        self.refresh_wallpaper_colors()


    # =========================================================
    # Cleanup
    # =========================================================

    def closeEvent(self, event):

        try:

            if self.stream:

                self.stream.stop_stream()
                self.stream.close()

            if hasattr(self, "p"):

                self.p.terminate()

        except Exception:
            pass

        event.accept()


# =============================================================
# System Tray
# =============================================================

class SystemTrayApp:

    def __init__(
        self,
        visualizer,
        app
    ):

        self.visualizer = visualizer
        self.app = app

        self.tray = QSystemTrayIcon()

        self.tray.setIcon(
            self.create_tray_icon()
        )

        self.tray.setToolTip(
            "Audio Wallpaper Visualizer"
        )

        self.menu = QMenu()

        self.setup_menu()

        self.tray.setContextMenu(
            self.menu
        )

        self.tray.show()


    def create_tray_icon(self):

        pixmap = QPixmap(
            64,
            64
        )

        pixmap.fill(
            Qt.transparent
        )

        painter = QPainter(
            pixmap
        )

        painter.setRenderHint(
            QPainter.Antialiasing
        )

        bars = [
            0.3,
            0.7,
            1.0,
            0.5,
            0.8,
            0.4,
        ]

        bar_width = 6
        gap = 4

        start_x = (
            64
            - (
                len(bars)
                * (bar_width + gap)
                - gap
            )
        ) // 2

        painter.setPen(
            Qt.NoPen
        )

        for i, value in enumerate(bars):

            bar_height = int(
                value * 42
            )

            x = (
                start_x
                + i * (bar_width + gap)
            )

            y = 54 - bar_height

            painter.setBrush(
                QBrush(
                    QColor(
                        100,
                        180,
                        255
                    )
                )
            )

            painter.drawRoundedRect(
                QRectF(
                    x,
                    y,
                    bar_width,
                    bar_height
                ),
                2,
                2
            )

        painter.end()

        return QIcon(pixmap)


    def setup_menu(self):

        # -----------------------------------------------------
        # Startup
        # -----------------------------------------------------

        self.startup_action = QAction(
            "Start with Windows",
            self.menu
        )

        self.startup_action.setCheckable(
            True
        )

        self.startup_action.setChecked(
            StartupManager.is_startup_enabled()
        )

        self.startup_action.triggered.connect(
            self.toggle_startup
        )

        self.menu.addAction(
            self.startup_action
        )

        self.menu.addSeparator()


        # -----------------------------------------------------
        # Wallpaper
        # -----------------------------------------------------

        reload_action = QAction(
            "Refresh Wallpaper Colors",
            self.menu
        )

        reload_action.triggered.connect(
            self.visualizer.refresh_wallpaper_colors
        )

        self.menu.addAction(
            reload_action
        )

        self.menu.addSeparator()

        # -----------------------------------------------------
        # Exit
        # -----------------------------------------------------

        quit_action = QAction(
            "Exit Visualizer",
            self.menu
        )

        quit_action.triggered.connect(
            self.app.quit
        )

        self.menu.addAction(
            quit_action
        )


    def toggle_startup(self, checked):

        success = (
            StartupManager
            .set_startup(checked)
        )

        if not success:

            self.startup_action.setChecked(
                not checked
            )

            QMessageBox.warning(
                None,
                "Error",
                "Failed to update Windows startup registry."
            )


# =============================================================
# Main
# =============================================================

if __name__ == "__main__":

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)

    # Keep running even though the overlay itself is not
    # a normal application window.
    app.setQuitOnLastWindowClosed(False)

    visualizer = WallpaperVisualizer()

    visualizer.show()

    tray_app = SystemTrayApp(
        visualizer,
        app
    )

    print("Wallpaper Visualizer running.")

    sys.exit(
        app.exec()
    )