"""Standalone script launched as a subprocess for screen-region capture.

Flow:
  1. Sleep briefly so the caller's window finishes hiding.
  2. Take a full screenshot of the primary monitor.
  3. Show a full-screen Tkinter overlay; user drags to select a region.
  4. Crop the screenshot to the selection, save to a temp PNG file.
  5. Print the temp file path to stdout so the parent process can read it.

Usage:
    python _screen_capture.py [delay_seconds]
"""

import sys
import os
import time
import tempfile
import tkinter as tk
from typing import Optional, Tuple


# ---------------------------------------------------------------------------
# Screenshot helpers
# ---------------------------------------------------------------------------

def _take_screenshot():
    """Return a full PIL Image of the primary monitor, or None on failure."""
    # mss is the most reliable cross-platform capture library
    try:
        import mss
        from PIL import Image
        with mss.mss() as sct:
            monitor = sct.monitors[1]  # index 1 = primary monitor
            sct_img = sct.grab(monitor)
            return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
    except ImportError:
        pass

    # Pillow ImageGrab — works on Windows & macOS out of the box
    try:
        from PIL import ImageGrab
        return ImageGrab.grab()
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Region-selector overlay
# ---------------------------------------------------------------------------

class RegionSelector:
    """Full-screen Tkinter overlay that lets the user drag-select a region."""

    def __init__(self, screenshot) -> None:
        self.selection: Optional[Tuple[int, int, int, int]] = None
        self._screenshot = screenshot
        self.operation = sys.platform
        self._start_x = self._start_y = 0
        self._rect_id: Optional[int] = None

        self.root = tk.Tk()
        self.root.withdraw()

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()

        self.root.overrideredirect(True)          # no title bar / decorations
        self.root.geometry(f"{sw}x{sh}+0+0")
        self.root.attributes("-topmost", True)
        
        # macOS specific: ensure fullscreen mode
        if sys.platform == "darwin":
            try:
                self.root.attributes("-fullscreen", True)
            except Exception:
                pass

        self._canvas = tk.Canvas(
            self.root, cursor="crosshair",
            highlightthickness=0, bd=0, bg="#1a1a1a",
        )
        self._canvas.pack(fill=tk.BOTH, expand=True)

        # ------------------------------------------------------------------
        # Background: darkened screenshot (requires Pillow)
        # ------------------------------------------------------------------
        try:
            from PIL import ImageTk, ImageEnhance
            darkened = ImageEnhance.Brightness(screenshot).enhance(0.45)
            self._bg_photo = ImageTk.PhotoImage(darkened)
            self._canvas.create_image(0, 0, image=self._bg_photo, anchor="nw")
        except ImportError:
            # Fallback: plain dark canvas — functional but no preview
            self._canvas.create_rectangle(0, 0, sw, sh, fill="#1a1a1a", outline="")

        # ------------------------------------------------------------------
        # Instruction banner
        # ------------------------------------------------------------------
        if self.operation == "darwin":
            text_id = self._canvas.create_text(
                sw // 2, 30,
                text="  Kéo để chọn vùng cần quét  •  Command + Q để hủy  ",
                fill="white", font=("Arial", 13, "bold"),
            )
        else:
            text_id = self._canvas.create_text(
                sw // 2, 30,
                text="  Kéo để chọn vùng cần quét  •  ESC để hủy  ",
                fill="white", font=("Arial", 13, "bold"),
            )
        bbox = self._canvas.bbox(text_id)
        if bbox:
            self._canvas.create_rectangle(
                bbox[0] - 6, bbox[1] - 5, bbox[2] + 6, bbox[3] + 5,
                fill="#222222", outline="",
            )
            self._canvas.tag_raise(text_id)

        # ------------------------------------------------------------------
        # Bindings
        # ------------------------------------------------------------------
        self._canvas.bind("<Button-1>", self._on_press)
        self._canvas.bind("<B1-Motion>", self._on_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)
        
        # Bind ESC to both root and canvas for better compatibility
        self.root.bind("<Escape>", lambda e: self._cancel())
        self._canvas.bind("<Escape>", lambda e: self._cancel())
        
        # Additional binding for 'q' key as fallback
        self.root.bind("q", lambda e: self._cancel())
        self.root.bind("Q", lambda e: self._cancel())

        self.root.deiconify()
        
        # Force focus after a brief delay (important for macOS)
        self.root.after(100, self._force_focus)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _force_focus(self) -> None:
        """Ensure window has focus - critical for macOS keyboard events."""
        try:
            self.root.focus_force()
            self.root.lift()
            self._canvas.focus_set()
        except Exception:
            pass

    def _clear_rect(self) -> None:
        if self._rect_id is not None:
            self._canvas.delete(self._rect_id)
            self._rect_id = None

    def _on_press(self, event: tk.Event) -> None:
        self._start_x = event.x
        self._start_y = event.y
        self._clear_rect()

    def _on_drag(self, event: tk.Event) -> None:
        self._clear_rect()
        x1 = min(self._start_x, event.x)
        y1 = min(self._start_y, event.y)
        x2 = max(self._start_x, event.x)
        y2 = max(self._start_y, event.y)
        self._rect_id = self._canvas.create_rectangle(
            x1, y1, x2, y2,
            outline="#FF3333", width=2, dash=(6, 3),
        )

    def _on_release(self, event: tk.Event) -> None:
        x1 = min(self._start_x, event.x)
        y1 = min(self._start_y, event.y)
        x2 = max(self._start_x, event.x)
        y2 = max(self._start_y, event.y)
        if x2 - x1 < 10 or y2 - y1 < 10:
            return  # selection too small, wait for another drag
        self.selection = (x1, y1, x2, y2)
        self.root.destroy()

    def _cancel(self) -> None:
        self.selection = None
        self.root.destroy()

    def run(self) -> Optional[Tuple[int, int, int, int]]:
        self.root.mainloop()
        return self.selection


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    delay = float(sys.argv[1]) if len(sys.argv) > 1 else 0.35
    time.sleep(delay)

    screenshot = _take_screenshot()
    if screenshot is None:
        print("ERROR: screenshot failed — install Pillow or mss", file=sys.stderr)
        sys.exit(1)

    try:
        selector = RegionSelector(screenshot)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    region = selector.run()
    if region is None:
        sys.exit(0)  # user cancelled

    x1, y1, x2, y2 = region
    cropped = screenshot.crop((x1, y1, x2, y2))

    tmp = tempfile.NamedTemporaryFile(
        suffix=".png", delete=False, prefix="xiangqi_capture_",
    )
    tmp.close()  # close before writing so Windows allows access
    cropped.save(tmp.name, "PNG")
    print(tmp.name, flush=True)


if __name__ == "__main__":
    main()
