"""JSON facts ledger — schema, validation, safe merge, diffing.

The ledger is the single source of truth for the interview. The model may only
ever propose *deltas*; everything here validates and merges them. An unknown key,
a bad type, or an out-of-range value is dropped silently and the rest is kept, so
a hallucinating model can never corrupt the file.
"""

import datetime
import json
import os
import re

# --- schema constants -------------------------------------------------------

POSES = ("none", "handshake", "seated", "stare", "fart")

PHYSICAL_KEYS = {
    "hand_still_gripped": bool,
    "handshake_duration_turns": int,
    "seated": bool,
    "farted": bool,
    "fart_count": int,
    "eye_contact_unbroken_turns": int,
    "left_early": bool,
}

FLAG_KEYS = (
    "asked_about_gary",
    "knows_gary_fate",
    "mentioned_bridge",
    "admitted_no_license",
    "lied_about_something",
    "insulted_the_town",
    "showed_genuine_enthusiasm",
    "acknowledged_the_bus_in_the_wall",
)

METER_KEYS = (
    "candor",
    "delusion",
    "hazard_awareness",
    "bureaucratic_compliance",
    "physical_comedy",
)

METER_MIN, METER_MAX = -5, 5

# The fifteen-tier ladder from the GDD, best to worst.
GRADE_LADDER = [
    "A+", "A", "A-",
    "B+", "B", "B-",
    "C+", "C", "C-",
    "D+", "D", "D-",
    "F+", "F", "F-",
]

MAX_FACT_LEN = 200
MAX_TEXT_LEN = 60
MAX_NAME_LEN = 15

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


# --- sanitising -------------------------------------------------------------

def sanitize_text(value, cap=MAX_TEXT_LEN):
    """Strip control characters, collapse whitespace, cap length.

    HTML-escaping happens on render (client side); storing the raw-ish text keeps
    the transcript readable and lets the model see what the player actually typed.
    """
    if not isinstance(value, str):
        return ""
    value = _CONTROL_CHARS.sub("", value)
    value = value.replace("\r", " ").replace("\n", " ")
    value = re.sub(r"\s+", " ", value).strip()
    return value[:cap]


def sanitize_name(value):
    value = sanitize_text(value, MAX_NAME_LEN).upper()
    value = "".join(c for c in value if c.isalnum() or c == " ").strip()
    return value or "APPLICANT"


# --- construction -----------------------------------------------------------

def new_ledger(player_name="APPLICANT"):
    return {
        "session_id": datetime.datetime.now().isoformat(timespec="seconds"),
        "player_name": sanitize_name(player_name),
        "turn": 0,
        "pose": "none",
        "pose_locked_at_turn": None,
        "physical_state": {
            "hand_still_gripped": False,
            "handshake_duration_turns": 0,
            "seated": False,
            "farted": False,
            "fart_count": 0,
            "eye_contact_unbroken_turns": 0,
            "left_early": False,
        },
        "facts_established": [],
        "flags": {k: False for k in FLAG_KEYS},
        "meters": {k: 0 for k in METER_KEYS},
        "answers": [],
        "callbacks_used": [],
        "running_grade": "C+",
    }


# --- merge ------------------------------------------------------------------

def merge_updates(ledger, updates, debug=False):
    """Validate and merge a model-proposed delta into the ledger.

    Returns a list of human-readable strings naming what was rejected, purely for
    --debug logging. Rejection is always silent as far as the game is concerned.
    """
    rejected = []
    if not isinstance(updates, dict):
        return ["updates was not an object"]

    # facts_established is append-only. Nothing is ever removed.
    facts = updates.get("facts_established")
    if isinstance(facts, str):
        facts = [facts]
    if isinstance(facts, list):
        for fact in facts:
            if not isinstance(fact, str):
                rejected.append("fact (not a string)")
                continue
            fact = sanitize_text(fact, MAX_FACT_LEN)
            if fact and fact not in ledger["facts_established"]:
                ledger["facts_established"].append(fact)
    elif facts is not None:
        rejected.append("facts_established (not a list)")

    flags = updates.get("flags")
    if isinstance(flags, dict):
        for key, value in flags.items():
            if key not in FLAG_KEYS:
                rejected.append("flag %r (unknown key)" % key)
                continue
            if not isinstance(value, bool):
                rejected.append("flag %r (not a bool)" % key)
                continue
            # Flags latch on; the model cannot un-know something.
            if value:
                ledger["flags"][key] = True
    elif flags is not None:
        rejected.append("flags (not an object)")

    meters = updates.get("meters")
    if isinstance(meters, dict):
        for key, value in meters.items():
            if key not in METER_KEYS:
                rejected.append("meter %r (unknown key)" % key)
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                rejected.append("meter %r (not a number)" % key)
                continue
            # Deltas themselves are capped so one turn cannot swing the grade.
            delta = max(-2, min(2, int(round(value))))
            ledger["meters"][key] = clamp_meter(ledger["meters"][key] + delta)
    elif meters is not None:
        rejected.append("meters (not an object)")

    callbacks = updates.get("callbacks_used")
    if isinstance(callbacks, str):
        callbacks = [callbacks]
    if isinstance(callbacks, list):
        for cb in callbacks:
            if not isinstance(cb, str):
                rejected.append("callback (not a string)")
                continue
            cb = sanitize_text(cb, 40)
            if cb and cb not in ledger["callbacks_used"]:
                ledger["callbacks_used"].append(cb)
    elif callbacks is not None:
        rejected.append("callbacks_used (not a list)")

    if debug and rejected:
        print("[ledger] dropped %d invalid field(s): %s" % (len(rejected), ", ".join(rejected)))
    return rejected


