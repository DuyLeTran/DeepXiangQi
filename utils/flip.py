import pygame
import os
from App.configuration import Settings
from App.position import Position


class FlipAnimator:
    """Encapsulates flip (converge/expand) animation logic for XiangQi pieces.

    This class is UI-agnostic beyond the provided callbacks; it depends on:
    - screen: pygame.Surface to draw onto
    - chess_board: provides pieces and their positions/colors
    - get_background(): returns current background surface to draw
    - draw_border(): callable to draw the side border
    - draw_rotate_button(): callable to draw rotate button
    - draw_all_ui(): callable to draw all UI elements except pieces (pieces are animated separately)
    """

    def __init__(self, screen: pygame.Surface, chess_board, get_background, draw_border, draw_rotate_button, draw_all_ui=None):
        self.screen = screen
        self.chess_board = chess_board
        self.get_background = get_background
        self.draw_border_cb = draw_border
        self.draw_rotate_button_cb = draw_rotate_button
        self.draw_all_ui_cb = draw_all_ui
        self._animating_flip = False
        self._flip_duration_ms = 350
        self._flip_start_time = 0
        self._flip_finalized = False
        self._anim_items = []

    # ---- Public API ----
    def begin(self) -> None:
        self._animating_flip = True
        self._flip_start_time = pygame.time.get_ticks()
        self._flip_finalized = False
        self._anim_items = []
        current_flipped = Settings.FLIPPED
        target_flipped = not current_flipped
        for color_dict in self.chess_board.pieces.values():
            for piece in color_dict.values():
                if piece.position == (-1, -1):
                    continue
                start_c = self._calc_screen_center_for(piece.position, current_flipped)
                dest_c = self._calc_screen_center_for(piece.position, target_flipped)
                self._anim_items.append((piece, start_c, dest_c))

    def is_animating(self) -> bool:
        return self._animating_flip

    def render_frame(self, selected_piece=None, valid_moves: list = None) -> None:
        if not self._animating_flip:
            return
        if valid_moves is None:
            valid_moves = []
        now = pygame.time.get_ticks()
        elapsed = now - self._flip_start_time
        t = min(1.0, elapsed / self._flip_duration_ms)

        # Draw static background (always in original orientation, never rotated)
        bg = self.get_background() or pygame.Surface((Settings.WIDTH, Settings.HEIGHT))
        # Fill and blit background
        self.screen.fill(Settings.Colors.BACKGROUND)

        # Respect setup mode scaling and centering, same logic as UIRenderer.draw_background
        if Settings.SETUP_MODE:
            scale = Settings.SETUP_BOARD_SCALE
            scaled_width = int(bg.get_width() * scale)
            scaled_height = int(bg.get_height() * scale)
            scaled_bg = pygame.transform.scale(bg, (scaled_width, scaled_height))

            board_area_width = Settings.WIDTH
            board_area_height = Settings.HEIGHT
            bg_x = (board_area_width - scaled_width) // 2
            bg_y = 50 + (board_area_height - scaled_height) // 2

            self.screen.blit(scaled_bg, (bg_x, bg_y))
        else:
            # Original board: draw at fixed offset (0, 50)
            self.screen.blit(bg, (0, 50))
        
        # Draw border
        self.draw_border_cb()

        # Draw interpolated pieces (only pieces animate, board stays fixed)
        # Compute board center dynamically (center of board area), works for all scales
        board_center = (Settings.WIDTH // 2, 50 + Settings.HEIGHT // 2)

        for piece, start_c, dest_c in self._anim_items:
            if t < 0.5:
                k = t / 0.5
                cx = start_c[0] + (board_center[0] - start_c[0]) * k
                cy = start_c[1] + (board_center[1] - start_c[1]) * k
            else:
                k = (t - 0.5) / 0.5
                cx = board_center[0] + (dest_c[0] - board_center[0]) * k
                cy = board_center[1] + (dest_c[1] - board_center[1]) * k
            self._draw_piece_at_center(piece, (int(cx), int(cy)))

        # Draw all other UI elements (selected piece, valid moves, buttons, etc.)
        # Use the current flip state for UI calculations
        if self.draw_all_ui_cb:
            self.draw_all_ui_cb(selected_piece, valid_moves)

        if t >= 1.0 and not self._flip_finalized:
            self._toggle_rotation()
            self._flip_finalized = True
        if t >= 1.0:
            self._animating_flip = False

    # ---- Internals ----
    def _toggle_rotation(self) -> None:
        # Move off-board pieces when flipping (setup mode only)
        if getattr(Settings, 'SETUP_MODE', False):
            # Remap off-board positions:
            # Flip:   black from above (y=-1,-2) → below (y=10,11), red from below → above
            # Unflip: black from below (y=10,11) → above (y=-1,-2), red from above → below
            
            # Build list of (piece, new_position) for off-board pieces
            pieces_to_move = []
            
            for color_dict in self.chess_board.pieces.values():
                for piece in color_dict.values():
                    if piece.position == (-1, -1):
                        continue
                    x, y = piece.position
                    
                    # Check whether the piece is in an off-board slot
                    is_off_board = False
                    new_y = None
                    
                    if (1 <= x <= 8):  # Off-board x range is 1 to 8
                        if piece.color == 'black':
                            # Black: if above (y=-1,-2) move to below (y=10,11)
                            if y == -1:
                                is_off_board = True
                                new_y = 10
                            elif y == -2:
                                is_off_board = True
                                new_y = 11
                            # Black: if below (y=10,11) move to above (y=-1,-2)
                            elif y == 10:
                                is_off_board = True
                                new_y = -1
                            elif y == 11:
                                is_off_board = True
                                new_y = -2
                        else:  # red
                            # Red: if below (y=10,11) move to above (y=-1,-2)
                            if y == 10:
                                is_off_board = True
                                new_y = -1
                            elif y == 11:
                                is_off_board = True
                                new_y = -2
                            # Red: if above (y=-1,-2) move to below (y=10,11)
                            elif y == -1:
                                is_off_board = True
                                new_y = 10
                            elif y == -2:
                                is_off_board = True
                                new_y = 11
                        
                        if is_off_board:
                            pieces_to_move.append((piece, (x, new_y)))
            
            # Two-pass move to handle swaps correctly:
            # first stash all pieces at a temporary invalid position to avoid conflicts
            old_positions = {}
            for piece, new_pos in pieces_to_move:
                old_positions[piece] = piece.position
            
            # Pass 1: move all pieces to a temporary invalid position
            temp_positions = {}
            for piece, new_pos in pieces_to_move:
                temp_positions[piece] = (-2, -2)  # Temporary invalid position
                piece.move_to(temp_positions[piece])
            
            # Pass 2: move from temporary position to the final destination
            for piece, new_pos in pieces_to_move:
                piece.move_to(new_pos)
        
        Settings.FLIPPED = not Settings.FLIPPED

    def _calc_screen_center_for(self, grid_pos: tuple[int, int], flipped: bool) -> tuple[int, int]:
        """
        Calculate the screen center for a given logical grid position.
        Mirrors the logic in Position.calculate_position but allows us to
        control the flipped state explicitly for the animation.
        """
        x, y = grid_pos
        # Determine board parameters depending on setup mode
        scale = Settings.SETUP_BOARD_SCALE if getattr(Settings, "SETUP_MODE", False) else 1.0

        if Settings.SETUP_MODE:
            # Background scaled and centered as in renderer & Position
            scaled_width = int(Settings.WIDTH * scale)
            scaled_height = int(Settings.HEIGHT * scale)
            bg_x = (Settings.WIDTH - scaled_width) // 2
            bg_y = 50 + (Settings.HEIGHT - scaled_height) // 2

            offset_x = 45 * scale
            offset_y = 45 * scale

            base_x = bg_x + offset_x
            base_y = bg_y + offset_y
            spacing = 90 * scale
        else:
            base_x = 45
            base_y = 95
            spacing = 90

        # Apply flip mapping
        if not flipped:
            cx = base_x + (x - 1) * spacing
            cy = base_y + y * spacing
        else:
            fx = 10 - x
            fy = 9 - y
            cx = base_x + (fx - 1) * spacing
            cy = base_y + fy * spacing

        return int(cx), int(cy)

    def _get_piece_image(self, piece) -> pygame.Surface:
        color_folder = 'Black' if piece.color == 'black' else 'Red'
        piece_type = piece.name[0]
        if piece_type == 'X':
            image_name = 'Xe đen' if piece.color == 'black' else 'Xe đỏ'
        elif piece_type == 'M':
            image_name = 'Mã đen' if piece.color == 'black' else 'Mã đỏ'
        elif piece_type == 'T' and piece.name != 'Tg':
            image_name = 'Tượng đen' if piece.color == 'black' else 'Tượng đỏ'
        elif piece_type == 'S':
            image_name = 'Sĩ đen' if piece.color == 'black' else 'Sĩ đỏ'
        elif piece.name == 'Tg':
            image_name = 'Tướng đen' if piece.color == 'black' else 'Tướng đỏ'
        elif piece_type == 'P':
            image_name = 'Pháo đen' if piece.color == 'black' else 'Pháo đỏ'
        elif piece_type == 'B':
            image_name = 'Tốt đen' if piece.color == 'black' else 'Tốt đỏ'
        else:
            image_name = ''
        image_path = f'Piece/{color_folder}/{image_name}.png'
        surf = pygame.image.load(image_path).convert_alpha()

        # Scale piece size according to setup mode to match board cell size
        base_cell_size = Settings.BASE_WIDTH / 9  # 810 / 9 = 90
        scale = Settings.SETUP_BOARD_SCALE if getattr(Settings, "SETUP_MODE", False) else 1.0
        cell_size = int(base_cell_size * scale)
        surf = pygame.transform.scale(surf, (cell_size, cell_size))
        return surf

    def _draw_piece_at_center(self, piece, center: tuple[int, int]) -> None:
        img = self._get_piece_image(piece)
        w, h = img.get_width(), img.get_height()
        top_left_x = center[0] - w // 2
        top_left_y = center[1] - h // 2
        self.screen.blit(img, (top_left_x, top_left_y))


