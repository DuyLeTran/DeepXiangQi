"""Standalone script launched as a subprocess to display an image in a Tkinter window."""

import sys
import os
import tkinter as tk
from pathlib import Path


def _load_photo(root: tk.Tk, image_path: str):
    """Load image using Pillow if available, else fall back to native tkinter."""
    try:
        from PIL import Image, ImageTk
        img = Image.open(image_path)
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        max_w = min(screen_w - 100, 900)
        max_h = min(screen_h - 100, 700)
        img.thumbnail((max_w, max_h), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        return photo, img.width, img.height
    except ImportError:
        pass

    # Native tkinter fallback (supports PNG and GIF on all platforms)
    photo = tk.PhotoImage(file=image_path)
    w, h = photo.width(), photo.height()
    if w > 900 or h > 700:
        factor = max(w // 900, h // 700) + 1
        photo = photo.subsample(factor, factor)
        w, h = photo.width(), photo.height()
    return photo, w, h


def main() -> None:
    if len(sys.argv) < 2:
        return
    image_path = sys.argv[1]
    if not os.path.isfile(image_path):
        return

    root = tk.Tk()
    root.title(Path(image_path).name)

    try:
        photo, w, h = _load_photo(root, image_path)
    except Exception as e:
        tk.Label(root, text=f"Cannot display image:\n{e}", padx=20, pady=20).pack()
        root.mainloop()
        return

    label = tk.Label(root, image=photo)
    label.image = photo  # keep reference to prevent GC
    label.pack()

    # Center window on screen
    root.update_idletasks()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    x = (sw - w) // 2
    y = (sh - h) // 2
    root.geometry(f"{w}x{h}+{x}+{y}")
    root.resizable(True, True)

    root.mainloop()


if __name__ == "__main__":
    main()
