"""
Chess piece detection service integrated into the app.

Full pipeline:
  original image → dual-model detect (pieces + board) → filter pieces inside board
                 → crop → pose-model(crop) → H → grid coords

Design:
  - Self-contained: all logic (dual-model merge, rule filtering, geometry, draw) lives here.
  - Models are loaded lazily once and reused for the entire session.
  - Each detection runs in a daemon thread so it never blocks the pygame loop.
  - If Settings.DEV_MODE = True: draw results onto the crop → save temp PNG
    → display in a tkinter window (blocking subprocess inside the thread)
    → delete the temp PNG as soon as the window closes.
  - Temporary screen-capture images (is_temp=True) are deleted after detection.
  - Only one detection runs at a time; new requests are ignored while busy.
"""

from __future__ import annotations

import os
import sys
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable, Optional

import cv2
import numpy as np
import yaml

_HERE         = Path(__file__).resolve().parent   # .../Reconstruction
_PROJECT_ROOT = _HERE.parent                      # .../XiangQi
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_VIEWER_SCRIPT = str(_PROJECT_ROOT / "utils" / "_image_viewer.py")

_DEFAULT_MAIN_MODEL = str(_HERE / "weights" / "detect-ultra.pt")
_DEFAULT_AUX_MODEL  = str(_HERE / "weights" / "detect-aux.pt")
_DEFAULT_POSE_MODEL = str(_HERE / "weights" / "pose-ultra.pt")
_DEFAULT_DATA_YAML  = str(_HERE / "weights" / "data_detect.yaml")


# ===========================================================================
# Constants
# ===========================================================================

VIRTUAL_BOARD_W = 800
VIRTUAL_BOARD_H = 900

_PALETTE_BGR: list[tuple[int, int, int]] = [
    (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255),
    (0, 255, 255), (128, 0, 128), (0, 165, 255), (203, 192, 255), (0, 100, 255),
    (255, 0, 128), (128, 255, 0), (255, 128, 0), (128, 0, 255), (0, 128, 255),
]

_PIECE_MAX: dict[str, int] = {
    "King": 1, "Advisor": 2, "Bishop": 2, "Knight": 2,
    "Cannon": 2, "Rook": 2, "Pawn": 5, "Board": 1,
}


# ===========================================================================
# Detection logic (self-contained)
# ===========================================================================

def _load_names(yaml_path: str) -> list[str]:
    with open(yaml_path, encoding="utf-8") as f:
        return yaml.safe_load(f).get("names", [])


def _color(cls: int) -> tuple[int, int, int]:
    return _PALETTE_BGR[cls % len(_PALETTE_BGR)]


def _short(name: str) -> str:
    p = name.split("_")
    if len(p) >= 2:
        return (p[0][0] + p[1][0]).upper() + ("n" if p[1] == "Knight" else "")
    return name[:2].upper()


def _piece_type(name: str) -> str | None:
    if name.lower() == "board":
        return "Board"
    p = name.split("_")
    return p[1] if len(p) >= 2 else None


def _iou(a: tuple, b: tuple) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    ua = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
    return inter / ua if ua > 0 else 0.0


def _run_model(model, img: np.ndarray, conf: float, device: str) -> list:
    results = model.predict(source=img, conf=conf, device=device, verbose=False)
    out = []
    for box in results[0].boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
        out.append((int(box.cls[0]), x1, y1, x2, y2, float(box.conf[0])))
    return out


def _filter(boxes: list, names: list[str], iou_t: float = 0.5) -> list:
    """Greedy filter: remove duplicate positions and enforce piece-count limits per Xiangqi rules."""
    kept: list = []
    counts: dict[int, int] = {}
    for box in sorted(boxes, key=lambda b: b[5], reverse=True):
        cls, x1, y1, x2, y2, conf = box
        name = names[cls] if cls < len(names) else ""
        pt = _piece_type(name)
        mx = _PIECE_MAX.get(pt) if pt else None
        if mx and counts.get(cls, 0) >= mx:
            continue
        if any(_iou((x1, y1, x2, y2), (k[1], k[2], k[3], k[4])) >= iou_t for k in kept):
            continue
        kept.append(box)
        counts[cls] = counts.get(cls, 0) + 1
    return kept


