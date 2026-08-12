"""
Polymarket public Gamma API (https://gamma-api.polymarket.com).
Market discovery/metadata reads need no wallet or API key. Each market has
`outcomes` (JSON string list, e.g. '["Yes","No"]' or candidate names) and
`outcomePrices` (parallel list of price strings, 0-1, which are the implied
probabilities).

Same caveat as kalshi.py: no stable per-race ID scheme, so we match on title
keywords against the open events list fetched once per run.
"""
import json
import requests

BASE_URL = "https://gamma-api.polymarket.com"
TIMEOUT = 20
MAX_PAGES = 40
PAGE_SIZE = 100


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


MIN_MATCH_SCORE = 2  # same reasoning as kalshi.py -- one incidental word
                      # overlap with an unrelated event shouldn't count as a
                      # match


def find_event(all_events, keywords):
    """Best keyword match against event titles, or None if nothing clears
    the minimum match threshold."""
    best_event, best_score = None, 0
    for event in all_events:
        title = (event.get("title") or "").lower()
        score = sum(1 for kw in keywords if kw.lower() in title)
        if score > best_score:
            best_event, best_score = event, score
    if best_score < MIN_MATCH_SCORE:
        return None
    return best_event


def event_to_odds(event):
    """Pull outcome/price pairs out of the first market on a matched event."""
    if not event:
        return None
    markets = event.get("markets") or []
    if not markets:
        return None
    market = markets[0]

    try:
        outcomes = json.loads(market.get("outcomes", "[]"))
        prices = json.loads(market.get("outcomePrices", "[]"))
    except (json.JSONDecodeError, TypeError):
        outcomes, prices = [], []

    outcome_odds = [
        {"outcome": o, "probability_pct": round(float(p) * 100, 1)}
        for o, p in zip(outcomes, prices)
    ]
    return {
        "event_title": event.get("title"),
        "slug": event.get("slug"),
        "outcomes": outcome_odds,
        "volume": market.get("volume"),
        "url": f"https://polymarket.com/event/{event.get('slug', '')}",
    }
