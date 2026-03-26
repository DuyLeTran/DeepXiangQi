"""Image upload utility: cross-platform file dialog and optional Tkinter preview."""

import os
import sys
import subprocess
from typing import Optional


_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_VIEWER_SCRIPT = os.path.join(_PROJECT_ROOT, "utils", "_image_viewer.py")
_FILE_DIALOG_SCRIPT = os.path.join(_PROJECT_ROOT, "utils", "_file_dialog.py")

_SUPPORTED_FILETYPES = [
    ("Image files", "*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tiff"),
    ("All files", "*.*"),
]


def open_image_dialog() -> Optional[str]:
    """Open a native cross-platform file dialog to select an image file.

    Returns the absolute path to the selected file, or None if cancelled.
    """
    # On macOS, mixing Tkinter with pygame/SDL in the same process can crash
    # (NSApplication subclass conflicts). Run the dialog in a subprocess.
    if sys.platform == "darwin":
        try:
            out = subprocess.check_output(
                [sys.executable, _FILE_DIALOG_SCRIPT],
                stderr=subprocess.DEVNULL,
                text=True,
            )
            path = (out or "").strip()
            return path or None
        except Exception:
            return None

    # On other OSes, running Tk in-process is usually fine and avoids the
    # subprocess overhead.
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        path = filedialog.askopenfilename(
            title="Chọn ảnh / Select image",
            filetypes=_SUPPORTED_FILETYPES,
        )
    finally:
        root.destroy()
    return path or None


def show_image_window(image_path: str) -> None:
    """Launch a separate subprocess that displays *image_path* in a Tkinter window.

    Running in a subprocess ensures the viewer's Tkinter event loop is fully
    isolated from the main pygame event loop and works correctly on every OS
    (including macOS, which requires Tkinter to run on the process main thread).
    """
    subprocess.Popen(
        [sys.executable, _VIEWER_SCRIPT, image_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def upload_image(show_preview: bool = True) -> Optional[str]:
    """Open a file dialog for the user to select an image from their computer.

    Args:
        show_preview: When True, display the selected image in a Tkinter window.

    Returns:
        Absolute path of the selected image, or None if the dialog was cancelled.
    """
    path = open_image_dialog()
    if path and show_preview:
        show_image_window(path)
    return path