def _missing_kings(boxes: list, names: list[str]) -> set[str]:
    present = {names[b[0]] for b in boxes if b[0] < len(names)}
    return {c for c in ("Red", "Black") if f"{c}_King" not in present}


def _rule_ok(cand: tuple, existing: list, names: list[str], iou_t: float = 0.5) -> bool:
    cls, x1, y1, x2, y2, _ = cand
    name = names[cls] if cls < len(names) else ""
    pt = _piece_type(name)
    mx = _PIECE_MAX.get(pt) if pt else None
    if mx and sum(1 for b in existing if b[0] == cls) >= mx:
        return False
    return not any(_iou((x1, y1, x2, y2), (k[1], k[2], k[3], k[4])) >= iou_t for k in existing)


def _refine(main: list, aux: list, names: list[str],
            low_t: float, aux_t: float, iou_t: float) -> tuple[list, list[int]]:
    """Step 1: replace low-confidence main boxes with better aux boxes at the same position."""
    refined = list(main)
    replaced: list[int] = []
    used: set[int] = set()

    for i, mb in enumerate(refined):
        m_cls, mx1, my1, mx2, my2, m_conf = mb
        m_name = names[m_cls] if m_cls < len(names) else ""
        if m_conf >= low_t or _piece_type(m_name) == "King":
            continue
        mbox = (mx1, my1, mx2, my2)
        missing = _missing_kings(refined, names)
        cands: list = []
        for j, ab in enumerate(aux):
            if j in used:
                continue
            a_cls, ax1, ay1, ax2, ay2, a_conf = ab
            if a_cls == m_cls or _iou(mbox, (ax1, ay1, ax2, ay2)) < iou_t:
                continue
            a_name = names[a_cls] if a_cls < len(names) else ""
            a_color = a_name.split("_")[0] if "_" in a_name else ""
            king_exc = _piece_type(a_name) == "King" and a_color in missing
            if not king_exc and a_conf <= aux_t:
                continue
            cands.append((a_conf, j, ab, king_exc))
        if not cands:
            continue
        cands.sort(key=lambda x: (x[3], x[0]), reverse=True)
        _, bj, best, _ = cands[0]
        tmp = [b for k, b in enumerate(refined) if k != i]
        if not _rule_ok(best, tmp, names, iou_t):
            continue
        refined[i] = best
        used.add(bj)
        replaced.append(i)

    return refined, replaced


def _merge(main: list, aux: list, names: list[str],
           refine_t: float = 0.70, aux_replace_t: float = 0.85,
           add_t: float = 0.70, iou_t: float = 0.5) -> tuple[list, list[int], list[int]]:
    """Merge dual-model results: replace low-confidence boxes and add pieces at new positions."""
    refined, replaced = _refine(main, aux, names, refine_t, aux_replace_t, iou_t)

    extras = [b for b in aux if not any(
        _iou((b[1], b[2], b[3], b[4]), (k[1], k[2], k[3], k[4])) >= iou_t for k in refined
    )]
    merged = refined
    added: list[int] = []
    for cand in sorted(extras, key=lambda b: b[5], reverse=True):
        if cand[5] < add_t:
            continue
        if not _rule_ok(cand, merged, names, iou_t):
            continue
        added.append(len(merged))
        merged.append(cand)

    return merged, added, replaced


# ===========================================================================
# Board detection & geometry helpers
# ===========================================================================

