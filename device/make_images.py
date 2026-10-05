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
import random
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

# -- the coin ---------------------------------------------------------------------
GW, GH = 72, 72    # sprite box in "pixels": room above and around the coin for the dust
SCALE = 8          # each sprite pixel becomes 8x8 screen pixels -> 576 px
FRAMES = 16
R = 18             # coin radius in sprite pixels
THICK = 3          # rim thickness in sprite pixels
CX, CY = GW // 2, GH - R - 6                # coin centre: low in the box, dust rises above it


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


# -- fairy dust ----------------------------------------------------------------------
# Particles leave the top edge of the coin with a sideways and upward kick, then fall under
# gravity. Two spawn per frame; a particle's age wraps with the 16-frame spin, so the loop is
# seamless. 1-bit can't fade, so a particle shrinks instead: sparkle, plus, dot, then blinks out.
random.seed(7)
LIFE = 16                                   # frames a particle lives
GRAV = 0.42                                 # sprite px / frame^2
PARTICLES = []
for k in range(FRAMES * 2):
    PARTICLES.append({
        "born": k // 2,
        "x0": CX + random.uniform(-0.55, 0.55) * R,     # along the coin's top edge
        "vx": random.choice((-1, 1)) * random.uniform(0.6, 1.9),   # out to either side
        "vy": random.uniform(2.6, 4.1),                  # upward: peaks 8-20 px up, then falls
        "life": random.randint(LIFE - 3, LIFE),
    })


def sparkle(s: ImageDraw.ImageDraw, x: int, y: int, size: int) -> None:
    if size >= 3:                            # four-point star
        s.line([x - 2, y, x + 2, y], fill=0); s.line([x, y - 2, x, y + 2], fill=0)
        s.point([(x - 1, y - 1), (x + 1, y - 1), (x - 1, y + 1), (x + 1, y + 1)], fill=255)
    elif size == 2:                          # plus
        s.line([x - 1, y, x + 1, y], fill=0); s.line([x, y - 1, x, y + 1], fill=0)
    else:                                    # dot
        s.point((x, y), fill=0)


def dust(s: ImageDraw.ImageDraw, f: int, coin_w: int) -> None:
    for p in PARTICLES:
        age = (f - p["born"]) % FRAMES
        if age >= p["life"]:
            continue
        # emitted from where the coin's top edge is this frame: narrow coin, narrow fountain
        x0 = CX + (p["x0"] - CX) * max(coin_w, 4) / (2 * R)
        x = round(x0 + p["vx"] * age)
        y = round(CY - R - 1 - p["vy"] * age + 0.5 * GRAV * age * age)
        if age == 0 or not (2 <= x < GW - 2 and 2 <= y < GH - 2):
            continue                         # still under the rim, or out of the box
        if ((x - CX) / (max(coin_w, 4) / 2 + THICK + 2)) ** 2 + ((y - CY) / (R + 2)) ** 2 < 1:
            continue                         # behind the coin
        left = p["life"] - age
        size = 3 if age <= 2 else (2 if age <= 6 else 1)
        if left <= 3 and age % 2:            # blink out
            continue
        sparkle(s, x, y, size)


def frame(i: int) -> Image.Image:
    theta = 2 * math.pi * i / FRAMES
    spr = Image.new("L", (GW, GH), 255)
    s = ImageDraw.Draw(spr)
    c = math.cos(theta)
    w = round(2 * R * abs(c))
    top = CY - R
    # the rim: a solid band the coin's thickness wide, on the side turning away; none face-on
    rim = round(THICK * abs(math.sin(theta)))
    side = 1 if math.sin(theta) * c > 0 else -1
    if w > 2:
        x0 = CX - w // 2
        for k in range(1, rim + 1):
            s.ellipse([x0 + side * k, top, x0 + side * k + w - 1, top + 2 * R - 1], fill=0)
        f = face(w)
        mask = Image.new("L", f.size, 0)
        ImageDraw.Draw(mask).ellipse([0, 0, f.width - 1, f.height - 1], fill=255)
        spr.paste(f, (x0, top), mask)
    else:
        s.rectangle([CX - THICK // 2 - 1, top, CX + THICK // 2, top + 2 * R - 1], fill=0)
    dust(s, i, w)
    return spr.resize((GW * SCALE, GH * SCALE), Image.NEAREST)


frames = [frame(i) for i in range(FRAMES)]
fw, fh = GW * SCALE, GH * SCALE
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
