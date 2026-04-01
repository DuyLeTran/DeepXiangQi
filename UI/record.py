import pygame
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from App.configuration import Settings
from utils.storeGameData import GameDataTree, Node

class RecordView:
    """Render helper for the 'Biên bản' (move record) tab."""

    def __init__(self, screen: pygame.Surface, font_path: str):
        self.screen = screen
        self.font_path = font_path
        self.header_font = pygame.font.Font(self.font_path, 28)
        self.row_font = pygame.font.Font(self.font_path, 26)
        # Viewport for scrolling (panel right): x ~ 810, width ~ 592, y from 50 -> 900
        self.panel_x = 810
        self.panel_w = 592
        self.viewport = pygame.Rect(self.panel_x, 50, self.panel_w, 850)  # 50 -> 900
        self.header_h = 40
        self.row_h = 45         # size of a row in pixels 810/45=18 rows
        self.scroll_offset = 0  # in pixels, 0 means top
        self.game_tree = GameDataTree()
        self.items: list[tuple[str, str, Node]] = []  # (move, note, node); STT is auto
        self.row_rects: list[pygame.Rect] = []  # cached on draw for hit-test
        self.current_node_index = -1  # Index of the current node in items (for highlighting)
        # Branch button state
        project_root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        branch_image_path = os.path.join(project_root, "assets", "branch.png")
        try:
            self.branch_image = pygame.image.load(branch_image_path).convert_alpha()
            # Scale to fit row height
            button_size = int(self.row_h * 0.7)  # 70% of row height
            self.branch_image = pygame.transform.scale(self.branch_image, (button_size, button_size))
        except:
            self.branch_image = None
        self.branch_button_rects: list[pygame.Rect] = []  # cached on draw for hit-test
        # Dropdown state
        self.dropdown_open_for_node: Node | None = None  # Node whose dropdown is currently open
        self.dropdown_rect: pygame.Rect | None = None  # Dropdown position rect
        self.dropdown_item_rects: list[pygame.Rect] = []  # Rects for each dropdown item
    
    def set_viewport(self, viewport: pygame.Rect) -> None:
        self.viewport = viewport
        self.panel_x = viewport.x
        self.panel_w = viewport.width

    def sync_with_tree(self) -> None:
        """Sync items list with the main line in the game tree. Shows all moves and highlights the current one."""
        old_count = len(self.items)
        old_current_index = self.current_node_index
        # Get the main line (all moves from root to the last node)
        main_line = self.game_tree.get_main_line()
        current_node = self.game_tree.get_current_node()
        
        self.items = []
        self.current_node_index = -1
        
        # Find the closest node to current_node that is in the main line.
        # If current_node is not in the main line, walk up to find the nearest ancestor that is.
        node_to_highlight = current_node
        if current_node not in main_line:
            # Walk up to find the nearest ancestor in the main line
            temp_node = current_node
            while temp_node is not None and temp_node not in main_line:
                if temp_node.parent is not None:
                    temp_node = temp_node.parent
                else:
                    break
            if temp_node in main_line:
                node_to_highlight = temp_node
        
        for idx, node in enumerate(main_line[1:], start=0):  # Skip root node (no move)
            # Prefer compact move notation from node.move_type; fallback to raw move text
            move_text = getattr(node, 'move_type', None)
            if not isinstance(move_text, str) or not move_text:
                move_text = node.move or ""
            note_text = node.note or ""
            # Store the node corresponding to this row (to know which nodes have multiple children)
            try:
                parent_node = node.parent
            except:
                parent_node = None
            self.items.append((move_text, note_text, parent_node))
            
            # Mark the index of the node to highlight (current node or nearest ancestor in main line)
            if node == node_to_highlight:
                self.current_node_index = idx
        
        # Auto-scroll logic
        if len(self.items) > old_count:
            # A new move was added (forward navigation) — scroll to the current move
            if self.current_node_index >= 0:
                self.scroll_to_row(self.current_node_index)
        elif self.current_node_index != old_current_index and self.current_node_index >= 0:
            # current_node_index changed (forward/backward) — scroll to the current move
            self.scroll_to_row(self.current_node_index)

    def draw_header(self) -> None:
        """Draw table header: 'STT' | 'Nước cờ' | 'Ghi chú' in the right panel."""
        if self.viewport.width <= 0 or self.viewport.height <= 0:
            return
        # Right panel panel at x ~ 809, width ~ 592, height ~ 850 (per renderer border)
        base_x = self.panel_x
        base_y = self.viewport.top
        total_w = self.panel_w
        col_widths = [int(total_w * 0.2), int(total_w * 0.4), int(total_w * 0.4)]
        col_widths[-1] = total_w - col_widths[0] - col_widths[1]
        col_labels = ["STT", "Nước cờ", "Ghi chú"]
        row_h = self.header_h

        x = base_x
        # Optional header background band (transparent here to match BookView's latest update)
        header_rect = pygame.Rect(base_x - 6, base_y - 4, sum(col_widths) + 12, row_h + 8)
        header_overlay = pygame.Surface((header_rect.width, header_rect.height), pygame.SRCALPHA)
        header_overlay.fill((200, 200, 200, 0))
        self.screen.blit(header_overlay, header_rect.topleft)

        for w, label in zip(col_widths, col_labels):
            cell_rect = pygame.Rect(x, base_y, w, row_h)
            pygame.draw.rect(self.screen, Settings.Colors.BLACK, cell_rect, width=1)

            text_surf = self.header_font.render(label, True, Settings.Colors.BLACK)
            text_rect = text_surf.get_rect(center=cell_rect.center)
            self.screen.blit(text_surf, text_rect.topleft)
            x += w

    def clear(self) -> None:
        self.items = []
        self.scroll_offset = 0

    def scroll(self, delta_pixels: int) -> None:
        """Scroll the list by delta_pixels; positive moves down (content up)."""
        # Content height is only the list rows (excluding header)
        list_content_h = len(self.items) * self.row_h
        # Available space for list (viewport minus header)
        list_area_h = self.viewport.height - self.header_h
        # Max offset: when scrolled, first row should be at header bottom
        max_offset = max(0, list_content_h - list_area_h)
        self.scroll_offset = max(0, min(self.scroll_offset + delta_pixels, max_offset))
    
    def scroll_to_bottom(self) -> None:
        """Scroll to show the last row (bottom of the list)."""
        # Content height is only the list rows (excluding header)
        list_content_h = len(self.items) * self.row_h
        # Available space for list (viewport minus header)
        list_area_h = self.viewport.height - self.header_h
        # Max offset: when scrolled, first row should be at header bottom
        max_offset = max(0, list_content_h - list_area_h)
        self.scroll_offset = max_offset
    
    def ensure_last_row_visible(self) -> None:
        """Ensure the last row is visible in the viewport."""
        if not self.items:
            return
        # Content height is only the list rows (excluding header)
        list_content_h = len(self.items) * self.row_h
        # Available space for list (viewport minus header)
        list_area_h = self.viewport.height - self.header_h
        # Position of last row relative to list area start
        last_row_top = self.viewport.top + self.header_h + (len(self.items) - 1) * self.row_h - self.scroll_offset
        
        header_bottom = self.viewport.top + self.header_h
        # If last row is above list area (would overlap header), scroll down
        if last_row_top < header_bottom:
            self.scroll_offset = max(0, (len(self.items) - 1) * self.row_h - list_area_h)
        # If last row is below viewport, scroll down to show it
        elif last_row_top + self.row_h > self.viewport.bottom:
            self.scroll_to_bottom()
    
    def scroll_to_row(self, row_index: int) -> None:
        """
        Scroll to ensure the row at row_index (0-based) is visible in the viewport.
        If already visible, scroll is unchanged. Otherwise, center the row in the viewport if possible.
        """
        if row_index < 0 or row_index >= len(self.items):
            return
        
        list_area_h = self.viewport.height - self.header_h
        header_bottom = self.viewport.top + self.header_h
        
        # Row's position within the list (excluding header)
        row_top_in_list = row_index * self.row_h
        row_bottom_in_list = row_top_in_list + self.row_h
        
        # Row's current screen position (relative to header_bottom)
        row_top_on_screen = header_bottom + row_top_in_list - self.scroll_offset
        row_bottom_on_screen = header_bottom + row_bottom_in_list - self.scroll_offset
        
        # If row is already fully visible, no scroll needed
        if row_top_on_screen >= header_bottom and row_bottom_on_screen <= self.viewport.bottom:
            return
        
        # Compute new scroll offset to bring row into view,
        # preferring to center it in the viewport
        target_row_center = row_top_in_list + self.row_h // 2
        target_scroll = target_row_center - list_area_h // 2
        
        # Clamp scroll offset to valid range
        list_content_h = len(self.items) * self.row_h
        max_offset = max(0, list_content_h - list_area_h)
        self.scroll_offset = max(0, min(target_scroll, max_offset))

    def draw_list(self) -> None:
        """Draw rows within the viewport, clipped, and a scrollbar."""
        if self.viewport.width <= 0 or self.viewport.height <= 0:
            return
        # Clip to list area only (below header), not entire viewport
        list_area = pygame.Rect(self.panel_x, self.viewport.top + self.header_h, 
                               self.panel_w, self.viewport.height - self.header_h)
        prev_clip = self.screen.get_clip()
        self.screen.set_clip(list_area)

        # Columns: match header widths
        col_widths = [int(self.panel_w * 0.2), int(self.panel_w * 0.4), int(self.panel_w * 0.4)]
        col_widths[-1] = self.panel_w - col_widths[0] - col_widths[1]
        x = self.panel_x
        # y_start: position of first row (index 1) relative to list area start
        y_start = self.viewport.top + self.header_h - self.scroll_offset

        # Background for list area
        list_bg = pygame.Rect(self.panel_x, self.viewport.top + self.header_h, self.panel_w, self.viewport.height - self.header_h)
        bg_overlay = pygame.Surface((list_bg.width, list_bg.height), pygame.SRCALPHA)
        bg_overlay.fill((255, 255, 255, 0))
        self.screen.blit(bg_overlay, list_bg.topleft)

        self.row_rects = []
        self.branch_button_rects = []
        for idx, (move_text, note_text, parent_node) in enumerate(self.items, start=1):
            row_y = y_start + (idx - 1) * self.row_h
            # Row rects
            stt_rect = pygame.Rect(x + 0, row_y, col_widths[0], self.row_h)
            move_rect = pygame.Rect(x + col_widths[0], row_y, col_widths[1], self.row_h)
            note_rect = pygame.Rect(x + col_widths[0] + col_widths[1], row_y, col_widths[2], self.row_h)

            # Only draw rows that are fully or partially visible in list area (below header)
            # Ensure row doesn't overlap with header area
            header_bottom = self.viewport.top + self.header_h
            if stt_rect.bottom <= header_bottom or stt_rect.top >= self.viewport.bottom:
                continue

            # Cache a combined rect for hit-test (span across all columns)
            combined_rect = pygame.Rect(stt_rect.x, row_y, sum(col_widths), self.row_h)
            self.row_rects.append(combined_rect)

            # Highlight the current node (active move)
            # current_node_index is 0-based; idx is 1-based (row number)
            if self.current_node_index >= 0 and (idx - 1) == self.current_node_index:
                hl_bg = pygame.Surface((combined_rect.width, combined_rect.height), pygame.SRCALPHA)
                hl_bg.fill((0, 120, 215, 40))  # RGBA
                self.screen.blit(hl_bg, combined_rect.topleft)

            # Draw borders
            pygame.draw.rect(self.screen, Settings.Colors.BLACK, stt_rect, width=1)
            pygame.draw.rect(self.screen, Settings.Colors.BLACK, move_rect, width=1)
            pygame.draw.rect(self.screen, Settings.Colors.BLACK, note_rect, width=1)

            # Render text (center vertically, left padding 6px)
            stt_surf = self.row_font.render(str(idx), True, Settings.Colors.BLACK)
            stt_pos = (stt_rect.x + 6, stt_rect.y + (self.row_h - stt_surf.get_height()) // 2)
            self.screen.blit(stt_surf, stt_pos)

            move_surf = self.row_font.render(move_text, True, Settings.Colors.BLACK)
            move_rect_centered = move_surf.get_rect(center=move_rect.center)
            self.screen.blit(move_surf, move_rect_centered.topleft)

            note_surf = self.row_font.render(note_text, True, Settings.Colors.BLACK)
            note_pos = (note_rect.x + 6, note_rect.y + (self.row_h - note_surf.get_height()) // 2)
            self.screen.blit(note_surf, note_pos)
            
            # Draw branch button if parent node has len > 1 (multiple children)
            if parent_node is not None and len(parent_node.children) > 1 and self.branch_image:
                button_size = self.branch_image.get_width()
                button_x = stt_rect.right - button_size - 5  # Right side of note column, 5px padding
                button_y = row_y + (self.row_h - button_size) // 2  # Center vertically
                branch_button_rect = pygame.Rect(button_x, button_y, button_size, button_size)
                self.branch_button_rects.append((branch_button_rect, parent_node))
                self.screen.blit(self.branch_image, branch_button_rect.topleft)

        # Restore clip
        self.screen.set_clip(prev_clip)

        # Draw dropdown if open
        self._draw_dropdown()

        # Draw a simple scrollbar at panel right
        self._draw_scrollbar()

    def _draw_scrollbar(self) -> None:
        # Scrollbar geometry
        bar_x = self.panel_x + self.panel_w - 10
        bar_rect = pygame.Rect(bar_x, self.viewport.top + self.header_h, 6, self.viewport.height - self.header_h)
        pygame.draw.rect(self.screen, Settings.Colors.DARK_GRAY, bar_rect, width=1)

        # Content height is only the list rows (excluding header)
        list_content_h = len(self.items) * self.row_h
        # Available space for list (viewport minus header)
        list_area_h = self.viewport.height - self.header_h
        if list_content_h <= list_area_h:
            return
        # Thumb height proportional to visible/content
        thumb_h = max(24, int((list_area_h / list_content_h) * bar_rect.height))
        max_offset = list_content_h - list_area_h
        ratio = (self.scroll_offset / max_offset) if max_offset > 0 else 0
        thumb_y = bar_rect.y + int((bar_rect.height - thumb_h) * ratio)
        thumb_rect = pygame.Rect(bar_rect.x + 1, thumb_y, bar_rect.width - 2, thumb_h)
        # Thumb fill
        thumb_overlay = pygame.Surface((thumb_rect.width, thumb_rect.height), pygame.SRCALPHA)
        thumb_overlay.fill((0, 0, 0, 80))
        self.screen.blit(thumb_overlay, thumb_rect.topleft)

    def _draw_dropdown(self) -> None:
        """Draw dropdown menu for branch variations."""
        if self.dropdown_open_for_node is None or self.dropdown_rect is None:
            return
        
        # Draw dropdown background
        dropdown_bg = pygame.Surface((self.dropdown_rect.width, self.dropdown_rect.height), pygame.SRCALPHA)
        dropdown_bg.fill((255, 255, 255, 255))  # White background
        self.screen.blit(dropdown_bg, self.dropdown_rect.topleft)
        pygame.draw.rect(self.screen, Settings.Colors.BLACK, self.dropdown_rect, width=1)
        
        # Draw dropdown items
        self.dropdown_item_rects = []
        item_height = 35
        for idx, child in enumerate(self.dropdown_open_for_node.children):
            item_y = self.dropdown_rect.y + idx * item_height
            item_rect = pygame.Rect(self.dropdown_rect.x, item_y, self.dropdown_rect.width, item_height)
            self.dropdown_item_rects.append((item_rect, child))
            
            # Highlight if hovered (optional, can add later)
            pygame.draw.rect(self.screen, Settings.Colors.BLACK, item_rect, width=1)
            
            # Draw move text
            move_text = getattr(child, 'move_type', None)
            if not isinstance(move_text, str) or not move_text:
                move_text = child.move or ""
            text_surf = self.row_font.render(f"{idx + 1}. {move_text}", True, Settings.Colors.BLACK)
            text_pos = (item_rect.x + 6, item_rect.y + (item_height - text_surf.get_height()) // 2)
            self.screen.blit(text_surf, text_pos)

    def draw(self) -> None:
        """Draw header + list within viewport."""
        self.draw_header()
        self.draw_list()

    def hit_row(self, mouse_pos: tuple[int, int]) -> int:
        """Return 0-based item index if a visible row is clicked, else -1."""
        if not self.row_rects:
            return -1
        for idx, rect in enumerate(self.row_rects):
            if rect.collidepoint(mouse_pos):
                # Map rect (screen space) already accounts for scroll_offset
                return idx
        return -1
    
    def hit_branch_button(self, mouse_pos: tuple[int, int]) -> Node | None:
        """Return parent node if branch button is clicked, else None."""
        for button_rect, parent_node in self.branch_button_rects:
            if button_rect.collidepoint(mouse_pos):
                return parent_node
        return None
    
    def open_dropdown(self, node: Node, button_rect: pygame.Rect) -> None:
        """Open dropdown menu for a node with multiple children."""
        self.dropdown_open_for_node = node
        # Position dropdown below button
        dropdown_width = 125
        dropdown_height = min(len(node.children) * 35, 200)  # Max 200px height
        dropdown_x = button_rect.right - dropdown_width
        dropdown_y = button_rect.bottom + 2
        # Ensure dropdown doesn't go outside viewport
        if dropdown_y + dropdown_height > self.viewport.bottom:
            dropdown_y = button_rect.top - dropdown_height - 2
        self.dropdown_rect = pygame.Rect(dropdown_x, dropdown_y, dropdown_width, dropdown_height)
        self.dropdown_item_rects = []
    
    def close_dropdown(self) -> None:
        """Close dropdown menu."""
        self.dropdown_open_for_node = None
        self.dropdown_rect = None
        self.dropdown_item_rects = []
    
    def hit_dropdown_item(self, mouse_pos: tuple[int, int]) -> tuple[int, Node] | None:
        """Return (child_index, child_node) if dropdown item is clicked, else None."""
        for item_rect, child_node in self.dropdown_item_rects:
            if item_rect.collidepoint(mouse_pos):
                # Find index of child in parent's children list
                if self.dropdown_open_for_node is not None:
                    for idx, child in enumerate(self.dropdown_open_for_node.children):
                        if child == child_node:
                            return (idx, child_node)
        return None