def _detect_board_keypoints(
    model, image_bgr: np.ndarray,
    board_class_id: int = 0, conf: float = 0.5, device: str = "cpu",
):
    """Use YOLO Pose to detect the 'board' class and extract its 4 corner keypoints."""
    results = model.predict(source=image_bgr, imgsz=800, conf=conf,
                            device=device, verbose=False)
    if not results:
        return None, None
    r = results[0]
    if r.boxes is None or len(r.boxes) == 0:
        return None, None

    boxes = r.boxes.xyxy.cpu().numpy()
    clss = r.boxes.cls.cpu().numpy()
    idxs = np.where(clss == board_class_id)[0]
    if len(idxs) == 0:
        return None, None

    cand = boxes[idxs]
    areas = (cand[:, 2] - cand[:, 0]) * (cand[:, 3] - cand[:, 1])
    best_local = int(np.argmax(areas))
    det_idx = int(idxs[best_local])
    bbox = boxes[det_idx].astype(int)

    if r.keypoints is None or r.keypoints.xy is None:
        return None, tuple(bbox.tolist())
    kpts = r.keypoints.xy.cpu().numpy()
    if det_idx >= kpts.shape[0] or kpts.shape[1] < 4:
        return None, tuple(bbox.tolist())

    corners = kpts[det_idx, [0, 1, 2, 3], :].astype(np.float32)
    return corners, tuple(bbox.tolist())


def _compute_h(
    image_bgr: np.ndarray, pose_model,
    board_class_id: int = 0, conf_pose: float = 0.5, device: str = "cpu",
):
    """
    Pose model on the image (usually cropped) → keypoints → homography H.
    Return (corners_src, H, bbox) or (None, None, None).
    """
    corners, bbox = _detect_board_keypoints(
        pose_model, image_bgr,
        board_class_id=board_class_id, conf=conf_pose, device=device,
    )
    if corners is None or bbox is None:
        return None, None, None

    h, w = image_bgr.shape[:2]
    src = corners.copy()
    src[:, 0] = np.clip(src[:, 0], 0, w - 1)
    src[:, 1] = np.clip(src[:, 1], 0, h - 1)

    dst = np.float32([
        [0, 0],
        [VIRTUAL_BOARD_W, 0],
        [VIRTUAL_BOARD_W, VIRTUAL_BOARD_H],
        [0, VIRTUAL_BOARD_H],
    ])
    H = cv2.getPerspectiveTransform(src, dst)
    return src, H, bbox


def _extract_board_bbox(pred_boxes: list, board_class_id: int):
    """Return the largest board bounding box from pred_boxes (cls, x1, y1, x2, y2, conf)."""
    boards = [b for b in pred_boxes if b[0] == board_class_id]
    if not boards:
        return None
    best = max(boards, key=lambda b: (b[3] - b[1]) * (b[4] - b[2]))
    return (best[1], best[2], best[3], best[4])


def _filter_pieces_inside_board(
    pred_boxes: list, board_bbox: tuple, board_class_id: int,
    added_indices: list[int] | None = None,
    replaced_indices: list[int] | None = None,
) -> tuple[list, set, set]:
    """Remove the board class and any piece whose center falls outside board_bbox."""
    bx1, by1, bx2, by2 = board_bbox
    orig_added = set(added_indices or [])
    orig_replaced = set(replaced_indices or [])
    filtered: list = []
    new_added: set = set()
    new_replaced: set = set()

    for orig_idx, box in enumerate(pred_boxes):
        cls, x1, y1, x2, y2, conf = box
        if cls == board_class_id:
            continue
        cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        if not (bx1 <= cx <= bx2 and by1 <= cy <= by2):
            continue
        new_idx = len(filtered)
        if orig_idx in orig_added:
            new_added.add(new_idx)
        if orig_idx in orig_replaced:
            new_replaced.add(new_idx)
        filtered.append(box)

    return filtered, new_added, new_replaced


def _crop_to_board(image_bgr: np.ndarray, bbox: tuple, padding: int = 5):
    """Crop the image to the board bounding box with a small padding to preserve corners."""
    h, w = image_bgr.shape[:2]
    x1, y1, x2, y2 = bbox
    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = min(w, x2 + padding)
    y2 = min(h, y2 + padding)
    return image_bgr[y1:y2, x1:x2].copy(), (x1, y1, x2, y2)


