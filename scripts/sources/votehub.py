"""
VoteHub polling API (https://votehub.com/polls/api/)
Free, open, no API key required. Licensed CC BY 4.0 — keep attributing VoteHub
as the source in anything built from this data.
"""
import datetime
import requests

BASE_URL = "https://api.votehub.com"
TIMEOUT = 20


def get_subjects():
    """Return the full list of {subject, poll_types} VoteHub currently tracks.
    Useful for double-checking that a race's `votehub_subject` in races.json
    still matches what VoteHub calls it."""
    resp = requests.get(f"{BASE_URL}/subjects", timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def get_polls(subject, poll_type, lookback_days=90):
    """Fetch polls for a subject/poll_type, filtered client-side to the
    lookback window (VoteHub's own filtering is applied too, but we don't
    rely on it exclusively since results have been inconsistent in testing)."""
    params = {"subject": subject, "poll_type": poll_type}
    resp = requests.get(f"{BASE_URL}/polls", params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    polls = resp.json()
    if isinstance(polls, dict):
        polls = polls.get("polls", [])

    cutoff = datetime.date.today() - datetime.timedelta(days=lookback_days)
    matched = []
    for poll in polls:
        poll_subject = (poll.get("subject") or "").strip().lower()
        if poll_subject != subject.strip().lower():
            continue  # belt-and-suspenders: the API's own filter isn't fully reliable
        try:
            end_date = datetime.date.fromisoformat(poll.get("end_date", ""))
        except ValueError:
            continue
        if end_date >= cutoff:
            matched.append(poll)
    matched.sort(key=lambda p: p["end_date"], reverse=True)
    return matched


def average_polls(polls, max_polls=10):
    """Simple (unweighted) average of the choices across the most recent
    `max_polls` polls. Good enough for a tracker; not a substitute for a
    real polling average methodology like Silver Bulletin's or 538's."""
    recent = polls[:max_polls]
    if not recent:
        return {}

    totals = {}
    counts = {}
    for poll in recent:
        for answer in poll.get("answers", []):
            choice = answer.get("choice")
            pct = answer.get("pct")
            if choice is None or pct is None:
                continue
            totals[choice] = totals.get(choice, 0) + pct
            counts[choice] = counts.get(choice, 0) + 1

    return {
        choice: round(totals[choice] / counts[choice], 1)
        for choice in totals
    }


def fetch_race_polling(subject, poll_type, lookback_days=90, max_polls=10):
    """High-level helper: returns (averages_dict, num_polls_used, most_recent_date)."""
    polls = get_polls(subject, poll_type, lookback_days=lookback_days)
    averages = average_polls(polls, max_polls=max_polls)
    most_recent = polls[0]["end_date"] if polls else None
    return averages, len(polls[:max_polls]), most_recent
