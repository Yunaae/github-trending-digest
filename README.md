# GitHub Trending Digest

Weekly email of the GitHub repos gaining stars fastest. Free: runs on GitHub Actions, no paid APIs.

- **Daily (06:00 UTC)** `snapshot.py` records github.com/trending + the top 100 repos created in the last 30 days, with star counts, into `data/YYYY-MM-DD.json` (committed by the workflow).
- **Mondays (07:00 UTC)** `digest.py` compares the last 7 days of snapshots, ranks by stars gained, and emails:
  - 🔥 Most stars gained (top 15)
  - 🚀 New & rising fast: repos < 30 days old (top 10)
  - Max 2 repos per owner, to stop one account flooding the list.

- **Sheet data** `ledger.py` rebuilds two CSVs after each run, written for non-technical readers:
  - `overall.csv`: top 100 since tracking started (ranked by times in the weekly email, then stars gained)
  - `monthly.csv`: top 25 per month by stars gained that month, newest month first
  - Weekly email picks are logged in `data/digests/`.
- **Live Google Sheet** (refreshes about hourly; needs this repo to be public), cell A1 of each tab:
  - `=IMPORTDATA("https://raw.githubusercontent.com/Yunaae/github-trending-digest/main/overall.csv")`
  - `=IMPORTDATA("https://raw.githubusercontent.com/Yunaae/github-trending-digest/main/monthly.csv")`

Descriptions are the repos' own GitHub descriptions (v1). Next step could be README summaries via a Claude Code routine on the Max plan.

## Setup
1. Push this folder to a GitHub repo.
2. Add repo secrets (Settings → Secrets → Actions):
   | Secret | Example |
   |---|---|
   | `SMTP_USER` | you@gmail.com |
   | `SMTP_PASSWORD` | Gmail **app password** (Google account → Security → App passwords) |
   | `EMAIL_TO` | where to send (comma-separate several) |
   | `SMTP_HOST` / `SMTP_PORT` | optional, default `smtp.gmail.com` / `587` |
3. Actions tab → run **Daily snapshot** then **Weekly digest** manually to test.

## Local
```
pip install -r requirements.txt
python snapshot.py
python digest.py --dry-run   # writes digest.html
```

## Known limits
- Logged-out github.com/trending shows only ~10 repos; the Search API fills the rest.
- First week: gains come from GitHub's own weekly/daily trending numbers until 7 days of snapshots exist.
