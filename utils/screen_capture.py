"""Screen-region capture utility.

Public API
----------
capture_screen_region(show_preview) -> Optional[str]
    Hides the pygame window, lets the user drag-select a region of the screen,
    captures it, optionally shows a Tkinter preview, and returns the saved PNG
    path (or None if the user cancelled).

cleanup_temp_files() -> None
    Deletes all temporary capture files created during the session.
    Should be called when the application exits.
"""

import os
import sys
import platform
import subprocess
from typing import Optional, List


_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CAPTURE_SCRIPT = os.path.join(_PROJECT_ROOT, "utils", "_screen_capture.py")

# Track all temp files created during this session
_temp_files: List[str] = []


# ---------------------------------------------------------------------------
# Cross-platform window helpers
# ---------------------------------------------------------------------------

def _minimize_pygame() -> None:
    """Iconify (minimize) the pygame window so the screen is visible."""
    import pygame
    pygame.display.iconify()


def _restore_pygame() -> None:
    """Attempt to restore / un-minimize the pygame window after capture."""
    try:
        import pygame
        system = platform.system()

        if system == "Windows":
            import ctypes
            hwnd = pygame.display.get_wm_info().get("window")
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE = 9
                ctypes.windll.user32.SetForegroundWindow(hwnd)

        elif system == "Linux":
            try:
                title = pygame.display.get_caption()[0]
                subprocess.Popen(
                    ["wmctrl", "-a", title],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except FileNotFoundError:
                pass

    except Exception:
        pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def capture_screen_region(show_preview: bool = True) -> Optional[str]:
    """Hide pygame window, capture a user-selected screen region.

    Steps:
      1. Minimize the pygame window so the desktop is visible.
      2. Run ``_screen_capture.py`` as a blocking subprocess which:
           - takes a full screenshot of the primary monitor,
           - shows a full-screen drag-to-select overlay,
           - crops the selection and writes it to a temp PNG,
           - prints the temp file path to stdout.
      3. Restore the pygame window.
      4. Optionally open the captured image in a Tkinter preview window.

    Args:
        show_preview: When True, display the captured region in a Tkinter
                      window (mirrors the gallery feature behaviour).

    Returns:
        Absolute path of the saved PNG, or None if cancelled / failed.

    Note:
        Temporary files are kept during the session and cleaned up when
        cleanup_temp_files() is called (typically on app exit).
    """
    if sys.platform != "darwin":
        _minimize_pygame()
    
    result = subprocess.run(
        [sys.executable, _CAPTURE_SCRIPT],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )

    if sys.platform != "darwin":
        _restore_pygame()

    image_path = result.stdout.strip()
    if not image_path or not os.path.isfile(image_path):
        return None

    # Track this file for cleanup on exit
    _temp_files.append(image_path)

    if show_preview:
        from utils.image_upload import show_image_window
        show_image_window(image_path)

    return image_path


def cleanup_temp_files() -> None:
    """Delete all temporary capture files created during this session.
    
    This should be called when the application exits to clean up temp files.
    Safe to call multiple times.
    """
    for path in _temp_files:
        try:
            if os.path.isfile(path):
                os.remove(path)
        except Exception:
            pass
    _temp_files.clear()
