import io
import json
from pathlib import Path

from PIL import Image

from budget_box import render

FIX = Path(__file__).parent / "fixtures"
PAGE = {"month_short": "Oct", "next_month_short": "Nov"}


def bucket(**kw):
    b = dict(label="Groceries", cap=400.0, spent=100.0, left=300.0, over=False, is_current=True,
             day=15, dim=31, w_spent=40.0, w_allow=100.0, w_left=60.0, w_days_left=4, w_days=7,
             w_end="2026-10-18")
    b.update(kw)
    return b


def test_left_this_week_spreads_over_remaining_days():
    num, phrase, sub, bad, foot1, foot2 = render.lines(bucket(), PAGE)
    assert (num, phrase, bad) == ("€60", "left this week", False)
    assert sub == "Spend up to €15 a day until Sunday"
    assert foot1 == "€100 spent of €400 in Oct" and foot2 == "€300 left for the month"


def test_last_day_of_week_says_today():
    assert render.lines(bucket(w_days_left=1), PAGE)[2] == "Spend up to €60 today"


def test_week_blown():
    num, phrase, sub, bad, *_ = render.lines(bucket(w_spent=130.0, w_left=-30.0), PAGE)
    assert (num, phrase, sub, bad) == ("€30", "over budget this week", "Budget resets Monday", True)


def test_partial_last_week_resets_next_month():
    # a week that ends mid-week (month end on a Saturday) resets with the new month
    sub = render.lines(bucket(w_left=-5.0, w_end="2026-10-31"), PAGE)[2]
    assert sub == "Budget resets Nov"


def test_month_blown():
    num, phrase, sub, bad, _, foot2 = render.lines(bucket(spent=450.0, left=-50.0, over=True), PAGE)
    assert (num, phrase, sub, bad) == ("€50", "over budget", "Oct's budget is all spent", True)
    assert foot2 == "€50 past the month's budget"


def test_plain_strips_emoji():
    assert render.plain("🥕 Groceries") == "Groceries"
    assert render.plain("✈️ Café ñ €") == "Café ñ €"


def _size(png: bytes):
    return Image.open(io.BytesIO(png)).size


def test_renders_every_fixture_in_every_orientation():
    for f in FIX.glob("*.json"):
        page = json.loads(f.read_text())
        assert _size(render.render(page, 1072, 1448)) == (1072, 1448)          # portrait
        assert _size(render.render(page, 1072, 1448, rotate=90)) == (1072, 1448)  # landscape, rotated back
        assert _size(render.render(page, 1448, 1072)) == (1448, 1072)          # landscape


def test_empty_page_renders():
    page = {"title": "Oct", "month_short": "Oct", "next_month_short": "Nov", "day": 1,
            "days_in_month": 31, "buckets": [], "nudges": []}
    assert _size(render.render(page)) == (1072, 1448)
