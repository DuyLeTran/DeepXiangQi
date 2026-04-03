"""Save / load full game tree (with branches) to JSON + root FEN.

New saves use encrypt-then-MAC: Fernet + HMAC-SHA256 over ciphertext (format xqsave2).
Plain JSON (version 1) from older builds can still be opened.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import subprocess
import sys
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from App.piece import ChessBoard
from utils.fen import FENHandler
from utils.navigation import Navigation
from utils.storeGameData import GameDataTree, Node

# Inner payload (decrypted or legacy plain JSON)
INNER_FORMAT_VERSION = 1

# Outer wrapper written by current save()
OUTER_FORMAT = "xqsave2"

_fernet: Fernet | None = None
_hmac_key: bytes | None = None


def _get_crypto() -> tuple[Fernet, bytes]:
    """Derive Fernet + HMAC keys (offline app — deters casual editing, not nation-state)."""
    global _fernet, _hmac_key
    if _fernet is not None and _hmac_key is not None:
        return _fernet, _hmac_key
    seed = b"XiangQiSaveGame-v2-DeepXiangQi"
    dk = hashlib.pbkdf2_hmac("sha256", seed, b"xqsave-v1", 100_000, 64)
    fernet_key = base64.urlsafe_b64encode(dk[:32])
    _hmac_key = dk[32:64]
    _fernet = Fernet(fernet_key)
    return _fernet, _hmac_key


def _encrypt_inner_payload(inner: dict[str, Any]) -> dict[str, Any]:
    fernet, hmac_key = _get_crypto()
    plain = json.dumps(inner, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    cipher = fernet.encrypt(plain)
    mac = hmac.new(hmac_key, cipher, hashlib.sha256).hexdigest()
    return {
        "format": OUTER_FORMAT,
        "cipher": base64.b64encode(cipher).decode("ascii"),
        "mac": mac,
    }


def _decode_saved_file_dict(raw: dict[str, Any]) -> dict[str, Any]:
    """Decrypt outer wrapper or pass through legacy plain JSON."""
    if raw.get("format") != OUTER_FORMAT:
        return raw
    cipher_b64 = raw.get("cipher")
    mac_hex = raw.get("mac")
    if not isinstance(cipher_b64, str) or not isinstance(mac_hex, str):
        raise ValueError("Invalid encrypted save file structure")
    cipher = base64.b64decode(cipher_b64)
    fernet, hmac_key = _get_crypto()
    expected = hmac.new(hmac_key, cipher, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, mac_hex):
        raise ValueError("Save file invalid or modified (MAC check failed)")
    try:
        plain = fernet.decrypt(cipher)
    except InvalidToken as e:
        raise ValueError("Save file invalid or corrupted (decryption failed)") from e
    return json.loads(plain.decode("utf-8"))

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_GAME_DIALOG_SCRIPT = os.path.join(_PROJECT_ROOT, "utils", "_game_dialog.py")


def _run_dialog_subprocess(mode: str) -> str | None:
    """macOS: isolate Tk from pygame."""
    try:
        out = subprocess.check_output(
            [sys.executable, _GAME_DIALOG_SCRIPT, mode],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        path = (out or "").strip()
        return path or None
    except Exception:
        return None


def _open_file_dialog() -> str | None:
    if sys.platform == "darwin":
        return _run_dialog_subprocess("open")
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        path = filedialog.askopenfilename(
            title="Mở ván cờ / Open game",
            filetypes=[
                ("Xiangqi save", "*.xqsave"),
                ("JSON (legacy)", "*.json"),
                ("All files", "*.*"),
            ],
        )
    finally:
        root.destroy()
    return path or None


def _save_file_dialog() -> str | None:
    if sys.platform == "darwin":
        return _run_dialog_subprocess("save")
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        path = filedialog.asksaveasfilename(
            title="Lưu ván cờ / Save game",
            defaultextension=".xqsave",
            filetypes=[
                ("Xiangqi save", "*.xqsave"),
                ("JSON (legacy)", "*.json"),
                ("All files", "*.*"),
            ],
        )
    finally:
        root.destroy()
    return path or None


def compute_current_path_indices(game_tree: GameDataTree) -> list[int]:
    """Indices of children along the path from root to current."""
    path = game_tree.get_current_path()
    indices: list[int] = []
    for i in range(1, len(path)):
        parent = path[i - 1]
        child = path[i]
        try:
            idx = parent.children.index(child)
        except ValueError as e:
            raise ValueError("Current path is inconsistent with tree children") from e
        indices.append(idx)
    return indices


def node_from_path_indices(game_tree: GameDataTree, indices: list[int]) -> Node:
    """Walk from root following child indices."""
    node = game_tree.root
    for idx in indices:
        if idx < 0 or idx >= len(node.children):
            raise IndexError(f"Invalid child index {idx} at node")
        node = node.children[idx]
    return node


def _serialize_node(node: Node) -> dict[str, Any]:
    return {
        "turn": node.turn,
        "move": node.move,
        "note": node.note,
        "last_choice": node.last_choice,
        "children": [_serialize_node(c) for c in node.children],
    }


def serialize_game_tree(game_tree: GameDataTree) -> dict[str, Any]:
    return _serialize_node(game_tree.root)


def _deserialize_node(data: dict[str, Any], parent: Node | None) -> Node:
    node = Node(
        turn=data.get("turn", "red"),
        move=data.get("move"),
        note=data.get("note"),
        parent=parent,
    )
    node.last_choice = int(data.get("last_choice", 0))
    for child_data in data.get("children", []):
        child = _deserialize_node(child_data, parent=node)
        node.children.append(child)
    return node


def deserialize_game_tree(tree_dict: dict[str, Any]) -> GameDataTree:
    game_tree = GameDataTree()
    game_tree.root = _deserialize_node(tree_dict, parent=None)
    game_tree.current = game_tree.root
    return game_tree


def save_game_json(
    chess_board: ChessBoard,
    game_tree: GameDataTree,
    navigation: Navigation,
    filepath: str | None = None,
) -> str | None:
    """
    Snapshot root FEN, serialize tree, write JSON.
    If filepath is None, shows save dialog.
    Returns path written, or None if cancelled / error.
    Restores board position after save.
    """
    if filepath is None:
        filepath = _save_file_dialog()
        if not filepath:
            return None

    indices = compute_current_path_indices(game_tree)
    tree_payload = serialize_game_tree(game_tree)
    target_node = node_from_path_indices(game_tree, indices)

    root_fen: str
    try:
        if not navigation.navigate_to_index(0):
            raise RuntimeError("Could not navigate to root for save")
        root_fen = FENHandler.to_fen(chess_board)

        inner = {
            "version": INNER_FORMAT_VERSION,
            "root_fen": root_fen,
            "current_path_indices": indices,
            "tree": tree_payload,
        }
        outer = _encrypt_inner_payload(inner)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(outer, f, ensure_ascii=False, indent=2)
    finally:
        if not navigation.navigate_to_node(target_node):
            raise RuntimeError("Could not restore board position after save")

    return filepath


def load_game_json(filepath: str | None = None) -> tuple[GameDataTree, str, list[int]] | None:
    """
    Read JSON file; return (game_tree, root_fen, current_path_indices).
    If filepath is None, shows open dialog.
    Returns None if cancelled.
    """
    if filepath is None:
        filepath = _open_file_dialog()
        if not filepath:
            return None

    with open(filepath, "r", encoding="utf-8") as f:
        raw = json.load(f)

    if not isinstance(raw, dict):
        raise ValueError("Invalid save file")
    payload = _decode_saved_file_dict(raw)

    version = payload.get("version", 1)
    if version != INNER_FORMAT_VERSION:
        raise ValueError(f"Unsupported save format version: {version}")

    root_fen = payload.get("root_fen")
    if not isinstance(root_fen, str) or not root_fen.strip():
        raise ValueError("Missing or invalid root_fen")

    indices = payload.get("current_path_indices", [])
    if not isinstance(indices, list):
        raise ValueError("current_path_indices must be a list")
    indices = [int(x) for x in indices]

    tree_dict = payload.get("tree")
    if not isinstance(tree_dict, dict):
        raise ValueError("Missing or invalid tree")

    game_tree = deserialize_game_tree(tree_dict)
    return game_tree, root_fen.strip(), indices


def apply_loaded_game(
    chess_board: ChessBoard,
    game_tree: GameDataTree,
    root_fen: str,
    current_path_indices: list[int],
) -> Navigation:
    """Apply FEN at root, replay to saved node. Returns new Navigation."""
    if not FENHandler.from_fen(root_fen, chess_board):
        raise ValueError("Invalid root_fen")

    game_tree.current = game_tree.root
    navigation = Navigation(chess_board, game_tree)

    target = node_from_path_indices(game_tree, current_path_indices)
    if not navigation.navigate_to_node(target):
        raise RuntimeError("Could not replay moves to saved position")

    return navigation
