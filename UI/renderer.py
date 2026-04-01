import pygame
import sys
import os
import math
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from App.configuration import Settings
from App.position import Position
from App.piece import ChessBoard, ChessPiece
from App.rule import Rule
from utils.flip import FlipAnimator
from UI.book import BookView
from UI.record import RecordView
class UIRenderer:
    """Class responsible for rendering UI elements and game state"""
    
    def __init__(self, screen: pygame.Surface, chess_board: ChessBoard, rule: Rule):
        self.screen = screen
        self.chess_board = chess_board
        self.rule = rule
        self.font_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Roboto Font", "Roboto-Regular.ttf")
        self.font = pygame.font.Font(self.font_path, 42)
        # Tab state
        self.tabs_labels = ["Khai cuộc", "Động cơ", "Biên bản"]
        self.tabs_rects: list[pygame.Rect] = []
        self.current_tab_index: int = 0
        # Menu dropdown state
        self.menu_is_open: bool = False
        # self.menu_items = ["Tạo mới", "Sắp quân", "Sao chép FEN", "Dán FEN", "Nhập FEN", "Mở ván cờ","Lưu ván cờ", "Thoát"]
        self.menu_items = ["Tạo mới", "Sắp quân", "Sao chép FEN", "Dán FEN", "Mở ván cờ","Lưu ván cờ", "Thoát"]
        self.menu_item_rects: list[pygame.Rect] = []
        # Menu animation state (encapsulated inside draw_menu_sidebar)
        self._menu_anim_start: int = 0  # 0 = no animation, >0 = animation start timestamp
        self._menu_anim_target: bool = False  # Target open/close state
        # Map menu items to their icon paths (None if no icon)
        project_root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.menu_item_icons = {
            "Tạo mới"      : os.path.join(project_root, "assets", "Menu_bar", "new.png"),
            "Sắp quân"     : os.path.join(project_root, "assets", "Menu_bar", "layer.png"),
            "Sao chép FEN" : os.path.join(project_root, "assets", "Menu_bar", "copy.png"),
            "Dán FEN"      : os.path.join(project_root, "assets", "Menu_bar", "paste.png"),
            # "Nhập FEN"     : os.path.join(project_root, "assets", "Menu_bar", "input.png"),
            "Mở ván cờ"    : os.path.join(project_root, "assets", "Menu_bar", "open.png"),
            "Lưu ván cờ"   : os.path.join(project_root, "assets", "Menu_bar", "save.png"),
            "Thoát"        : os.path.join(project_root, "assets", "Menu_bar", "exit.png"),
        }
        # Cache for already-loaded icons
        self._menu_icon_cache: dict[str, pygame.Surface] = {}
        # Subviews
        self.book_view = BookView(self.screen, self.font_path)
        self.record_view = RecordView(self.screen, self.font_path)
        # Flip animator (delegated logic)
        self._flip_animator = FlipAnimator(
            screen=self.screen,
            chess_board=self.chess_board,
            get_background=lambda: getattr(self, '_background_image', None),
            draw_border=self.draw_border,
            draw_rotate_button=self.draw_rotate_button,
            draw_all_ui=lambda sp, vm: self.draw_all_ui_except_pieces(sp, vm),
        )
        # Backward button click animation state
        self._backward_click_time: int = 0  # 0 means not clicked, >0 means click timestamp
        # Forward button click animation state
        self._forward_click_time: int = 0  # 0 means not clicked, >0 means click timestamp
        # Expand button click animation state
        self._expand_click_time: int = 0  # 0 means not clicked, >0 means click timestamp
        # Add button dropdown menu state
        self.add_menu_is_open: bool = False
        # Initialize menu item rects to avoid AttributeError
        self.camera_rect = pygame.Rect(0, 0, 0, 0)
        self.gallery_rect = pygame.Rect(0, 0, 0, 0)
        self.add_menu_bg_rect = pygame.Rect(0, 0, 0, 0)
        # Notification system
        self.notification_message: str | None = None
        self.notification_start_time: int | None = None
        self.NOTIFICATION_DURATION = 4000  # 4 seconds in milliseconds
        # Checkmate notification state
        self.checkmate_notification_active: bool = False
        self.checkmate_notification_dismissed: bool = False  # Track if user dismissed it
        self.checkmate_close_button_rect: pygame.Rect = pygame.Rect(0, 0, 0, 0)  # Close button rect
    def draw_background(self, background_image: pygame.Surface) -> None:
        """Draw the chess board background, always in original orientation (never rotate)"""
        # remember the last background used so animations can reuse it
        self._background_image = background_image
        self.screen.fill(Settings.Colors.BACKGROUND)
        
        # Draw board background using dynamic layout
        if Settings.SETUP_MODE:
            scale = Settings.SETUP_BOARD_SCALE
            scaled_width = int(Settings.WIDTH * scale)
            scaled_height = int(Settings.HEIGHT * scale)
            scaled_background = pygame.transform.scale(background_image, (scaled_width, scaled_height))
            
            bg_x = Settings.BOARD_X + (Settings.WIDTH - scaled_width) // 2
            bg_y = Settings.BOARD_Y + (Settings.HEIGHT - scaled_height) // 2
            
            self.screen.blit(scaled_background, (bg_x, bg_y))
        else:
            scaled_background = pygame.transform.scale(background_image, (Settings.WIDTH, Settings.HEIGHT))
            self.screen.blit(scaled_background, (Settings.BOARD_X, Settings.BOARD_Y))
    
    def draw_border(self) -> None:
        """Draw the UI border"""
        if Settings.PANEL_MODE == "hidden":
            return
        border_function = pygame.Rect(Settings.PANEL_X, Settings.PANEL_Y, Settings.PANEL_W, Settings.PANEL_H)
        pygame.draw.rect(self.screen, Settings.Colors.BLACK, border_function, 1)

    def is_side_panel_visible(self) -> bool:
        return Settings.PANEL_MODE in ("right", "bottom") and Settings.PANEL_W > 0 and Settings.PANEL_H > 0

    def _get_side_panel_rect(self) -> pygame.Rect:
        if not self.is_side_panel_visible():
            return pygame.Rect(0, 0, 0, 0)
        return pygame.Rect(Settings.PANEL_X, Settings.PANEL_Y, Settings.PANEL_W, Settings.PANEL_H)

    def _sync_panel_viewports(self) -> tuple[pygame.Rect, pygame.Rect]:
        """
        Sync Book/Record viewports with current panel layout.
        Returns (tabs_rect, content_rect).
        """
        panel_rect = self._get_side_panel_rect()
        if panel_rect.width <= 0 or panel_rect.height <= 0:
            empty = pygame.Rect(0, 0, 0, 0)
            if hasattr(self.book_view, "set_viewport"):
                self.book_view.set_viewport(empty)
            if hasattr(self.record_view, "set_viewport"):
                self.record_view.set_viewport(empty)
            return empty, empty

        tab_h = min(50, max(34, panel_rect.height // 5))
        tabs_rect = pygame.Rect(panel_rect.x, panel_rect.bottom - tab_h, panel_rect.width, tab_h)
        content_rect = pygame.Rect(panel_rect.x, panel_rect.y, panel_rect.width, max(0, panel_rect.height - tab_h))

        if hasattr(self.book_view, "set_viewport"):
            self.book_view.set_viewport(content_rect)
        if hasattr(self.record_view, "set_viewport"):
            self.record_view.set_viewport(content_rect)
        return tabs_rect, content_rect
    
    def draw_pieces(self) -> None:
        """Draw all chess pieces"""
        self.chess_board.draw(self.screen)
    
    def draw_old_position_selection(self) -> None:
        """Draw selection highlight at old position"""
        # Prefer the record view's game tree as the source of truth
        
        tree = getattr(self, 'record_view', None)
        if tree is None or not hasattr(tree, 'game_tree'):
            return 
        current = tree.game_tree.current
        move_str = getattr(current, 'move', None)
        if not move_str:
            return 
        # Extract first coordinate pair from move string, robust to formats with '->'
        try:
            first_l = move_str.find('(')
            first_r = move_str.find(')', first_l + 1)
            if first_l == -1 or first_r == -1:
                return 
            coord = move_str[first_l + 1:first_r]
            x_str, y_str = coord.split(',')
            old_position = (int(x_str), int(y_str))
        except Exception:
            return 

        # if selected_piece is not None and Position.calculate_position(old_position) != Position.calculate_position(selected_piece.position):
        
        cx, cy = Position.calculate_position(old_position)
        radius = 10
        line = max(radius-20, 5)
        top_left_center = (cx-radius, cy-radius)
        top_right_center = (cx+radius, cy-radius)
        bottom_left_center = (cx-radius, cy+radius)
        bottom_right_center = (cx+radius, cy+radius)

        pygame.draw.line(self.screen, Settings.Colors.WHITE, top_left_center, (top_left_center[0]+line, top_left_center[1]), 3)
        pygame.draw.line(self.screen, Settings.Colors.WHITE, top_left_center, (top_left_center[0], top_left_center[1]+line), 3)

        pygame.draw.line(self.screen, Settings.Colors.WHITE, top_right_center, (top_right_center[0]-line, top_right_center[1]), 3)
        pygame.draw.line(self.screen, Settings.Colors.WHITE, top_right_center, (top_right_center[0], top_right_center[1]+line), 3)

        pygame.draw.line(self.screen, Settings.Colors.WHITE, bottom_left_center, (bottom_left_center[0]+line, bottom_left_center[1]), 3)
        pygame.draw.line(self.screen, Settings.Colors.WHITE, bottom_left_center, (bottom_left_center[0], bottom_left_center[1]-line), 3)

        pygame.draw.line(self.screen, Settings.Colors.WHITE, bottom_right_center, (bottom_right_center[0]-line, bottom_right_center[1]), 3)
        pygame.draw.line(self.screen, Settings.Colors.WHITE, bottom_right_center, (bottom_right_center[0], bottom_right_center[1]-line), 3)

    def draw_new_position_selection(self) -> None:
        """Draw selection highlight at new position"""
        # Prefer the record view's game tree as the source of truth
        
        tree = getattr(self, 'record_view', None)
        if tree is None or not hasattr(tree, 'game_tree'):
            return 
        current = tree.game_tree.current
        move_str = getattr(current, 'move', None)
        if not move_str:
            return 
        # Extract first coordinate pair from move string, robust to formats with '->'
        try:
            first_l = move_str.find('(')
            first_r = move_str.find(')', first_l + 1)

            second_l = move_str.find('(', first_r + 1)
            second_r = move_str.find(')', second_l + 1)

            if first_l == -1 or first_r == -1 or second_l == -1 or second_r == -1:
                return 
            coord = move_str[second_l + 1:second_r]
            x_str, y_str = coord.split(',')
            new_position = (int(x_str), int(y_str))
        except Exception:
            return 

        # if selected_piece is not None and Position.calculate_position(old_position) != Position.calculate_position(selected_piece.position):
        
        cx, cy = Position.calculate_position(new_position)
        scale = Settings.BOARD_SCALE * (Settings.SETUP_BOARD_SCALE if Settings.SETUP_MODE else 1.0)
        radius = max(18, int(40 * scale))
        line = max(int(20 * scale), 3)
        stroke = max(1, int(3 * scale))
        top_left_center = (cx-radius, cy-radius)
        top_right_center = (cx+radius, cy-radius)
        bottom_left_center = (cx-radius, cy+radius)
        bottom_right_center = (cx+radius, cy+radius)

        pygame.draw.line(self.screen, Settings.Colors.GREEN, top_left_center, (top_left_center[0]+line, top_left_center[1]), stroke)
        pygame.draw.line(self.screen, Settings.Colors.GREEN, top_left_center, (top_left_center[0], top_left_center[1]+line), stroke)

        pygame.draw.line(self.screen, Settings.Colors.GREEN, top_right_center, (top_right_center[0]-line, top_right_center[1]), stroke)
        pygame.draw.line(self.screen, Settings.Colors.GREEN, top_right_center, (top_right_center[0], top_right_center[1]+line), stroke)

        pygame.draw.line(self.screen, Settings.Colors.GREEN, bottom_left_center, (bottom_left_center[0]+line, bottom_left_center[1]), stroke)
        pygame.draw.line(self.screen, Settings.Colors.GREEN, bottom_left_center, (bottom_left_center[0], bottom_left_center[1]-line), stroke)

        pygame.draw.line(self.screen, Settings.Colors.GREEN, bottom_right_center, (bottom_right_center[0]-line, bottom_right_center[1]), stroke)
        pygame.draw.line(self.screen, Settings.Colors.GREEN, bottom_right_center, (bottom_right_center[0], bottom_right_center[1]-line), stroke)

    def draw_selected_piece(self, selected_piece: ChessPiece | None) -> None:
        """Draw highlight around selected piece"""
        if selected_piece is not None:
            cx, cy = Position.calculate_position(selected_piece.position)
            scale = Settings.BOARD_SCALE * (Settings.SETUP_BOARD_SCALE if Settings.SETUP_MODE else 1.0)
            radius = max(16, int(44 * scale))
            stroke = max(1, int(2 * scale))
            pygame.draw.circle(self.screen, Settings.Colors.GREEN, (int(cx + 2 * scale), int(cy + 1 * scale)), radius, stroke)
    
    def draw_valid_moves(self, valid_moves: list[tuple[int, int]]) -> None:
        """Draw valid move indicators"""
        scale = Settings.BOARD_SCALE * (Settings.SETUP_BOARD_SCALE if Settings.SETUP_MODE else 1.0)
        marker_radius = max(4, int(10 * scale))
        for mv in valid_moves:
            mx, my = Position.calculate_position(mv)
            pygame.draw.circle(self.screen, Settings.Colors.LIGHT_BLUE, (mx, my), marker_radius)
    
    def draw_in_check(self) -> None:
        """Draw check status with translucent overlay and text"""
        is_in_check = self.rule.is_in_check('red' if self.chess_board.turn == 'red' else 'black')
        if not is_in_check:
            return

        if self.checkmate_notification_dismissed: return

        # Translucent red band across the general area
        band_rect = pygame.Rect(135, 455, 540, 90)
        overlay = pygame.Surface((band_rect.width, band_rect.height), pygame.SRCALPHA)
        overlay.fill((255, 0, 0, 200))  # RGBA with alpha for transparency
        self.screen.blit(overlay, (band_rect.x, band_rect.y))

        # Text centered on the band
        label = "CHIẾU TƯỚNG"
        self.font.set_bold(True)
        text_surface = self.font.render(label, True, Settings.Colors.WHITE)
        self.font.set_bold(False)
        text_rect = text_surface.get_rect(center=band_rect.center)
        self.screen.blit(text_surface, text_rect)
        

    def draw_checkmate(self) -> None:
        """Draw checkmate status with translucent banner and text"""
        is_checkmate = self.rule.is_checkmate('red' if self.chess_board.turn == 'red' else 'black')
        
        # If there's no checkmate, reset the notification state
        if not is_checkmate:
            self.checkmate_notification_active = False
            self.checkmate_notification_dismissed = False
            return
        
        # If there's checkmate and notification hasn't been dismissed, activate it
        if is_checkmate and not self.checkmate_notification_dismissed:
            self.checkmate_notification_active = True
        
        # Only show if notification is still active (not dismissed)
        if not self.checkmate_notification_active or self.checkmate_notification_dismissed:
            return
        # Large translucent banner across the middle of the board
        # Board drawing origin at (0, 50), board size ~ 810x900
        banner_rect = pygame.Rect(60, 405, 690, 185)
        overlay = pygame.Surface((banner_rect.width, banner_rect.height), pygame.SRCALPHA)
        # Use darker overlay for stronger emphasis
        overlay.fill((0, 0, 0, 230))
        self.screen.blit(overlay, (banner_rect.x, banner_rect.y))

        # Winner/loser text
        label = "CHIẾU HẾT - ĐỎ THUA" if self.chess_board.turn == 'red' else "CHIẾU HẾT - ĐEN THUA"
        self.font.set_bold(True)
        if label == "CHIẾU HẾT - ĐEN THUA":
            text_surface = self.font.render(label, True, Settings.Colors.WHITE)
        else:
            text_surface = self.font.render(label, True, Settings.Colors.RED)
        self.font.set_bold(False)
        text_rect = text_surface.get_rect(center=banner_rect.center)
        self.screen.blit(text_surface, text_rect)
        
        # Draw close button (X in circle) at top-right corner
        close_button_radius = 20
        close_button_x = banner_rect.right - 5
        close_button_y = banner_rect.top + 5
        close_button_center = (close_button_x, close_button_y)
        
        # Draw circle background (semi-transparent white)
        circle_surface = pygame.Surface((close_button_radius * 2 + 4, close_button_radius * 2 + 4), pygame.SRCALPHA)
        # pygame.draw.circle(circle_surface, (255, 0, 0, 180), (close_button_radius + 2, close_button_radius + 2), close_button_radius)
        pygame.draw.circle(circle_surface, (255, 0, 0), (close_button_radius + 2, close_button_radius + 2), close_button_radius)
        self.screen.blit(circle_surface, (close_button_x - close_button_radius - 2, close_button_y - close_button_radius - 2))
        
        # Draw circle border
        pygame.draw.circle(self.screen, Settings.Colors.BLACK, close_button_center, close_button_radius, 2)
        
        # Draw X symbol
        x_size = 10
        pygame.draw.line(
            self.screen, 
            Settings.Colors.WHITE,
            (close_button_x - x_size, close_button_y - x_size),
            (close_button_x + x_size, close_button_y + x_size),
            3
        )
        pygame.draw.line(
            self.screen,
            Settings.Colors.WHITE,
            (close_button_x + x_size, close_button_y - x_size),
            (close_button_x - x_size, close_button_y + x_size),
            3
        )
        
        # Store button rect for click detection
        self.checkmate_close_button_rect = pygame.Rect(
            close_button_x - close_button_radius,
            close_button_y - close_button_radius,
            close_button_radius * 2,
            close_button_radius * 2
        )
    
    def render_all(self, background_image: pygame.Surface, selected_piece, old_position: tuple[int, int], valid_moves: list[tuple[int, int]]) -> None:
        """Render all UI elements in one call"""
        self.draw_background(background_image)
        self.draw_border()
        self.draw_pieces()
        self.draw_old_position_selection(selected_piece)
        self.draw_selected_piece(selected_piece)
        self.draw_valid_moves(valid_moves)
        self.draw_in_check()
        self.draw_checkmate()
        self.draw_rotate_button()
        self.draw_right_menu_buttons()
        # self.book()
    
    def draw_menu_button(self) -> None:
        """Draw the menu button icon at fixed position"""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        menu_path = os.path.join(project_root, "assets", "menu.png")
        try:
            menu_image = pygame.image.load(menu_path).convert_alpha()
            menu_image = pygame.transform.scale(menu_image, (35, 35))
        except Exception:
            menu_image = None
        # Place menu button at (30, 7)
        menu_pos = (30, 7)

        # Compute rect after scaling (keep original size if None)
        if menu_image is not None:
            self.menu_rect = menu_image.get_rect(topleft=menu_pos)
            self.screen.blit(menu_image, menu_pos)
        else:
            self.menu_rect = pygame.Rect(menu_pos[0], menu_pos[1], 0, 0)
            # Fallback: draw a placeholder circle if asset not found
            pygame.draw.circle(self.screen, Settings.Colors.GRAY, (menu_pos[0] + 20, menu_pos[1] + 20), 20, 2)

    def draw_rotate_button(self) -> None:
        """Draw the rotate button icon at fixed position"""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        rotate_path = os.path.join(project_root, "assets", "rotate.png")
        
        try:
            rotate_image = pygame.image.load(rotate_path).convert_alpha()
            rotate_image = pygame.transform.scale(rotate_image, (45, 45))
        except Exception:
            rotate_image = None
        # Place rotate button at (135, 5)
        rotate_pos = (85, 0)

        # Draw DARK_GRAY background around the rotate button when FLIPPED = True
        is_animating = self.is_animating() if hasattr(self, 'is_animating') else False
        
        # Show background if:
        # 1. FLIPPED = True and NOT currently animating (animation already finished)
        # 2. Currently animating and the target state is True (i.e. currently FLIPPED = False)
        # Do NOT show when: FLIPPED = True and currently animating (will flip back to False)
        should_show_bg = (Settings.FLIPPED and not is_animating) or (is_animating and not Settings.FLIPPED)
        
        if should_show_bg:
            # Background is slightly larger than the button
            bg_padding = 5
            bg_rect = pygame.Rect(
                rotate_pos[0] - bg_padding,
                rotate_pos[1] - bg_padding,
                45 + bg_padding * 2,
                45 + bg_padding * 2
            )
            pygame.draw.rect(self.screen, Settings.Colors.DARK_GRAY, bg_rect)

        # Compute rect after scaling (keep original size if None)
        if rotate_image is not None:
            self.rotate_rect = rotate_image.get_rect(topleft=rotate_pos)
            self.screen.blit(rotate_image, rotate_pos)
        else:
            self.rotate_rect = pygame.Rect(rotate_pos[0], rotate_pos[1], 0, 0)
            # Fallback: draw a placeholder circle if asset not found
            pygame.draw.circle(self.screen, Settings.Colors.GRAY, (rotate_pos[0] + 20, rotate_pos[1] + 20), 20, 2)
    
    def draw_forward_backward_buttons(self) -> None:
        """Draw the forward and backward button icons at fixed position"""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        forward_path = os.path.join(project_root, "assets", "forward.png")
        backward_path = os.path.join(project_root, "assets", "backward.png")

        try:
            forward_image = pygame.image.load(forward_path).convert_alpha()
            forward_image = pygame.transform.scale(forward_image, (40, 40))
            backward_image = pygame.image.load(backward_path).convert_alpha()
            backward_image = pygame.transform.scale(backward_image, (40, 40))
        except Exception:
            forward_image = None
            backward_image = None
        # Place forward and backward buttons at (110, 0) and (110, 45)
        backward_pos = (145, 5)
        forward_pos = (200, 5)
        
        # Draw backward button with click animation
        if backward_image is not None:
            # Check if we should show click animation (within 0.1s after click)
            if self._backward_click_time > 0:
                current_time = pygame.time.get_ticks()
                elapsed = current_time - self._backward_click_time
                click_duration = 100  # 0.1 seconds = 100 milliseconds
                
                if elapsed < click_duration:
                    # Draw DARK_GRAY background for click effect
                    bg_padding = 5
                    bg_rect = pygame.Rect(
                        backward_pos[0] - bg_padding,
                        backward_pos[1] - bg_padding,
                        40 + bg_padding * 2,
                        40 + bg_padding * 2
                    )
                    pygame.draw.rect(self.screen, Settings.Colors.DARK_GRAY, bg_rect)
                else:
                    # Animation finished, reset
                    self._backward_click_time = 0
            
            self.backward_rect = backward_image.get_rect(topleft=backward_pos)
            self.screen.blit(backward_image, backward_pos)
        else:
            self.backward_rect = pygame.Rect(backward_pos[0], backward_pos[1], 0, 0)
            # Fallback: draw a placeholder circle if asset not found
            pygame.draw.circle(self.screen, Settings.Colors.GRAY, (backward_pos[0] + 20, backward_pos[1] + 20), 20, 2)
        
        # Draw forward button with click animation
        if forward_image is not None:
            # Check if we should show click animation (within 0.1s after click)
            if self._forward_click_time > 0:
                current_time = pygame.time.get_ticks()
                elapsed = current_time - self._forward_click_time
                click_duration = 100  # 0.1 seconds = 100 milliseconds
                
                if elapsed < click_duration:
                    # Draw DARK_GRAY background for click effect
                    bg_padding = 5
                    bg_rect = pygame.Rect(
                        forward_pos[0] - bg_padding,
                        forward_pos[1] - bg_padding,
                        40 + bg_padding * 2,
                        40 + bg_padding * 2
                    )
                    pygame.draw.rect(self.screen, Settings.Colors.DARK_GRAY, bg_rect)
                else:
                    # Animation finished, reset
                    self._forward_click_time = 0
            
            self.forward_rect = forward_image.get_rect(topleft=forward_pos)
            self.screen.blit(forward_image, forward_pos)
        else:
            self.forward_rect = pygame.Rect(forward_pos[0], forward_pos[1], 0, 0)
            # Fallback: draw a placeholder circle if asset not found
            pygame.draw.circle(self.screen, Settings.Colors.GRAY, (forward_pos[0] + 20, forward_pos[1] + 20), 20, 2)
    
    def draw_red_and_black_computer(self) -> None:
        """Draw both red and black computer buttons and set their rects."""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        red_computer_path = os.path.join(project_root, "assets", "red_computer.png")
        black_computer_path = os.path.join(project_root, "assets", "black_computer.png")

        # Load images with safe fallbacks
        try:
            red_img = pygame.image.load(red_computer_path).convert_alpha()
            red_img = pygame.transform.scale(red_img, (50, 40))
        except Exception:
            red_img = None
        try:
            black_img = pygame.image.load(black_computer_path).convert_alpha()
            black_img = pygame.transform.scale(black_img, (50, 40))
        except Exception:
            black_img = None

        red_pos = (250, 5)
        black_pos = (310, 5)

        if red_img is not None:
            self.red_computer_rect = red_img.get_rect(topleft=red_pos)
            self.screen.blit(red_img, red_pos)
        else:
            self.red_computer_rect = pygame.Rect(red_pos[0], red_pos[1], 0, 0)
            pygame.draw.circle(self.screen, Settings.Colors.GRAY, (red_pos[0] + 20, red_pos[1] + 20), 20, 2)

        if black_img is not None:
            self.black_computer_rect = black_img.get_rect(topleft=black_pos)
            self.screen.blit(black_img, black_pos)
        else:
            self.black_computer_rect = pygame.Rect(black_pos[0], black_pos[1], 0, 0)
            pygame.draw.circle(self.screen, Settings.Colors.GRAY, (black_pos[0] + 20, black_pos[1] + 20), 20, 2)

    def draw_magnifying_glass_button(self) -> None:
        """Draw the magnifying glass button icon at fixed position"""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        magnifying_glass_path = os.path.join(project_root, "assets", "magnifying_glass.png")
        try:
            magnifying_glass_image = pygame.image.load(magnifying_glass_path).convert_alpha()
            magnifying_glass_image = pygame.transform.scale(magnifying_glass_image, (40, 40))
        except Exception:
            magnifying_glass_image = None
        # Place magnifying glass button at (250, 5)
        magnifying_glass_pos = (375, 5)
        if magnifying_glass_image is not None:
            self.magnifying_glass_rect = magnifying_glass_image.get_rect(topleft=magnifying_glass_pos)
            self.screen.blit(magnifying_glass_image, magnifying_glass_pos)
        else:
            self.magnifying_glass_rect = pygame.Rect(magnifying_glass_pos[0], magnifying_glass_pos[1], 0, 0)
            pygame.draw.circle(self.screen, Settings.Colors.GRAY, (magnifying_glass_pos[0] + 20, magnifying_glass_pos[1] + 20), 20, 2)

    def draw_general_button(self, pos: tuple[int, int] = None) -> None:
        """Draw the general button icon at fixed position"""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # Place general button at (430, 5)
        general_pos = pos if pos is not None else (430, 5)
        if self.chess_board.turn == 'red':
            general_path = os.path.join(project_root, "assets", "xiangqi_red_general.png")
        else:
            general_path = os.path.join(project_root, "assets", "xiangqi_black_general.png")

        try:
            general_image = pygame.image.load(general_path).convert_alpha()
            general_image = pygame.transform.scale(general_image, (40, 40))
        except Exception:
            general_image = None
            
        if general_image is not None:
                self.general_rect = general_image.get_rect(topleft=general_pos)
                self.screen.blit(general_image, general_pos)
        else:
                self.general_rect = pygame.Rect(general_pos[0], general_pos[1], 0, 0)
                pygame.draw.circle(self.screen, Settings.Colors.GRAY, (general_pos[0] + 20, general_pos[1] + 20), 20, 2)

    def draw_add_button(self) -> None:
        """Draw the add button icon at fixed position"""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        add_path = os.path.join(project_root, "assets", "add.png")
        # Place add button at (530, 5)
        add_pos = (487, 5)
        try:
            add_image = pygame.image.load(add_path).convert_alpha()
            add_image = pygame.transform.scale(add_image, (40, 40))
        except Exception:
            add_image = None
            
        if add_image is not None:
                self.add_rect = add_image.get_rect(topleft=add_pos)
                self.screen.blit(add_image, add_pos)
        else:
                self.add_rect = pygame.Rect(add_pos[0], add_pos[1], 0, 0)
                pygame.draw.circle(self.screen, Settings.Colors.GRAY, (add_pos[0] + 20, add_pos[1] + 20), 20, 2)
        
        # Draw dropdown menu if open
        if self.add_menu_is_open:
            self.draw_add_menu(add_pos)
    
    def draw_add_menu(self, add_pos: tuple[int, int]) -> None:
        """Draw the add button dropdown menu with camera and gallery options"""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        camera_path = os.path.join(project_root, "assets", "camera.png")
        gallery_path = os.path.join(project_root, "assets", "gallery.png")
        
        # Position menu items right below the add button, arranged horizontally
        menu_item_size = 40
        menu_spacing = 20
        menu_start_y = add_pos[1] + 40 + 5
        
        # Calculate positions for horizontal layout
        camera_pos = (add_pos[0]-30, menu_start_y)
        gallery_pos = (add_pos[0]-30 + menu_item_size + menu_spacing, menu_start_y)
        
        # Draw white background for both icons
        bg_padding = 5
        total_width = (menu_item_size + menu_spacing) * 2 - menu_spacing + bg_padding * 2
        total_height = menu_item_size + bg_padding * 2
        bg_rect = pygame.Rect(
            camera_pos[0] - bg_padding,
            menu_start_y - bg_padding,
            total_width,
            total_height
        )
        pygame.draw.rect(self.screen, Settings.Colors.WHITE, bg_rect)
        # Store menu background rect for click detection
        self.add_menu_bg_rect = bg_rect
        
        # Draw camera button
        try:
            camera_image = pygame.image.load(camera_path).convert_alpha()
            camera_image = pygame.transform.scale(camera_image, (menu_item_size+5, menu_item_size))
        except Exception:
            camera_image = None
        
        if camera_image is not None:
            self.camera_rect = camera_image.get_rect(topleft=camera_pos)
            self.screen.blit(camera_image, camera_pos)
        else:
            self.camera_rect = pygame.Rect(camera_pos[0], camera_pos[1], 0, 0)
            pygame.draw.circle(self.screen, Settings.Colors.GRAY, (camera_pos[0] + 20, camera_pos[1] + 20), 20, 2)
        
        # Draw gallery button
        try:
            gallery_image = pygame.image.load(gallery_path).convert_alpha()
            gallery_image = pygame.transform.scale(gallery_image, (menu_item_size, menu_item_size))
        except Exception:
            gallery_image = None
        
        if gallery_image is not None:
            self.gallery_rect = gallery_image.get_rect(topleft=gallery_pos)
            self.screen.blit(gallery_image, gallery_pos)
        else:
            self.gallery_rect = pygame.Rect(gallery_pos[0], gallery_pos[1], 0, 0)
            pygame.draw.circle(self.screen, Settings.Colors.GRAY, (gallery_pos[0] + 20, gallery_pos[1] + 20), 20, 2)
    def draw_expand_button(self) -> None: 
        """Draw the expand button icon at fixed position"""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        expand_path = os.path.join(project_root, "assets", "Arrange", "expand.png")

        try:
            expand_image = pygame.image.load(expand_path).convert_alpha()
            expand_image = pygame.transform.scale(expand_image, (40, 40))
        except Exception:
            expand_image = None
        # Place expand button at (145, 5)
        expand_pos = (150, 5)
        
        # Draw expand button with click animation
        if expand_image is not None:
            # Check if we should show click animation (within 0.1s after click)
            if self._expand_click_time > 0:
                current_time = pygame.time.get_ticks()
                elapsed = current_time - self._expand_click_time
                click_duration = 100  # 0.1 seconds = 100 milliseconds
                
                if elapsed < click_duration:
                    # Draw DARK_GRAY background for click effect
                    bg_padding = 5
                    bg_rect = pygame.Rect(
                        expand_pos[0] - bg_padding,
                        expand_pos[1] - bg_padding,
                        40 + bg_padding * 2,
                        40 + bg_padding * 2
                    )
                    pygame.draw.rect(self.screen, Settings.Colors.DARK_GRAY, bg_rect)
                else:
                    # Animation finished, reset
                    self._expand_click_time = 0
            
            self.expand_rect = expand_image.get_rect(topleft=expand_pos)
            self.screen.blit(expand_image, expand_pos)
        else:
            self.expand_rect = pygame.Rect(expand_pos[0], expand_pos[1], 0, 0)
            # Fallback: draw a placeholder circle if asset not found
            pygame.draw.circle(self.screen, Settings.Colors.GRAY, (expand_pos[0] + 20, expand_pos[1] + 20), 20, 2)
    def draw_tick_button(self) -> None: 
        """Draw the tick button icon at fixed position"""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        tick_path = os.path.join(project_root, "assets", "Arrange", "tick.png")

        try:
            tick_image = pygame.image.load(tick_path).convert_alpha()
            tick_image = pygame.transform.scale(tick_image, (40, 40))
        except Exception:
            tick_image = None
        # Place tick button at (145, 5)
        tick_pos = (210, 5)
        
        # Draw tick button
        if tick_image is not None:
            self.tick_rect = tick_image.get_rect(topleft=tick_pos)
            self.screen.blit(tick_image, tick_pos)
        else:
            self.tick_rect = pygame.Rect(tick_pos[0], tick_pos[1], 0, 0)
            # Fallback: draw a placeholder circle if asset not found
            pygame.draw.circle(self.screen, Settings.Colors.GRAY, (tick_pos[0] + 20, tick_pos[1] + 20), 20, 2)
        
    def is_tick_clicked(self, mouse_pos: tuple[int, int]) -> bool:
        """Return True if the tick button was clicked"""
        return hasattr(self, 'tick_rect') and self.tick_rect.collidepoint(mouse_pos)
   
    def is_expand_clicked(self, mouse_pos: tuple[int, int]) -> bool:
        """Return True if the expand button was clicked"""
        return hasattr(self, 'expand_rect') and self.expand_rect.collidepoint(mouse_pos)
    
    def on_expand_clicked(self) -> None:
        """Trigger click animation for expand button"""
        self._expand_click_time = pygame.time.get_ticks()
    
    def is_general_clicked(self, mouse_pos: tuple[int, int]) -> bool:
        """Return True if the general button was clicked"""
        return hasattr(self, 'general_rect') and self.general_rect.collidepoint(mouse_pos)

    def is_add_button_clicked(self, mouse_pos: tuple[int, int]) -> bool:
        """Return True if the add button was clicked"""
        return hasattr(self, 'add_rect') and self.add_rect.collidepoint(mouse_pos)
    
    def toggle_add_menu(self) -> None:
        """Toggle the add button dropdown menu"""
        self.add_menu_is_open = not self.add_menu_is_open
    
    def is_camera_clicked(self, mouse_pos: tuple[int, int]) -> bool:
        """Return True if the camera button was clicked"""
        return self.add_menu_is_open and hasattr(self, 'camera_rect') and self.camera_rect.collidepoint(mouse_pos)
    
    def is_gallery_clicked(self, mouse_pos: tuple[int, int]) -> bool:
        """Return True if the gallery button was clicked"""
        return self.add_menu_is_open and hasattr(self, 'gallery_rect') and self.gallery_rect.collidepoint(mouse_pos)
    
    def is_click_in_add_menu_area(self, mouse_pos: tuple[int, int]) -> bool:
        """Return True if click is within add button or menu area"""
        if not self.add_menu_is_open:
            return False
        # Check if click is in add button
        if hasattr(self, 'add_rect') and self.add_rect.collidepoint(mouse_pos):
            return True
        # Check if click is in menu background area
        if hasattr(self, 'add_menu_bg_rect') and self.add_menu_bg_rect.collidepoint(mouse_pos):
            return True
        # Check if click is in camera or gallery buttons
        if hasattr(self, 'camera_rect') and self.camera_rect.collidepoint(mouse_pos):
            return True
        if hasattr(self, 'gallery_rect') and self.gallery_rect.collidepoint(mouse_pos):
            return True
        return False

    def is_rotate_clicked(self, mouse_pos: tuple[int, int]) -> bool:
        """Return True if the rotate button was clicked"""
        return self.rotate_rect.collidepoint(mouse_pos)
    
    def is_backward_clicked(self, mouse_pos: tuple[int, int]) -> bool:
        """Return True if the backward button was clicked"""
        return hasattr(self, 'backward_rect') and self.backward_rect.collidepoint(mouse_pos)
    
    def on_backward_clicked(self) -> None:
        """Trigger click animation for backward button"""
        self._backward_click_time = pygame.time.get_ticks()
    
    def is_forward_clicked(self, mouse_pos: tuple[int, int]) -> bool:
        """Return True if the forward button was clicked"""
        return hasattr(self, 'forward_rect') and self.forward_rect.collidepoint(mouse_pos)
    
    def on_forward_clicked(self) -> None:
        """Trigger click animation for forward button"""
        self._forward_click_time = pygame.time.get_ticks()

    def is_menu_clicked(self, mouse_pos: tuple[int, int]) -> bool:
        """Return True if the menu button was clicked"""
        return self.menu_rect.collidepoint(mouse_pos)

    def toggle_menu(self) -> None:
        """Toggle menu sidebar visibility (starts animation)."""
        self._menu_anim_target = not self.menu_is_open
        self._menu_anim_start = pygame.time.get_ticks()

    def _get_menu_offset_x(self) -> int:
        """Helper method để tính offset x của menu (dùng chung logic với draw_menu_sidebar)"""
        sidebar_width = 280
        animation_duration = 100
        
        if self._menu_anim_start > 0:
            now = pygame.time.get_ticks()
            elapsed = now - self._menu_anim_start
            t = min(1.0, elapsed / animation_duration)
            if t >= 1.0:
                return 0 if self._menu_anim_target else -sidebar_width
            ease_t = 1 - (1 - t) ** 3
            if self._menu_anim_target:
                return int(-sidebar_width + (sidebar_width * ease_t))
            else:
                return int(-sidebar_width * ease_t)
        return 0 if self.menu_is_open else -sidebar_width

    def get_hovered_menu_item(self, mouse_pos: tuple[int, int]) -> int:
        """Get the index of menu item being hovered, return -1 if none"""
        # Also check during animation
        if not self.menu_is_open and self._menu_anim_start == 0:
            return -1
        
        sidebar_width = 280
        offset_x = self._get_menu_offset_x()
        
        # Check hover inside sidebar with animation offset
        sidebar_rect = pygame.Rect(offset_x, 50, sidebar_width, self.screen.get_height() - 50)
        if not sidebar_rect.collidepoint(mouse_pos):
            return -1
        
        # Compute menu item rects with offset
        sidebar_y = 50
        item_start_y = sidebar_y + 20
        item_width = sidebar_width - 20
        item_height = 50
        item_spacing = 10
        item_x = offset_x + 10
        
        # Check hover over each menu item
        for i in range(len(self.menu_items)):
            item_y = item_start_y + i * (item_height + item_spacing)
            item_rect = pygame.Rect(item_x, item_y, item_width, item_height)
            if item_rect.collidepoint(mouse_pos):
                return i
        return -1

    def draw_menu_sidebar(self, mouse_pos: tuple[int, int] = None) -> None:
        """Draw the menu sidebar panel with slide animation (all animation logic is self-contained)."""
        sidebar_width = 280
        sidebar_y = 50
        sidebar_height = self.screen.get_height()
        animation_duration = 100  # milliseconds
        
        # Compute animation progress and offset
        offset_x = 0
        should_draw = False
        
        if self._menu_anim_start > 0:
            # Animation in progress
            now = pygame.time.get_ticks()
            elapsed = now - self._menu_anim_start
            t = min(1.0, elapsed / animation_duration)
            
            if t >= 1.0:
                # Animation complete
                self.menu_is_open = self._menu_anim_target
                self._menu_anim_start = 0
                offset_x = 0 if self.menu_is_open else -sidebar_width
                should_draw = self.menu_is_open
            else:
                # In-progress: ease-out cubic
                ease_t = 1 - (1 - t) ** 3
                if self._menu_anim_target:
                    # Opening: slide from -280 to 0
                    offset_x = -sidebar_width + (sidebar_width * ease_t)
                else:
                    # Closing: slide from 0 to -280
                    offset_x = -sidebar_width * ease_t
                should_draw = True
        else:
            # No animation
            should_draw = self.menu_is_open
            offset_x = 0 if self.menu_is_open else -sidebar_width
        
        # Skip drawing if fully slid off-screen
        if offset_x <= -sidebar_width:
            return
        
        if not should_draw:
            return

        # Draw sidebar with offset
        sidebar_x = int(offset_x)
        
        # Draw shadow behind sidebar (alpha varies with animation progress)
        if self._menu_anim_start > 0:
            now = pygame.time.get_ticks()
            elapsed = now - self._menu_anim_start
            t = min(1.0, elapsed / animation_duration)
            shadow_alpha = int(80 * t)
        else:
            shadow_alpha = 80
        shadow_surface = pygame.Surface((sidebar_width, sidebar_height), pygame.SRCALPHA)
        shadow_surface.fill((0, 0, 0, shadow_alpha))
        self.screen.blit(shadow_surface, (sidebar_x + 5, sidebar_y + 5))
        
        # Draw sidebar background (white)
        sidebar_rect = pygame.Rect(sidebar_x, sidebar_y, sidebar_width, sidebar_height)
        pygame.draw.rect(self.screen, Settings.Colors.WHITE, sidebar_rect)
        pygame.draw.rect(self.screen, Settings.Colors.BLACK, sidebar_rect, 2)

        # Draw menu items (using sidebar_x with offset applied)
        item_start_y = sidebar_y + 20
        item_width = sidebar_width - 20
        item_height = 50
        item_spacing = 10
        item_x = sidebar_x + 10

        # Font for menu items
        menu_font = pygame.font.Font(self.font_path, 22)
        self.menu_item_rects = []

        # Get the currently hovered item index
        hovered_idx = -1
        if mouse_pos:
            hovered_idx = self.get_hovered_menu_item(mouse_pos)

        # Draw each menu item
        for i, item_text in enumerate(self.menu_items):
            item_y = item_start_y + i * (item_height + item_spacing)
            item_rect = pygame.Rect(item_x, item_y, item_width, item_height)
            self.menu_item_rects.append(item_rect)

            # Draw item background with hover effect
            item_bg_rect = pygame.Rect(item_x, item_y, item_width, item_height)
            if i == hovered_idx:
                # Hover: light blue
                pygame.draw.rect(self.screen, (200, 230, 255), item_bg_rect)
                pygame.draw.rect(self.screen, (100, 150, 255), item_bg_rect, 2)
            else:
                # Default background
                pygame.draw.rect(self.screen, (240, 240, 240), item_bg_rect)
                pygame.draw.rect(self.screen, Settings.Colors.GRAY, item_bg_rect, 1)

            # Draw icon and text
            icon_size = 30    # icon size in pixels
            icon_padding = 10  # gap between icon and text
            text_x = item_x + 15
            
            # Draw icon if available
            icon_path = self.menu_item_icons.get(item_text)
            if icon_path:
                # Load from cache or load fresh
                if item_text not in self._menu_icon_cache:
                    try:
                        icon_image = pygame.image.load(icon_path).convert_alpha()
                        icon_image = pygame.transform.scale(icon_image, (icon_size, icon_size))
                        self._menu_icon_cache[item_text] = icon_image

                    except Exception:
                        self._menu_icon_cache[item_text] = None

                
                icon_image = self._menu_icon_cache.get(item_text)
                if icon_image:
                    icon_x = item_x + 15
                    icon_y = item_y + (item_height - icon_size) // 2
                    self.screen.blit(icon_image, (icon_x, icon_y))
                    # Shift text right to make room for the icon
                    text_x = icon_x + icon_size + icon_padding
                # print("self._menu_icon_cache:", self._menu_icon_cache)
            # Draw text
            text_color = Settings.Colors.BLACK if i != hovered_idx else (50, 100, 200)
            text_surface = menu_font.render(item_text, True, text_color)
            text_y = item_y + (item_height - text_surface.get_height()) // 2
            self.screen.blit(text_surface, (text_x, text_y))
        
        # Draw author text with sidebar offset
        author = Settings.get_author()
        author_x = sidebar_x + 30  # Adjusted for sidebar offset
        author_y = self.screen.get_height() - 30
        author_rect = pygame.Rect(author_x, author_y, 200, 30)
        author_surface = menu_font.render(author, True, Settings.Colors.BLACK)
        self.screen.blit(author_surface, author_rect.topleft)

    def check_menu_item_click(self, mouse_pos: tuple[int, int]) -> int:
        """Check if a menu item was clicked, return index or -1"""
        # Also check during animation
        if not self.menu_is_open and self._menu_anim_start == 0:
            return -1
        
        sidebar_width = 280
        offset_x = self._get_menu_offset_x()
        
        # Check click inside sidebar with animation offset
        sidebar_rect = pygame.Rect(offset_x, 50, sidebar_width, self.screen.get_height() - 50)
        if not sidebar_rect.collidepoint(mouse_pos):
            return -1
        
        # Compute menu item rects with offset
        sidebar_y = 50
        item_start_y = sidebar_y + 20
        item_width = sidebar_width - 20
        item_height = 50
        item_spacing = 10
        item_x = offset_x + 10
        
        # Check click on each menu item
        for i in range(len(self.menu_items)):
            item_y = item_start_y + i * (item_height + item_spacing)
            item_rect = pygame.Rect(item_x, item_y, item_width, item_height)
            if item_rect.collidepoint(mouse_pos):
                return i
        return -1

    def toggle_rotation(self) -> None:
        """Toggle board rotation flag"""
        Settings.FLIPPED = not Settings.FLIPPED

    def draw_all_ui_except_pieces(self, selected_piece, valid_moves: list) -> None:
        """Draw all UI elements except pieces (pieces are drawn separately during animation)"""
        # Only draw the buttons needed for the current mode
        if Settings.SETUP_MODE:
            # Setup mode: draw only menu and rotate button
            self.draw_menu_button()
            self.draw_menu_sidebar()  # Draw menu sidebar if open
            self.draw_rotate_button()
            self.draw_expand_button()
            self.draw_tick_button()
            self.draw_general_button(pos=(270, 5))
        else:
            # Normal play mode: draw all components
            # Don't draw selection indicators during flip animation
            # self.draw_old_position_selection()
            # self.draw_selected_piece(selected_piece)
            # self.draw_valid_moves(valid_moves)
            self.draw_in_check()
            self.draw_checkmate()
            self.draw_menu_button()
            self.draw_menu_sidebar()  # Draw menu sidebar if open
            self.draw_rotate_button()
            self.draw_forward_backward_buttons()
            self.draw_red_and_black_computer()
            self.draw_magnifying_glass_button()
            self.draw_general_button()
            self.draw_add_button()
            self.draw_right_menu_buttons()
            self.tab_content()

    # ---- Flip animation delegation ----
    def begin_flip_animation(self) -> None:
        self._flip_animator.begin()

    def is_animating(self) -> bool:
        return self._flip_animator.is_animating()

    def render_flip_animation(self, selected_piece=None, valid_moves: list = None) -> None:
        if valid_moves is None:
            valid_moves = []
        self._flip_animator.render_frame(selected_piece, valid_moves)


    def draw_right_menu_buttons(self) -> None:
        """Draw tabs inside responsive side panel and keep rects for hit testing."""
        self.tabs_rects = []
        if not self.is_side_panel_visible():
            return

        tabs_rect, _ = self._sync_panel_viewports()
        if tabs_rect.width <= 0 or tabs_rect.height <= 0:
            return

        box_w = tabs_rect.width // max(1, len(self.tabs_labels))
        box_h = tabs_rect.height
        small_font = pygame.font.Font(self.font_path, max(18, min(28, int(box_h * 0.56))))

        for i, label in enumerate(self.tabs_labels):
            x = tabs_rect.x + i * box_w
            width = box_w if i < len(self.tabs_labels) - 1 else tabs_rect.right - x
            rect = pygame.Rect(x, tabs_rect.y, width, box_h)
            self.tabs_rects.append(rect)

            # Highlight active tab
            if i == self.current_tab_index:
                # light fill for active
                active_overlay = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
                active_overlay.fill((0, 200, 0, 60))
                self.screen.blit(active_overlay, rect.topleft)

            pygame.draw.rect(self.screen, Settings.Colors.BLACK, rect, width=2)
            # Draw label to the right of the box to avoid cramped text
            text_surf = small_font.render(label, True, Settings.Colors.BLACK)
            text_rect = text_surf.get_rect(center=rect.center)
            self.screen.blit(text_surf, text_rect.topleft)

    def tab_hit(self, mouse_pos: tuple[int, int]) -> int:
        """Return the tab index if a tab button is clicked, else -1."""
        for i, rect in enumerate(self.tabs_rects or []):
            if rect.collidepoint(mouse_pos):
                return i
        return -1

    def set_current_tab(self, index: int) -> None:
        if 0 <= index < len(self.tabs_labels):
            self.current_tab_index = index

    # Function book: Display content under the right menu tabs based on the current tab (current_tab_index).
    def tab_content(self) -> None:
        """Render content under the tabs based on current tab."""
        if not self.is_side_panel_visible():
            return
        self._sync_panel_viewports()
        # 0: Opening (Khai cuộc), 1: Engine (Động cơ), 2: Move record (Biên bản)
        if self.current_tab_index == 0:
            self.book_view.draw_header()
        elif self.current_tab_index == 2:
            self.record_view.draw()
            
    def verify_author_integrity(self) -> bool:
        """Verify the integrity of the author information, return True if integrity is not compromised"""
        author = Settings.get_author()
        if "Unknown" in author:
            return False # Integrity is compromised
        else:
            return True # Integrity is not compromised

    def show_notification(self, message: str) -> None:
        """Show a notification message on screen for 3-5 seconds"""
        self.notification_message = message
        self.notification_start_time = pygame.time.get_ticks()
    
    def draw_notification(self) -> None:
        """Draw notification message on screen if active"""
        if self.notification_message is None or self.notification_start_time is None:
            return
        
        current_time = pygame.time.get_ticks()
        elapsed = current_time - self.notification_start_time
        
        # Auto-hide after duration
        if elapsed >= self.NOTIFICATION_DURATION:
            self.notification_message = None
            self.notification_start_time = None
            return
        
        # Draw notification banner
        notification_font = pygame.font.Font(self.font_path, 32)
        if "Lỗi" in self.notification_message or "Error" in self.notification_message:
            text_color = Settings.Colors.RED
        else:
            text_color = Settings.Colors.WHITE


        text_surface = notification_font.render(self.notification_message, True, text_color)
        
        # Calculate banner size with padding
        padding = 23
        banner_width = text_surface.get_width() + padding * 2
        banner_height = text_surface.get_height() + padding * 2
        
        # Center banner on screen
        banner_x = (self.screen.get_width() - banner_width) // 2
        banner_y = 100  # Position near top
        
        # Draw semi-transparent background
        banner_rect = pygame.Rect(banner_x, banner_y, banner_width, banner_height)
        overlay = pygame.Surface((banner_width, banner_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))  # Black with transparency
        self.screen.blit(overlay, banner_rect)
        
        # Draw text centered in banner
        text_rect = text_surface.get_rect(center=banner_rect.center)
        self.screen.blit(text_surface, text_rect)
    
    def close_notification(self) -> None:
        """Close notification if clicked"""
        if self.notification_message is not None:
            self.notification_message = None
            self.notification_start_time = None
    
    def is_checkmate_close_button_clicked(self, mouse_pos: tuple[int, int]) -> bool:
        """Check if the checkmate close button was clicked"""
        return (self.checkmate_notification_active and 
                hasattr(self, 'checkmate_close_button_rect') and 
                self.checkmate_close_button_rect.collidepoint(mouse_pos))
    
    def close_checkmate_notification(self) -> None:
        """Close checkmate notification if clicked"""
        if self.checkmate_notification_active:
            self.checkmate_notification_active = False
            self.checkmate_notification_dismissed = True  # Mark as dismissed to prevent re-showing