import pygame
from App.configuration import Settings
from App.position import Position


class ChessPiece:
    def __init__(self, name: str, color: str, position: tuple[int, int]):
        self.name = name
        self.color = color
        self.position = position
        self.is_selected = False

    def move_to(self, new_position: tuple[int, int]) -> None:
        self.position = new_position

    def draw(self, screen: pygame.Surface, rect_width: int = 90, rect_height: int = 90) -> None:
        # Determine piece size based on runtime board layout and setup scale
        setup_scale = Settings.SETUP_BOARD_SCALE if Settings.SETUP_MODE else 1.0
        cell_size = int(90 * Settings.BOARD_SCALE * setup_scale)

        rect_width = rect_height = cell_size

        center_x, center_y = Position.calculate_position(self.position)
        top_left_x = center_x - rect_width // 2
        top_left_y = center_y - rect_height // 2

        color_folder = 'Black' if self.color == 'black' else 'Red'
        image_path = f'Piece/{color_folder}/{self._get_piece_image_name()}.png'
        piece_image = pygame.image.load(image_path)
        piece_image = pygame.transform.scale(piece_image, (rect_width, rect_height))
        screen.blit(piece_image, (top_left_x, top_left_y))
    
    def _get_piece_image_name(self) -> str:
        piece_type = self.name[0]
        if piece_type == 'X':
            return 'Xe đen' if self.color == 'black' else 'Xe đỏ'
        elif piece_type == 'M':
            return 'Mã đen' if self.color == 'black' else 'Mã đỏ'
        elif piece_type == 'T' and self.name != 'Tg':
            return 'Tượng đen' if self.color == 'black' else 'Tượng đỏ'
        elif piece_type == 'S':
            return 'Sĩ đen' if self.color == 'black' else 'Sĩ đỏ'
        elif self.name == 'Tg':
            return 'Tướng đen' if self.color == 'black' else 'Tướng đỏ'
        elif piece_type == 'P':
            return 'Pháo đen' if self.color == 'black' else 'Pháo đỏ'
        elif piece_type == 'B':
            return 'Tốt đen' if self.color == 'black' else 'Tốt đỏ'
        return ''
class ChessBoard:
    def __init__(self):
        """
        Initialize the chess board and its pieces
        self.pieces = {
                'black': { 'X1': ChessPiece(...), 'X9': ChessPiece(...), ... },
                'red': { 'X1': ChessPiece(...), 'X9': ChessPiece(...), ... }
            }
        """

        self.pieces: dict[str, dict[str, ChessPiece]] = {
            'black':{},
            'red':{}
        }
        self._initialize_pieces()
        self.turn = 'red'

    def reset(self) -> None:
        """Reset board to initial position and set turn to red."""
        self.pieces = {
            'black': {},
            'red': {}
        }
        self._initialize_pieces()
        self.turn = 'red'

    def _initialize_pieces(self):
        # Initialize black pieces
        black_positions = {
            'X1': (1,0), 'M2': (2,0), 'T3': (3,0), 'S4': (4,0),
            'Tg': (5,0), 'S6': (6,0), 'T7': (7,0), 'M8': (8,0),
            'X9': (9,0), 'P2': (2,2), 'P8': (8,2), 'B1': (1,3),
            'B3': (3,3), 'B5': (5,3), 'B7': (7,3), 'B9': (9,3)
        }
        
        # Initialize red pieces
        red_positions = {
            'X9': (1,9), 'M8': (2,9), 'T7': (3,9), 'S6': (4,9),
            'Tg': (5,9), 'S4': (6,9), 'T3': (7,9), 'M2': (8,9),
            'X1': (9,9), 'P8': (2,7), 'P2': (8,7), 'B9': (1,6),
            'B7': (3,6), 'B5': (5,6), 'B3': (7,6), 'B1': (9,6)
        }

        for name, pos in black_positions.items():
            self.pieces['black'][name] = ChessPiece(name, 'black', pos)
        for name, pos in red_positions.items():
            self.pieces['red'][name] = ChessPiece(name, 'red', pos)

    def get_piece_at(self, position: tuple[int, int]) -> ChessPiece | None:
        for color_dict in self.pieces.values():
            for piece in color_dict.values():
                if piece.position == position:
                    return piece
        return None
    
    def move_piece(self, color:str, piece_name: str, new_position: tuple[int, int]) -> None:
        if color in self.pieces and piece_name in self.pieces[color]:
            target_piece = self.get_piece_at(new_position)
            if target_piece:
                target_piece.position = (-1, -1)  # Move captured piece off board
            
            # Move the piece
            self.pieces[color][piece_name].move_to(new_position)

    def draw(self, screen: pygame.Surface) -> None:
        for color_dict in self.pieces.values():
            for piece in color_dict.values():
                piece.draw(screen)
    def switch_turn(self) -> None:
        self.turn = 'red' if self.turn == 'black' else 'black'