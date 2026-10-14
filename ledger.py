"""Rebuild the two sheet tabs from all snapshots + digest logs.

- overall.csv: the top repos since tracking started (one row per repo).
- monthly.csv: the top repos of each month, newest month first.

Written for non-technical readers: plain-English headers, few columns, short descriptions.
Idempotent: always recomputed from data/, so it can run any number of times.
"""
import csv
import datetime as dt
import json
from pathlib import Path

from snapshot import DATA_DIR

ROOT = Path(__file__).parent
OVERALL_ROWS = 100
MONTHLY_ROWS = 25
DESC_LEN = 120
MAX_PER_OWNER = 2  # same rule as the email, so one account cannot flood a list


def short(text):
    text = " ".join((text or "").split())
    if not text:
        return "(no description)"
    return text if len(text) <= DESC_LEN else text[:DESC_LEN].rsplit(" ", 1)[0] + "…"


def load_snapshots():
    return [(f.stem, json.loads(f.read_text(encoding="utf-8"))) for f in sorted(DATA_DIR.glob("*.json"))]


def load_digests():
    return [(f.stem, json.loads(f.read_text(encoding="utf-8"))) for f in sorted((DATA_DIR / "digests").glob("*.json"))]


def gain(points, start, weekly, created_in_period):
    """Stars gained over snapshot points [(day, stars, stars_today)], from `start` stars.

    Repos created in the period started at 0. Summed daily "stars today" and the
    best weekly-digest gain are lower bounds when the repo was spotted late.
    """
    if created_in_period:
        start = 0
    return max(points[-1][1] - start, sum(p[2] for p in points), max(weekly, default=0))


def build(snapshots, digests):
    info, history = {}, {}
    for day, items in snapshots:
        for r in items:
            info.setdefault(r["name"], {}).update({k: v for k, v in r.items() if v})
            history.setdefault(r["name"], []).append((day, r["stars"], r.get("stars_today", 0)))

    weekly = {}  # name -> [(digest day, stars gained that week)]
    for day, items in digests:
        for r in items:
            weekly.setdefault(r["name"], []).append((day, r["gain"]))
            info.setdefault(r["name"], {}).update({k: v for k, v in r.items() if v and k != "gain"})
            # Repos featured from weekly trending may never appear in a daily snapshot.
            history.setdefault(r["name"], []).append((day, r["stars"], 0))
    for h in history.values():
        h.sort()
    return info, history, weekly


def cap_owners(rows, limit):
    seen, out = {}, []
    for r in rows:
        seen[r["Made by"]] = seen.get(r["Made by"], 0) + 1
        if seen[r["Made by"]] <= MAX_PER_OWNER:
            out.append(r)
    return out[:limit]


def row(name, r):
    owner, project = name.split("/", 1)
    return {
        "Project": project,
        "Made by": owner,
        "What it does": short(r.get("description")),
        "Language": r.get("language") or "—",
    }


def overall(info, history, weekly):
    rows = []
    for name, h in history.items():
        r = info[name]
        w = weekly.get(name, [])
        g = gain(h, h[0][1], [x[1] for x in w], r.get("created_at", "") >= h[0][0])
        rows.append({
            **row(name, r),
            "Total stars": h[-1][1],
            "Stars gained since first spotted": g,
            "Times in weekly email": len(w),
            "First spotted": h[0][0],
            "Link": f"https://github.com/{name}",
        })
    rows.sort(key=lambda x: (x["Times in weekly email"], x["Stars gained since first spotted"]), reverse=True)
    return [{"Rank": i, **x} for i, x in enumerate(cap_owners(rows, OVERALL_ROWS), 1)]


def monthly(info, history, weekly):
    months = sorted({day[:7] for h in history.values() for day, _, _ in h}, reverse=True)
    out = []
    for month in months:
        rows = []
        for name, h in history.items():
            in_month = [x for x in h if x[0][:7] == month]
            if not in_month:
                continue
            before = [x for x in h if x[0][:7] < month]
            start = before[-1][1] if before else in_month[0][1]
            w = [g for day, g in weekly.get(name, []) if day[:7] == month]
            g = gain(in_month, start, w, info[name].get("created_at", "")[:7] == month)
            if g > 0:
                rows.append({**row(name, info[name]), "Stars gained this month": g, "Total stars": in_month[-1][1],
                             "Link": f"https://github.com/{name}"})
        rows.sort(key=lambda x: x["Stars gained this month"], reverse=True)
        label = dt.date.fromisoformat(month + "-01").strftime("%B %Y")
        out += [{"Month": label, "Rank": i, **x} for i, x in enumerate(cap_owners(rows, MONTHLY_ROWS), 1)]
    return out


def write(path, rows):
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]) if rows else ["Rank"])
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows to {path.name}")


def main():
    info, history, weekly = build(load_snapshots(), load_digests())
    write(ROOT / "overall.csv", overall(info, history, weekly))
    write(ROOT / "monthly.csv", monthly(info, history, weekly))


if __name__ == "__main__":
    main()
