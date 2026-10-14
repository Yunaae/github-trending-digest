"""Rebuild repos.csv: one row per repo ever seen, from all snapshots + digest logs.

Idempotent: always recomputed from data/, so it can run any number of times.
"""
import csv
import json
from pathlib import Path

from snapshot import DATA_DIR

OUT = Path(__file__).parent / "repos.csv"
COLUMNS = [
    "repo", "url", "description", "language", "stars_now", "first_seen", "last_seen",
    "days_trending", "weeks_in_digest", "best_week_gain", "gained_since_first_seen", "created_at",
]


def main():
    repos = {}
    for f in sorted(DATA_DIR.glob("*.json")):
        day = f.stem
        for r in json.loads(f.read_text(encoding="utf-8")):
            cur = repos.setdefault(r["name"], {
                "repo": r["name"], "url": f"https://github.com/{r['name']}", "first_seen": day,
                "first_stars": r["stars"], "days_trending": 0, "weeks_in_digest": 0, "best_week_gain": 0,
            })
            cur.update({k: v for k, v in r.items() if k in ("description", "language", "created_at") and v})
            cur["stars_now"] = r["stars"]
            cur["last_seen"] = day
            cur["days_trending"] += bool(r.get("trending"))

    for f in sorted((DATA_DIR / "digests").glob("*.json")):
        for r in json.loads(f.read_text(encoding="utf-8")):
            # Weekly-trending repos can be featured without ever appearing in a daily snapshot.
            cur = repos.setdefault(r["name"], {
                "repo": r["name"], "url": f"https://github.com/{r['name']}", "first_seen": f.stem,
                "last_seen": f.stem, "first_stars": r["stars"] - r["gain"], "stars_now": r["stars"],
                "days_trending": 0, "weeks_in_digest": 0, "best_week_gain": 0,
                **{k: r[k] for k in ("description", "language", "created_at") if r.get(k)},
            })
            cur["weeks_in_digest"] += 1
            cur["best_week_gain"] = max(cur["best_week_gain"], r["gain"])

    for r in repos.values():
        r["gained_since_first_seen"] = r["stars_now"] - r["first_stars"]

    rows = sorted(repos.values(), key=lambda r: (r["weeks_in_digest"], r["gained_since_first_seen"]), reverse=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} repos to {OUT.name}")


if __name__ == "__main__":
    main()
