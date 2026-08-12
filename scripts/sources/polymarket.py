"""
Polymarket public Gamma API (https://gamma-api.polymarket.com).
Market discovery/metadata reads need no wallet or API key.

IMPORTANT: elections are structured as one grouped EVENT containing
multiple per-candidate binary yes/no MARKETS (Polymarket calls this a
"negRisk" or grouped event) -- each market's `outcomes`/`outcomePrices` are
just generically ["Yes","No"], which on their own don't say WHICH candidate
that yes/no question is about. The field that actually names the candidate
is `groupItemTitle` on the market object (confirmed against docs.polymarket
.com's current schema). An earlier version of this file only read
markets[0]'s outcomes directly, which is why the display just said "Yes"
with no candidate name attached.
"""
import json
import requests

BASE_URL = "https://gamma-api.polymarket.com"
TIMEOUT = 20
MAX_PAGES = 40
PAGE_SIZE = 100
MIN_MATCH_SCORE = 2  # same reasoning as kalshi.py -- one incidental word
                      # overlap with an unrelated event shouldn't count as a
                      # match


def fetch_all_open_events():
    """Paginate through open political events once per run."""
    events = []
    offset = 0
    for _ in range(MAX_PAGES):
        params = {"closed": "false", "limit": PAGE_SIZE, "offset": offset}
        resp = requests.get(f"{BASE_URL}/events", params=params, timeout=TIMEOUT)
        if resp.status_code != 200:
            break
        batch = resp.json()
        if not batch:
            break
        events.extend(batch)
        offset += PAGE_SIZE
        if len(batch) < PAGE_SIZE:
            break
    return events


def find_event(all_events, keywords):
    """Best keyword match against event titles/subtitles, or None if
    nothing clears the minimum match threshold."""
    best_event, best_score = None, 0
    for event in all_events:
        text = f"{event.get('title') or ''} {event.get('subtitle') or ''}".lower()
        score = sum(1 for kw in keywords if kw.lower() in text)
        if score > best_score:
            best_event, best_score = event, score
    if best_score < MIN_MATCH_SCORE:
        return None
    return best_event


def _yes_price_pct(market):
    """Pull the price for specifically the 'Yes' outcome out of a market's
    outcomes/outcomePrices JSON-string-encoded arrays."""
    try:
        outcomes = json.loads(market.get("outcomes") or "[]")
        prices = json.loads(market.get("outcomePrices") or "[]")
    except (json.JSONDecodeError, TypeError):
        return None
    for outcome, price in zip(outcomes, prices):
        if str(outcome).strip().lower() == "yes":
            try:
                return round(float(price) * 100, 1)
            except (TypeError, ValueError):
                return None
    return None


def event_to_odds(event):
    """Convert a matched event's markets into a per-candidate odds list.
    For a grouped election event, each market is one candidate's binary
    yes/no contract -- groupItemTitle names that candidate, and the price
    of the 'Yes' outcome is the market-implied probability they win. Falls
    back to the market's own question text if groupItemTitle isn't set
    (e.g. a simple non-grouped two-outcome market)."""
    if not event:
        return None
    markets = event.get("markets") or []
    if not markets:
        return None

    candidates = []
    for market in markets:
        label = market.get("groupItemTitle") or market.get("question") or "Unknown"
        candidates.append({"outcome": label, "probability_pct": _yes_price_pct(market)})

    candidates.sort(key=lambda c: (c["probability_pct"] is None, -(c["probability_pct"] or 0)))

    return {
        "event_title": event.get("title"),
        "slug": event.get("slug"),
        "outcomes": candidates,
        "url": f"https://polymarket.com/event/{event.get('slug', '')}",
    }
