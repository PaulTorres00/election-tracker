# Race Desk — 2026 Midterms Tracker

A small dashboard that tracks polling averages, prediction-market odds, and
fundraising for a configurable list of 2026 Senate and House races, hosted
entirely on GitHub (no server, no hosting bill).

**How it works:** a scheduled GitHub Action runs a Python script every few
hours that pulls fresh data from four free, public APIs and writes it to a
JSON file. GitHub Pages serves a static dashboard that reads that JSON.
Nothing to deploy, nothing to keep running — GitHub does both jobs for you.

## Data sources

| Source | What it provides | Auth needed |
|---|---|---|
| [VoteHub](https://votehub.com/polls/api/) | Per-race polling averages | None (free, open API) |
| [Kalshi](https://kalshi.com) | Prediction-market odds | None for reading public market data |
| [Polymarket](https://polymarket.com) | Prediction-market odds | None for reading public event data |
| [FEC (OpenFEC)](https://api.open.fec.gov) | Campaign fundraising totals | None required (shared `DEMO_KEY`, 1,000 req/hr) |

Candidate names are **not** hardcoded anywhere — the FEC lookup is by
office/state/district, and Kalshi/Polymarket matching is by keyword — so the
config doesn't go stale when candidates change after a primary.

**A heads-up on the odds data:** election-related prediction markets are a
fast-moving legal area right now — several states restrict or are actively
litigating against Kalshi/Polymarket specifically over election contracts,
and there's a federal bill pending that would ban them outright. None of
that affects displaying public odds the way a news site would, but it means
market availability could change with little notice. That's part of why the
Kalshi/Polymarket integrations here fail gracefully (a card just shows "no
matching market found") rather than assuming the source will always be there.

## One-time setup

1. **Create a new GitHub repository** and push this folder's contents to it.
   A public repo is the simplest path — GitHub Pages on a free personal
   account only publishes from public repos. (Everything this tool displays
   is already-public polling/odds data, so that's a reasonable trade for most
   teams. If you need the repo itself private, GitHub Pro supports Pages
   from a private personal repo, and GitHub Team/Enterprise for orgs — note
   the *site* is still generally publicly reachable by URL even then, unless
   you're on Enterprise Cloud with Pages access control.)

2. **Enable GitHub Pages:** Settings → Pages → Source: "Deploy from a
   branch" → Branch: `main`, folder `/docs`. Save. Your dashboard will be
   live at `https://<your-username>.github.io/<repo-name>/` within a minute
   or two.

3. **Let the workflow commit data back:** Settings → Actions → General →
   Workflow permissions → select "Read and write permissions". Without this,
   the scheduled job can fetch data but can't save it.

4. **(Optional) Add your own FEC API key:** the shared `DEMO_KEY` works fine
   at this project's scale, but if you hit rate limits, grab a free key at
   <https://api.data.gov/signup/> and add it as a repository secret named
   `FEC_API_KEY` (Settings → Secrets and variables → Actions → New repository
   secret).

5. **Run it once:** Actions tab → "Update election data" → Run workflow.
   Refresh the Pages site after it finishes (~1 minute) and the placeholder
   data will be replaced with a live snapshot.

## Editing the race list

Everything lives in `config/races.json`. To add a race, copy an existing
entry and change the fields — no code changes needed:

```json
{
  "id": "sen-tx-2026",
  "chamber": "senate",
  "office_code": "S",
  "state": "Texas",
  "state_abbr": "TX",
  "district": null,
  "label": "Texas — U.S. Senate",
  "votehub_subject": "2026 Texas",
  "votehub_poll_type": "us-senator",
  "kalshi_keywords": ["Texas", "Senate"],
  "polymarket_keywords": ["Texas Senate"]
}
```

To find the exact `votehub_subject` string for a race, check
`https://api.votehub.com/subjects` — it lists every subject VoteHub
currently tracks polls for (e.g. `"2026 PA-08"`, `"2026 Michigan"`).

For House races, `chamber` is `"house"`, `office_code` is `"H"`, and
`district` is the two-digit district number as a string (e.g. `"08"`).

## Running locally

```bash
pip install -r requirements.txt
python scripts/fetch_data.py
```

Then serve the `docs/` folder over HTTP (not by opening `index.html`
directly — browsers block `fetch()` on `file://` URLs):

```bash
cd docs && python3 -m http.server 8000
```

Visit `http://localhost:8000`.

## Project layout

```
config/races.json          — the list of races to track (edit this to customize)
scripts/fetch_data.py      — orchestrator: pulls all sources, writes docs/data/
scripts/sources/           — one small client module per data source
docs/                       — the GitHub Pages site (static HTML/CSS/JS, no build step)
docs/data/latest.json      — current snapshot (overwritten each run)
docs/data/history/*.json   — per-race history for the trend sparklines
.github/workflows/         — the scheduled fetch job
```

## Known limitations, honestly

- **Kalshi/Polymarket matching is keyword-based**, not a stable race-ID
  lookup, since neither platform exposes one. Spot-check the matched market
  link on each card occasionally, especially right after adding a new race.
- **VoteHub's per-race API is in beta** per their own docs — expect some
  rough edges, and expect polling coverage to be thin for lower-profile
  House races early in the cycle.
- **The polling average is a simple mean of the most recent 10 polls**, not
  a real methodology like Silver Bulletin's or 538's (pollster ratings,
  recency weighting, house-effect adjustment, etc.). Treat it as a rough
  signal, not a forecast.
- This is aggregating already-public data for internal reference — it's
  not a wagering platform and doesn't place any bets.
