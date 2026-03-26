"""
reconstructor.py - Place chess pieces onto the ChessBoard from detect_service results.

Coordinate convention:
  Model (detect_service): u ∈ [0, 8],  v ∈ [0, 9]
  Board (ChessBoard)    : u ∈ [1, 9],  v ∈ [0, 9]
  → board_u = model_u + 1
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE         = Path(__file__).resolve().parent   # .../Reconstruction
_PROJECT_ROOT = _HERE.parent                      # .../XiangQi
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from App.piece import ChessBoard, ChessPiece


# ---------------------------------------------------------------------------
# Position rules (model coordinate system: u ∈ [0,8], v ∈ [0,9])
# ---------------------------------------------------------------------------

_VALID_POSITIONS: dict[str, set[tuple[int, int]]] = {
    "Black_Advisor": {(3,0),(5,0),(4,1),(3,2),(5,2)},
    "Red_Advisor":   {(3,9),(5,9),(4,8),(3,7),(5,7)},
    "Black_Bishop":  {(2,0),(6,0),(0,2),(8,2),(2,4),(6,4),(4,2)},
    "Red_Bishop":    {(2,9),(6,9),(0,7),(8,7),(2,5),(6,5),(4,7)},
    "Black_King":    {(u, v) for u in range(3, 6) for v in range(0, 3)},
    "Red_King":      {(u, v) for u in range(3, 6) for v in range(7, 10)},
}

_FORBIDDEN_BLACK_PAWN: frozenset[tuple[int, int]] = frozenset({
    (1,3),(3,3),(5,3),(7,3),
    (1,4),(3,4),(5,4),(7,4),
})
_FORBIDDEN_RED_PAWN: frozenset[tuple[int, int]] = frozenset({
    (1,6),(3,6),(5,6),(7,6),
    (1,5),(3,5),(5,5),(7,5),
})


def _violates_position_rule(name: str, u: int, v: int) -> bool:
    if name in _VALID_POSITIONS:
        return (u, v) not in _VALID_POSITIONS[name]
    if name == "Black_Pawn":
        return v < 3 or (u, v) in _FORBIDDEN_BLACK_PAWN
    if name == "Red_Pawn":
        return v > 6 or (u, v) in _FORBIDDEN_RED_PAWN
    return False


# ---------------------------------------------------------------------------
# Mapping: model name → (color, piece_type)
# ---------------------------------------------------------------------------

_DETECT_NAME_MAP: dict[str, tuple[str, str]] = {
    "Black_Advisor": ("black", "S"),
    "Black_Bishop":  ("black", "T"),
    "Black_Cannon":  ("black", "P"),
    "Black_King":    ("black", "Tg"),
    "Black_Knight":  ("black", "M"),
    "Black_Pawn":    ("black", "B"),
    "Black_Rook":    ("black", "X"),
    "Red_Advisor":   ("red",   "S"),
    "Red_Bishop":    ("red",   "T"),
    "Red_Cannon":    ("red",   "P"),
    "Red_King":      ("red",   "Tg"),
    "Red_Knight":    ("red",   "M"),
    "Red_Pawn":      ("red",   "B"),
    "Red_Rook":      ("red",   "X"),
}

# Index-based naming order per piece type (matches ChessBoard._initialize_pieces)
_NAME_INDICES: dict[str, list[int]] = {
    "X": [1, 9],
    "M": [2, 8],
    "T": [3, 7],
    "S": [4, 6],
    "P": [2, 8],
    "B": [1, 3, 5, 7, 9],
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def reconstruct_board(
    grid_results: list[dict],
    chess_board: ChessBoard,
) -> None:
    """
    Place pieces from detect_service results onto chess_board.

    First moves all pieces off the board to (-1, -1), then repositions
    each detected piece at its detected coordinate.

    Args:
        grid_results : list[dict] returned by detect_service._worker, each element has:
                         "name"  – model name, e.g. "Black_Rook"
                         "grid"  – (u, v) in model coords (u: 0‒8, v: 0‒9)
                         "conf"  – confidence
        chess_board  : ChessBoard instance to update in place.
    """
    # Move all pieces off the board
    for color in ("black", "red"):
        for piece in chess_board.pieces[color].values():
            piece.move_to((-1, -1))

    counters: dict[str, dict[str, int]] = {"black": {}, "red": {}}

    for r in grid_results:
        model_u, model_v = r.get("grid", (None, None))
        if model_u is None or model_v is None:
            continue

        detect_name = r.get("name", "")
        if detect_name not in _DETECT_NAME_MAP:
            continue

        color, piece_type = _DETECT_NAME_MAP[detect_name]

        # Convert to board coordinate system
        board_u = model_u + 1
        board_v = model_v

        if not (1 <= board_u <= 9 and 0 <= board_v <= 9):
            continue

        # Skip if the position violates a rule (use model u before +1)
        if _violates_position_rule(detect_name, model_u, model_v):
            continue

        # Determine the piece name used by the chess board
        if piece_type == "Tg":
            piece_name = "Tg"
        else:
            idx  = counters[color].get(piece_type, 0)
            nums = _NAME_INDICES[piece_type]
            piece_name = f"{piece_type}{nums[idx] if idx < len(nums) else nums[-1]}"
            counters[color][piece_type] = idx + 1

        # Update position (reuse existing piece object or create a new one if needed)
        if piece_name in chess_board.pieces[color]:
            chess_board.pieces[color][piece_name].move_to((board_u, board_v))
        else:
            chess_board.pieces[color][piece_name] = ChessPiece(
                piece_name, color, (board_u, board_v)
            )
