class Node:
    def __init__(self, turn: str = 'red', move: str | None = None, note: str | None = None, parent: 'Node | None' = None):
        self.turn = turn  # side to move AFTER this node is applied
        self.move = move  # notation like "X1 (1,0) (1,1)"
        self.note = note
        self.move_type = self.type_of_move()        
        self.parent = parent
        self.children: list[Node] = []
        self.captured_piece = None
        self.last_choice: int = 0  # Index of the last selected child (default 0)

    def __len__(self) -> int:
        return len(self.parent.children)

    def add_child(self, turn: str, move: str, note: str | None = None, captured_piece = None) -> 'Node':
        child = Node(turn=turn, move=move, note=note, parent=self)
        child.captured_piece = captured_piece
        self.children.append(child)
        # Update last_choice to the index of the newly added child
        self.last_choice = len(self.children) - 1
        return child

    def is_root(self) -> bool:
        return self.parent is None

    def type_of_move(self) -> str:
        name, old_position, new_position = self.move.split(' ') if self.move else (None, None, None)
        if old_position and new_position:
            old_position = tuple(map(int, old_position.strip('()').split(',')))
            new_position = tuple(map(int, new_position.strip('()').split(',')))
        else:
            old_position = (None, None)
            new_position = (None, None)

        # return name, self.turn, old_position, new_position
        # if name != 'Tg': name = name[0]
        if name is None or old_position is None or  new_position is None: return name, self.turn, old_position, new_position 
        if name != 'Tg':
            name = name[0]
        else:
            name = name  # Tg
        
        if self.turn == 'red':
            if   old_position[0] != new_position[0] and old_position[1] == new_position[1]: return f'{name}{10-int(old_position[0])}-{10-int(new_position[0])}'
            elif old_position[0] == new_position[0] and old_position[1] > new_position[1]:  return f'{name}{10-int(old_position[0])}.{int(old_position[1])- int(new_position[1])}'
            elif old_position[0] == new_position[0] and old_position[1] < new_position[1]:  return f'{name}{10-int(old_position[0])}/{abs(int(old_position[1])- int(new_position[1]))}'
            elif old_position[0] != new_position[0] and old_position[1] > new_position[1]:  return f'{name}{10-int(old_position[0])}.{10-int(new_position[0])}'
            elif old_position[0] != new_position[0] and old_position[1] < new_position[1]:  return f'{name}{10-int(old_position[0])}/{10-int(new_position[0])}'
        else:
            if   old_position[0] != new_position[0] and old_position[1] == new_position[1]: return f'{name}{int(old_position[0])}-{int(new_position[0])}'
            elif old_position[0] == new_position[0] and old_position[1] > new_position[1]:  return f'{name}{int(old_position[0])}/{int(old_position[1])- int(new_position[1])}'
            elif old_position[0] == new_position[0] and old_position[1] < new_position[1]:  return f'{name}{int(old_position[0])}.{abs(int(old_position[1])- int(new_position[1]))}'
            elif old_position[0] != new_position[0] and old_position[1] > new_position[1]:  return f'{name}{int(old_position[0])}/{int(new_position[0])}'
            elif old_position[0] != new_position[0] and old_position[1] < new_position[1]:  return f'{name}{int(old_position[0])}.{int(new_position[0])}'

class GameDataTree:
    def __init__(self):
        # Root represents initial position before any move
        self.root = Node(turn='red', move=None, note=None, parent=None)
        self.current = self.root    
    # --- Navigation ---
    def go_root(self) -> None:
        self.current = self.root
        return self.current

    def go_parent(self) -> None:
        if self.current.parent is not None:
            self.current = self.current.parent

    def go_child(self, index: int) -> None:
        if 0 <= index < len(self.current.children):
            self.current = self.current.children[index]

    # --- Mutation ---
    def reset(self) -> None:
        """Reset the tree to its initial state (create a fresh root, discard all data)."""
        # Create a new root, clearing all previous data
        self.root = Node(turn='red', move=None, note=None, parent=None)
        self.current = self.root
    
    def add_move(self, turn: str, move: str, note: str | None = None, captured_piece = None) -> Node:
        """Add a child under current node and move current pointer to it."""
        # Check whether this move already exists among the children
        for index, node in enumerate(self.current.children):
            if node.move == move:
                # Already exists: switch to that branch and update last_choice
                self.current.last_choice = index
                self.current = node
                return self.current
        # Not found: create a new branch
        self.current = self.current.add_child(turn=turn, move=move, note=note, captured_piece=captured_piece)
        return self.current

    # --- Accessors ---
    def get_children(self) -> list[Node]:
        return self.current.children

    def get_current_path(self) -> list[Node]:
        path: list[Node] = []
        node = self.current
        while node is not None:
            path.append(node)
            node = node.parent
        path.reverse()
        return path

    def get_current_node(self) -> Node:
        return self.current
    
    def get_main_line(self) -> list[Node]:
        """
        Return the main line from root to the last node.
        At each node the child selected by last_choice is followed.
        """
        path: list[Node] = []
        node = self.root
        while node is not None:
            path.append(node)
            # Follow child by last_choice (or first child if last_choice is out of range)
            if len(node.children) > 0:
                choice_index = node.last_choice if 0 <= node.last_choice < len(node.children) else 0
                node = node.children[choice_index]
            else:
                break
        return path
    
    def go_to_main_line_index(self, index: int) -> bool:
        """
        Move current pointer to the node at index in the main line.
        index: 0 = root, 1 = first move, 2 = second move, ...
        Returns True on success, False if index is out of range.
        """
        main_line = self.get_main_line()
        if 0 <= index < len(main_line):
            self.current = main_line[index]
            return True
        return False

if __name__ == "__main__":
    tree = GameDataTree()
    tree.add_move('red', 'X1 (1,0) (1,1)', 'Note 1')
    tree.add_move('black', 'X2 (2,0) (2,1)', 'Note 2')
    # print(tree.get_current_path())
    # print(tree.current.move, tree.current.turn)

    # for node in tree.get_current_path():
    #     print(node.move, node.turn)
    # print(tree.current.move)
    # print(tree.current.move_type[2], type(tree.current.move_type[2]))
    # print(tree.current.move_type[3], type(tree.current.move_type[3]))
    # print(tree.current.move_type)
    # print(tree.get_current_path()[2].move)
    # print(tree.get_previous_node().move)
    # print(tree.current.move)
    tree.go_parent()
    tree.add_move('black', 'P8 (8,2) (8,4)', 'Note 2')
    # print(tree.current.move)

    # tree.go_parent()
    # print(len(tree.current.children))
    # print(tree.current.__len__())
    print(tree.current.move)