def _shift_boxes_to_crop(pred_boxes: list, ox: int, oy: int) -> list:
    """Translate bounding box coordinates from the original image space to the crop space."""
    return [(cls, x1 - ox, y1 - oy, x2 - ox, y2 - oy, conf)
            for cls, x1, y1, x2, y2, conf in pred_boxes]


def _compute_centers(pred_boxes: list) -> np.ndarray:
    centers = []
    for cls, x1, y1, x2, y2, conf in pred_boxes:
        centers.append(((x1 + x2) / 2.0, (y1 + y2) / 2.0))
    return np.array(centers, dtype=np.float32) if centers else np.zeros((0, 2), dtype=np.float32)


def _project_points(pts: np.ndarray, H: np.ndarray) -> np.ndarray:
    if pts.size == 0:
        return pts
    return cv2.perspectiveTransform(
        pts.reshape(-1, 1, 2).astype(np.float32), H,
    ).reshape(-1, 2)


def _center_to_grid(center) -> tuple[int, int]:
    """Convert a virtual-board pixel coordinate to a grid cell (u, v): 0 ≤ u ≤ 8, 0 ≤ v ≤ 9."""
    if isinstance(center, np.ndarray):
        x, y = float(center[0]), float(center[1])
    else:
        x, y = center
    cell_w = VIRTUAL_BOARD_W / 8.0
    cell_h = VIRTUAL_BOARD_H / 9.0
    u_base = int(x // cell_w)
    v_base = int(y // cell_h)
    u = u_base + 1 if (x - u_base * cell_w) > 50 else u_base
    v = v_base + 1 if (y - v_base * cell_h) > 50 else v_base
    return max(0, min(8, u)), max(0, min(9, v))


# ===========================================================================
# Position-rule correction
# ===========================================================================

# margin = mean + 2*std (px on the virtual board) used when trying to shift coordinates
_CORRECTION_MARGIN: float = 3.10 + 2 * 2.12   # ≈ 7.34 px

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
    """Return True if piece *name* at (u, v) violates a position rule."""
    if name in _VALID_POSITIONS:
        return (u, v) not in _VALID_POSITIONS[name]
    if name == "Black_Pawn":
        return v < 3 or (u, v) in _FORBIDDEN_BLACK_PAWN
    if name == "Red_Pawn":
        return v > 6 or (u, v) in _FORBIDDEN_RED_PAWN
    return False


def _correct_grid_position(
    name: str,
    u_base_px: float,
    v_base_px: float,
    occupied: set[tuple[int, int]],
    margin: float = _CORRECTION_MARGIN,
) -> tuple[int, int] | None:
    """
    Try shifting the center in the 4 cardinal directions (±margin px on the virtual board)
    to find a valid grid cell: not occupied and not violating any position rule.
    Returns (u, v) if found, None otherwise.
    """
    for du, dv in ((margin, 0.0), (0.0, margin), (0.0, -margin), (-margin, 0.0)):
        nu, nv = _center_to_grid((u_base_px + du, v_base_px + dv))
        if (nu, nv) in occupied:
            continue
        if not _violates_position_rule(name, nu, nv):
            print(f"Corrected position: {name} ({u_base_px}, {v_base_px}) -> ({nu}, {nv})")
            return nu, nv
    return None


# ===========================================================================
# Draw helpers
# ===========================================================================

def _adaptive_font_scale(img_w: int, img_h: int) -> tuple[float, int, int]:
    """
    Compute font_scale, line_thickness, and dot_radius adapted to the image size.
    Smaller images use smaller text to avoid overlap.
    Reference: 800x600 image → font_scale=0.55, lw=2, dot=4.
    """
    ref = min(img_w, img_h)
    scale = np.clip(ref / 600.0, 0.3, 1.4)
    font_scale  = round(0.55 * scale, 3)
    line_w      = max(1, int(2 * scale))
    dot_r       = max(2, int(4 * scale))
    return font_scale, line_w, dot_r


def _draw_boxes(img: np.ndarray, boxes: list, names: list[str],
                highlight: set[int] | None = None,
                centers_board: np.ndarray | None = None,
                grid_overrides: list[tuple[int, int] | None] | None = None) -> None:
    h, w = img.shape[:2]
    fs, base_lw, dot_r = _adaptive_font_scale(w, h)
    grid_fs = fs * 0.85

    for idx, box in enumerate(boxes):
        cls, x1, y1, x2, y2, conf = box
        hl = highlight is not None and idx in highlight
        name = names[cls] if cls < len(names) else "??"
        label = f"{_short(name)} {conf:.2f}"
        col = _color(cls)
        lw = base_lw + 2 if hl else base_lw

        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, fs, 1)
        lh = th + 6
        if y1 - lh >= 0:
            ly1, ly2, ty = y1 - lh, y1, y1 - 3
        else:
            ly1, ly2, ty = y2, y2 + lh, y2 + th + 3
        ly1 = max(0, min(ly1, h - 1))
        ly2 = max(0, min(ly2, h))
        ty  = max(th + 2, min(ty, h - 2))

        cv2.rectangle(img, (x1, y1), (x2, y2), col, lw)
        if hl:
            cv2.rectangle(img, (x1 - 2, y1 - 2), (x2 + 2, y2 + 2), (255, 255, 255), 1)
        cv2.rectangle(img, (x1, ly1), (min(x1 + tw + 4, w), ly2), col, -1)
        cv2.putText(img, label, (x1 + 2, ty),
                    cv2.FONT_HERSHEY_SIMPLEX, fs, (0, 0, 0), 1, cv2.LINE_AA)
        if hl:
            (_, hth), _ = cv2.getTextSize("[+]", cv2.FONT_HERSHEY_SIMPLEX, fs * 0.7, 1)
            cv2.putText(img, "[+]", (x1 + 2, ty + th + 4),
                        cv2.FONT_HERSHEY_SIMPLEX, fs * 0.7, (0, 200, 0), 1, cv2.LINE_AA)

        if centers_board is not None and idx < len(centers_board):
            u, v = centers_board[idx]
            if np.isfinite(u) and np.isfinite(v):
                # Use corrected coordinates if available, otherwise recompute from raw
                if grid_overrides is not None and idx < len(grid_overrides) and grid_overrides[idx] is not None:
                    gu, gv = grid_overrides[idx]
                else:
                    gu, gv = _center_to_grid((u, v))
                cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
                cv2.circle(img, (cx, cy), dot_r, col, -1)
                grid_label = f"({gu},{gv})"
                (gtw, gth), _ = cv2.getTextSize(grid_label, cv2.FONT_HERSHEY_SIMPLEX, grid_fs, 1)
                color = (0,0,200) if 'Black' in name else (0,0,0)
                cv2.putText(img, grid_label, (cx + dot_r + 2, cy + gth // 2),
                            cv2.FONT_HERSHEY_SIMPLEX, grid_fs, color, base_lw, cv2.LINE_AA)


# ===========================================================================
# DetectionService
# ===========================================================================

class DetectionService:
    """
    Background chess piece detection service integrated with the pygame app.

    Pipeline:
      original image → dual-model detect (pieces + board) → filter pieces inside board
                     → crop → pose-model(crop) → H → grid coords
    """

    def __init__(
        self,
        main_model_path: str = _DEFAULT_MAIN_MODEL,
        aux_model_path:  str = _DEFAULT_AUX_MODEL,
        pose_model_path: str = _DEFAULT_POSE_MODEL,
        data_yaml:       str = _DEFAULT_DATA_YAML,
        conf_thres:   float  = 0.20,
        conf_pose:    float  = 0.50,
        refine_conf:  float  = 0.70,
        add_conf:     float  = 0.70,
        board_class_id_detect: int = 14,
        board_class_id_pose:   int = 0,
        crop_padding:  int    = 5,
        device: str | None    = None,
    ) -> None:
        self._main_path   = main_model_path
        self._aux_path    = aux_model_path
        self._pose_path   = pose_model_path
        self._data_yaml   = data_yaml
        self._conf        = conf_thres
        self._conf_pose   = conf_pose
        self._refine_conf = refine_conf
        self._add_conf    = add_conf
        self._board_cls_detect = board_class_id_detect
        self._board_cls_pose   = board_class_id_pose
        self._crop_padding     = crop_padding
        self._device: str = device or self._auto_device()

        self._main_model  = None
        self._aux_model   = None
        self._pose_model  = None
        self._names: list[str] = []

        self._model_lock = threading.Lock()
        self._busy_lock  = threading.Lock()
        self._is_busy    = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def preload_models(self) -> None:
        """Load models early in a background thread without blocking the app."""
        threading.Thread(target=self._load_models, daemon=True).start()

    def detect_async(
        self,
        image_path: Optional[str],
        is_temp: bool = False,
        on_notify: Optional[Callable[[str], None]] = None,
        on_result: Optional[Callable[[list], None]] = None,
    ) -> bool:
        """
        Run detection in a daemon thread.

        Args:
            image_path : path to the input image (None or non-existent → skip).
            is_temp    : True if the file is temporary (screen capture) → auto-delete when done.
            on_notify  : callback(str) to push notifications to the pygame UI.
            on_result  : callback(list[dict]) receiving grid_results after detection and
                         correction. Each dict has keys:
                           "name"  – model name (e.g. "Black_Rook")
                           "grid"  – (u, v) in model coords (u: 0‒8, v: 0‒9)
                           "conf"  – confidence
                           "cls", "short"

        Returns:
            True if the thread was started, False if busy or path is invalid.
        """
        if not image_path or not os.path.isfile(image_path):
            return False
        with self._busy_lock:
            if self._is_busy:
                if on_notify:
                    on_notify("Đang nhận diện... vui lòng chờ.")
                return False
            self._is_busy = True

        threading.Thread(
            target=self._worker,
            args=(image_path, is_temp, on_notify, on_result),
            daemon=True,
        ).start()
        return True

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _auto_device() -> str:
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    def _load_models(self) -> None:
        with self._model_lock:
            if self._main_model is not None:
                return
            from ultralytics import YOLO
            self._main_model = YOLO(self._main_path)
            self._aux_model  = YOLO(self._aux_path)
            self._pose_model = YOLO(self._pose_path)
            self._names      = _load_names(self._data_yaml)

    def _worker(
        self,
        image_path: str,
        is_temp: bool,
        on_notify: Optional[Callable[[str], None]],
        on_result: Optional[Callable[[list], None]] = None,
    ) -> None:
        try:
            self._load_models()

            img_bgr = cv2.imread(image_path)
            if img_bgr is None:
                if on_notify:
                    on_notify("Lỗi: không đọc được ảnh.")
                return

            t_start = time.perf_counter()

            # ── Step 1: Dual-model detection on the ORIGINAL image (pieces + board) ──
            t0 = time.perf_counter()
            main_raw = _run_model(self._main_model, img_bgr, self._conf, self._device)
            main_boxes = _filter(main_raw, self._names)
            aux_raw = _run_model(self._aux_model, img_bgr, self._conf, self._device)
            aux_boxes = _filter(aux_raw, self._names)
            all_boxes, added_indices, replaced_indices = _merge(
                main_boxes, aux_boxes, self._names,
                refine_t=self._refine_conf, add_t=self._add_conf,
            )
            t_detect = time.perf_counter() - t0

            # ── Step 2: Extract board bbox from dual-model results ──
            board_bbox = _extract_board_bbox(all_boxes, self._board_cls_detect)
            if board_bbox is None:
                if on_notify:
                    on_notify("Lỗi: không detect được bàn cờ.")
                return

            # ── Step 3: Filter pieces inside the board and remove the board class ──
            pieces_in_board, new_added, new_replaced = _filter_pieces_inside_board(
                all_boxes, board_bbox, self._board_cls_detect,
                added_indices, replaced_indices,
            )

            # ── Step 4: Crop image to the board bounding box ──
            img_crop, crop_bbox = _crop_to_board(img_bgr, board_bbox, self._crop_padding)
            ox, oy = crop_bbox[0], crop_bbox[1]

            # ── Step 5: Pose model on the cropped image → keypoints → H ──
            t0 = time.perf_counter()
            corners, H, _ = _compute_h(
                img_crop, self._pose_model,
                board_class_id=self._board_cls_pose,
                conf_pose=self._conf_pose,
                device=self._device,
            )
            t_pose = time.perf_counter() - t0

            # ── Step 6: Translate piece coordinates from original image space to crop space ──
            pred_boxes_crop = _shift_boxes_to_crop(pieces_in_board, ox, oy)

            if H is None:
                t_total = time.perf_counter() - t_start
                if on_notify:
                    on_notify(
                        f"Nhận diện: {len(pred_boxes_crop)} quân  "
                        f"(không tính được tọa độ lưới)  "
                        f"{t_total * 1000:.0f}ms"
                    )
                from App.configuration import Settings
                if Settings.DEV_MODE:
                    self._show_dev_result(
                        img_crop, pred_boxes_crop,
                        new_added, new_replaced, corners, None,
                        t_detect, t_pose, t_total, Path(image_path).name,
                    )
                return

            # ── Step 7: Compute centers (crop space) and project onto the virtual board ──
            centers_img = _compute_centers(pred_boxes_crop)
            centers_board = _project_points(centers_img, H)

            

            # ── Step 8: Build grid results list ──
            grid_results: list[dict] = []
            for i, (cls_id, x1, y1, x2, y2, conf) in enumerate(pred_boxes_crop):
                name = self._names[cls_id] if cls_id < len(self._names) else ""
                u, v = centers_board[i] if i < len(centers_board) else (np.nan, np.nan)
                if np.isfinite(u) and np.isfinite(v):
                    gu, gv = _center_to_grid((u, v))
                else:
                    gu, gv = None, None
                grid_results.append({
                    "cls": cls_id,
                    "name": name,
                    "short": _short(name) if name else str(cls_id),
                    "grid": (gu, gv),
                    "conf": conf,
                })

            # ── Step 9: Correct coordinates that violate position rules ──
            occupied_grids: set[tuple[int, int]] = {
                r["grid"] for r in grid_results if r["grid"][0] is not None
            }
            for i, r in enumerate(grid_results):
                gu, gv = r["grid"]
                if gu is None:
                    continue
                if not _violates_position_rule(r["name"], gu, gv):
                    continue
                u_px = float(centers_board[i][0])
                v_px = float(centers_board[i][1])
                occupied_grids.discard((gu, gv))
                corrected = _correct_grid_position(
                    r["name"], u_px, v_px, occupied_grids
                )
                if corrected is not None:
                    r["grid"] = corrected
                    occupied_grids.add(corrected)
                else:
                    occupied_grids.add((gu, gv))

            t_total = time.perf_counter() - t_start

            # ── Return results to the caller ──
            if on_result:
                on_result(grid_results)

            # ── Push notification to UI ──
            if on_notify:
                on_notify(
                    f"Nhận diện: {len(pred_boxes_crop)} quân  "
                    # f"(+{len(new_added)} thêm | ~{len(new_replaced)} thay)  "
                    f"{t_total * 1000:.0f}ms"
                )

            # ── Show result image if DEV_MODE is enabled ──
            from App.configuration import Settings
            if Settings.DEV_MODE:
                self._show_dev_result(
                    img_crop, pred_boxes_crop,
                    new_added, new_replaced, corners, centers_board,
                    t_detect, t_pose, t_total, Path(image_path).name,
                    grid_results=grid_results,
                )

        finally:
            if is_temp and os.path.isfile(image_path):
                try:
                    os.remove(image_path)
                except OSError:
                    pass
            with self._busy_lock:
                self._is_busy = False

    def _show_dev_result(
        self,
        img_crop: np.ndarray,
        pred_boxes_crop: list,
        added: set, replaced: set,
        corners: np.ndarray | None,
        centers_board: np.ndarray | None,
        t_detect: float,
        t_pose: float,
        total_time: float,
        source_name: str,
        grid_results: list[dict] | None = None,
    ) -> None:
        """Render pipeline results, save to a temp PNG, open viewer, then clean up."""
        result_path = self._render_result(
            img_crop, pred_boxes_crop, added, replaced, corners, centers_board,
            t_detect, t_pose, total_time, source_name, self._device,
            grid_results=grid_results,
        )
        if result_path:
            subprocess.run(
                [sys.executable, _VIEWER_SCRIPT, result_path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            try:
                os.remove(result_path)
            except OSError:
                pass

    def _render_result(
        self,
        img_crop: np.ndarray,
        pred_boxes_crop: list,
        added: set, replaced: set,
        corners: np.ndarray | None,
        centers_board: np.ndarray | None,
        t_detect: float,
        t_pose: float,
        total_time: float,
        source_name: str,
        device: str,
        grid_results: list[dict] | None = None,
    ) -> Optional[str]:
        """Draw pipeline results onto the cropped image, save as a temp PNG, and return the path."""
        try:
            result_img = img_crop.copy()

            if corners is not None and len(corners) == 4:
                pts_i = corners.astype(int).reshape(-1, 1, 2)
                cv2.polylines(result_img, [pts_i], True, (0, 255, 0), 2)
                for i, (x, y) in enumerate(corners):
                    cv2.circle(result_img, (int(x), int(y)), 6, (255, 0, 0), -1)
                    cv2.putText(result_img, str(i), (int(x) + 3, int(y) - 3),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 3, cv2.LINE_AA)

            highlight = (added | replaced) if (added or replaced) else None
            grid_overrides = [r["grid"] for r in grid_results] if grid_results else None
            _draw_boxes(result_img, pred_boxes_crop, self._names,
                        highlight=highlight, centers_board=centers_board,
                        grid_overrides=grid_overrides)

            img_h, img_w = result_img.shape[:2]
            base_scale = min(img_w / 800, img_h / 600)
            font_scale = max(0.4, min(0.75, 0.58 * base_scale))
            bar_h = max(20, int(26 * base_scale))
            total_ms  = total_time * 1000
            detect_ms = t_detect * 1000
            pose_ms   = t_pose * 1000
            n = len(pred_boxes_crop)
            piece_info = f"{n} quan (+{len(added)} ~{len(replaced)})"

            # Try detail levels from full → abbreviated → minimal until text fits
            candidates = [
                (
                    f"{source_name}  |  {piece_info}  |  "
                    f"detect={detect_ms:.0f}ms  pose={pose_ms:.0f}ms  total={total_ms:.0f}ms | {device}"
                ),
                (
                    f"{piece_info}  |  "
                    f"detect={detect_ms:.0f}ms  pose={pose_ms:.0f}ms  total={total_ms:.0f}ms | {device}"
                ),
                f"{piece_info}  |  total={total_ms:.0f}ms | {device}",
                f"{n} quan  {total_ms:.0f}ms | {device}",
            ]
            info = candidates[-1]
            for candidate in candidates:
                (tw, _), _ = cv2.getTextSize(candidate, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)
                if tw <= img_w - 16:
                    info = candidate
                    break

            (_, text_h), _ = cv2.getTextSize(info, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)
            bar_h = max(bar_h, text_h + 8)
            overlay = result_img.copy()
            cv2.rectangle(overlay, (0, 0), (img_w, bar_h), (30, 30, 30), -1)
            cv2.addWeighted(overlay, 0.7, result_img, 0.3, 0, result_img)
            text_y = (bar_h + text_h) // 2
            cv2.putText(result_img, info, (8, text_y),
                        cv2.FONT_HERSHEY_SIMPLEX, font_scale, (220, 220, 220), 1, cv2.LINE_AA)

            fd, path = tempfile.mkstemp(suffix="_xq_detect.png")
            os.close(fd)
            cv2.imwrite(path, result_img)
            del result_img
            return path
        except Exception as e:
            print(f"[DetectionService] render error: {e}")
            return None
