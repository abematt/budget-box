"""Regenerate the two static screens the device draws without the server: sleep.png (shown
while suspended) and updating.png (a banner laid over the last page on wake, until fresh data
arrives). Run from the repo root: python device/make_images.py

Both are drawn landscape and rotated to the portrait framebuffer, matching ROTATE=90.
updating.png covers the footer's "as of" line: dash.sh places it at x=992 on the framebuffer."""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
from budget_box.render import font  # noqa: E402

W, H = 1448, 1072
OUT = Path(__file__).resolve().parent

img = Image.new("L", (W, H), 255)
d = ImageDraw.Draw(img)
d.text((W // 2, H // 2 - 60), "Budget Box", font=font(150, True), fill=0, anchor="mm")
d.text((W // 2, H // 2 + 90), "asleep · press the power button to wake", font=font(36), fill=110, anchor="mm")
img.rotate(90, expand=True).save(OUT / "sleep.png", optimize=True)

band = Image.new("L", (W, 70), 255)
ImageDraw.Draw(band).text((W // 2, 30), "Updating…", font=font(30, True), fill=0, anchor="mm")
band.rotate(90, expand=True).save(OUT / "updating.png", optimize=True)
print("wrote", OUT / "sleep.png", OUT / "updating.png")
