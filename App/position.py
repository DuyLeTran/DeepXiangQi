from App.configuration import Settings

class Position:
    @staticmethod
    def calculate_position(pos: tuple[int, int]) -> tuple[int, int]:
        x, y = pos
        board_scale = Settings.BOARD_SCALE
        setup_scale = Settings.SETUP_BOARD_SCALE if getattr(Settings, "SETUP_MODE", False) else 1.0
        total_scale = board_scale * setup_scale

        if Settings.SETUP_MODE:
            scaled_width = int(Settings.BASE_WIDTH * total_scale)
            scaled_height = int(Settings.BASE_HEIGHT * total_scale)
            bg_x = Settings.BOARD_X + (Settings.WIDTH - scaled_width) // 2
            bg_y = Settings.BOARD_Y + (Settings.HEIGHT - scaled_height) // 2
            offset_x = 45 * total_scale
            offset_y = 45 * total_scale
            base_x = bg_x + offset_x
            base_y = bg_y + offset_y
            spacing = 90 * total_scale
        else:
            base_x = Settings.BOARD_X + 45 * board_scale
            base_y = Settings.BOARD_Y + 45 * board_scale
            spacing = 90 * board_scale

        # Handle flip: only flip positions that are on the board, not off-board positions
        if Settings.FLIPPED and (1 <= x <= 9) and (0 <= y <= 9):
            # flipped view: rotate 180 degrees around board center; grid 1..9, 0..9
            fx = 10 - x  # invert x across 1..9
            fy = 9 - y   # invert y across 0..9
            return int(base_x + (fx - 1) * spacing), int(base_y + fy * spacing)
        else:
            # No flip or off-board position: keep original coordinates
            return int(base_x + (x - 1) * spacing), int(base_y + y * spacing)

    @staticmethod
    def check_valid_position(pos: tuple[int, int]) -> tuple[tuple[int, int], bool]:
        board_scale = Settings.BOARD_SCALE
        setup_scale = Settings.SETUP_BOARD_SCALE if getattr(Settings, "SETUP_MODE", False) else 1.0
        total_scale = board_scale * setup_scale

        if Settings.SETUP_MODE:
            scaled_width = int(Settings.BASE_WIDTH * total_scale)
            scaled_height = int(Settings.BASE_HEIGHT * total_scale)
            bg_x = Settings.BOARD_X + (Settings.WIDTH - scaled_width) // 2
            bg_y = Settings.BOARD_Y + (Settings.HEIGHT - scaled_height) // 2

            offset_x = 45 * total_scale
            offset_y = 45 * total_scale

            base_x = bg_x + offset_x
            base_y = bg_y + offset_y
            spacing = 90 * total_scale
            
            # Click tolerance radius in cell units, always 0.45 cells
            tolerance = 0.45

            a = (pos[0] - base_x) / spacing + 1
            b = (pos[1] - base_y) / spacing
            x = round(a)
            y = round(b)
            
            # In setup mode, both on-board and off-board positions are accepted.
            # On-board: 1 <= x <= 9, 0 <= y <= 9
            # Off-board staging rows (2 rows per side):
            #   Not flipped: black pieces above (y=-1, y=-2), red pieces below (y=10, y=11)
            #   Flipped:     black pieces below (y=10, y=11), red pieces above (y=-1, y=-2)
            in_board = (1 <= x <= 9) and (0 <= y <= 9)
            
            # Determine off-board row mapping depending on the flip state
            if not Settings.FLIPPED:
                # Not flipped: black pieces above, red pieces below
                black_top_row = (1 <= x <= 8) and (y == -2)
                black_bottom_row = (1 <= x <= 8) and (y == -1)
                red_top_row = (1 <= x <= 8) and (y == 10)
                red_bottom_row = (1 <= x <= 8) and (y == 11)
            else:
                # Flipped: black pieces below, red pieces above
                black_top_row = (1 <= x <= 8) and (y == 10)
                black_bottom_row = (1 <= x <= 8) and (y == 11)
                red_top_row = (1 <= x <= 8) and (y == -2)
                red_bottom_row = (1 <= x <= 8) and (y == -1)
            
            is_in_valid_area = in_board or black_top_row or black_bottom_row or red_top_row or red_bottom_row
            
            if is_in_valid_area:
                # Check whether the click is close enough to a cell center
                if in_board:
                    distance_sq = (x - a) ** 2 + (y - b) ** 2
                    if distance_sq <= tolerance ** 2:
                        if not Settings.FLIPPED:
                            return (x, y), True
                        fx = 10 - x
                        fy = 9 - y
                        return (fx, fy), True
                else:
                    # Off-board position: accept if click is close enough
                    distance_sq = (x - a) ** 2 + (y - b) ** 2
                    if distance_sq <= tolerance ** 2:
                        return (x, y), True
            
            return (x, y), False
        else:
            base_x = Settings.BOARD_X + 45 * board_scale
            base_y = Settings.BOARD_Y + 45 * board_scale
            spacing = 90 * board_scale
            # Click tolerance radius in cell units, always 0.45 cells
            tolerance = 0.45

            a = (pos[0] - base_x) / spacing + 1
            b = (pos[1] - base_y) / spacing
            x = round(a)
            y = round(b)
            is_valid = (1 <= x <= 9) and (0 <= y <= 9) and ((x - a) ** 2 + (y - b) ** 2 <= tolerance ** 2)
            if not is_valid:
                return (x, y), False
            if not Settings.FLIPPED:
                return (x, y), True
            # map clicked coordinates to flipped board coordinates
            fx = 10 - x
            fy = 9 - y
            return (fx, fy), True