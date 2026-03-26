from utils.storeGameData import GameDataTree, Node
from App.piece import ChessBoard


class Navigation:
    """Handles forward/backward navigation through the game tree."""
    
    def __init__(self, chess_board: ChessBoard, game_tree: GameDataTree):
        self.chess_board = chess_board
        self.game_tree = game_tree
    
    def go_backward_one_move(self) -> bool:
        """
        Go back one move.
        Returns True on success, False if already at root or no move to undo.
        """
        if self.game_tree.current.move is None or self.game_tree.current.is_root():
            return False
        
        # Parse move string: "X1 (1,0) (1,1)"
        parts = self.game_tree.current.move.split(' ')
        piece_name = parts[0]
        old_pos_str = parts[1].strip('()')
        new_pos_str = parts[2].strip('()')
        old_position = tuple(map(int, old_pos_str.split(',')))
        new_position = tuple(map(int, new_pos_str.split(',')))
        
        # Find the piece currently at new_position (the piece that just moved)
        moved_piece = self.chess_board.get_piece_at(new_position)
        
        if moved_piece and moved_piece.name == piece_name:
            # Move piece back to its original position
            moved_piece.move_to(old_position)
            
            # Restore the captured piece if any
            captured_piece = self.game_tree.current.captured_piece
            if captured_piece is not None:
                # Check whether the captured_piece reference is still valid
                # (piece object exists and is currently at (-1, -1))
                if captured_piece.position == (-1, -1):
                    # Valid reference: restore to new_position
                    captured_piece.position = new_position
                # If the reference is stale (reset after a navigate call),
                # we cannot restore the exact captured piece;
                # this is handled in navigate_to_node by refreshing the reference.

            # Move up to the parent node
            self.game_tree.go_parent()
            # Switch turn back to the side that just moved
            self.chess_board.switch_turn()
            return True
        
        return False
    
    def go_forward_one_move(self) -> bool:
        """
        Advance one move (child selected by last_choice, or first child if last_choice is unset).
        Returns True on success, False if there are no children.
        """
        if len(self.game_tree.current.children) == 0:
            return False
        
        # Select child by last_choice (or first child if last_choice is out of range)
        choice_index = self.game_tree.current.last_choice if 0 <= self.game_tree.current.last_choice < len(self.game_tree.current.children) else 0
        child_node = self.game_tree.current.children[choice_index]
        if child_node.move is None:
            return False
        
        # Parse move string: "X1 (1,0) (1,1)"
        parts = child_node.move.split(' ')
        piece_name = parts[0]
        old_pos_str = parts[1].strip('()')
        new_pos_str = parts[2].strip('()')
        old_position = tuple(map(int, old_pos_str.split(',')))
        new_position = tuple(map(int, new_pos_str.split(',')))
        
        # Find the piece at old_position
        moved_piece = self.chess_board.get_piece_at(old_position)
        if moved_piece and moved_piece.name == piece_name:
            # Check for any piece at new_position (will be captured)
            captured_piece = self.chess_board.get_piece_at(new_position)
            if captured_piece:
                # Remove captured piece from the board
                captured_piece.position = (-1, -1)
                # Update the captured_piece reference in child_node with the current board object
                # so that going backward can restore it correctly
                child_node.captured_piece = captured_piece
            
            # Move piece to its new position
            moved_piece.move_to(new_position)
            
            # Advance to the child node by last_choice
            self.game_tree.go_child(choice_index)
            # Switch turn
            self.chess_board.switch_turn()
            return True
        
        return False
    
    def navigate_to_index(self, target_index: int) -> bool:
        """
        Navigate to the move at target_index in the main line.
        Computes the required forward/backward steps from the current position.
        target_index: 0 = root, 1 = first move, 2 = second move, ...
        Returns True on success, False if target_index is out of range.
        """
        main_line = self.game_tree.get_main_line()
        if target_index < 0 or target_index >= len(main_line):
            return False
        
        # Find the current position index in main_line
        current_index = -1
        for idx, node in enumerate(main_line):
            if node == self.game_tree.current:
                current_index = idx
                break
        
        # If not found in main_line, we may be on a branch — go back to root first
        if current_index == -1:
            # Go backward to root
            while not self.game_tree.current.is_root():
                if not self.go_backward_one_move():
                    # Cannot go further back; may already be at root or an error occurred
                    break
            current_index = 0
        
        # Calculate the number of forward or backward steps needed
        if current_index < target_index:
            # Need to go forward
            for _ in range(target_index - current_index):
                if not self.go_forward_one_move():
                    return False
        elif current_index > target_index:
            # Need to go backward
            for _ in range(current_index - target_index):
                if not self.go_backward_one_move():
                    return False
        
        return True
    
    def navigate_to_node(self, target_node: Node) -> bool:
        """
        Navigate to a specific node by finding the path from root and replaying all moves.
        Returns True on success, False if no path to the node is found.
        """
        # Find path from root to target_node
        def find_path_to_node(root: Node, target: Node, path: list[Node] = None) -> list[Node] | None:
            if path is None:
                path = []
            path.append(root)
            if root == target:
                return path
            for child in root.children:
                result = find_path_to_node(child, target, path.copy())
                if result:
                    return result
            return None
        
        path = find_path_to_node(self.game_tree.root, target_node)
        if not path:
            return False
        
        # Go backward to root to restore the board to the root state
        # (do not use reset() because root may not be the initial position when using setup/FEN)
        while not self.game_tree.current.is_root():
            if not self.go_backward_one_move():
                # Cannot go further back; board state may not match current node.
                # We still attempt to continue rather than resetting,
                # since root may not be the original starting position.
                break
        self.game_tree.go_root()
        
        # Replay all moves in the path (skip root)
        for node in path[1:]:
            if node.move:
                parts = node.move.split(' ')
                piece_name = parts[0]
                old_pos_str = parts[1].strip('()')
                new_pos_str = parts[2].strip('()')
                old_position = tuple(map(int, old_pos_str.split(',')))
                new_position = tuple(map(int, new_pos_str.split(',')))
                
                moved_piece = self.chess_board.get_piece_at(old_position)
                if moved_piece and moved_piece.name == piece_name:
                    captured_piece = self.chess_board.get_piece_at(new_position)
                    if captured_piece:
                        captured_piece.position = (-1, -1)
                        # Refresh the captured_piece reference with the current board object
                        # so that going backward can restore it correctly
                        node.captured_piece = captured_piece
                    moved_piece.move_to(new_position)
                    self.chess_board.switch_turn()
            
            # Advance to this node in the tree
            # Find the child index of this node under its parent
            if node.parent is not None:
                for idx, child in enumerate(node.parent.children):
                    if child == node:
                        self.game_tree.go_child(idx)
                        break
        
        return True
