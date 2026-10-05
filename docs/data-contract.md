# Data contract

budget-box never sees a database. It asks a **source** for pages and for a change signal. With
`SOURCE=http`, the source is any service that implements these three endpoints under
`SOURCE_URL`, authenticated with `Authorization: Bearer $SOURCE_TOKEN`.

| Endpoint | Returns |
|---|---|
| `GET /views` | Page ids to cycle through, one per line, as `text/plain`. The first one is the default. |
| `GET /data?view=<id>` | One page as JSON (below). Header `X-Data-Version` (or `X-Ledger-Version`): the current change counter. `404` for an unknown id. |
| `GET /wait?v=<n>&timeout=<s>` | `{"version": <int>, "changed": <bool>}`. Answers at once if the counter is not `n`; otherwise as soon as it moves, or after `timeout` seconds with `changed: false`. |

## A page

```json
{
  "title": "Oct",
  "month": "2026-10",
  "month_short": "Oct",
  "next_month_short": "Nov",
  "day": 15,
  "days_in_month": 31,
  "buckets": [
    {
      "label": "Eating out",
      "cap": 400.0, "spent": 320.0, "left": 80.0, "over": false,
      "is_current": true, "day": 15, "dim": 31,
      "w_allow": 78.0, "w_spent": 56.0, "w_left": 22.0,
      "w_days": 7, "w_days_left": 4, "w_end": "2026-10-18"
    }
  ],
  "nudges": [
    {"text": "Sam: 2 transactions waiting to be sorted", "urgent": true},
    {"text": "Alex: last added expenses 3 days ago", "urgent": true}
  ]
}
```

- **Month figures:** `cap`, `spent`, and `left` (cap minus spent, negative when `over`).
- **Week figures:** `w_allow` is this week's budget. The reference source computes it as what was
  left of the cap at the start of the week, spread evenly over the days to month end, times the
  week's days. `w_spent` is spending since Monday and `w_left` is `w_allow - w_spent`.
- **Week position:** `w_days` is the length of this week, which is 7 except at the month's edges.
  `w_days_left` counts today through `w_end`, the last day of the week.
- **`is_current`** is false for a past month. The block then shows the month total only.
- **`nudges`** are up to two footer sentences. The source decides the wording, which is where
  people's names belong. `urgent` makes a nudge bold.
- **Labels** may carry emoji. The renderer strips them, since the fonts have none.

A **personal** page adds `"personal": true`, `"spent"`, `"cap"` and
`"breakdown": [["Groceries", 376.0], ...]`, sorted biggest first. Its `buckets` holds one block
for the person's whole spending, or is empty when no cap is set.

`tests/fixtures/` has a complete example of each. With `SOURCE=demo`, those files are the pages.
