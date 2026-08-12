"""
FEC OpenFEC API (https://api.open.fec.gov). Official, free, no signup
required for light use — DEMO_KEY gets 1,000 requests/hour. For heavier use,
get your own free key at https://api.data.gov/signup/ and set FEC_API_KEY
as an environment variable (the GitHub Actions workflow already passes it
through if you add it as a repo secret).

We look candidates up by office/state/district/cycle rather than by name,
so races.json never needs a hardcoded candidate list — it just works for
whoever is actually running, including after primaries.
"""
import os
import requests

BASE_URL = "https://api.open.fec.gov/v1"
TIMEOUT = 20
API_KEY = os.environ.get("FEC_API_KEY", "DEMO_KEY")


def get_candidates(office_code, state_abbr, district=None, cycle=2026):
    """office_code: 'S' for Senate, 'H' for House."""
    params = {
        "api_key": API_KEY,
        "office": office_code,
        "state": state_abbr,
        "cycle": cycle,
        "per_page": 20,
    }
    if district:
        params["district"] = district
    resp = requests.get(f"{BASE_URL}/candidates/", params=params, timeout=TIMEOUT)
    if resp.status_code != 200:
        return []
    return resp.json().get("results", [])


def get_totals(candidate_id, cycle=2026):
    params = {"api_key": API_KEY, "cycle": cycle}
    resp = requests.get(
        f"{BASE_URL}/candidates/{candidate_id}/totals/", params=params, timeout=TIMEOUT
    )
    if resp.status_code != 200:
        return None
    results = resp.json().get("results", [])
    return results[0] if results else None


def fetch_race_fundraising(office_code, state_abbr, district=None, cycle=2026):
    """Returns a list of {name, party, receipts, cash_on_hand} per candidate."""
    candidates = get_candidates(office_code, state_abbr, district, cycle)
    out = []
    for cand in candidates:
        totals = get_totals(cand["candidate_id"], cycle=cycle)
        out.append({
            "name": cand.get("name"),
            "party": cand.get("party"),
            "receipts": totals.get("receipts") if totals else None,
            "cash_on_hand": totals.get("last_cash_on_hand_end_period") if totals else None,
        })
    return out
