# XiangQi Reconstruction

A desktop **Xiangqi (Chinese Chess)** application built with Python and Pygame, featuring an **AI-powered board reconstruction** system that detects and reconstructs piece positions from real-world photos or screen captures.
<p align="center">
<img src="XiangQi-demo.gif" width="720" alt="XiangQi Demo">
</p>
> *The demo above shows the full workflow: launching the app, playing moves, using the board reconstruction feature from a screen capture, and navigating the move record.*

---

## Research Paper

This project is accompanied by a research paper describing the AI pipeline design, model training, and evaluation results. If you want to learn more about the technical approach — including the dual-model detection strategy, homography-based board localization, and the piece-position correction algorithm — please refer to the paper:

[**"Xiangqi Board Reconstruction Using Computer Vision and Deep Learning"**](https://drive.google.com/file/d/1lIpAoEM14-YhtANV4rW6AdYe1Z6EWL3e/view?usp=sharing)


**Dataset (Roboflow):** [XiangQi Dataset](https://universe.roboflow.com/duytranle/xiangqi-ubjij/dataset/18)

The paper covers:

- Dataset collection and annotation for Xiangqi piece detection
- YOLO-based dual-model detection pipeline
- YOLO Pose for board corner keypoint estimation
- Homography projection to map piece positions onto a virtual grid
- Rule-based position correction for invalid placements

---

## Features

- **Interactive gameplay** — play Xiangqi with full rule enforcement (valid moves, check, checkmate detection)
- **Board reconstruction via AI** — upload a photo or take a screen capture of a real board; YOLO-based models detect pieces and reconstruct the position automatically
- **Setup mode** — freely arrange pieces on the board to study any position
- **Move record** — full game tree with branching variations and backward/forward navigation
- **FEN support** — copy and paste FEN strings for position exchange
- **Board flip** — rotate the board 180° with a smooth animation
- **Opening book** — integrated opening reference panel

---

## Project Structure

```
XiangQi/
├── App/
│   ├── app.py              # Main entry point
│   ├── configuration.py    # Global settings (FPS, colors, modes, device)
│   ├── piece.py            # Chess piece and board model
│   ├── position.py         # Coordinate mapping (screen ↔ grid)
│   └── rule.py             # Move validation and game rules
├── Reconstruction/
│   ├── detect_service.py   # Detection pipeline (dual-model + pose)
│   ├── reconstructor.py    # Maps detection results → ChessBoard
│   └── weights/            # YOLO model weights (.pt) and data.yaml
├── UI/
│   ├── renderer.py         # Pygame drawing and UI components
│   ├── record.py           # Move record panel (scrollable, branching)
│   └── book.py             # Opening book panel
├── utils/
│   ├── navigation.py       # Forward/backward navigation in game tree
│   ├── setupMode.py        # Piece-arrangement mode logic
│   ├── storeGameData.py    # Game tree data structure
│   ├── flip.py             # Board flip / rotation helpers
│   ├── fen.py              # FEN encoding and decoding
│   ├── screen_capture.py   # Screen region capture
│   └── image_upload.py     # Image upload via file dialog
├── board/
│   └── board.jpg           # Board background image
├── Piece/                  # Piece image assets (Red / Black)
├── assets/                 # UI icons and images
├── Roboto Font/            # Font files 
├── requirements.txt
├── db.sqlite3     
└── README.md
```

---

## Requirements

- **Python 3.11** (recommended; 3.10+ should work)
- **CPU is recommended** for the detection pipeline — the app processes only one image at a time, so CPU inference is fast enough and avoids the overhead of setting up CUDA. A GPU is optional and only useful if you plan to process many images in bulk.

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/DuyLeTran/DeepXiangQi.git
cd DeepXiangQi
```

### 2. Create and activate a virtual environment (recommended)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

> **CPU vs GPU:**  
> The default `requirements.txt` installs the CPU build of PyTorch, which is the **recommended setup**.  
> Because the app detects only one image per request, CPU inference completes in a few seconds and requires no extra configuration.  
>
> If you still want GPU acceleration (e.g. for custom batch experiments), install the CUDA build manually:
>
> ```bash
> # Example for CUDA 12.8
> pip install torch --index-url https://download.pytorch.org/whl/cu128
> ```
>
> Then change `DEVICE = 'cuda'` in `App/configuration.py`.

### 4. Place model weights

The AI detection pipeline requires three YOLO weight files inside `Reconstruction/weights/`:


| File              | Purpose                                      |
| ----------------- | -------------------------------------------- |
| `detect-ultra.pt` | Primary piece detector                       |
| `duy-best-26s.pt` | Auxiliary piece detector (improves accuracy) |
| `pose-ultra.pt`   | Board corner keypoint detector               |


These weights are **not included** in the repository due to size. Contact the author or download them from the release page and place them in `Reconstruction/weights/`.

### 5. Run the application

```bash
python App/app.py
```

> Make sure to run from the **project root directory** so that relative paths (board image, assets, fonts, weights) resolve correctly.

---

## Usage

### Basic gameplay


| Action             | How                                      |
| ------------------ | ---------------------------------------- |
| Select a piece     | Left-click on it                         |
| Move a piece       | Left-click on a highlighted valid square |
| Flip the board     | Click the **Rotate** button (↻)          |
| Undo / redo a move | Click **←** / **→** navigation buttons   |
| New game           | Menu → **Tạo mới**                       |


### Board reconstruction from an image

1. Click the **＋** (Add) button in the toolbar.
2. Choose **Camera** to capture a screen region, or **Gallery** to upload an image from disk.
3. The AI pipeline runs in the background — a notification appears when detection is complete and the board is reconstructed automatically.

> The demo GIF above demonstrates reconstructing a board position from a live screen capture of a real Xiangqi broadcast.

### Setup mode

1. Menu → **Sắp quân** to enter setup mode.
2. Click a piece to select it; valid placement squares are highlighted.
3. Move pieces freely, including to and from the off-board staging area.
4. Click **Expand** to move all pieces (except the king) to the staging area at once.
5. Click **✓ (Tick)** to confirm the layout and return to normal play.

### FEN

- Menu → **Sao chép FEN** — copies the current position as a FEN string to the clipboard.
- Menu → **Dán FEN** — pastes a FEN string from the clipboard to set the board position.

### Move record

- Switch to the **Biên bản** tab (right panel) to view the full move list.
- Click any move row to jump directly to that position.
- When multiple variations exist at a move, a branch button (⊞) appears — click it to select a variation.
- Use the mouse wheel to scroll through long games.

---

## Configuration

Open `App/configuration.py` to adjust settings:


| Setting               | Default | Description                                                                  |
| --------------------- | ------- | ---------------------------------------------------------------------------- |
| `FPS`                 | `120`   | Target frame rate                                                            |
| `FLIPPED`             | `False` | Start with the board flipped                                                 |
| `DEV_MODE`            | `True`  | Show AI detection overlay after reconstruction                               |
| `DEVICE`              | `'cpu'` | Inference device — `'cpu'` is recommended; `'cuda'` only if GPU is available |
| `SHOW_UPLOADED_IMAGE` | `False` | Preview uploaded image in a separate window                                  |


---

## License

This project is for educational and research purposes. Please contact the author before using it in commercial products.
leduytran0501@gmail.com