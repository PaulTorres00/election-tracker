"""
Kalshi public market data (https://docs.kalshi.com).
Reading event/market data needs no API key.

IMPORTANT: Kalshi's `title`/`subtitle` fields at the MARKET level are
deprecated in the current API (confirmed against docs.kalshi.com's current
OpenAPI schema) and come back empty. An earlier version of this file read
`market["title"]` to match races and to display the result -- which is why
matching silently failed for every race. The fields that are actually
populated now:
  - Event.title / Event.sub_title   -- use these to find the right race
  - Market.yes_sub_title             -- names WHICH CANDIDATE this specific
                                         yes/no market is about
  - Market.yes_bid_dollars           -- price as a decimal-dollar string
                                         (e.g. "0.5600" = 56%), not cents

Kalshi structures an election as one EVENT containing multiple per-candidate
binary yes/no MARKETS (one market per candidate, each asking "will this
specific person win?"), fetched here in one call via with_nested_markets.

See matching.py for the keyword-matching logic shared with polymarket.py.
"""
import requests
from . import matching

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
TIMEOUT = 20
MAX_PAGES = 40   # safety cap so a pagination bug can't loop forever
PAGE_SIZE = 200


def fetch_all_open_events():
    """Paginate through every open event once per run, with each event's
    nested markets included so we get every candidate's yes_sub_title and
    price in the same call rather than a separate request per event."""
    events = []
    cursor = None
    for _ in range(MAX_PAGES):
        params = {
            "limit": PAGE_SIZE,
            "status": "open",
            "with_nested_markets": "true",
        }
        if cursor:
            params["cursor"] = cursor
        resp = requests.get(f"{BASE_URL}/events", params=params, timeout=TIMEOUT)
        if resp.status_code != 200:
            break
        data = resp.json()
        batch = data.get("events", [])
        events.extend(batch)
        cursor = data.get("cursor")
        if not cursor or not batch:
            break
    return events


def find_event(all_events, keywords):
    """Return the open event that best matches `keywords` (see matching.py
    for how), or None if nothing qualifies."""
    return matching.find_best_event(
        all_events,
        keywords,
        text_fn=lambda e: f"{e.get('title') or ''} {e.get('sub_title') or ''}",
    )


def event_to_odds(event, exclude_outcomes=None, manual_url=None):
    """Convert a matched event's nested markets into a per-candidate odds
    list. Each market under an election event is one candidate's binary
    yes/no contract: yes_sub_title names the candidate, yes_bid_dollars is
    the market-implied probability they win.

    exclude_outcomes: optional list of outcome labels to drop -- useful for
    a top-two-primary state (California, Washington) where the market may
    still list an old "Republican Party"/"Democratic Party" contract from
    before the primary result was known, even though the actual November
    matchup turned out to be same-party and that outcome is now impossible.

    manual_url: optional verified link (set per-race via races.json's
    "kalshi_url") to use instead of the generic Midterms Hub fallback --
    Kalshi's real per-market URL structure isn't reliably derivable from the
    API fields alone, so a manually-confirmed link is more trustworthy than
    a guessed pattern.
    """
    if not event:
        return None
    markets = event.get("markets") or []
    if not markets:
        return None

    exclude_set = {o.strip().lower() for o in (exclude_outcomes or [])}

    candidates = []
    for market in markets:
        label = market.get("yes_sub_title") or market.get("ticker") or "Unknown"
        if label.strip().lower() in exclude_set:
            continue
        price_str = market.get("yes_bid_dollars")
        try:
            pct = round(float(price_str) * 100, 1) if price_str else None
        except (TypeError, ValueError):
            pct = None
        candidates.append({"outcome": label, "probability_pct": pct})

    candidates.sort(key=lambda c: (c["probability_pct"] is None, -(c["probability_pct"] or 0)))

    return {
        "event_title": event.get("title"),
        "outcomes": candidates,
        "url": manual_url or "https://kalshi.com/elections/midterms",
    }
