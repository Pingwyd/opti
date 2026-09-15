"""Shared tray/window icon helpers (Pillow + Qt)."""

from __future__ import annotations

from PyQt6.QtGui import QIcon, QImage, QPixmap


def make_tray_icon_image():
    """Create a simple tray icon with Pillow (no external asset required)."""
    from PIL import Image, ImageDraw

    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Dark rounded square with coral spark accent
    draw.rounded_rectangle((4, 4, size - 4, size - 4), radius=14, fill=(20, 20, 22, 255))
    draw.ellipse((22, 20, 42, 40), fill=(240, 128, 96, 230))
    draw.ellipse((30, 34, 44, 48), fill=(240, 128, 96, 140))
    return img


def app_icon() -> QIcon:
    """Shared window/tray icon so Qt never falls back to the framework logo."""
    img = make_tray_icon_image()
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    data = img.tobytes("raw", "RGBA")
    qimg = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
    return QIcon(QPixmap.fromImage(qimg))
