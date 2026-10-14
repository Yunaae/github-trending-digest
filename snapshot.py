"""Daily snapshot: record trending + fast-growing new repos and their star counts.

Writes data/YYYY-MM-DD.json. Run once a day; digest.py compares snapshots.
"""
import datetime as dt
import json
import os
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

DATA_DIR = Path(__file__).parent / "data"
UA = {"User-Agent": "github-trending-digest"}


def to_int(text):
    m = re.search(r"[\d,]+", text or "")
    return int(m.group().replace(",", "")) if m else 0


def scrape_trending(since="daily"):
    """Parse github.com/trending. There is no official API for it."""
    html = requests.get(f"https://github.com/trending?since={since}", headers=UA, timeout=30).text
    repos = []
    for row in BeautifulSoup(html, "html.parser").select("article.Box-row"):
        link = row.select_one("h2 a")
        if not link:
            continue
        name = link["href"].strip("/")
        desc = row.select_one("p")
        lang = row.select_one('[itemprop="programmingLanguage"]')
        stars = row.select_one('a[href$="/stargazers"]')
        gained = row.select_one("span.float-sm-right")
        repos.append({
            "name": name,
            "description": desc.get_text(strip=True) if desc else "",
            "language": lang.get_text(strip=True) if lang else "",
            "stars": to_int(stars.get_text() if stars else ""),
            "stars_period": to_int(gained.get_text() if gained else ""),
        })
    return repos


def search_new_repos(days=30, min_stars=100):
    """Repos created recently, sorted by stars: catches risers trending misses."""
    since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    headers = {**UA, "Accept": "application/vnd.github+json"}
    if os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    r = requests.get(
        "https://api.github.com/search/repositories",
        params={"q": f"created:>{since} stars:>{min_stars}", "sort": "stars", "order": "desc", "per_page": 100},
        headers=headers,
        timeout=30,
    )
    r.raise_for_status()
    return [{
        "name": it["full_name"],
        "description": it["description"] or "",
        "language": it["language"] or "",
        "stars": it["stargazers_count"],
        "created_at": it["created_at"][:10],
    } for it in r.json()["items"]]


def main():
    repos = {}
    for r in search_new_repos():
        repos[r["name"]] = r
    for r in scrape_trending("daily"):
        repos.setdefault(r["name"], {}).update(r)
        repos[r["name"]]["stars_today"] = repos[r["name"]].pop("stars_period")
        repos[r["name"]]["trending"] = True

    DATA_DIR.mkdir(exist_ok=True)
    out = DATA_DIR / f"{dt.date.today().isoformat()}.json"
    out.write_text(json.dumps(sorted(repos.values(), key=lambda r: r["name"]), indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {len(repos)} repos to {out}")


if __name__ == "__main__":
    main()
