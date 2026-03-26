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
    
    # Current window dimensions (can be updated during runtime)
    WIDTH: int = BASE_WIDTH
    HEIGHT: int = BASE_HEIGHT
    
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