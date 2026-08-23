"""Prompt assembly, defensive JSON parsing, fallback, and the ending composition.

The backend is injected. This module never imports a specific implementation, so
adding a fourth backend requires no change here.
"""

import json
import os
import re
import threading
import time

from . import backends, content, ledger as ledger_mod

# The backend itself times out at 45s, but the player must never watch a stall.
# At the soft deadline the turn is served from the bank and the subprocess is
# abandoned mid-animation.
SOFT_DEADLINE_SECONDS = 20

# A "personal best" needs the physical-conduct meter pinned to its ceiling.
METER_MAX_COMEDY = ledger_mod.METER_MAX

# The 20s default assumes a 3-8s call. On a machine where `claude -p` takes
# longer than that to boot, a fixed 20s would send every single turn to the bank
# and the live backend would never be used at all. So the first overrun teaches
# it: we keep timing the abandoned worker, and once one comes back we raise the
# deadline enough to catch the next one. `--patience N` sets it up front.
_deadline = {"seconds": float(SOFT_DEADLINE_SECONDS), "pinned": False}


def set_patience(seconds):
    """Pin the soft deadline from the command line and stop it adapting."""
    _deadline["seconds"] = float(max(1, min(backends.TIMEOUT_SECONDS, seconds)))
    _deadline["pinned"] = True


_WORLD_BIBLE_CACHE = {"text": None}


def world_bible(base_dir):
    """Load world_bible.md from this folder and nowhere else.

    The path is built from the prototype's own directory, so the folder can be
    copied anywhere on disk and still run.
    """
    if _WORLD_BIBLE_CACHE["text"] is None:
        path = os.path.join(base_dir, "world_bible.md")
        try:
            with open(path, "r", encoding="utf-8") as handle:
                _WORLD_BIBLE_CACHE["text"] = handle.read()
        except OSError:
            _WORLD_BIBLE_CACHE["text"] = "(world_bible.md missing — improvise nothing.)"
    return _WORLD_BIBLE_CACHE["text"]


# --- prompt assembly --------------------------------------------------------

def stable_prefix(base_dir):
    """The half of the prompt that is byte-identical on every single turn.

    build_prompt() is defined in terms of this, so the two cannot drift. The
    warm CLI process is primed with it once per interview; everything after it
    changes turn to turn and is sent fresh.
    """
    return "\n".join([
        content.PERSONA,
        "",
        "=== WORLD BIBLE (the only canon; do not invent outside it) ===",
        world_bible(base_dir),
        "",
    ])


def build_prompt(base_dir, led, history, question, answer_label, answer_text):
    """Assemble the five-part prompt described in the design."""
    recent = history[-4:]
    if recent:
        exchanges = "\n\n".join(
            "MANAGER: %s\n%s: %s" % (h["reply"], led["player_name"], h["answer"])
            for h in recent
        )
    else:
        exchanges = "(none — this is the first exchange)"

    given = answer_text if answer_text else answer_label
    return stable_prefix(base_dir) + "\n".join([
        content.PROMPT_SPLIT_MARKER,
        json.dumps(led, indent=2, ensure_ascii=False),
        "",
        content.REACTIVITY_RULES,
        "",
        "=== LAST 4 EXCHANGES ===",
        exchanges,
        "",
        "=== THIS TURN ===",
        "You asked: %s" % question["prompt"],
        "%s answered: %s" % (led["player_name"], given),
        "",
        content.OUTPUT_CONTRACT,
    ])


# --- defensive parsing ------------------------------------------------------

_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.M)


