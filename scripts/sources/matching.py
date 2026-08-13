"""
Shared keyword-matching logic for finding the right Kalshi/Polymarket event
for a race. Both platforms need the exact same two things done correctly,
so this is factored out into one place rather than duplicated -- duplicated
copies are how the keyword-list bug and the kalshi/polymarket drift happened
earlier in this project.

WORD-BOUNDARY MATCHING (not substring): confirmed live that plain substring
matching produces real false positives -- a "NE Senate" keyword (for
Nebraska) matched inside "PhilippiNE SENate" and "MaiNE SENate" purely
because those words happen to END in "ne" right before "Senate". Likewise
"IA Senate" (Iowa) matched inside "PennsylvanIA SENate" and "GeorgIA
SENate". Requiring the keyword to appear as a whole word/phrase (not
spanning the tail of one word into the next) fixes this whole class of bug.

CATEGORY EXCLUSIONS: Kalshi/Polymarket run several DIFFERENT kinds of
markets per race, not just "who wins the general election" -- confirmed
live categories that otherwise score just as well on state+chamber keywords
as the real win-probability event:
  - "voter turnout" / "margin of victory" brackets
  - primary-specific vote-share brackets (e.g. "Democratic primary: X vote
    percent") -- note this is a DIFFERENT election than the general
  - combined multi-race markets (e.g. "Maine Governor-Senate combo")
  - statewide aggregate seat-count markets (e.g. "how many House seats will
    Democrats win in California?") -- same market matches every district
  - next-cycle markets already open for a future year (seen: "(2028)")
"""
import re

MIN_MATCH_SCORE = 2  # require at least 2 keyword hits, not just 1 incidental
                      # word overlap

EXCLUDED_TITLE_PATTERNS = [
    "voter turnout", "turnout",
    "margin of victory",
    "primary", "vote percent",
    "combo",
    "how many",
    "2028", "2027", "2030",  # other election cycles already listed
]


def _word_boundary_match(keyword, text):
    """True if `keyword` appears in `text` as a whole word/phrase --
    NOT as a substring spanning the tail of one word into the next."""
    pattern = r"\b" + re.escape(keyword.lower()) + r"\b"
    return re.search(pattern, text) is not None


def find_best_event(all_events, keywords, text_fn):
    """Return the event that best matches `keywords`, or None if nothing
    clears the minimum threshold or every candidate falls into an excluded
    category. `text_fn(event)` should return the searchable text (title +
    subtitle, field names vary by platform) for one event."""
    best_event, best_score = None, 0
    for event in all_events:
        text = text_fn(event).lower()
        if any(pattern in text for pattern in EXCLUDED_TITLE_PATTERNS):
            continue
        score = sum(1 for kw in keywords if _word_boundary_match(kw, text))
        if score > best_score:
            best_event, best_score = event, score
    if best_score < MIN_MATCH_SCORE:
        return None
    return best_event
