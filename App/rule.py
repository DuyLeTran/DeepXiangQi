import pygame
from piece import ChessPiece, ChessBoard

class Rule:
    def __init__(self, chess_board: ChessBoard):
        self.chess_board = chess_board

    def get_valid_moves(self, piece: ChessPiece, check_for_check: bool = True) -> list[tuple[int, int]]:
        piece_type = piece.name[0]
        basic_moves = []
        
        if piece_type == 'X':
            basic_moves = self._get_rook_moves(piece)
        elif piece_type == 'M':
            basic_moves = self._get_knight_moves(piece)
        elif piece_type == 'T' and piece.name != 'Tg':
            basic_moves = self._get_elephant_moves(piece)
        elif piece_type == 'S':
            basic_moves = self._get_advisor_moves(piece)
        elif piece.name == 'Tg':
            basic_moves = self._get_king_moves(piece)
        elif piece_type == 'P':
            basic_moves = self._get_cannon_moves(piece)
        elif piece_type == 'B':
            basic_moves = self._get_pawn_moves(piece)
        
        if not check_for_check:
            return basic_moves
        
        # Filter out moves that would leave the king in check
        safe_moves = []
        for move in basic_moves:
            # Simulate the move
            original_pos = piece.position
            captured_piece = self.chess_board.get_piece_at(move)
            
            # Make the move
            piece.move_to(move)
            if captured_piece:
                captured_piece.position = (-1, -1)
            
            # Check if this move leaves the king in check
            if not self.is_in_check(piece.color):
                safe_moves.append(move)
            
            # Undo the move
            piece.move_to(original_pos)
            if captured_piece:
                captured_piece.position = move
        
        return safe_moves
    def _is_valid_position(self, pos: tuple[int, int]) -> bool:
        '''Check if the position is within the board'''
        x, y = pos
        return 1 <= x <= 9 and 0 <= y <= 9
    
    def _is_same_color(self, piece1: ChessPiece, piece2: ChessPiece) -> bool:
        return piece1.color == piece2.color

    def _get_piece_at(self, pos: tuple[int, int]) -> ChessPiece | None:
        return self.chess_board.get_piece_at(pos)
    
    
    def _get_rook_moves(self, piece: ChessPiece) -> list[tuple[int, int]]:
        valid_moves = []
        x, y = piece.position

        # Check moves in all four directions
        directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            while self._is_valid_position((nx, ny)):
                target = self._get_piece_at((nx, ny))
                if target is None:
                    valid_moves.append((nx, ny))
                elif not self._is_same_color(piece, target):
                    valid_moves.append((nx, ny))
                    break
                else:
                    break
                nx += dx
                ny += dy

        return valid_moves

    def _get_knight_moves(self, piece: ChessPiece) -> list[tuple[int, int]]:
        valid_moves = []
        x, y = piece.position
        moves = [
            (2, 1), (2, -1), (-2, 1), (-2, -1),
            (1, 2), (1, -2), (-1, 2), (-1, -2)
        ]

        for dx, dy in moves:
            nx, ny = x + dx, y + dy
            if self._is_valid_position((nx, ny)):
                # Check for blocking pieces
                if abs(dx) == 2:
                    block_x = x + (dx // 2)
                    block_y = y
                else:
                    block_x = x
                    block_y = y + (dy // 2)

                if self._get_piece_at((block_x, block_y)) is None:
                    target = self._get_piece_at((nx, ny))
                    if target is None or not self._is_same_color(piece, target):
                        valid_moves.append((nx, ny))

        return valid_moves

    def _get_elephant_moves(self, piece: ChessPiece) -> list[tuple[int, int]]:
        valid_moves = []
        x, y = piece.position
        moves = [(2, 2), (2, -2), (-2, 2), (-2, -2)]

        for dx, dy in moves:
            nx, ny = x + dx, y + dy
            if self._is_valid_position((nx, ny)):
                # Check if move is within the correct half of the board
                if (piece.color == 'red' and ny >= 5) or (piece.color == 'black' and ny <= 4):
                    # Check for blocking pieces
                    block_x = x + (dx // 2)
                    block_y = y + (dy // 2)
                    if self._get_piece_at((block_x, block_y)) is None:
                        target = self._get_piece_at((nx, ny))
                        if target is None or not self._is_same_color(piece, target):
                            valid_moves.append((nx, ny))

        return valid_moves

    def _get_advisor_moves(self, piece: ChessPiece) -> list[tuple[int, int]]:
        valid_moves = []
        x, y = piece.position
        moves = [(1, 1), (1, -1), (-1, 1), (-1, -1)]

        for dx, dy in moves:
            nx, ny = x + dx, y + dy
            if self._is_valid_position((nx, ny)):
                # Check if move is within the palace
                if piece.color == 'red':
                    if 4 <= nx <= 6 and 7 <= ny <= 9:
                        target = self._get_piece_at((nx, ny))
                        if target is None or not self._is_same_color(piece, target):
                            valid_moves.append((nx, ny))
                else:  # black
                    if 4 <= nx <= 6 and 0 <= ny <= 2:
                        target = self._get_piece_at((nx, ny))
                        if target is None or not self._is_same_color(piece, target):
                            valid_moves.append((nx, ny))

        return valid_moves

    def _get_king_moves(self, piece: ChessPiece) -> list[tuple[int, int]]:
        valid_moves = []
        x, y = piece.position
        moves = [(1, 0), (-1, 0), (0, 1), (0, -1)]

        for dx, dy in moves:
            nx, ny = x + dx, y + dy
            if self._is_valid_position((nx, ny)):
                # Check if move is within the palace
                if piece.color == 'red':
                    if 4 <= nx <= 6 and 7 <= ny <= 9:
                        target = self._get_piece_at((nx, ny))
                        if target is None or not self._is_same_color(piece, target):
                            valid_moves.append((nx, ny))
                else:  # black
                    if 4 <= nx <= 6 and 0 <= ny <= 2:
                        target = self._get_piece_at((nx, ny))
                        if target is None or not self._is_same_color(piece, target):
                            valid_moves.append((nx, ny))

        # Check for flying general
        if piece.color == 'red':
            for ny in range(y - 1, -1, -1):
                target = self._get_piece_at((x, ny))
                if target is not None:
                    if target.name == 'Tg' and target.color == 'black':
                        valid_moves.append((x, ny))
                    break
        else:  # black
            for ny in range(y + 1, 10):
                target = self._get_piece_at((x, ny))
                if target is not None:
                    if target.name == 'Tg' and target.color == 'red':
                        valid_moves.append((x, ny))
                    break

        return valid_moves

    def _get_cannon_moves(self, piece: ChessPiece) -> list[tuple[int, int]]:
        valid_moves = []
        x, y = piece.position

        # Check moves in all four directions
        directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            jumped = False
            while self._is_valid_position((nx, ny)):
                target = self._get_piece_at((nx, ny))
                if target is None:
                    if not jumped:
                        valid_moves.append((nx, ny))
                else:
                    if not jumped:
                        jumped = True
                    else:
                        if not self._is_same_color(piece, target):
                            valid_moves.append((nx, ny))
                        break
                nx += dx
                ny += dy

        return valid_moves

    def _get_pawn_moves(self, piece: ChessPiece) -> list[tuple[int, int]]:
        valid_moves = []
        x, y = piece.position

        if piece.color == 'red':
            # Forward move
            if y > 0:
                target = self._get_piece_at((x, y - 1))
                if target is None or not self._is_same_color(piece, target):
                    valid_moves.append((x, y - 1))
            
            # Side moves after crossing the river
            if y <= 4:
                for dx in [-1, 1]:
                    nx = x + dx
                    if 1 <= nx <= 9:
                        target = self._get_piece_at((nx, y))
                        if target is None or not self._is_same_color(piece, target):
                            valid_moves.append((nx, y))
        else:  # black
            # Forward move
            if y < 9:
                target = self._get_piece_at((x, y + 1))
                if target is None or not self._is_same_color(piece, target):
                    valid_moves.append((x, y + 1))
            
            # Side moves after crossing the river
            if y >= 5:
                for dx in [-1, 1]:
                    nx = x + dx
                    if 1 <= nx <= 9:
                        target = self._get_piece_at((nx, y))
                        if target is None or not self._is_same_color(piece, target):
                            valid_moves.append((nx, y))

        return valid_moves 
    
    def is_in_check(self, color: str) -> bool:
        """Check if the king of the given color is in check"""
        # Find the king
        king = None
        for piece in self.chess_board.pieces[color].values():
            if piece.name == 'Tg':
                king = piece
                break
        
        if king is None:
            return False
        
        # Check if any opponent piece can attack the king
        opponent_color = 'red' if color == 'black' else 'black'
        for piece in self.chess_board.pieces[opponent_color].values():
            if piece.position == (-1, -1):  # Skip captured pieces
                continue
            valid_moves = self.get_valid_moves(piece, check_for_check=False)
            if king.position in valid_moves:
                return True
        
        return False
    
    def is_checkmate(self, color: str) -> bool:
        """Check if the given color is in checkmate"""
        # if not self.is_in_check(color):
        #     return False
        
        # Check if there are any valid moves that can get out of check
        for piece in self.chess_board.pieces[color].values():
            if piece.position == (-1, -1):  # Skip captured pieces
                continue
            valid_moves = self.get_valid_moves(piece, check_for_check=False)
            for move in valid_moves:
                # Simulate the move
                original_pos = piece.position
                captured_piece = self.chess_board.get_piece_at(move)
                
                # Make the move
                piece.move_to(move)
                if captured_piece:
                    captured_piece.position = (-1, -1)
                
                # Check if still in check after this move
                still_in_check = self.is_in_check(color)
                
                # Undo the move
                piece.move_to(original_pos)
                if captured_piece:
                    captured_piece.position = move
                
                if not still_in_check:
                    return False
        
        return True
    
    