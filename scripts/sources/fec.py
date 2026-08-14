"""
FEC OpenFEC API (https://api.open.fec.gov). Official, free, no signup
required for light use — DEMO_KEY gets 1,000 requests/hour. For heavier use,
get your own free key at https://api.data.gov/signup/ and set FEC_API_KEY
as an environment variable (the GitHub Actions workflow already passes it
through if you add it as a repo secret).

We look candidates up by office/state/district/cycle rather than by name,
so races.json never needs a hardcoded candidate list — it just works for
whoever is actually running, including after primaries.

NOTE: DEMO_KEY is a single key shared by EVERYONE who uses the OpenFEC API
without registering their own -- since it's shared globally across all
unregistered users, not just this project, its 1,000/hour limit can get
used up by other people entirely, independent of how often we run. If
fundraising keeps coming back empty, getting a free personal key (link
above) and adding it as the FEC_API_KEY repo secret removes that shared-
limit risk entirely.
"""
import os
import requests

BASE_URL = "https://api.open.fec.gov/v1"
TIMEOUT = 20
API_KEY = os.environ.get("FEC_API_KEY", "DEMO_KEY")


def log(msg):
    print(f"[fec] {msg}", flush=True)


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
        # Previously silently returned [] here with zero visibility into
        # why -- logging the actual status/response so a bad key, rate
        # limit, or bad parameter shows up in the Actions log instead of
        # just quietly producing empty fundraising data every time.
        log(f"WARNING: candidates lookup failed ({office_code}/{state_abbr}/{district}, "
            f"cycle={cycle}): HTTP {resp.status_code} -- {resp.text[:300]}")
        return []
    results = resp.json().get("results", [])
    if not results:
        log(f"No candidates found for {office_code}/{state_abbr}/{district}, cycle={cycle} "
            f"(request succeeded, but FEC has no matching registered candidates)")
    return results


def get_totals(candidate_id, cycle=2026):
    params = {"api_key": API_KEY, "cycle": cycle}
    resp = requests.get(
        f"{BASE_URL}/candidates/{candidate_id}/totals/", params=params, timeout=TIMEOUT
    )
    if resp.status_code != 200:
        log(f"WARNING: totals lookup failed for candidate {candidate_id}: "
            f"HTTP {resp.status_code} -- {resp.text[:300]}")
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
