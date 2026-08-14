#!/usr/bin/env python3
"""
Pulls the latest polling average, prediction-market odds, and fundraising
totals for every race in config/races.json, and writes the result to
docs/data/latest.json (what the dashboard reads) plus a rolling per-race
history file under docs/data/history/ (what the trend sparklines read).

Run it locally with:
    pip install -r requirements.txt
    python scripts/fetch_data.py

In production this runs on a schedule via .github/workflows/update-data.yml.
"""
import datetime
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(__file__))
from sources import votehub, kalshi, polymarket, fec  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config", "races.json")
DATA_DIR = os.path.join(ROOT, "docs", "data")
HISTORY_DIR = os.path.join(DATA_DIR, "history")
HISTORY_MAX_POINTS = 180  # ~6 months at one snapshot/day, plenty for a midterm cycle


def log(msg):
    print(f"[fetch_data] {msg}", flush=True)


def safe(label, fn, *args, **kwargs):
    """Run a fetch step; on failure, log it and return None instead of
    crashing the whole run — one flaky source shouldn't take the rest down."""
    try:
        return fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 - deliberately broad, this is a data pipeline
        log(f"WARNING: {label} failed: {exc}")
        traceback.print_exc()
        return None


def build_race_snapshot(race, all_kalshi_events, all_polymarket_events):
    log(f"Processing {race['label']}...")

    polling = safe(
        f"{race['id']} votehub",
        votehub.fetch_race_polling,
        race["votehub_subject"],
        race["votehub_poll_type"],
        exclude_choices=race.get("exclude_choices"),
    )
    polling_averages, polls_used, most_recent_poll_date = polling or ({}, 0, None)

    kalshi_event = safe(f"{race['id']} kalshi", kalshi.find_event, all_kalshi_events, race["keywords"])
    kalshi_odds = safe(
        f"{race['id']} kalshi convert", kalshi.event_to_odds, kalshi_event,
        exclude_outcomes=race.get("exclude_market_outcomes"),
        manual_url=race.get("kalshi_url"),
    ) if kalshi_event else None

    if race.get("disable_polymarket"):
        polymarket_odds = None
    else:
        poly_event = safe(f"{race['id']} polymarket", polymarket.find_event, all_polymarket_events, race["keywords"])
        polymarket_odds = safe(
            f"{race['id']} polymarket convert", polymarket.event_to_odds, poly_event,
            exclude_outcomes=race.get("exclude_market_outcomes"),
        ) if poly_event else None

    fundraising = safe(
        f"{race['id']} fec",
        fec.fetch_race_fundraising,
        race["office_code"],
        race["state_abbr"],
        race.get("district"),
    ) or []

    return {
        "id": race["id"],
        "label": race["label"],
        "chamber": race["chamber"],
        "state": race["state"],
        "district": race.get("district"),
        "polling": {
            "averages": polling_averages,
            "polls_used": polls_used,
            "most_recent_poll_date": most_recent_poll_date,
            "source": "VoteHub (https://votehub.com)",
        },
        "kalshi": kalshi_odds,
        "polymarket": polymarket_odds,
        "fundraising": fundraising,
    }


def append_history(race_id, snapshot, timestamp):
    os.makedirs(HISTORY_DIR, exist_ok=True)
    path = os.path.join(HISTORY_DIR, f"{race_id}.json")
    history = []
    if os.path.exists(path):
        try:
            with open(path) as f:
                history = json.load(f)
        except (json.JSONDecodeError, OSError):
            history = []

    # Stored as a generic {choice_label: pct} dict rather than fixed dem/rep
    # fields, since VoteHub's per-race polls may use candidate names as
    # choice labels rather than party labels (only the national generic-
    # ballot subject is confirmed to use literal "Dem"/"Rep" labels).
    kalshi_outcomes = (snapshot["kalshi"] or {}).get("outcomes") or []
    kalshi_leader_pct = kalshi_outcomes[0]["probability_pct"] if kalshi_outcomes else None

    history.append({
        "timestamp": timestamp,
        "polling_averages": snapshot["polling"]["averages"],
        "kalshi_leading_pct": kalshi_leader_pct,
    })
    history = history[-HISTORY_MAX_POINTS:]

    with open(path, "w") as f:
        json.dump(history, f, indent=2)


def main():
    with open(CONFIG_PATH) as f:
        config = json.load(f)
    races = config["races"]

    log("Fetching full open-event list from Kalshi (once for this run)...")
    all_kalshi_events = safe("kalshi bulk fetch", kalshi.fetch_all_open_events) or []
    log(f"  -> {len(all_kalshi_events)} open Kalshi events loaded")

    log("Fetching full open-events list from Polymarket (once for this run)...")
    all_polymarket_events = safe("polymarket bulk fetch", polymarket.fetch_all_open_events) or []
    log(f"  -> {len(all_polymarket_events)} open Polymarket events loaded")

    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    snapshots = []
    for race in races:
        snapshot = build_race_snapshot(race, all_kalshi_events, all_polymarket_events)
        snapshots.append(snapshot)
        append_history(race["id"], snapshot, timestamp)

    os.makedirs(DATA_DIR, exist_ok=True)
    output = {"generated_at": timestamp, "races": snapshots}
    with open(os.path.join(DATA_DIR, "latest.json"), "w") as f:
        json.dump(output, f, indent=2)

    log(f"Done. Wrote {len(snapshots)} race snapshots to docs/data/latest.json")


if __name__ == "__main__":
    main()
