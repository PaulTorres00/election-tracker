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


def average_polls(polls, max_polls=10, exclude_choices=None):
    """Average the choices across the most recent polls -- but ONLY among
    polls that tested the same matchup as the single most recent poll.

    Why the matchup-anchoring: right after a primary (or any candidate
    dropping out), VoteHub's poll history for a race still contains older
    polls that tested the since-outdated field. A plain average across "the
    last N polls" blends those old names in alongside the current nominee,
    and a name with more accumulated poll volume can outrank the actual
    nominee even though it's no longer a live matchup.

    exclude_choices: an optional list of choice labels to blacklist entirely
    -- for a candidate CONFIRMED to have dropped out (not just "there's
    newer data now", but "this person is definitely not on the ballot").
    Matchup-anchoring alone can't fix that case if no poll testing the real
    current matchup exists yet; excluding the name outright means any poll
    that tested them gets dropped rather than shown as if they're still
    running. A poll left with fewer than 2 remaining choices after
    exclusion is skipped entirely, rather than shown as a lopsided single-
    candidate result.

    Returns (averages_dict, num_polls_used, most_recent_date_used).
    """
    if not polls:
        return {}, 0, None

    exclude_set = {c.strip().lower() for c in (exclude_choices or [])}

    def usable_answers(poll):
        return [
            a for a in poll.get("answers", [])
            if a.get("choice") and a["choice"].strip().lower() not in exclude_set
            and a.get("pct") is not None
        ]

    usable = [(p, usable_answers(p)) for p in polls]
    usable = [(p, ans) for p, ans in usable if len(ans) >= 2]
    if not usable:
        return {}, 0, None

    def choice_set(answers):
        return frozenset(a["choice"] for a in answers)

    current_matchup = choice_set(usable[0][1])
    matching = [(p, ans) for p, ans in usable if choice_set(ans) == current_matchup]
    recent = matching[:max_polls]

    totals = {}
    counts = {}
    for _, answers in recent:
        for answer in answers:
            choice = answer["choice"]
            totals[choice] = totals.get(choice, 0) + answer["pct"]
            counts[choice] = counts.get(choice, 0) + 1

    averages = {
        choice: round(totals[choice] / counts[choice], 1)
        for choice in totals
    }
    most_recent_used = recent[0][0]["end_date"] if recent else None
    return averages, len(recent), most_recent_used


def fetch_race_polling(subject, poll_type, lookback_days=90, max_polls=10, exclude_choices=None):
    """High-level helper: returns (averages_dict, num_polls_used, most_recent_date)."""
    polls = get_polls(subject, poll_type, lookback_days=lookback_days)
    return average_polls(polls, max_polls=max_polls, exclude_choices=exclude_choices)
