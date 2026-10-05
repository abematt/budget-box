"""Turn one page of budget data (docs/data-contract.md) into a grayscale PNG for e-ink.

E-ink has 16 grays and no colour, so state is carried by weight and wording instead: an
overspent bucket gets bold type, a solid black bar and the word "over". Everything is laid out
for the Kindle Paperwhite 4 (1072x1448, 300 ppi) and scales off the panel's short side.

Each bucket block reads top to bottom as plain sentences, weekly-first:

    Groceries
    €22                              <- big number
    left this week                   <- the phrase that completes it
    Spend up to €6 a day until Sunday   <- what to do about it
    [=========|-----]                <- this week's budget, tick = today within Mon-Sun
    €320 spent of €400 in Oct
    €80 left for the month

The weekly budget ("envelope") is computed by the data source: what was left of the monthly
cap at the start of the week, spread evenly over the days to month end.
"""
from __future__ import annotations

import glob
import io
from datetime import date, datetime
from functools import lru_cache
from typing import Any
from zoneinfo import ZoneInfo
import os

from PIL import Image, ImageDraw, ImageFont

INK, INK2, MUTED, RULE, TRACK = 0, 60, 110, 215, 225
# one bucket block at scale 1, in design pixels (+ breathing room); see _bucket_block
BLOCK_H = 40 * 1.6 + 150 * 1.05 + 44 * 1.35 + 36 * 1.9 + 22 + 34 + 28 * 1.4 + 28 + 40
TZ = ZoneInfo(os.environ.get("TZ", "Europe/Madrid"))


# -- fonts -------------------------------------------------------------------------

_CANDIDATES = {
    # (regular, bold): first pair found wins. Inter in the container; DejaVu as the Debian
    # fallback; Helvetica Neue for local runs on a Mac.
    "inter": ("/usr/share/fonts/**/Inter-Regular.*", "/usr/share/fonts/**/Inter-Bold.*"),
    "inter-var": ("/usr/share/fonts/**/Inter*.ttf", None),
    "dejavu": ("/usr/share/fonts/**/DejaVuSans.ttf", "/usr/share/fonts/**/DejaVuSans-Bold.ttf"),
    "mac": ("/System/Library/Fonts/HelveticaNeue.ttc", "/System/Library/Fonts/HelveticaNeue.ttc"),
}


@lru_cache(maxsize=None)
def _font_files() -> tuple[str, str | None, str]:
    for kind, (reg, bold) in _CANDIDATES.items():
        r = sorted(glob.glob(reg, recursive=True))
        if not r:
            continue
        b = sorted(glob.glob(bold, recursive=True)) if bold else []
        return r[0], (b[0] if b else None), kind
    raise RuntimeError("no usable TrueType font found")


@lru_cache(maxsize=64)
def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    reg, bld, kind = _font_files()
    if kind == "mac":
        return ImageFont.truetype(reg, size, index=1 if bold else 0)
    if bold and bld:
        return ImageFont.truetype(bld, size)
    f = ImageFont.truetype(reg, size)
    if bold and kind == "inter-var":  # variable font: pick the Bold instance
        try:
            f.set_variation_by_name("Bold")
        except Exception:
            pass
    return f


def plain(label: str) -> str:
    """Drop emoji and symbols (the fonts have no glyphs for them; e-ink gains nothing from them).
    Keeps Latin text including accents and €."""
    kept = "".join(c for c in label if ord(c) < 0x2190 and c not in "️‍")
    return " ".join(kept.split())


# -- wording -----------------------------------------------------------------------

def lines(b: dict[str, Any], page: dict[str, Any]) -> tuple[str, str, str, bool, str, str]:
    """(number, phrase, sub, bad, foot1, foot2) for one bucket."""
    mon = page["month_short"]
    foot1 = f"€{b['spent']:,.0f} spent of €{b['cap']:,.0f} in {mon}"
    foot2 = (f"€{b['left']:,.0f} left for the month" if not b["over"]
             else f"€{-b['left']:,.0f} past the month's budget")
    if not b["is_current"] or not b.get("w_end"):
        word = "over" if b["over"] else "under"
        return f"€{abs(b['left']):,.0f}", word, "", b["over"], foot1, foot2
    wk_end = date.fromisoformat(b["w_end"])
    ends_sunday = wk_end.weekday() == 6
    until = "Sunday" if ends_sunday else wk_end.strftime("%A %-d")
    if b["over"]:
        return f"€{-b['left']:,.0f}", "over budget", f"{mon}'s budget is all spent", True, foot1, foot2
    if b["w_left"] < 0:
        nxt = "Monday" if ends_sunday else page["next_month_short"]
        return f"€{-b['w_left']:,.0f}", "over budget this week", f"Budget resets {nxt}", True, foot1, foot2
    per = b["w_left"] / max(b["w_days_left"], 1)
    sub = (f"Spend up to €{per:,.0f} today" if b["w_days_left"] <= 1
           else f"Spend up to €{per:,.0f} a day until {until}")
    return f"€{b['w_left']:,.0f}", "left this week", sub, False, foot1, foot2


