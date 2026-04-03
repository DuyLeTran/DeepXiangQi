"""Subprocess entry for JSON open/save dialogs (macOS: avoids Tk + pygame in one process).

Usage:
  python utils/_game_dialog.py open
  python utils/_game_dialog.py save
Prints selected path to stdout (empty if cancelled).
"""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import filedialog

_SAVE_TYPES = [
    ("Xiangqi save", "*.xqsave"),
    ("JSON (legacy)", "*.json"),
    ("All files", "*.*"),
]
_OPEN_TYPES = [
    ("Xiangqi save", "*.xqsave"),
    ("JSON", "*.json"),
    ("All files", "*.*"),
]


def main() -> None:
    mode = (sys.argv[1] if len(sys.argv) > 1 else "open").lower()
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        if mode == "save":
            path = filedialog.asksaveasfilename(
                title="Lưu ván cờ / Save game",
                defaultextension=".xqsave",
                filetypes=_SAVE_TYPES,
            )
        else:
            path = filedialog.askopenfilename(
                title="Mở ván cờ / Open game",
                filetypes=_OPEN_TYPES,
            )
    finally:
        root.destroy()

    sys.stdout.write(path or "")


if __name__ == "__main__":
    main()
