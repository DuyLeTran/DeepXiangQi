"""Standalone script launched as a subprocess to open a Tk file dialog.

This exists because mixing Tkinter and pygame/SDL in the same macOS process can
crash due to NSApplication class conflicts. Running the dialog in a subprocess
isolates Tk from the main game loop.
"""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import filedialog


SUPPORTED_FILETYPES = [
    ("Image files", "*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tiff"),
    ("All files", "*.*"),
]


def main() -> None:
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        path = filedialog.askopenfilename(
            title="Chọn ảnh / Select image",
            filetypes=SUPPORTED_FILETYPES,
        )
    finally:
        root.destroy()

    # Print only the selected path (or empty string) for the parent process.
    sys.stdout.write(path or "")


if __name__ == "__main__":
    main()

