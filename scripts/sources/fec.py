"""
FEC OpenFEC API (https://api.open.fec.gov). Official, free.

IMPORTANT (confirmed live): the `cycle` parameter on /candidates/ does NOT
restrict results to candidates who ran in that specific cycle -- it returns
every candidate who has EVER run for that office/state, going back decades
(e.g. an Ohio Senate query returned 20 candidates spanning the 1990s through
today). Each candidate object's own `election_years` list is what actually
says which specific cycles they were on the ballot for, so we filter on
that client-side instead of trusting the query parameter alone.

This matters a lot for rate limits too: DEMO_KEY's real limit is 40 calls/
hour (confirmed from FEC's own error message -- not 1,000/hour as commonly
quoted elsewhere). Without the election_years filter, a single race could
trigger a totals lookup for 20 irrelevant historical candidates instead of
the 2-4 who are actually running this cycle, burning through that limit
almost immediately. Filtering first cuts total API calls dramatically.

For heavier use, get your own free key at https://api.data.gov/signup/ and
set FEC_API_KEY as an environment variable (the GitHub Actions workflow
already passes it through if you add it as a repo secret) -- it's a wider
safety margin on top of the election_years fix, not a substitute for it.

We look candidates up by office/state/district/cycle rather than by name,
so races.json never needs a hardcoded candidate list -- it just works for
whoever is actually running, including after primaries.
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
        log(f"WARNING: candidates lookup failed ({office_code}/{state_abbr}/{district}, "
            f"cycle={cycle}): HTTP {resp.status_code} -- {resp.text[:300]}")
        return []

    results = resp.json().get("results", [])
    if not results:
        log(f"No candidates found for {office_code}/{state_abbr}/{district}, cycle={cycle} "
            f"(request succeeded, but FEC has no matching registered candidates)")
        return []

    # See module docstring -- `cycle` alone doesn't filter to this specific
    # cycle, so narrow client-side using each candidate's own election_years.
    active = [c for c in results if cycle in (c.get("election_years") or [])]
    if not active:
        log(f"WARNING: {len(results)} candidates found for {office_code}/{state_abbr}/"
            f"{district}, but none list {cycle} in election_years -- using all "
            f"{len(results)} unfiltered rather than returning nothing (double check "
            f"the election_years field is what's expected).")
        return results

    log(f"{office_code}/{state_abbr}/{district}: {len(results)} total candidates found, "
        f"narrowed to {len(active)} actually on the {cycle} ballot")
    return active


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
