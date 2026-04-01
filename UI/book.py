import pygame
import os
from App.configuration import Settings


class BookView:
    """Render helper for the 'Khai cuộc' (opening book) tab."""

    def __init__(self, screen: pygame.Surface, font_path: str):
        self.screen = screen
        self.font_path = font_path
        self.header_font = pygame.font.Font(self.font_path, 28)
        self.viewport = pygame.Rect(810, 50, 592, 850)

    def set_viewport(self, viewport: pygame.Rect) -> None:
        self.viewport = viewport

    def draw_header(self) -> None:
        """Draw table header: 'Nước cờ' | 'Điểm' | 'Hợp lệ' | 'Ghi chú' in the right panel."""
        if self.viewport.width <= 0 or self.viewport.height <= 0:
            return
        base_x = self.viewport.x
        base_y = self.viewport.y
        total_w = self.viewport.width
        col_widths = [int(total_w * 0.32), int(total_w * 0.17), int(total_w * 0.17), int(total_w * 0.34)]
        col_widths[-1] = total_w - sum(col_widths[:-1])
        col_labels = ["Nước cờ", "Điểm", "Hợp lệ", "Ghi chú"]
        row_h = 40

        x = base_x
        # Draw header background band (light gray)
        header_rect = pygame.Rect(base_x - 6, base_y - 4, sum(col_widths) + 12, row_h + 8)
        header_overlay = pygame.Surface((header_rect.width, header_rect.height), pygame.SRCALPHA)
        header_overlay.fill((200, 200, 200, 0))
        self.screen.blit(header_overlay, header_rect.topleft)

        for i, (w, label) in enumerate(zip(col_widths, col_labels)):
            cell_rect = pygame.Rect(x, base_y, w, row_h)
            pygame.draw.rect(self.screen, Settings.Colors.BLACK, cell_rect, width=1)

            text_surf = self.header_font.render(label, True, Settings.Colors.BLACK)
            text_rect = text_surf.get_rect(center=cell_rect.center)
            self.screen.blit(text_surf, text_rect.topleft)
            x += w


