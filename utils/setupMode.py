import sys
import os
import random
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from App.piece import ChessBoard, ChessPiece
from App.configuration import Settings


class SetupMode:
    """Manages the piece-arrangement (setup) mode logic."""
    
    def __init__(self, chess_board: ChessBoard):
        """
        Initialize SetupMode with the chess board.
        
        Args:
            chess_board: The current chess board instance.
        """
        self.chess_board = chess_board
    
    def get_valid_positions(self, piece: ChessPiece) -> list[tuple[int, int]]:
        """
        Compute valid placement positions for a piece in setup mode.
        
        Rules:
        - Pawn (B): cannot be placed lower than its default row (black: y >= 3, red: y <= 6)
        - Advisor (S): must stay inside the palace (black: 4<=x<=6, 0<=y<=2; red: 4<=x<=6, 7<=y<=9)
        - Elephant (T): cannot cross the river (black: y <= 4, red: y >= 5)
        - King (Tg): must stay in the palace, same as advisor
        - Other pieces (Rook, Knight, Cannon): can be placed anywhere on the board (except occupied squares)
        
        Args:
            piece: The piece to compute valid positions for.
        
        Returns:
            List of valid (x, y) positions for the piece.
        """
        valid_positions = []
        piece_type = piece.name[0]
        color = piece.color
        
        # Add off-board positions for staging pieces in 2 rows (8 per row)
        # Not flipped: black pieces above (y=-1, y=-2), red pieces below (y=10, y=11)
        # Flipped:     black pieces below (y=10, y=11), red pieces above (y=-1, y=-2)
        
        # Determine off-board slots based on piece color and flip state
        is_flipped = getattr(Settings, 'FLIPPED', False)
        
        if color == 'black':
            # Black pieces: above the board when not flipped, below when flipped
            if not is_flipped:
                # Black pieces: 2 rows above the board
                # Row 1: y = -1, x from 1 to 8
                for x in range(1, 9):  # x from 1 to 8
                    pos = (x, -1)
                    existing_piece = self.chess_board.get_piece_at(pos)
                    if existing_piece is not None and existing_piece != piece:
                        continue
                    valid_positions.append(pos)
                
                # Row 2: y = -2, x from 1 to 8
                for x in range(1, 9):  # x from 1 to 8
                    pos = (x, -2)
                    existing_piece = self.chess_board.get_piece_at(pos)
                    if existing_piece is not None and existing_piece != piece:
                        continue
                    valid_positions.append(pos)
            else:
                # Black pieces: 2 rows below the board (when flipped)
                # Row 1: y = 10, x from 1 to 8
                for x in range(1, 9):  # x from 1 to 8
                    pos = (x, 10)
                    existing_piece = self.chess_board.get_piece_at(pos)
                    if existing_piece is not None and existing_piece != piece:
                        continue
                    valid_positions.append(pos)
                
                # Row 2: y = 11, x from 1 to 8
                for x in range(1, 9):  # x from 1 to 8
                    pos = (x, 11)
                    existing_piece = self.chess_board.get_piece_at(pos)
                    if existing_piece is not None and existing_piece != piece:
                        continue
                    valid_positions.append(pos)
        else:  # red
            # Red pieces: below the board when not flipped, above when flipped
            if not is_flipped:
                # Red pieces: 2 rows below the board
                # Row 1: y = 10, x from 1 to 8
                for x in range(1, 9):  # x from 1 to 8
                    pos = (x, 10)
                    existing_piece = self.chess_board.get_piece_at(pos)
                    if existing_piece is not None and existing_piece != piece:
                        continue
                    valid_positions.append(pos)
                
                # Row 2: y = 11, x from 1 to 8
                for x in range(1, 9):  # x from 1 to 8
                    pos = (x, 11)
                    existing_piece = self.chess_board.get_piece_at(pos)
                    if existing_piece is not None and existing_piece != piece:
                        continue
                    valid_positions.append(pos)
            else:
                # Red pieces: 2 rows above the board (when flipped)
                # Row 1: y = -1, x from 1 to 8
                for x in range(1, 9):  # x from 1 to 8
                    pos = (x, -1)
                    existing_piece = self.chess_board.get_piece_at(pos)
                    if existing_piece is not None and existing_piece != piece:
                        continue
                    valid_positions.append(pos)
                
                # Row 2: y = -2, x from 1 to 8
                for x in range(1, 9):  # x from 1 to 8
                    pos = (x, -2)
                    existing_piece = self.chess_board.get_piece_at(pos)
                    if existing_piece is not None and existing_piece != piece:
                        continue
                    valid_positions.append(pos)
        
        # Iterate over all positions on the board
        for x in range(1, 10):  # x from 1 to 9
            for y in range(0, 10):  # y from 0 to 9
                pos = (x, y)
                
                # Skip occupied squares (except the piece's current position)
                existing_piece = self.chess_board.get_piece_at(pos)
                if existing_piece is not None and existing_piece != piece:
                    continue
                
                # Validate position by piece type
                is_valid = False
                
                if piece_type == 'B':  # Pawn (Tốt)
                    # Black: cannot be placed below row 3 (y >= 3)
                    # Red:   cannot be placed above row 6 (y <= 6)
                    if color == 'black':
                        is_valid = y >= 3 and (y > 5 or x % 2 != 0)
                    else:  # red
                        is_valid = y <= 6 and (y < 5 or x % 2 != 0)
                        
                elif piece_type == 'S':  # Advisor (Sĩ)
                    # Must stay inside the palace
                    if color == 'black':
                        is_valid = 4 <= x <= 6 and 0 <= y <= 2 and (y % 2 ==0 and x % 2 == 0 or y % 2 != 0 and x % 2 != 0)
                    else:  # red
                        is_valid = 4 <= x <= 6 and 7 <= y <= 9 and (y % 2 ==0 and x % 2 != 0 or y % 2 != 0 and x % 2 == 0)
                        
                elif piece_type == 'T' and piece.name != 'Tg':  # Elephant (Tượng)
                    # Cannot cross the river
                    if color == 'black':
                        valid_pos = [(3,0), (1,2), (3,4), (5,2), (7,0), (9,2), (7,4)]
                        is_valid = pos in valid_pos
                    else:  # red
                        valid_pos = [(3,9), (1,7), (3,5), (5,7), (7,9), (9,7), (7,5)]
                        is_valid = pos in valid_pos
                        
                elif piece.name == 'Tg':  # King (Tướng)
                    # Must stay in the palace (same rule as advisor)
                    if color == 'black':
                        is_valid = 4 <= x <= 6 and 0 <= y <= 2
                    else:  # red
                        is_valid = 4 <= x <= 6 and 7 <= y <= 9
                        
                else:  # Rook (Xe), Knight (Mã), Cannon (Pháo)
                    # Can be placed anywhere on the board
                    is_valid = True
                
                if is_valid:
                    valid_positions.append(pos)
        
        return valid_positions
    
    def move_off_board_pieces_to_removed(self) -> None:
        """
        Move all pieces at off-board positions (y=-1, -2, 10, 11) to position (-1, -1).
        Called when the user confirms the setup (tick button).
        """
        # Build the list of all off-board positions
        off_board_positions = []
        for x in range(1, 9):  # x from 1 to 8
            off_board_positions.extend([(x, -1), (x, -2), (x, 10), (x, 11)])
        
        # Find and move pieces that are at off-board positions
        for color_dict in self.chess_board.pieces.values():
            for piece in color_dict.values():
                if piece.position in off_board_positions:
                    piece.move_to((-1, -1))
    
    def place_removed_pieces_to_off_board(self) -> None:
        """
        Randomly place pieces currently at (-1, -1) into off-board slots by color.
        Called when entering setup mode.
        """
        # Determine off-board slot layout based on the flip state
        is_flipped = getattr(Settings, 'FLIPPED', False)
        
        # Collect pieces currently at (-1, -1)
        black_pieces_to_place = []
        red_pieces_to_place = []
        
        for color_dict in self.chess_board.pieces.values():
            for piece in color_dict.values():
                if piece.position == (-1, -1):
                    if piece.color == 'black':
                        black_pieces_to_place.append(piece)
                    else:
                        red_pieces_to_place.append(piece)
        
        # Shuffle for random placement
        random.shuffle(black_pieces_to_place)
        random.shuffle(red_pieces_to_place)
        
        # Determine off-board slot positions per color
        if not is_flipped:
            # Not flipped: black above (y=-1, -2), red below (y=10, 11)
            black_positions = [(x, y) for x in range(1, 9) for y in [-1, -2]]
            red_positions = [(x, y) for x in range(1, 9) for y in [10, 11]]
        else:
            # Flipped: black below (y=10, 11), red above (y=-1, -2)
            black_positions = [(x, y) for x in range(1, 9) for y in [10, 11]]
            red_positions = [(x, y) for x in range(1, 9) for y in [-1, -2]]
        
        # Shuffle slot lists for random assignment
        random.shuffle(black_positions)
        random.shuffle(red_positions)
        
        # Place black pieces into off-board slots
        used_black_positions = set()
        for piece in black_pieces_to_place:
            # Find the first available slot
            for pos in black_positions:
                if pos not in used_black_positions and self.chess_board.get_piece_at(pos) is None:
                    piece.move_to(pos)
                    used_black_positions.add(pos)
                    break
        
        # Place red pieces into off-board slots
        used_red_positions = set()
        for piece in red_pieces_to_place:
            # Find the first available slot
            for pos in red_positions:
                if pos not in used_red_positions and self.chess_board.get_piece_at(pos) is None:
                    piece.move_to(pos)
                    used_red_positions.add(pos)
                    break
    
    def move_board_pieces_to_off_board(self) -> None:
        """
        Move all on-board pieces (in setup mode) to off-board slots, excluding the king.
        Pieces are placed into color-appropriate off-board slots.
        """
        # Determine off-board slot layout based on the flip state
        is_flipped = getattr(Settings, 'FLIPPED', False)
        
        # Collect pieces currently on the board (excluding the king)
        black_pieces_to_move = []
        red_pieces_to_move = []
        
        for color_dict in self.chess_board.pieces.values():
            for piece in color_dict.values():
                # Skip the king and pieces already off-board or captured
                if piece.name == 'Tg':
                    continue
                if piece.position == (-1, -1):
                    continue
                
                x, y = piece.position
                # Only move pieces that are currently on the board (1 <= x <= 9, 0 <= y <= 9)
                if not (1 <= x <= 9 and 0 <= y <= 9):
                    continue
                
                if piece.color == 'black':
                    black_pieces_to_move.append(piece)
                else:
                    red_pieces_to_move.append(piece)
        
        # Shuffle for random placement
        random.shuffle(black_pieces_to_move)
        random.shuffle(red_pieces_to_move)
        
        # Determine off-board slot positions per color
        if not is_flipped:
            # Not flipped: black above (y=-1, -2), red below (y=10, 11)
            black_positions = [(x, y) for x in range(1, 9) for y in [-1, -2]]
            red_positions = [(x, y) for x in range(1, 9) for y in [10, 11]]
        else:
            # Flipped: black below (y=10, 11), red above (y=-1, -2)
            black_positions = [(x, y) for x in range(1, 9) for y in [10, 11]]
            red_positions = [(x, y) for x in range(1, 9) for y in [-1, -2]]
        
        # Shuffle slot lists for random assignment
        random.shuffle(black_positions)
        random.shuffle(red_positions)
        
        # Place black pieces into off-board slots
        used_black_positions = set()
        for piece in black_pieces_to_move:
            # Find the first available slot
            for pos in black_positions:
                if pos not in used_black_positions and self.chess_board.get_piece_at(pos) is None:
                    piece.move_to(pos)
                    used_black_positions.add(pos)
                    break
        
        # Place red pieces into off-board slots
        used_red_positions = set()
        for piece in red_pieces_to_move:
            # Find the first available slot
            for pos in red_positions:
                if pos not in used_red_positions and self.chess_board.get_piece_at(pos) is None:
                    piece.move_to(pos)
                    used_red_positions.add(pos)
                    break