def extract_json(raw):
    """Strip fences, find the outermost {...} by brace matching, json.loads.

    Returns a dict or None. Never raises.
    """
    if not raw or not isinstance(raw, str):
        return None
    text = _FENCE.sub("", raw).strip()

    start = text.find("{")
    if start == -1:
        return None

    depth, in_string, escaped, end = 0, False, False, -1
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end == -1:
        return None

    try:
        parsed = json.loads(text[start:end])
    except (ValueError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def clean_reply(text):
    """Enforce the persona's hard rules on whatever came back."""
    if not isinstance(text, str):
        return None
    text = re.sub(r"\*[^*]{0,80}\*", "", text)              # stage directions
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    # When it echoes a typed answer back it reliably leaves a space before the
    # closing quote: “Alive. Behind this exact wheel. ” Tidy that up.
    text = re.sub(r"\s+([”\"'])", r"\1", text)
    if not text:
        return None
    # Trim to five sentences.
    sentences = re.findall(r"[^.!?…]+(?:\.{3}|…|[.!?])?", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) > 5:
        text = " ".join(sentences[:5])
    return text[:600]


# --- the turn ---------------------------------------------------------------

def ask(base_dir, backend_name, led, history, question, answer_label, answer_text, debug=False):
    """Run one turn. Always returns (reply, updates, grade_note, callback, source).

    Any failure anywhere routes to the response bank without crashing or stalling.
    """
    turn_seed = led.get("turn", 0)
    given = answer_text if answer_text else answer_label

    if backend_name == "none":
        return _bank_turn(led, question, turn_seed, given)

    generate = backends.get(backend_name)
    prompt = build_prompt(base_dir, led, history, question, answer_label, answer_text)

    if debug:
        print("\n[interviewer] prompt is %d chars" % len(prompt))

    raw = _generate_with_deadline(generate, prompt, debug)

    if raw is None:
        return _bank_turn(led, question, turn_seed, given)

    parsed = extract_json(raw)
    if parsed is None:
        print("[interviewer] could not parse model output as JSON — using bank")
        if debug:
            print("[interviewer] raw was:\n%s" % raw[:2000])
        return _bank_turn(led, question, turn_seed, given)

    reply = clean_reply(parsed.get("reply"))
    if not reply:
        print("[interviewer] model returned no usable reply — using bank")
        return _bank_turn(led, question, turn_seed, given)

    updates = parsed.get("ledger_updates")
    if not isinstance(updates, dict):
        updates = {}

    grade_note = ledger_mod.sanitize_text(parsed.get("grade_note", ""), 120)
    callback = ledger_mod.sanitize_text(parsed.get("callback_reference", ""), 40)
    return reply, updates, grade_note, callback, backend_name


def _generate_with_deadline(generate, prompt, debug):
    """Call the backend on a worker thread and give up on it at the soft deadline.

    A backend that raises, or one still running at 20s, both come back as None so
    the caller drops into the bank mid-animation rather than stalling the player.
    """
    box = {}
    started = time.time()

    def run():
        try:
            box["raw"] = generate(prompt, debug)
        except Exception as err:                            # noqa: BLE001 - a turn never dies
            print("[interviewer] backend raised %s: %s — using bank" % (type(err).__name__, err))
            box["raw"] = None
        box["elapsed"] = time.time() - started
        _learn(box["elapsed"])

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    deadline = _deadline["seconds"]
    worker.join(deadline)
    if worker.is_alive():
        print("[interviewer] backend still running at %.0fs — serving this turn from the bank"
              % deadline)
        return None
    if debug:
        print("[interviewer] backend answered in %.1fs" % box.get("elapsed", 0))
    return box.get("raw")


def _learn(elapsed):
    """Raise the soft deadline once a call is seen to take longer than it."""
    if _deadline["pinned"] or elapsed <= _deadline["seconds"]:
        return
    raised = min(backends.TIMEOUT_SECONDS, elapsed + 5)
    if raised > _deadline["seconds"]:
        print("[interviewer] a call took %.0fs; raising the soft deadline %.0fs -> %.0fs "
              "so the next turn can be served live" % (elapsed, _deadline["seconds"], raised))
        _deadline["seconds"] = raised


def _bank_turn(led, question, turn_seed, answer=None):
    # Hypotheticals are drawn from a pool but share one bank entry.
    key = question.get("bank_key", question["id"])
    reply = content.bank_reply(key, led, turn_seed, answer)
    callback = ""
    if led["physical_state"].get("hand_still_gripped"):
        callback = "handshake_turn%d" % led["physical_state"]["handshake_duration_turns"]
    elif led["pose"] == "stare":
        callback = "stare_turn%d" % led["physical_state"]["eye_contact_unbroken_turns"]
    updates = {"callbacks_used": [callback]} if callback else {}
    return reply, updates, "response bank", callback, "bank"


# --- endings ----------------------------------------------------------------

def compose_exit(led):
    """The early-exit send-off, assembled from the ledger. He hires you anyway."""
    ps = led["physical_state"]
    turns = led["turn"]
    name = content.mangle_name(led["player_name"], turns)
    lines = []

    if turns <= 1:
        lines.append("You lasted less than one full question. …That is not a record, "
                     "%s, but it is close enough that I will have to look it up." % name)
    else:
        lines.append("Nine minutes. …Or %d questions, which is how Form 12-B measures it, "
                     "and Form 12-B is what I have." % turns)

    if led["pose"] == "handshake":
        lines.append("You never let go of my hand. I want to be clear that I am not "
                     "objecting. I am asking whether you intend to take it with you.")
    elif led["pose"] == "seated":
        lines.append("You are standing up. I had gotten used to you sitting down. …Very "
                     "little in this office gets used to anything.")
    elif led["pose"] == "stare":
        lines.append("The applicant is leaving. The applicant is leaving while still facing "
                     "me. I am dictating this into the annex as it happens.")
    elif led["pose"] == "fart":
        lines.append("You may go. The ventilation was condemned in 2004 and I would not "
                     "want you to feel responsible for a municipal failure.")

    if led["flags"].get("asked_about_gary"):
        lines.append("You asked about Gary. …Nobody in Fairweather has ever seen Gary "
                     "arrive. Only leave. I notice you're doing the same.")
    else:
        lines.append("You never asked about Gary. Everyone asks about Gary. …I'll note "
                     "the omission on line fourteen and leave it there.")

    lines.append("You're hired. The drivers keep dying. When can you start. …Please "
                 "don't go.")
    return " ".join(lines)


def compose_report(led):
    """Deterministic end-of-shift report card, in the GDD's receipt format."""
    grade = ledger_mod.refresh_grade(led)
    meters = led["meters"]

    # Three lines are assessed and add up to the grade; two are recorded and
    # explicitly do not. Showing the arithmetic is the point — the card should
    # make it obvious where the letter came from.
    rows = []
    for key, label in content.SCORED_LINE_LABELS:
        value = meters[key]
        rows.append({
            "label": label,
            "value": value,
            "tier": content.tier_for(value),
            "display": "%+d" % value,
        })

    noted = []
    for key, label, note in content.NOTED_LINE_LABELS:
        value = meters[key]
        noted.append({
            "label": label,
            "value": value,
            "tier": (content.delusion_note(value) if key == "delusion"
                     else content.conduct_note(value)),
            "display": "%+d" % value,
            "note": note,
        })

    high_grade = grade[0] in ("A", "B")
    abandoned = led["physical_state"]["left_early"]

    # The record mark stays rare: a maxed physical-conduct meter AND a grade that
    # earned it. Without the grade condition a C- run was closing on "Personal best."
    # A commendation outranks it, so the record mark is what a B-grade run gets
    # for spectacular physical conduct rather than a second prize for an A.
    commended = grade in ("A+", "A", "A-") and not abandoned
    record = (meters["physical_comedy"] >= METER_MAX_COMEDY
              and high_grade and not abandoned and not commended)
    stamp = None
    if commended:
        stamp = content.CLOSING_STAMPS["commendation"]
    elif record:
        stamp = content.CLOSING_STAMPS["personal_best"]

    seed = len(led["facts_established"]) + led["turn"]
    band = "abandoned" if abandoned else ("record" if record else grade[0].upper())

    points = ledger_mod.grade_points(led)
    return {
        "grade": grade,
        "pose": led["pose"],
        "rows": rows,
        "noted": noted,
        "total": points,
        "total_display": "%+d" % points,
        "total_range": "%+d..%+d" % (ledger_mod.GRADE_MIN, ledger_mod.GRADE_MAX),
        "standout": content.standout_line(led, seed),
        "sign_off": content.grade_blurb(grade, seed, abandoned, record),
        "band": band,
        "stamp": stamp,
        "hired_line": content.HIRED_LINE,
        "facts": led["facts_established"],
        "callbacks": led["callbacks_used"],
        "name": led["player_name"],
    }
