"""
Kalshi public market data (https://api.elections.kalshi.com/trade-api/v2).
Reading market prices needs no API key. Prices are in cents (1-99) and map
directly to an implied probability, e.g. yes_bid=63 means the market implies
a 63% chance of "yes".

NOTE ON SCOPE: Kalshi doesn't expose a stable per-race ticker scheme we can
hardcode, so this fetches the open-markets list once and matches races by
keyword against the market title. That's a heuristic, not a guarantee — spot
check matches against https://kalshi.com/politics occasionally, especially
right after we add a new race to config/races.json.
"""
import requests

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
TIMEOUT = 20
MAX_PAGES = 40   # safety cap so a pagination bug can't loop forever
PAGE_SIZE = 200


def fetch_all_open_markets():
    """Paginate through every open market once. Cached by the caller for the
    life of a single script run so we don't re-fetch per race."""
    markets = []
    cursor = None
    for _ in range(MAX_PAGES):
        params = {"limit": PAGE_SIZE, "status": "open"}
        if cursor:
            params["cursor"] = cursor
        resp = requests.get(f"{BASE_URL}/markets", params=params, timeout=TIMEOUT)
        if resp.status_code != 200:
            break
        data = resp.json()
        batch = data.get("markets", [])
        markets.extend(batch)
        cursor = data.get("cursor")
        if not cursor or not batch:
            break
    return markets


MIN_MATCH_SCORE = 2  # require at least 2 keyword hits, not just 1 incidental
                      # word overlap -- otherwise a generic word shared with
                      # an unrelated market (e.g. a sports market whose title
                      # happens to mention a team city that overlaps with a
                      # race's state name) gets accepted as "the" match


def find_market(all_markets, keywords):
    """Return the open market whose title matches the most keywords
    (case-insensitive substring match), or None if nothing clears the
    minimum match threshold."""
    best_market, best_score = None, 0
    for market in all_markets:
        title = (market.get("title") or "").lower()
        score = sum(1 for kw in keywords if kw.lower() in title)
        if score > best_score:
            best_market, best_score = market, score
    if best_score < MIN_MATCH_SCORE:
        return None
    return best_market


def market_to_odds(market):
    """Convert a Kalshi market object into a simple odds dict."""
    if not market:
        return None
    yes_bid = market.get("yes_bid")
    return {
        "ticker": market.get("ticker"),
        "title": market.get("title"),
        "yes_probability_pct": yes_bid,   # cents == implied % for "yes"
        "volume": market.get("volume"),
        "url": f"https://kalshi.com/markets/{market.get('ticker', '').split('-')[0].lower()}",
    }
