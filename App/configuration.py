from typing import Tuple, Union
from cryptography.fernet import Fernet
import sys
import os
import sqlite3

class Settings:
    """Main configuration class for the XiangQi game."""
    
    # Base dimensions (reference size)
    BASE_WIDTH: int = 810
    BASE_HEIGHT: int = 900
    HEADER_HEIGHT: int = 50
    BASE_PANEL_WIDTH: int = 590
    MIN_PANEL_WIDTH: int = BASE_PANEL_WIDTH // 2
    MIN_PANEL_HEIGHT: int = 180
    
    # Current board dimensions (inside the window, can be updated during runtime)
    WIDTH: int = BASE_WIDTH
    HEIGHT: int = BASE_HEIGHT
    
    # Current window dimensions
    WINDOW_WIDTH: int = BASE_WIDTH + BASE_PANEL_WIDTH
    WINDOW_HEIGHT: int = BASE_HEIGHT + HEADER_HEIGHT
    
    # Computed board layout inside window
    BOARD_X: int = 0
    BOARD_Y: int = HEADER_HEIGHT
    BOARD_SCALE: float = 1.0
    CELL_SIZE: float = 90.0
    PANEL_MODE: str = "right"  # "right" | "bottom" | "hidden"
    PANEL_X: int = BASE_WIDTH
    PANEL_Y: int = HEADER_HEIGHT
    PANEL_W: int = BASE_PANEL_WIDTH
    PANEL_H: int = BASE_HEIGHT
    
    # Scaling factors (will be calculated based on current window size)
    SCALE_X: float = 1.0
    SCALE_Y: float = 1.0
    
    @classmethod
    def update_dimensions(cls, new_width: int, new_height: int) -> None:
        """Update window dimensions and recalculate scaling factors."""
        cls.WIDTH = new_width
        cls.HEIGHT = new_height
        cls.SCALE_X = new_width / cls.BASE_WIDTH
        cls.SCALE_Y = new_height / cls.BASE_HEIGHT

    @classmethod
    def update_window_size(cls, window_width: int, window_height: int) -> None:
        """
        Update runtime window/board layout.
        Board is always fully visible and centered in the current window.
        """
        cls.WINDOW_WIDTH = max(640, int(window_width))
        cls.WINDOW_HEIGHT = max(540, int(window_height))

        available_h = max(100, cls.WINDOW_HEIGHT - cls.HEADER_HEIGHT)
        scale_by_w = cls.WINDOW_WIDTH / cls.BASE_WIDTH
        scale_by_h = available_h / cls.BASE_HEIGHT
        cls.BOARD_SCALE = max(0.45, min(scale_by_w, scale_by_h))

        cls.WIDTH = max(1, int(cls.BASE_WIDTH * cls.BOARD_SCALE))
        cls.HEIGHT = max(1, int(cls.BASE_HEIGHT * cls.BOARD_SCALE))
        cls.CELL_SIZE = 90.0 * cls.BOARD_SCALE

        # Keep original layout behavior: board is anchored to the left.
        cls.BOARD_X = 0
        cls.BOARD_Y = cls.HEADER_HEIGHT

        # Responsive panel placement:
        # - right: if there is enough horizontal room beside the board
        # - bottom: if width is tight but there is enough room below board
        # - hidden: if neither layout has enough room
        right_panel_w = cls.WINDOW_WIDTH - cls.WIDTH
        bottom_panel_h = cls.WINDOW_HEIGHT - (cls.HEADER_HEIGHT + cls.HEIGHT)
        can_show_right = right_panel_w >= cls.MIN_PANEL_WIDTH
        can_show_bottom = bottom_panel_h >= cls.MIN_PANEL_HEIGHT

        if can_show_right:
            cls.PANEL_MODE = "right"
            cls.PANEL_X = cls.WIDTH
            cls.PANEL_Y = cls.HEADER_HEIGHT
            cls.PANEL_W = right_panel_w
            cls.PANEL_H = cls.HEIGHT
        elif can_show_bottom:
            cls.PANEL_MODE = "bottom"
            cls.PANEL_X = 0
            cls.PANEL_Y = cls.HEADER_HEIGHT + cls.HEIGHT
            cls.PANEL_W = cls.WINDOW_WIDTH
            cls.PANEL_H = bottom_panel_h
        else:
            cls.PANEL_MODE = "hidden"
            cls.PANEL_X = 0
            cls.PANEL_Y = 0
            cls.PANEL_W = 0
            cls.PANEL_H = 0

        cls.SCALE_X = cls.BOARD_SCALE
        cls.SCALE_Y = cls.BOARD_SCALE
    
    @classmethod
    def scale_value(cls, value: float, axis: str = 'x') -> float:
        """Scale a value based on the current window size."""
        return value * (cls.SCALE_X if axis == 'x' else cls.SCALE_Y)
    
    # Colors (RGB tuples or hex strings)
    class Colors:
        """Color constants used throughout the game."""
        WHITE: Tuple[int, int, int] = (255, 255, 255)
        BLACK: Tuple[int, int, int] = (0, 0, 0)
        GRAY: Tuple[int, int, int] = (200, 200, 200)
        DARK_GRAY: Tuple[int, int, int] = (169, 169, 169)
        BLUE: Tuple[int, int, int] = (0, 0, 255)
        GREEN: Tuple[int, int, int] = (0, 255, 0)
        RED: Tuple[int, int, int] = (255, 0, 0)
        DARK_GREEN: str = '#33CC33'
        LIGHT_BLUE: str = '#00C9C8'
        BACKGROUND: str = '#FFFDF4'
    
    # Game performance settings
    FPS: int = 120

    # View settings
    FLIPPED: bool = False  # if True, the board is displayed rotated 180 degrees

    # Upload/Gallery settings
    SHOW_UPLOADED_IMAGE: bool = False  # show uploaded image in a Tkinter window
    
    # Show/hide AI results
    DEV_MODE : bool = False

    # Device using for detection
    DEVICE : str = 'cpu'

    # Setup mode settings
    SETUP_MODE: bool = False  # if True, enter piece setup mode
    SETUP_BOARD_SCALE: float = 0.7  # Scale factor for board in setup mode (60% of original)
    
    # Author information (encoded to prevent easy modification)
    @staticmethod
    def get_author() -> str:
        """Get author name. Returns formatted author string."""
        if not os.path.exists('db.sqlite3'):
            return f"Author: Unknown"
        try:
            conn = sqlite3.connect('db.sqlite3')
            cursor = conn.cursor()
            cursor.execute("SELECT author, key FROM author")
            result = cursor.fetchone()
            if result:
                author, key = result
        except Exception :
            return f"Author: Unknown"
        finally:
            conn.close()

        try:
            cipher_suite = Fernet(key.encode('utf-8'))
            decoded = cipher_suite.decrypt(author.encode('utf-8'))
            decoded = decoded.decode('utf-8')
        except Exception :
            return f"Author: Unknown"
        return f"Author: {decoded}"