# -- drawing -----------------------------------------------------------------------

def _header_footer(d, page, w, h, m, px, battery, now):
    d.text((m, px(60)), page["title"], font=font(px(44), True), fill=INK)
    d.text((m, px(118)), f"Day {page['day']} of {page['days_in_month']}", font=font(px(30)), fill=MUTED)
    d.text((w - m, px(70)), now.strftime("%a %-d %b · %H:%M"), font=font(px(28)), fill=MUTED, anchor="ra")
    bottom = h - px(170)
    # up to two nudges from the source: side by side when they fit, stacked otherwise
    nudges = page.get("nudges", [])[:2]
    fsz = px(34)
    widths = sum(font(fsz, True).getlength(n["text"]) for n in nudges) + font(fsz).getlength("   ")
    if len(nudges) == 2 and widths > w - 2 * m:
        bottom = h - px(230)
        d.line([m, bottom, w - m, bottom], fill=RULE, width=px(2))
        for i, n in enumerate(nudges):
            d.text((m, bottom + px(50 + 60 * i)), n["text"], font=font(fsz, n["urgent"]),
                   fill=INK if n["urgent"] else MUTED, anchor="lm")
    else:
        d.line([m, bottom, w - m, bottom], fill=RULE, width=px(2))
        ty = bottom + px(58)
        for i, n in enumerate(nudges):
            x, anchor = (m, "lm") if i == 0 else (w - m, "rm")
            d.text((x, ty), n["text"], font=font(fsz, n["urgent"]), fill=INK if n["urgent"] else MUTED, anchor=anchor)
    tail = f"as of {now.strftime('%H:%M')}" + (f" · battery {battery}" if battery else "")
    d.text((w // 2, h - px(44)), tail, font=font(px(24)), fill=150, anchor="ma")
    return px(200), bottom


def _fit_scale(bs, page, bw, row_h, px) -> float:
    """Biggest type that fits: the widest line within the block width, the whole block within
    the row height."""
    widest = 1.0
    for b in bs:
        num, phrase, sub, _, foot1, foot2 = lines(b, page)
        widest = max(widest, font(px(150), True).getlength(num), font(px(44), True).getlength(phrase),
                     font(px(36)).getlength(sub), font(px(40), True).getlength(b["label"]),
                     font(px(28)).getlength(foot1), font(px(28)).getlength(foot2))
    by_width = (bw * 0.98) / widest
    by_height = row_h / px(BLOCK_H)
    return max(0.4, min(by_width, by_height, 1.8))


def _pad(row_h, px, scale) -> int:
    """Spare height above a block so it sits centred in its row rather than hugging the top."""
    return max(0, round((row_h - px(BLOCK_H * scale)) / 2))


def _bucket_block(d, b, page, x, y, bw, px, scale):
    num, phrase, sub, bad, foot1, foot2 = lines(b, page)
    lbl, big, mid, small = px(40 * scale), px(150 * scale), px(44 * scale), px(28 * scale)
    d.text((x, y), b["label"], font=font(lbl, True), fill=INK)
    y += round(lbl * 1.6)
    d.text((x, y), num, font=font(big, True), fill=INK)
    y += round(big * 1.05)
    d.text((x, y), phrase, font=font(mid, True), fill=INK)
    y += round(mid * 1.35)
    if sub:
        d.text((x, y), sub, font=font(px(36 * scale), bad), fill=INK if bad else MUTED)
    y += round(px(36 * scale) * 1.9)
    bar_h = px(22 * scale)
    if b["is_current"] and b["w_allow"] > 0:
        frac, over = min(b["w_spent"] / b["w_allow"], 1.0), b["w_left"] < 0
        tick = (b["w_days"] - b["w_days_left"] + 1) / b["w_days"]   # today, within Mon-Sun
    else:
        frac = min(b["spent"] / b["cap"], 1.0) if b["cap"] else 1.0
        over, tick = b["over"], (b["day"] / b["dim"] if b["is_current"] else None)
    d.rectangle([x, y, x + bw, y + bar_h], fill=TRACK)
    d.rectangle([x, y, x + round(bw * frac), y + bar_h], fill=INK if over else INK2)
    if tick is not None:
        tx = x + round(bw * min(max(tick, 0), 1))
        d.rectangle([tx - px(3), y - px(14), tx + px(3), y + bar_h + px(14)], fill=INK)
    y += bar_h + px(34 * scale)
    d.text((x, y), foot1, font=font(small), fill=MUTED)
    y += round(small * 1.4)
    d.text((x, y), foot2, font=font(small), fill=MUTED)


def _breakdown(d, items, x, y, bw, bottom, px):
    """Where it went: category and amount, biggest first, as many as fit."""
    f, fb = font(px(30)), font(px(30), True)
    d.text((x, y), "WHERE IT WENT", font=font(px(24), True), fill=MUTED)
    y += px(50)
    row = px(52)
    for label, amt in items:
        if y + row > bottom:
            break
        d.text((x, y), plain(label), font=f, fill=INK2)
        d.text((x + bw, y), f"€{amt:,.0f}", font=fb, fill=INK, anchor="ra")
        y += row
    if not items:
        d.text((x, y), "Nothing yet this month", font=f, fill=MUTED)


def render(page: dict[str, Any], w: int = 1072, h: int = 1448, battery: str | None = None,
           rotate: int = 0, now: datetime | None = None) -> bytes:
    """Portrait: buckets stacked. Landscape (rotate 90/270 with portrait w/h, or w > h): a
    two-column grid. A personal page puts its one block left and the breakdown right."""
    now = now or datetime.now(TZ)
    if rotate in (90, 270) and h > w:
        w, h = h, w
    landscape = w > h
    img = Image.new("L", (w, h), 255)
    d = ImageDraw.Draw(img)
    k = (h if landscape else w) / 1072          # scale off the panel's short side
    m = round(1072 * 0.067 * k)                 # side margin (72px on a PW4)

    def px(n: float) -> int:
        return max(1, round(n * k))

    top, bottom = _header_footer(d, page, w, h, m, px, battery, now)
    bs = [{**b, "label": plain(b["label"])} for b in page.get("buckets", [])]
    personal = bool(page.get("personal"))
    if not bs and not personal:
        d.text((w // 2, h // 2), "No budgets yet", font=font(px(40)), fill=MUTED, anchor="mm")
    elif personal and not bs:
        d.text((m, top + px(40)), f"No monthly cap set · spent €{page.get('spent', 0):,.0f} so far",
               font=font(px(36)), fill=MUTED)
        _breakdown(d, page.get("breakdown", []), m, top + px(130), w - 2 * m, bottom - px(20), px)
    elif landscape or personal:
        cols = 2 if (len(bs) > 1 or personal) else 1
        rows = 1 if personal else -(-len(bs) // cols)
        gap = px(60)
        bw = (w - 2 * m - gap * (cols - 1)) // cols
        row_h = (bottom - top) / rows
        scale = _fit_scale(bs, page, bw, row_h, px)
        for i, b in enumerate(bs):
            r, c = divmod(i, cols)
            x, y = m + c * (bw + gap), round(top + r * row_h)
            _bucket_block(d, b, page, x, y + _pad(row_h, px, scale), bw, px, scale)
            if r:
                d.line([x, y - px(12 * scale), x + bw, y - px(12 * scale)], fill=RULE, width=px(2))
        if personal:
            _breakdown(d, page.get("breakdown", []), m + bw + gap, top + px(30), bw, bottom - px(20), px)
        if cols == 2:
            cx = m + bw + gap // 2
            d.line([cx, top, cx, bottom - px(20)], fill=RULE, width=px(2))
    else:
        row_h = (bottom - top) / len(bs)
        scale = _fit_scale(bs, page, w - 2 * m, row_h, px)
        for i, b in enumerate(bs):
            y = round(top + i * row_h)
            _bucket_block(d, b, page, m, y + _pad(row_h, px, scale), w - 2 * m, px, scale)
            if i:
                d.line([m, y - px(12 * scale), w - m, y - px(12 * scale)], fill=RULE, width=px(2))

    if rotate in (90, 270):
        img = img.rotate(rotate, expand=True)   # back to the portrait framebuffer
    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()
