import pygame
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from App.configuration import Settings
from App.piece import ChessBoard
from App.rule import Rule
from App.position import Position
from UI.renderer import UIRenderer
from utils.storeGameData import GameDataTree
from utils.setupMode import SetupMode
from utils.navigation import Navigation
from utils.fen import FENHandler
from utils.save_load import apply_loaded_game, load_game_json, save_game_json
from utils.image_upload import upload_image
from utils.screen_capture import capture_screen_region, cleanup_temp_files
from Reconstruction.detect_service import DetectionService
from Reconstruction.reconstructor import reconstruct_board


pygame.init()

# Set initial window position at startup, shift up by 7% of screen height
try:
    # Get current display info from pygame
    full_screen = pygame.display.Info()
    screen_w = full_screen.current_w  # screen width
    screen_h = full_screen.current_h  # screen height

    # Base game window size (auto-shrink on small displays)
    base_window_w = Settings.BASE_WIDTH + Settings.BASE_PANEL_WIDTH
    base_window_h = Settings.BASE_HEIGHT + Settings.HEADER_HEIGHT
    window_w = min(base_window_w, max(900, screen_w - 40))
    window_h = min(base_window_h, max(700, screen_h - 80))

    # Center window horizontally
    x = (screen_w - window_w) // 2
    # Shift window up by 7% of screen height (relative, works on any display)
    y = max(0, (screen_h - window_h) // 2 - int(screen_h * 0.07))
    # y = max(0, (screen_h - window_h) // 2 -100)

    # Set environment variable to define the initial window position
    os.environ["SDL_VIDEO_WINDOW_POS"] = f"{x},{y}"

except Exception:
    pass


FPS = Settings.FPS

Settings.update_window_size(window_w, window_h)
screen = pygame.display.set_mode((Settings.WINDOW_WIDTH, Settings.WINDOW_HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("XiangQi Chess")

try:
    icon = pygame.image.load('assets/icon.png')
    pygame.display.set_icon(icon)
except:
    print("Warning: Could not load icon.png")

background = pygame.image.load('board/board.jpg')

# Initialize chess board
chess_board = ChessBoard()
rule = Rule(chess_board)
ui_renderer = UIRenderer(screen, chess_board, rule)
game_tree = GameDataTree()
setup_mode = SetupMode(chess_board)
navigation = Navigation(chess_board, game_tree)

clock = pygame.time.Clock()

# Initialize detection service (models are loaded lazily in a background thread)
_WEIGHTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Reconstruction", "weights")
detect_service = DetectionService(
    main_model_path=os.path.join(_WEIGHTS_DIR, "detect-ultra.pt"),
    aux_model_path =os.path.join(_WEIGHTS_DIR, "detect-aux.pt"),
    pose_model_path=os.path.join(_WEIGHTS_DIR, "pose-ultra.pt"),
    data_yaml      =os.path.join(_WEIGHTS_DIR, "data_detect.yaml"),
    device = Settings.DEVICE,
)
detect_service.preload_models()  # preload models in background without blocking the main thread

# Selection state
selected_piece = None
old_position = None
valid_moves: list[tuple[int, int]] = []
# Track previous flip state to detect changes
previous_flipped = Settings.FLIPPED


def _on_detect_result(results: list) -> None:
    """Callback chạy trong detection thread khi nhận diện thành công."""
    global game_tree, navigation, selected_piece, old_position, valid_moves
    reconstruct_board(results, chess_board)
    ui_renderer.checkmate_notification_dismissed = False
    game_tree = GameDataTree()
    navigation = Navigation(chess_board, game_tree)
    if hasattr(ui_renderer, 'record_view'):
        ui_renderer.record_view.game_tree = game_tree
        ui_renderer.record_view.sync_with_tree()
    selected_piece = None
    old_position = None
    valid_moves = []
    Settings.SETUP_MODE = False


# from utils.load import load_game_tree
# game_tree = load_game_tree()


while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            cleanup_temp_files()
            pygame.quit()
            sys.exit()
        elif event.type == pygame.VIDEORESIZE:
            win_w, win_h = event.size
            Settings.update_window_size(win_w, win_h)
            screen = pygame.display.set_mode((Settings.WINDOW_WIDTH, Settings.WINDOW_HEIGHT), pygame.RESIZABLE)
            ui_renderer.screen = screen
            if hasattr(ui_renderer, 'book_view'):
                ui_renderer.book_view.screen = screen
            if hasattr(ui_renderer, 'record_view'):
                ui_renderer.record_view.screen = screen

        elif event.type == pygame.MOUSEWHEEL:
            if (getattr(ui_renderer, 'current_tab_index', None) == 2 and
                hasattr(ui_renderer, 'record_view') and
                getattr(ui_renderer, 'is_side_panel_visible', None) and
                ui_renderer.is_side_panel_visible()):
                # event.y > 0 means scroll up; move content accordingly
                ui_renderer.record_view.scroll(-event.y * 40)


        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_pos = pygame.mouse.get_pos()
            
            # Close notification if active (allow early dismissal)
            if ui_renderer.notification_message is not None:
                ui_renderer.close_notification()
                
            
            # Close checkmate notification if close button is clicked
            if ui_renderer.is_checkmate_close_button_clicked(mouse_pos):
                ui_renderer.close_checkmate_notification()
                continue

            if getattr(ui_renderer, 'is_animating', None) and ui_renderer.is_animating():
                continue
            # Handle menu button click first
            if ui_renderer.is_menu_clicked(mouse_pos):
                ui_renderer.toggle_menu()
                continue

            # Handle menu item click
            menu_item_idx = ui_renderer.check_menu_item_click(mouse_pos)
            if menu_item_idx != -1:
                ui_renderer.menu_is_open = False  # Close menu after selection
                # Handle each menu item
                if menu_item_idx == 0:  # "Tạo mới"
                    chess_board.reset()
                    game_tree = GameDataTree()
                    navigation = Navigation(chess_board, game_tree)
                    if hasattr(ui_renderer, 'record_view'):
                        ui_renderer.record_view.game_tree = game_tree
                        ui_renderer.record_view.sync_with_tree()
                    selected_piece = None
                    valid_moves = []
                    # Exit setup mode if it was active
                    Settings.SETUP_MODE = False
                elif menu_item_idx == 1:  # "Sắp quân"
                    # Enable setup mode: scale and center the board and pieces,
                    # and disable all other action buttons except rotate.
                    Settings.SETUP_MODE = True  # Toggle setup mode
                    # Place captured pieces (at (-1,-1)) into off-board slots
                    setup_mode.place_removed_pieces_to_off_board()
                elif menu_item_idx == 2:  # "Sao chép FEN"
                    if FENHandler.copy_fen(chess_board):
                        ui_renderer.show_notification("Đã sao chép FEN vào clipboard.")
                    else:
                        ui_renderer.show_notification("Lỗi: Sao chép FEN thất bại.")
                elif menu_item_idx == 3:  # "Dán FEN"
                    if FENHandler.paste_fen(chess_board):
                        # Reset tree/navigation because the board state has completely changed
                        ui_renderer.checkmate_notification_dismissed = False  # Reset checkmate notification dismissed state
                        game_tree = GameDataTree()
                        navigation = Navigation(chess_board, game_tree)
                        if hasattr(ui_renderer, 'record_view'):
                            ui_renderer.record_view.game_tree = game_tree
                            ui_renderer.record_view.sync_with_tree()
                        selected_piece = None
                        old_position = None
                        valid_moves = []
                        Settings.SETUP_MODE = False
                        ui_renderer.show_notification("Đã dán FEN từ clipboard.")
                    else:
                        ui_renderer.show_notification("Lỗi: Dán FEN thất bại (clipboard rỗng hoặc FEN không hợp lệ).")
                # elif menu_item_idx == 4:  # "Nhập FEN"
                #     # TODO: Implement input FEN
                #     print("Nhập FEN - Chức năng chưa được triển khai")
                elif menu_item_idx == 4:  # "Mở ván cờ"
                    try:
                        loaded = load_game_json(None)
                        if loaded is not None:
                            game_tree, root_fen, path_indices = loaded
                            navigation = apply_loaded_game(
                                chess_board, game_tree, root_fen, path_indices
                            )
                            if hasattr(ui_renderer, "record_view"):
                                ui_renderer.record_view.game_tree = game_tree
                                ui_renderer.record_view.sync_with_tree()
                            selected_piece = None
                            old_position = None
                            valid_moves = []
                            Settings.SETUP_MODE = False
                            ui_renderer.checkmate_notification_dismissed = False
                            ui_renderer.show_notification("Đã mở ván cờ.")
                    except Exception as exc:
                        ui_renderer.show_notification(f"Lỗi mở ván cờ: {exc}")
                elif menu_item_idx == 5:  # "Lưu ván cờ"
                    try:
                        out_path = save_game_json(
                            chess_board, game_tree, navigation, None
                        )
                        if out_path:
                            ui_renderer.show_notification(
                                f"Đã lưu ván cờ: {os.path.basename(out_path)}"
                            )
                    except Exception as exc:
                        ui_renderer.show_notification(f"Lỗi lưu ván cờ: {exc}")
                elif menu_item_idx == 6:  # "Thoát"
                    cleanup_temp_files()
                    pygame.quit()
                    # os.system("cls")
                    # os.system("python App/app.py")
                    sys.exit()
                continue
            # Close menu if click is outside the sidebar (after checking other buttons)
            if ui_renderer.menu_is_open:
                # Check whether the click is inside the sidebar (sidebar width = 280)
                sidebar_rect = pygame.Rect(0, 50, 280, ui_renderer.screen.get_height())
                clicked_in_sidebar = sidebar_rect.collidepoint(mouse_pos)
                
                if not clicked_in_sidebar:
                    ui_renderer.menu_is_open = False
                    continue
            
            # Handle add button click
            if getattr(ui_renderer, 'is_add_button_clicked', None) and ui_renderer.is_add_button_clicked(mouse_pos):
                if hasattr(ui_renderer, 'toggle_add_menu'):
                    ui_renderer.toggle_add_menu()
                continue
            # Handle camera button click (from add menu)
            if getattr(ui_renderer, 'is_camera_clicked', None) and ui_renderer.is_camera_clicked(mouse_pos):
                ui_renderer.add_menu_is_open = False
                captured_path = capture_screen_region(show_preview=Settings.SHOW_UPLOADED_IMAGE)
                detect_service.detect_async(
                    captured_path,
                    is_temp=True,
                    on_notify=ui_renderer.show_notification,
                    on_result=_on_detect_result,
                )
                continue
            # Handle gallery button click (from add menu)
            if getattr(ui_renderer, 'is_gallery_clicked', None) and ui_renderer.is_gallery_clicked(mouse_pos):
                ui_renderer.add_menu_is_open = False
                uploaded_path = upload_image(show_preview=Settings.SHOW_UPLOADED_IMAGE)
                detect_service.detect_async(
                    uploaded_path,
                    is_temp=False,
                    on_notify=ui_renderer.show_notification,
                    on_result=_on_detect_result,
                )
                continue
            # Close add menu if clicking outside (check before handling other buttons)
            if getattr(ui_renderer, 'add_menu_is_open', False):
                # Check if click is outside add button and menu area
                if hasattr(ui_renderer, 'is_click_in_add_menu_area'):
                    if not ui_renderer.is_click_in_add_menu_area(mouse_pos):
                        ui_renderer.add_menu_is_open = False
                        continue
            # Handle general button click
            if getattr(ui_renderer, 'is_general_clicked', None) and ui_renderer.is_general_clicked(mouse_pos):
                chess_board.switch_turn()
                game_tree.reset()
                # Sync record view immediately
                if hasattr(ui_renderer, 'record_view'):
                    ui_renderer.record_view.game_tree = game_tree
                    ui_renderer.record_view.sync_with_tree()
                continue

            # Handle rotate button click first (always active, even in setup mode)
            if ui_renderer.is_rotate_clicked(mouse_pos):
                if getattr(ui_renderer, 'begin_flip_animation', None):
                    ui_renderer.begin_flip_animation()
                else:
                    ui_renderer.toggle_rotation()
                continue
            
            # Handle expand / backward / forward buttons
            if Settings.SETUP_MODE:
                # Setup mode: this slot is used by the expand button; skip backward/forward
                if getattr(ui_renderer, 'is_expand_clicked', None) and ui_renderer.is_expand_clicked(mouse_pos):
                    if hasattr(ui_renderer, 'on_expand_clicked'):
                        ui_renderer.on_expand_clicked()
                    # Move all on-board pieces (except the king) to off-board slots
                    setup_mode.move_board_pieces_to_off_board()
                    # Clear selection after expand
                    selected_piece = None
                    old_position = None
                    valid_moves = []
                    continue
                if getattr(ui_renderer, 'is_tick_clicked', None) and ui_renderer.is_tick_clicked(mouse_pos):
                    # Tick: confirm current board layout and exit setup mode
                    # Move off-board pieces back to (-1, -1) (removed state)
                    setup_mode.move_off_board_pieces_to_removed()
                    Settings.SETUP_MODE = False
                    # Clear selected piece and valid-move highlights
                    selected_piece = None
                    old_position = None
                    valid_moves = []
                    game_tree.reset()
                    # Sync record view immediately
                    if hasattr(ui_renderer, 'record_view'):
                        ui_renderer.record_view.game_tree = game_tree
                        ui_renderer.record_view.sync_with_tree()
                    continue
            else:
                # Normal play mode: backward / forward buttons are active
                # Handle backward button click
                if getattr(ui_renderer, 'is_backward_clicked', None) and ui_renderer.is_backward_clicked(mouse_pos):
                    if hasattr(ui_renderer, 'on_backward_clicked'):
                        ui_renderer.on_backward_clicked()
                    # Backward: move piece back to its previous position based on the current node
                    if navigation.go_backward_one_move():
                        # Sync record view
                        if hasattr(ui_renderer, 'record_view'):
                            ui_renderer.record_view.game_tree = game_tree
                            ui_renderer.record_view.sync_with_tree()
                        # Clear selection
                        selected_piece = None
                        valid_moves = []
                    continue
                # Handle forward button click
                if getattr(ui_renderer, 'is_forward_clicked', None) and ui_renderer.is_forward_clicked(mouse_pos):
                    if hasattr(ui_renderer, 'on_forward_clicked'):
                        ui_renderer.on_forward_clicked()
                    # Forward: move piece from old to new position based on the child node
                    if navigation.go_forward_one_move():
                        # Sync record view
                        if hasattr(ui_renderer, 'record_view'):
                            ui_renderer.record_view.game_tree = game_tree
                            ui_renderer.record_view.sync_with_tree()
                        # Clear selection
                        selected_piece = None
                        valid_moves = []
                    continue
            # Handle right menu tab click next
            if getattr(ui_renderer, 'tab_hit', None) and getattr(ui_renderer, 'is_side_panel_visible', None) and ui_renderer.is_side_panel_visible():
                tab_idx = ui_renderer.tab_hit(mouse_pos)
                if tab_idx != -1:
                    ui_renderer.set_current_tab(tab_idx)
                    continue
            
            # Handle record view row click (tab 2 = "Biên bản" / move record)
            if (getattr(ui_renderer, 'current_tab_index', None) == 2 and
                hasattr(ui_renderer, 'record_view') and
                getattr(ui_renderer, 'is_side_panel_visible', None) and
                ui_renderer.is_side_panel_visible()):
                record_view = ui_renderer.record_view
                
                # Check dropdown item click first (highest priority)
                if record_view.dropdown_open_for_node is not None:
                    dropdown_item = record_view.hit_dropdown_item(mouse_pos)
                    if dropdown_item is not None:
                        child_index, child_node = dropdown_item
                        # Update last_choice on the parent node
                        record_view.dropdown_open_for_node.last_choice = child_index
                        # Navigate to the selected variation using navigation.navigate_to_node
                        if navigation.navigate_to_node(child_node):
                            # Sync record view
                            record_view.game_tree = game_tree
                            record_view.sync_with_tree()
                            record_view.close_dropdown()
                            
                            selected_piece = None
                            valid_moves = []
                        else:
                            record_view.close_dropdown()
                        continue
                    else:
                        # Click outside dropdown, close it
                        record_view.close_dropdown()
                
                # Check branch button click
                if record_view.viewport.collidepoint(mouse_pos):
                    clicked_node = record_view.hit_branch_button(mouse_pos)
                    if clicked_node is not None:
                        # Find the button rect for this node
                        for button_rect, node in record_view.branch_button_rects:
                            if node == clicked_node:
                                record_view.open_dropdown(node, button_rect)
                                break
                        continue
                
                # Check whether the click is inside the record view viewport
                if record_view.viewport.collidepoint(mouse_pos):
                    # Compute the row index from the click position
                    header_bottom = record_view.viewport.top + record_view.header_h
                    if mouse_pos[1] >= header_bottom:
                        # Calculate index based on Y position and scroll offset
                        click_y_relative = mouse_pos[1] - header_bottom
                        row_index = int((click_y_relative + record_view.scroll_offset) / record_view.row_h)
                        
                        if 0 <= row_index < len(record_view.items):
                            # Calculate target_index in the main line
                            # row_index is 0-based in items (root is excluded)
                            # target_index in main_line: 0 = root, 1 = first move, ...
                            target_index = row_index + 1  # +1 because main_line[0] is root
                            
                            # Use navigate_to_index to jump to the target move;
                            # it automatically computes the required forward/backward steps
                            if navigation.navigate_to_index(target_index):
                                # Sync record view
                                record_view.game_tree = game_tree
                                record_view.sync_with_tree()
                                
                                # Clear selection
                                selected_piece = None
                                valid_moves = []
                    continue
        
            grid_pos, is_valid = Position.check_valid_position(mouse_pos)
            if is_valid:
                if Settings.SETUP_MODE:
                    # Setup mode: dedicated piece-placement logic
                    clicked_piece = chess_board.get_piece_at(grid_pos)
                    if clicked_piece is not None:
                        # Clicked a piece: select it and show valid positions
                        selected_piece = clicked_piece
                        valid_moves = setup_mode.get_valid_positions(clicked_piece)
                        old_position = grid_pos
                    else:
                        # Clicked an empty square: move piece if selected and destination is valid
                        if selected_piece is not None and grid_pos in valid_moves:
                            # Move piece (no turn switch, no game_tree entry)
                            chess_board.move_piece(selected_piece.color, selected_piece.name, grid_pos)
                            # Clear selection after moving
                            selected_piece = None
                            old_position = None
                            valid_moves = []
                        else:
                            # Clicked an invalid empty square: clear selection
                            selected_piece = None
                            old_position = None
                            valid_moves = []
                else:
                    # Normal play mode
                    clicked_piece = chess_board.get_piece_at(grid_pos)
                    if clicked_piece is not None and clicked_piece.color == chess_board.turn:
                        # Select or reselect a piece
                        selected_piece = clicked_piece
                        valid_moves = rule.get_valid_moves(clicked_piece)
                        old_position = grid_pos
                    else:
                        # Empty square: move if it's a valid destination
                        if selected_piece is not None and grid_pos in valid_moves and selected_piece.color == chess_board.turn:
                            # Check if any piece occupies the destination (will be captured)
                            captured_piece = chess_board.get_piece_at(grid_pos)
                            # Move piece
                            chess_board.move_piece(selected_piece.color, selected_piece.name, grid_pos)
                            game_tree.add_move(chess_board.turn, f"{selected_piece.name} ({old_position[0]},{old_position[1]}) ({grid_pos[0]},{grid_pos[1]})", "", captured_piece=captured_piece)
                            chess_board.switch_turn()
                            # Sync record view with game tree
                            if hasattr(ui_renderer, 'record_view'):
                                ui_renderer.record_view.game_tree = game_tree
                                ui_renderer.record_view.sync_with_tree()
                            
                        
                        # Clear selection after clicking on an empty or invalid square
                        selected_piece = None
                        valid_moves = []
            else:
                # Click outside board clears selection
                selected_piece = None
                old_position = None
                valid_moves = []


            
    mouse_pos = pygame.mouse.get_pos()
    # print(Position.check_valid_position(mouse_pos)[0])
    
    if getattr(ui_renderer, 'verify_author_integrity', None) and not ui_renderer.verify_author_integrity():
        ui_renderer.show_notification("Lỗi: Tác giả không hợp lệ, vui lòng kiểm tra lại.")
        
    # If flip state changed and a piece is selected, recalculate valid_moves
    current_flipped = Settings.FLIPPED
    if current_flipped != previous_flipped:
        # Flip state changed; recalculate valid_moves if a piece is selected
        if selected_piece is not None and Settings.SETUP_MODE:
            valid_moves = setup_mode.get_valid_positions(selected_piece)
        previous_flipped = current_flipped
    
    #  Render
    if getattr(ui_renderer, 'is_animating', None) and ui_renderer.is_animating():
        ui_renderer.render_flip_animation(selected_piece, valid_moves)
    elif Settings.SETUP_MODE:
        # Setup mode: only draw the basic board components and the rotate button
        ui_renderer.draw_background(background)
        ui_renderer.draw_border()
        ui_renderer.draw_pieces()
        # ui_renderer.draw_selected_piece(selected_piece)
        ui_renderer.draw_valid_moves(valid_moves)
        ui_renderer.draw_menu_button()
        ui_renderer.draw_menu_sidebar(mouse_pos)
        ui_renderer.draw_rotate_button()
        ui_renderer.draw_expand_button()
        ui_renderer.draw_tick_button()
        ui_renderer.draw_general_button(pos=(270, 5))
        ui_renderer.draw_notification()

    else:
        # Normal play mode: draw all UI components
        ui_renderer.draw_background(background)
        ui_renderer.draw_border()
        ui_renderer.draw_pieces()
        ui_renderer.draw_old_position_selection()
        ui_renderer.draw_new_position_selection()
        ui_renderer.draw_selected_piece(selected_piece)
        ui_renderer.draw_valid_moves(valid_moves)
        ui_renderer.draw_in_check()
        ui_renderer.draw_checkmate()

        ui_renderer.draw_menu_button()
        ui_renderer.draw_menu_sidebar(mouse_pos)
        ui_renderer.draw_rotate_button()
        ui_renderer.draw_forward_backward_buttons()
        ui_renderer.draw_red_and_black_computer()
        ui_renderer.draw_magnifying_glass_button()
        ui_renderer.draw_general_button()
        ui_renderer.draw_add_button()

        ui_renderer.draw_right_menu_buttons()
        ui_renderer.tab_content()
        ui_renderer.draw_notification()



    pygame.display.update()
    clock.tick(FPS)