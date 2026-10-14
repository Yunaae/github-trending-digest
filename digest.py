"""Weekly digest: rank repos by stars gained over the last 7 days and email it.

Usage:
  python digest.py            # build + send (needs SMTP_* and EMAIL_TO env vars)
  python digest.py --dry-run  # build only, writes digest.html
"""
import datetime as dt
import html
import json
import os
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from snapshot import DATA_DIR, scrape_trending

TOP_GAINERS = 15
TOP_RISERS = 10
NEW_REPO_DAYS = 30
MAX_PER_OWNER = 2


def load_week():
    cutoff = dt.date.today() - dt.timedelta(days=8)
    snaps = []
    for f in sorted(DATA_DIR.glob("*.json")):
        day = dt.date.fromisoformat(f.stem)
        if day >= cutoff:
            snaps.append((day, json.loads(f.read_text(encoding="utf-8"))))
    return snaps


def compute(snaps, weekly_trending):
    """Merge snapshots into one record per repo with a weekly star gain."""
    repos = {}
    for day, items in snaps:
        for r in items:
            cur = repos.setdefault(r["name"], {"first_stars": r["stars"], "days_trending": 0, "trending_gain": 0})
            cur.update({k: v for k, v in r.items() if v not in ("", None)})
            cur["days_trending"] += bool(r.get("trending"))
            cur["trending_gain"] += r.get("stars_today", 0)
    for r in repos.values():
        # Summed daily "stars today" is a lower bound when we lack an early snapshot.
        r["gain"] = max(r["stars"] - r["first_stars"], r["trending_gain"])

    # github.com/trending?since=weekly gives "stars this week" directly,
    # so the digest is useful even before a full week of snapshots exists.
    for r in weekly_trending:
        cur = repos.setdefault(r["name"], {"days_trending": 0, "gain": 0})
        cur.update({k: v for k, v in r.items() if v not in ("", None) and k != "stars_period"})
        cur["gain"] = max(cur["gain"], r["stars_period"])

    # A repo created during the window started at 0 stars.
    for r in repos.values():
        if r.get("created_at") and dt.date.fromisoformat(r["created_at"]) >= dt.date.today() - dt.timedelta(days=7):
            r["gain"] = max(r["gain"], r["stars"])
    return [r for r in repos.values() if r["gain"] > 0]


def top(repos, n, owners):
    """Best n by gain, with at most MAX_PER_OWNER repos per account across the email."""
    picked = []
    for r in sorted(repos, key=lambda r: r["gain"], reverse=True):
        owner = r["name"].split("/")[0]
        if owners.get(owner, 0) < MAX_PER_OWNER:
            owners[owner] = owners.get(owner, 0) + 1
            picked.append(r)
            if len(picked) == n:
                break
    return picked


def rank(repos):
    owners = {}
    gainers = top(repos, TOP_GAINERS, owners)
    taken = {r["name"] for r in gainers}
    new_cutoff = dt.date.today() - dt.timedelta(days=NEW_REPO_DAYS)
    risers = [
        r for r in repos
        if r["name"] not in taken and r.get("created_at") and dt.date.fromisoformat(r["created_at"]) >= new_cutoff
    ]
    return gainers, top(risers, TOP_RISERS, owners)


def card(i, r):
    meta = [f"⭐ {r['stars']:,}", f"<b style='color:#1a7f37'>+{r['gain']:,} this week</b>"]
    if r.get("language"):
        meta.append(html.escape(r["language"]))
    if r.get("created_at"):
        meta.append(f"created {r['created_at']}")
    return f"""
<tr><td style="padding:12px 0;border-bottom:1px solid #eee">
  <div style="font-size:16px"><b>{i}.</b> <a href="https://github.com/{r['name']}" style="color:#0969da;text-decoration:none"><b>{html.escape(r['name'])}</b></a></div>
  <div style="color:#333;margin:4px 0">{html.escape(r.get('description') or 'No description.')}</div>
  <div style="color:#666;font-size:13px">{' · '.join(meta)}</div>
</td></tr>"""


def section(title, subtitle, items):
    if not items:
        return ""
    rows = "".join(card(i, r) for i, r in enumerate(items, 1))
    return f"""<h2 style="margin:28px 0 4px">{title}</h2>
<div style="color:#666;font-size:13px">{subtitle}</div>
<table width="100%" cellspacing="0" cellpadding="0">{rows}</table>"""


def build_html(gainers, risers, n_snapshots):
    today = dt.date.today()
    week = f"{(today - dt.timedelta(days=7)):%d %b} – {today:%d %b %Y}"
    return f"""<html><body style="font-family:-apple-system,Segoe UI,Arial,sans-serif;max-width:680px;margin:auto;padding:16px;color:#111">
<h1 style="margin-bottom:0">GitHub weekly trends</h1>
<div style="color:#666">{week} · based on {n_snapshots} daily snapshots</div>
{section("🔥 Most stars gained", "Repos that gained the most stars this week.", gainers)}
{section("🚀 New & rising fast", f"Repos created in the last {NEW_REPO_DAYS} days that are taking off.", risers)}
</body></html>"""


def send(subject, body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = os.environ["SMTP_USER"]
    msg["To"] = os.environ["EMAIL_TO"]
    msg.attach(MIMEText(body, "html", "utf-8"))
    with smtplib.SMTP(os.getenv("SMTP_HOST", "smtp.gmail.com"), int(os.getenv("SMTP_PORT", "587"))) as s:
        s.starttls()
        s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        s.sendmail(msg["From"], msg["To"].split(","), msg.as_string())


def main():
    snaps = load_week()
    gainers, risers = rank(compute(snaps, scrape_trending("weekly")))
    body = build_html(gainers, risers, len(snaps))
    if "--dry-run" in sys.argv:
        Path("digest.html").write_text(body, encoding="utf-8")
        print(f"Wrote digest.html ({len(gainers)} gainers, {len(risers)} risers)")
        return
    send(f"GitHub weekly trends: {dt.date.today():%d %b %Y}", body)
    print("Digest sent")


if __name__ == "__main__":
    main()