def clamp_meter(value):
    return max(METER_MIN, min(METER_MAX, int(value)))


def add_fact(ledger, fact):
    """Append-only fact insertion used by the engine itself (not the model)."""
    fact = sanitize_text(fact, MAX_FACT_LEN)
    if fact and fact not in ledger["facts_established"]:
        ledger["facts_established"].append(fact)


def apply_meters(ledger, deltas):
    """Apply an engine-authored (deterministic) meter delta dict."""
    for key, delta in (deltas or {}).items():
        if key in METER_KEYS:
            ledger["meters"][key] = clamp_meter(ledger["meters"][key] + int(delta))


# --- pose -------------------------------------------------------------------

def lock_pose(ledger, pose, turn):
    if pose not in POSES:
        pose = "none"
    ledger["pose"] = pose
    ledger["pose_locked_at_turn"] = turn
    ps = ledger["physical_state"]
    if pose == "handshake":
        ps["hand_still_gripped"] = True
        ps["handshake_duration_turns"] = 1
    elif pose == "seated":
        ps["seated"] = True
    elif pose == "fart":
        ps["farted"] = True
        ps["fart_count"] = 1
    elif pose == "stare":
        ps["eye_contact_unbroken_turns"] = 1


# A pose that persists becomes more remarkable, and the physical-conduct line
# should show that: a handshake nobody ends is funnier at turn seven than at
# turn two. The fart is deliberately excluded — one clean cue, then silence.
CONDUCT_ESCALATION = {"handshake_duration_turns": (4, 7), "eye_contact_unbroken_turns": (5,)}


def advance_physical_state(ledger):
    """Tick the per-turn physical counters. Called once per completed turn."""
    ps = ledger["physical_state"]
    if ps["hand_still_gripped"]:
        ps["handshake_duration_turns"] += 1
        if ps["handshake_duration_turns"] in CONDUCT_ESCALATION["handshake_duration_turns"]:
            _bump_conduct(ledger)
    if ledger["pose"] == "stare":
        ps["eye_contact_unbroken_turns"] += 1
        if ps["eye_contact_unbroken_turns"] in CONDUCT_ESCALATION["eye_contact_unbroken_turns"]:
            _bump_conduct(ledger)


def _bump_conduct(ledger):
    ledger["meters"]["physical_comedy"] = clamp_meter(ledger["meters"]["physical_comedy"] + 1)


# --- grading ----------------------------------------------------------------

# Only three meters are actually assessed, plus delusion as a deduction.
# Physical conduct is recorded and remarked upon but deliberately not scored:
# the Authority has no box for what you did, which is the joke, and it also
# means the funniest choice in the game never costs you the grade.
SCORED_METERS = ("candor", "hazard_awareness", "bureaucratic_compliance")
DEDUCTED_METER = "delusion"
UNSCORED_METERS = ("physical_comedy",)

GRADE_MIN = -(len(SCORED_METERS) + 1) * METER_MAX          # -20
GRADE_MAX = (len(SCORED_METERS) + 1) * METER_MAX           # +20


def grade_points(ledger):
    """The single number the letter grade is derived from. Range -20..+20."""
    m = ledger["meters"]
    return sum(m[k] for k in SCORED_METERS) - m[DEDUCTED_METER]


def compute_grade(ledger):
    """Deterministic grade from the meters. The model never supplies this."""
    points = grade_points(ledger)
    span = float(GRADE_MAX - GRADE_MIN)
    idx = int(round((GRADE_MAX - points) / span * (len(GRADE_LADDER) - 1)))
    idx = max(0, min(len(GRADE_LADDER) - 1, idx))
    return GRADE_LADDER[idx]


def refresh_grade(ledger):
    ledger["running_grade"] = compute_grade(ledger)
    return ledger["running_grade"]


# --- persistence & diffing --------------------------------------------------

def snapshot(ledger):
    return json.loads(json.dumps(ledger))


def _flatten(obj, prefix=""):
    flat = {}
    for key, value in obj.items():
        path = "%s.%s" % (prefix, key) if prefix else key
        if isinstance(value, dict):
            flat.update(_flatten(value, path))
        elif isinstance(value, list):
            flat[path] = list(value)
        else:
            flat[path] = value
    return flat


def diff(before, after):
    """Return [(path, old, new)] for every changed field."""
    a, b = _flatten(before), _flatten(after)
    changes = []
    for key in b:
        old, new = a.get(key, "<absent>"), b[key]
        if old == new:
            continue
        if isinstance(new, list) and isinstance(old, list):
            added = [x for x in new if x not in old]
            if not added:
                continue
            new = "+%s" % json.dumps(added, ensure_ascii=False)
            old = "%d item(s)" % len(old)
        changes.append((key, old, new))
    return changes


def print_diff(before, after, action, debug=False):
    """Unconditional per-turn console diff — this is grading evidence."""
    changes = diff(before, after)
    turn = after.get("turn", "?")
    print("")
    print("+-- LEDGER  turn %s ---------------------------------------" % turn)
    print("|   action: %s" % action)
    if not changes:
        print("|   (no fields changed)")
    for key, old, new in changes:
        print("|   %-42s %s -> %s" % (key, _short(old), _short(new)))
    print("+----------------------------------------------------------")
    if debug:
        print(json.dumps(after, indent=2, ensure_ascii=False))


def _short(value, cap=64):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= cap else text[: cap - 3] + "..."


def save(ledger, path):
    """Rewrite ledger.json atomically after every turn."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(ledger, handle, indent=2, ensure_ascii=False)
    os.replace(tmp, path)
