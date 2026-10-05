"""Regenerate the static screens the device draws without the server. Run from the repo root:
    python device/make_images.py

- sleep.png        shown while suspended
- waking.png       shown on wake until fresh data arrives: a blank screen with the coin
- loading/NN.png   frames of a spinning pixel-art euro coin, redrawn in place by loading.sh
- loading/pos      where the frames go on the framebuffer: "x y"

The coin is pure black and white on purpose: loading.sh animates it with a fast two-level
e-ink waveform, which can't show grays. Everything is drawn landscape and rotated to the
portrait framebuffer, matching ROTATE=90."""
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
from budget_box.render import font  # noqa: E402

W, H = 1448, 1072
OUT = Path(__file__).resolve().parent


def portrait(img):
    return img.rotate(90, expand=True)


# -- sleep -------------------------------------------------------------------------
img = Image.new("L", (W, H), 255)
d = ImageDraw.Draw(img)
d.text((W // 2, H // 2 - 80), "Budget Box", font=font(150, True), fill=0, anchor="mm")
d.text((W // 2, H // 2 + 70), "asleep · press the power button to wake", font=font(36), fill=110, anchor="mm")
portrait(img).save(OUT / "sleep.png", optimize=True)

# -- the coin ----------------------------------------------------------------------
GRID = 44          # sprite resolution in "pixels"
SCALE = 9          # each sprite pixel becomes 9x9 screen pixels -> 396 px
FRAMES = 16
R = 18             # coin radius in sprite pixels
THICK = 3          # rim thickness in sprite pixels


def face(width: int) -> Image.Image:
    """The coin face squashed to `width` sprite pixels wide (1-bit)."""
    big = 8                                   # draw the face large, then squash: crisper glyph
    D = 2 * R * big
    f = Image.new("L", (D, D), 255)
    g = ImageDraw.Draw(f)
    g.ellipse([0, 0, D - 1, D - 1], fill=255, outline=0, width=2 * big)
    g.ellipse([5 * big, 5 * big, D - 1 - 5 * big, D - 1 - 5 * big], outline=0, width=big)
    g.text((D // 2, D // 2 + big), "€", font=font(int(D * 0.5), True), fill=0, anchor="mm")
    f = f.resize((max(width, 1), 2 * R), Image.LANCZOS)
    return f.point(lambda v: 0 if v < 140 else 255)


def frame(theta: float) -> Image.Image:
    spr = Image.new("L", (GRID, GRID), 255)
    s = ImageDraw.Draw(spr)
    c = math.cos(theta)
    w = round(2 * R * abs(c))
    cx, top = GRID // 2, GRID // 2 - R
    # the rim: a solid band the coin's thickness wide, on the side turning away; none face-on
    rim = round(THICK * abs(math.sin(theta)))
    side = 1 if math.sin(theta) * c > 0 else -1
    if w > 2:
        x0 = cx - w // 2
        for k in range(1, rim + 1):
            s.ellipse([x0 + side * k, top, x0 + side * k + w - 1, top + 2 * R - 1], fill=0)
        # the face itself (white disc with black art) over the rim
        f = face(w)
        mask = Image.new("L", f.size, 0)
        ImageDraw.Draw(mask).ellipse([0, 0, f.width - 1, f.height - 1], fill=255)
        spr.paste(f, (x0, top), mask)
    else:
        # edge-on: just the rim, a vertical bar
        s.rectangle([cx - THICK // 2 - 1, top, cx + THICK // 2, top + 2 * R - 1], fill=0)
    # a little shadow line under the coin, shrinking with it, grounds the spin
    sw = max(4, round((w or THICK) * 0.8))
    s.line([cx - sw // 2, top + 2 * R + 3, cx + sw // 2, top + 2 * R + 3], fill=0, width=1)
    return spr.resize((GRID * SCALE, GRID * SCALE), Image.NEAREST)


frames = [frame(2 * math.pi * i / FRAMES) for i in range(FRAMES)]
fw = fh = GRID * SCALE
X0, Y0 = (W - fw) // 2, (H - fh) // 2       # landscape top-left of the sprite box

waking = Image.new("L", (W, H), 255)
waking.paste(frames[0], (X0, Y0))
portrait(waking).save(OUT / "waking.png", optimize=True)

out = OUT / "loading"
out.mkdir(exist_ok=True)
for old in out.glob("*.png"):
    old.unlink()
for i, f in enumerate(frames):
    portrait(f).save(out / f"{i:02d}.png", optimize=True)
# PIL's rotate(90) maps landscape (x, y) to portrait (y, W - 1 - x): the box's landscape
# top-left (X0, Y0) lands at portrait x = Y0, y = W - (X0 + fw).
(out / "pos").write_text(f"{Y0} {W - (X0 + fw)}\n")
for stale in ("updating.png",):
    (OUT / stale).unlink(missing_ok=True)
print(f"wrote sleep.png, waking.png and {FRAMES} frames ({fw}px) at", (out / "pos").read_text().strip())
