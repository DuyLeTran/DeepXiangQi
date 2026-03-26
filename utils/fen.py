import pyperclip

from App.piece import ChessBoard, ChessPiece


class FENHandler:
    """Xiangqi FEN helper (copy/paste)."""
    
    # Piece letters (uppercase=red, lowercase=black)
    _TYPE_TO_FEN = {
        'X': 'R',   # rook (xe)
        'M': 'N',   # knight (mã)
        'T': 'B',   # bishop/elephant (tượng)
        'S': 'A',   # advisor (sĩ)
        'Tg': 'K',  # king (tướng)
        'P': 'C',   # cannon (pháo)
        'B': 'P',   # pawn (tốt)
    }

    # _FEN_TO_TYPE = {
    #     'r': 'X',
    #     'n': 'M',
    #     'b': 'T',
    #     'a': 'S',
    #     'k': 'Tg',
    #     'c': 'P',
    #     'p': 'B',
    # }

    _FEN_TO_TYPE = {
        'r': 'X',
        'n': 'M',
        'h': 'M',
        'b': 'T',
        'e': 'T',
        'a': 'S',
        'k': 'Tg',
        'c': 'P',
        'p': 'B',
    }

    # Naming scheme used by this codebase
    _NAME_BY_TYPE_AND_INDEX = {
        'X': [1, 9],
        'M': [2, 8],
        'T': [3, 7],
        'S': [4, 6],
        'P': [2, 8],
        'B': [1, 3, 5, 7, 9],
    }
    
    @staticmethod
    def to_fen(chess_board: ChessBoard) -> str:
        board = [['.' for _ in range(9)] for _ in range(10)]

        for color in ('black', 'red'):
            for piece_name, piece in chess_board.pieces[color].items():
                x, y = piece.position
                if not (1 <= x <= 9 and 0 <= y <= 9):
                    continue

                piece_type = 'Tg' if piece_name == 'Tg' else piece_name[0]
                fen_ch = FENHandler._TYPE_TO_FEN.get(piece_type, '.')
                fen_ch = fen_ch.upper() if color == 'red' else fen_ch.lower()
                board[y][x - 1] = fen_ch

        rows: list[str] = []
        for row in board:
            out = []
            empties = 0
            for cell in row:
                if cell == '.':
                    empties += 1
                    continue
                if empties:
                    out.append(str(empties))
                    empties = 0
                out.append(cell)
            if empties:
                out.append(str(empties))
            rows.append(''.join(out))

        turn_ch = 'r' if chess_board.turn == 'red' else 'b'
        return f"{'/'.join(rows)} {turn_ch}"
        # return f"{'/'.join(rows)} {turn_ch} 0 1"
    
    @staticmethod
    def from_fen(fen_string: str, chess_board: ChessBoard) -> bool:
        try:
            parts = fen_string.strip().split()
            if not parts:
                return False

            rows = parts[0].split('/')

            if len(rows) != 10:
                return False

            # Move all pieces to (-1, -1) instead of clearing
            for color in ('black', 'red'):
                for piece in chess_board.pieces[color].values():
                    piece.move_to((-1, -1))
            # chess_board.pieces = {'black': {}, 'red': {}}

            used: dict[str, dict[str, int]] = {'black': {}, 'red': {}}

            for y, row in enumerate(rows):
                x = 0
                for ch in row:
                    if ch.isdigit():
                        x += int(ch)
                        continue
                    if not ch.isalpha():
                        return False
                    if x >= 9:
                        return False

                    color = 'red' if ch.isupper() else 'black'
                    piece_type = FENHandler._FEN_TO_TYPE.get(ch.lower())
                    if not piece_type:
                        return False

                    if piece_type == 'Tg':
                        piece_name = 'Tg'
                    else:
                        idx = used[color].get(piece_type, 0)
                        nums = FENHandler._NAME_BY_TYPE_AND_INDEX[piece_type]
                        piece_name = f"{piece_type}{nums[idx] if idx < len(nums) else nums[-1]}"
                        used[color][piece_type] = idx + 1

                    chess_board.pieces[color][piece_name] = ChessPiece(piece_name, color, (x + 1, y))
                    x += 1

                if x != 9:
                    return False

            turn_ch = parts[1].lower() if len(parts) > 1 else 'r'
            chess_board.turn = 'red' if turn_ch in ('w','white', 'r', 'red') else 'black'
            return True
        except Exception as e:
            print(f"Error parsing FEN: {e}")
            return False
    
    @staticmethod
    def copy_fen(chess_board: ChessBoard) -> bool:
        try:
            pyperclip.copy(FENHandler.to_fen(chess_board))
            return True
        except Exception as e:
            print(f"Error copying FEN: {e}")
            return False
    
    @staticmethod
    def paste_fen(chess_board: ChessBoard) -> bool:
        try:
            fen_string = pyperclip.paste().strip()
            return bool(fen_string) and FENHandler.from_fen(fen_string, chess_board)
        except Exception as e:
            print(f"Error pasting FEN: {e}")
            return False
