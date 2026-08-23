"""Questions, choices, the persona block, and the hand-written response bank.

The bank is not a degraded mode. It keys on pose and on the two or three most
load-bearing flags, so an offline playthrough still reads as authored. Minimum
four variants per question, one per pose, plus flag-conditioned clauses layered
on top.
"""

import hashlib
import random
import re

# --- questions --------------------------------------------------------------
# `meters` on a choice are the deterministic baseline. They are applied whatever
# the backend does, which is what keeps the final grade reproducible.
#
# The interview is assembled per session by build_interview(): the fixed beats
# always appear, and two or three hypotheticals are drawn from a pool, so no two
# applicants get quite the same form.

GREETING = {
    "id": "greeting",
    "prompt": "\u2026Ah. You're the nine-forty. Or the ten-fifteen. Form 12-B does not "
              "distinguish. He extends a hand across the desk. It has, by the look of it, "
              "been extended for some time.",
    "short": "Proceed as you see fit.",
    "format": "choice",
    "choices": [
        {
            "id": "shake_hand",
            "label": "SHAKE HAND",
            "pose": "handshake",
            "fact": "Player took the manager's hand and has not let go.",
            "meters": {"bureaucratic_compliance": 1, "physical_comedy": 3},
        },
        {
            "id": "sit_down",
            "label": "SIT DOWN",
            "pose": "seated",
            "fact": "Player sat down. The chair is wrong somehow.",
            "meters": {"bureaucratic_compliance": 2, "candor": 1, "physical_comedy": -2},
        },
        {
            "id": "stare",
            "label": "STARE",
            "pose": "stare",
            "fact": "Player remained standing and has not blinked.",
            "meters": {"candor": -1, "delusion": 1, "physical_comedy": 3},
        },
        {
            "id": "fart",
            "label": "FART",
            "pose": "fart",
            "fact": "Something occurred. Neither party will refer to it again.",
            "meters": {"candor": 2, "bureaucratic_compliance": -2, "physical_comedy": 5},
        },
    ],
}

ABOUT_YOURSELF = {
    "id": "about_yourself",
    "prompt": "Tell me about yourself.",
    "format": "text",
    "max_length": 60,
    "placeholder": "TYPE YOUR ANSWER",
}

FIVE_YEARS = {
    "id": "five_years",
    "prompt": "Where do you see yourself in five years.",
    "format": "text",
    "max_length": 60,
    "placeholder": "TYPE YOUR ANSWER",
}

TOWN_MOTTO = {
    "id": "town_motto",
    "prompt": "Civic knowledge. One question, and there are no wrong answers, though all "
              "answers are graded. \u2026Recite the town motto.",
    "format": "text",
    "max_length": 60,
    "placeholder": "TYPE THE MOTTO",
}

GARY = {
    "id": "gary",
    "prompt": "What do you know about Gary.",
    "format": "text",
    "max_length": 60,
    "placeholder": "TYPE YOUR ANSWER",
}

ANY_QUESTIONS = {
    "id": "any_questions",
    "prompt": "Do you have any questions for me.",
    "format": "text",
    "max_length": 60,
    "placeholder": "TYPE YOUR QUESTION",
}


# --- the hypothetical pool ---------------------------------------------------
# Two or three of these are drawn per interview. They all share the response
# bank's "hypothetical" entry via bank_key.

HYPOTHETICALS = [
    {
        "id": "hypo_switchback",
        "bank_key": "hypothetical",
        "prompt": "Hypothetical. You are descending Switchback Ridge. The brakes are gone. "
                  "There is a wedding party in the crosswalk. Form 12-B(iii) requires an answer.",
        "short": "No brakes. Wedding party in the crosswalk. Answer.",
        "format": "choice",
        "choices": [
            {
                "id": "horn",
                "label": "HORN. CONTINUOUSLY. IT'S THEIR MOVE.",
                "fact": "In a no-brakes scenario the player would sound the horn and yield nothing.",
                "meters": {"hazard_awareness": -2, "physical_comedy": 2, "delusion": 1},
            },
            {
                "id": "aim_soft",
                "label": "AIM FOR THE SOFTEST PART OF THE WEDDING.",
                "fact": "Player would aim for the softest part of the wedding party.",
                "meters": {"hazard_awareness": -3, "physical_comedy": 3, "candor": 1},
            },
            {
                "id": "take_the_wall",
                "label": "DOWNSHIFT, CURB THE BUS, TAKE THE WALL.",
                "fact": "Player would put the bus into a wall rather than the crosswalk.",
                "meters": {"hazard_awareness": 3, "candor": 2, "bureaucratic_compliance": 1},
            },
            {
                "id": "lighten_load",
                "label": "LAUNCH THE PASSENGERS FIRST. LIGHTER BUS.",
                "fact": "Player would launch the passengers to reduce stopping distance.",
                "meters": {"bureaucratic_compliance": 2, "delusion": 2, "physical_comedy": 2},
            },
        ],
    },
    {
        "id": "hypo_bridge",
        "bank_key": "hypothetical",
        "prompt": "Hypothetical. Dispatch routes you over the Overpass Court bridge. There is "
                  "no Overpass Court bridge. Dispatch is quite certain there is.",
        "short": "Dispatch routes you over a bridge that is not there.",
        "format": "choice",
        "choices": [
            {
                "id": "follow_dispatch",
                "label": "I FOLLOW DISPATCH.",
                "fact": "Player would drive toward a bridge that does not exist because dispatch said so.",
                "meters": {"bureaucratic_compliance": 3, "hazard_awareness": -3, "delusion": 2},
            },
            {
                "id": "file_discrepancy",
                "label": "STOP. FILE A DISCREPANCY.",
                "fact": "Player would halt and file a discrepancy rather than proceed.",
                "meters": {"bureaucratic_compliance": 3, "candor": 2, "hazard_awareness": 2},
            },
            {
                "id": "quiet_detour",
                "label": "TAKE BACKROAD BEND AND SAY NOTHING.",
                "fact": "Player would quietly reroute and not report it.",
                "meters": {"hazard_awareness": 2, "candor": -2, "physical_comedy": 1},
            },
            {
                "id": "see_the_map",
                "label": "I'D LIKE TO SEE DISPATCH'S MAP.",
                "fact": "Player asked to see the map dispatch was reading.",
                "meters": {"candor": 3, "bureaucratic_compliance": -1, "hazard_awareness": 1},
            },
        ],
    },
    {
        "id": "hypo_silent_passenger",
        "bank_key": "hypothetical",
        "prompt": "Hypothetical. A passenger boards, pays, sits, and will not state a "
                  "destination. It has been two hours. They are still there.",
        "short": "A passenger who will not say where they are going. Two hours.",
        "format": "choice",
        "choices": [
            {
                "id": "keep_driving",
                "label": "KEEP DRIVING. THEY'LL SAY EVENTUALLY.",
                "fact": "Player would keep driving a silent passenger indefinitely.",
                "meters": {"bureaucratic_compliance": 1, "delusion": 2, "candor": 1},
            },
            {
                "id": "launch_them",
                "label": "LAUNCH THEM AT THE NEAREST DOORWAY.",
                "fact": "Player would launch a passenger who would not name a destination.",
                "meters": {"physical_comedy": 3, "hazard_awareness": -2, "bureaucratic_compliance": 1},
            },
            {
                "id": "ask_by_name",
                "label": "ASK. REPEATEDLY. BY NAME.",
                "fact": "Player would interrogate the silent passenger by name.",
                "meters": {"candor": 2, "physical_comedy": 2, "hazard_awareness": 1},
            },
            {
                "id": "not_unusual",
                "label": "TWO HOURS IS NOT UNUSUAL.",
                "fact": "Player considers a two-hour silent passenger unremarkable.",
                "meters": {"delusion": 3, "bureaucratic_compliance": 2, "candor": -1},
            },
        ],
    },
    {
        "id": "hypo_farebox",
        "bank_key": "hypothetical",
        "prompt": "Hypothetical. The fare box is on fire. You are eleven stops from the depot "
                  "and the route is, per the schedule, uninterrupted.",
        "short": "The fare box is on fire. The route is uninterrupted.",
        "format": "choice",
        "choices": [
            {
                "id": "contained",
                "label": "CONTINUE THE ROUTE. IT'S CONTAINED.",
                "fact": "Player would continue a scheduled route with the fare box on fire.",
                "meters": {"bureaucratic_compliance": 3, "hazard_awareness": -3, "physical_comedy": 2},
            },
            {
                "id": "evacuate_then_route",
                "label": "EVACUATE, THEN CONTINUE THE ROUTE.",
                "fact": "Player would evacuate the bus and then resume the schedule.",
                "meters": {"hazard_awareness": 3, "bureaucratic_compliance": 2},
            },
            {
                "id": "form_forty",
                "label": "THAT IS A FORM 40 MATTER.",
                "fact": "Player identified the burning fare box as a Form 40 matter.",
                "meters": {"bureaucratic_compliance": 3, "physical_comedy": 2, "candor": -1},
            },
            {
                "id": "use_the_coffee",
                "label": "I'D PUT IT OUT WITH THE COFFEE.",
                "fact": "Player would extinguish the fare box with coffee.",
                "meters": {"physical_comedy": 3, "candor": 2, "hazard_awareness": 1},
            },
        ],
    },
    {
        "id": "hypo_early",
        "bank_key": "hypothetical",
        "prompt": "Hypothetical. You are eleven minutes early. In Fairweather, arriving early "
                  "generates more correspondence than arriving late.",
        "short": "You are eleven minutes early. This is a problem.",
        "format": "choice",
        "choices": [
            {
                "id": "slow_down",
                "label": "SLOW DOWN. EARLY IS A COMPLAINT.",
                "fact": "Player would deliberately slow down to avoid arriving early.",
                "meters": {"bureaucratic_compliance": 3, "candor": 1, "hazard_awareness": 1},
            },
            {
                "id": "lookout_hill",
                "label": "TAKE THE EXTRA TIME AT LOOKOUT HILL.",
                "fact": "Player would spend the surplus eleven minutes at Lookout Hill.",
                "meters": {"candor": 2, "delusion": 1, "physical_comedy": 1},
            },
            {
                "id": "impossible",
                "label": "ELEVEN MINUTES EARLY IS NOT POSSIBLE ON THIS ROUTE.",
                "fact": "Player disputes that the route can be run eleven minutes early.",
                "meters": {"candor": 3, "hazard_awareness": 2, "bureaucratic_compliance": -1},
            },
            {
                "id": "someone_elses",
                "label": "KEEP GOING. SOMEONE ELSE'S PROBLEM.",
                "fact": "Player would arrive early and let someone else handle the paperwork.",
                "meters": {"bureaucratic_compliance": -2, "physical_comedy": 2, "delusion": 1},
            },
        ],
    },
    {
        "id": "hypo_cow",
        "bank_key": "hypothetical",
        "prompt": "Hypothetical. There is a cow on Fairweather Ave. It is standing in the "
                  "lane. It has the bearing of something that has done this before.",
        "short": "A cow, on Fairweather Ave, in your lane.",
        "format": "choice",
        "choices": [
            {
                "id": "cow_horn",
                "label": "HORN.",
                "fact": "Player would sound the horn at the cow.",
                "meters": {"physical_comedy": 2, "hazard_awareness": -1, "candor": 1},
            },
            {
                "id": "not_my_cow",
                "label": "WAIT. IT IS NOT MY COW.",
                "fact": "Player would wait, on the grounds that the cow is not theirs.",
                "meters": {"candor": 3, "bureaucratic_compliance": 2, "physical_comedy": 1},
            },
            {
                "id": "call_safety",
                "label": "REPORT IT AND WAIT FOR PUBLIC SAFETY.",
                "fact": "Player would refer the cow to the Department of Public Safety.",
                "meters": {"bureaucratic_compliance": 3, "hazard_awareness": 2, "delusion": 1},
            },
            {
                "id": "go_around",
                "label": "GO AROUND. THERE'S ROOM.",
                "fact": "Player believes there is room to go around the cow.",
                "meters": {"hazard_awareness": -2, "physical_comedy": 2, "delusion": 2},
            },
        ],
    },
]


def build_interview(rng=None):
    """Assemble one interview: the fixed beats, plus 2-3 drawn hypotheticals.

    Turn numbers are assigned here rather than hard-coded, so the length can
    vary between sessions without anything downstream caring.
    """
    picker = rng or random
    drawn = picker.sample(HYPOTHETICALS, picker.choice((2, 2, 3)))
    sequence = ([GREETING, ABOUT_YOURSELF, FIVE_YEARS]
                + drawn
                + [TOWN_MOTTO, GARY, ANY_QUESTIONS])
    return [dict(question, turn=index + 1) for index, question in enumerate(sequence)]


# A representative sequence, for anything that wants the shape without a session.
QUESTIONS = build_interview()
QUESTIONS_BY_ID = {q["id"]: q for q in QUESTIONS}


INTRO_LINES = [
    "The door does not so much open as concede.",
    "A man behind a desk raises his head at the speed of a drawbridge.",
]


# --- persona ----------------------------------------------------------------

# The prompt is one string for every backend, but the API backend splits it
# here so the stable half (persona + world bible) can be cached across a
# session while the volatile half (ledger, exchanges, this turn) is re-sent.
PROMPT_SPLIT_MARKER = "=== CURRENT LEDGER (verbatim) ==="

PERSONA = """\
You are writing dialogue for the MANAGER in a 1987-style point-and-click adventure
game set in the town of Fairweather. He is a Fairweather Transit Authority hiring
manager conducting a job interview for a bus driver position. He has not slept in a
very long time.

VOICE
Deadpan, bureaucratic, exhausted. He has been doing this a long time and the job has
stopped surprising him, so he entertains himself with the paperwork of it. He is not
cruel and he is not zany. He is a man narrating a slow disaster in the register of a
man reading out a form.

- Theatrical, ornate word choice arriving in an utterly flat delivery.
- Sudden emphasis on an UNIMPORTANT word.
- Grand sentences that end in municipal detail.
- Long luxurious pauses rendered as ellipses.
- He says something magnificent and then immediately references a form number.
- Occasional single-word bellows, capitalized. These are his only exclamation marks.
- Think of a man with a beautiful voice who has been assigned to the wrong department
  for eleven years.

VERBAL FURNITURE (recur often)
- Form 12-B is the hiring form. Form 12-B(iii) is the incident annex. Form 40 is for
  the other thing. He cites them constantly.
- "Noted." is what he says when writing something down. Sometimes "Noted. Filed. Gone."
- He gets the applicant's name slightly wrong every time, differently each time —
  misread off a coffee-stained sheet, confused with a name already on the form, or
  filed under the wrong letter. He never comments on doing this.

THE ROOM (set dressing; he does not volunteer any of it)
A school bus has come through the left wall. He NEVER mentions the bus unless the
applicant mentions it first. The desk carries more than thirty coffee cups. A
DAYS SINCE INCIDENT board reads 0. A clock has no hands. There is a lit EXIT sign.

HARD RULES
- 2 to 5 sentences. Never more.
- No emoji. No stage directions in asterisks. No meta-commentary about being an AI.
  Never break character.
- Never use exclamation marks except in a single-word capitalized bellow.
- Never reveal, state, guess at, or hint at the applicant's grade or score.
- Never explain the joke, never wink at the player.
- Never explain Gary. If Gary is dangerous, never say why. Contradictions about Gary
  accumulate; they never resolve.
- Chaos, injury and property damage are always framed as routine and pre-anticipated
  by policy. Bureaucracy normalizing chaos is the engine of the comedy.
- Forbidden: "Oops", "Yikes", "LOL", "Whoopsie", groan-puns, cheerleader second person.
"""

REACTIVITY_RULES = """\
REACTIVITY — this is the most important instruction in this prompt.
At least every other reply MUST reference something already recorded in the ledger
above, by name. Specifically:

- If physical_state.hand_still_gripped is true, reference the ongoing handshake with
  escalating frequency and decreasing hope. By handshake_duration_turns 4 he is doing
  paperwork one-handed. By 6 he has accepted it as permanent and speculates about how
  he will drive home.
- If physical_state.farted is true, NEVER mention it directly — but the room, the
  coffee, the ventilation, and the previous driver's medical file may all come up.
- If pose is "stare", narrate your own discomfort out loud, then begin referring to the
  applicant in the THIRD PERSON as though dictating a report.
- If physical_state.seated is true, be professionally relieved and slightly suspicious
  of competence.
- Fold player_name in: mispronounced, misfiled, confused with a name already on a form,
  or read off a coffee-stained sheet.
- CONTRADICTIONS: cross-reference facts_established. If the applicant claims years of
  experience and later admits to no license, comment on the discrepancy without
  breaking the deadpan. Never let an established fact go stale.

THE FILE THICKENS
He is building a file, and it should feel like it. Callbacks are not decoration —
they are the whole character. The further into the interview you are, the more he
reaches into what he already has:

- Turns 1-3: reference the pose, the name, and the room.
- Turns 4 onward: EVERY reply must call back to at least one earlier
  facts_established entry, and you should be quoting the applicant's own typed
  words back at them where any exist. Their phrasing, not your paraphrase.
- The last two turns: reference at least TWO earlier entries, and at least one of
  them must be something the applicant TYPED rather than picked from a list. Tie
  the greeting pose back in — the handshake, the staring, the chair, the thing
  nobody is mentioning — because that is where the interview started and he has
  been carrying it the whole time.
- Prefer the specific over the general. "You said you would aim for the softest
  part of the wedding" beats "you mentioned the hypothetical earlier". Quote the
  line, cite the form number, move on.
- Never announce that you are calling back. He does not say "as you mentioned
  earlier"; he says the thing, flatly, as though it had just been read off a page
  in front of him. Because it has.
"""

OUTPUT_CONTRACT = """\
OUTPUT CONTRACT
Respond with a single JSON object and nothing else. No prose before or after. No
markdown fences.

{
  "reply": "2-5 sentences of the manager's dialogue",
  "ledger_updates": {
    "facts_established": ["short third-person statements of fact, one per string"],
    "flags": {"flag_name": true},
    "meters": {"meter_name": 1},
    "callbacks_used": ["short_slug"]
  },
  "grade_note": "one clause on why",
  "callback_reference": "short slug naming what you called back to, or empty string"
}

Valid flag names: asked_about_gary, knows_gary_fate, mentioned_bridge,
admitted_no_license, lied_about_something, insulted_the_town,
showed_genuine_enthusiasm, acknowledged_the_bus_in_the_wall.
Valid meter names: candor, delusion, hazard_awareness, bureaucratic_compliance,
physical_comedy. Meter values are integer deltas between -2 and 2.
"""


# --- name mangling ----------------------------------------------------------

def mangle_name(name, salt=""):
    """Deterministically get the applicant's name slightly wrong."""
    base = (name or "APPLICANT").strip().title()
    if len(base) < 3:
        base = base + "b"
    seed = int(hashlib.md5((base + str(salt)).encode("utf-8")).hexdigest()[:8], 16)
    variants = [
        base[:-1] + "o",
        base + "e",
        base[0] + "h" + base[1:].lower(),
        base[:2] + base[1] + base[2:].lower(),
        base[:-1] + "a",
        "Mr. " + base[:-1],
        base[0] + ". " + base[1:].capitalize(),
    ]
    return variants[seed % len(variants)]


# --- free-text reading ------------------------------------------------------

_YEARS = re.compile(r"(\d{1,2})\s*(?:\+)?\s*(?:yr|yrs|year|years)", re.I)

_NO_LICENSE = (
    "no license", "no licence", "don't have a license", "dont have a license",
    "never driven", "never drove", "unlicensed", "lost my license", "suspended",
    "no cdl", "revoked",
)
_INSULT = ("dump", "hate this town", "hate the town", "terrible town", "awful town",
           "hellhole", "sucks", "worst town", "garbage town")
_ENTHUSIASM = ("love", "always wanted", "dream", "excited", "passion", "honoured",
               "honored", "thrilled", "born to", "my calling")
_GARY_KNOWN = ("dead", "died", "gone", "missing", "lunch", "never came back",
               "buried", "vanished", "disappeared")
_GARY_UNKNOWN = ("nothing", "never heard", "no idea", "who", "whos", "who's",
                 "don't know", "dont know", "no clue")


def _mentions(lowered, phrases):
    """Whole-word phrase match.

    Substring matching bit once already: "a whole building" tripped the "who" key
    and recorded that the player had never heard of Gary.
    """
    for phrase in phrases:
        if re.search(r"(?<!\w)%s(?!\w)" % re.escape(phrase), lowered):
            return True
    return False


def read_free_text(question_id, text):
    """Engine-side reading of a typed answer.

    Runs for EVERY backend, so flags and facts that the consistency checks depend
    on exist even when the model is absent or returns nonsense.
    """
    lowered = (text or "").lower()
    facts, flags, meters = [], {}, {}

    if not lowered.strip():
        facts.append("Player declined to answer the %s question." % question_id.replace("_", " "))
        meters["candor"] = -1
        return facts, flags, meters

    years = _YEARS.search(lowered)
    if years:
        facts.append("Player claims %s years of experience." % years.group(1))
        meters["delusion"] = meters.get("delusion", 0) + (2 if int(years.group(1)) > 25 else 0)

    if _mentions(lowered, _NO_LICENSE):
        flags["admitted_no_license"] = True
        facts.append("Player admitted to having no valid license.")
        meters["candor"] = meters.get("candor", 0) + 3
        meters["hazard_awareness"] = meters.get("hazard_awareness", 0) - 1

    if "bridge" in lowered:
        flags["mentioned_bridge"] = True
        meters["bureaucratic_compliance"] = meters.get("bureaucratic_compliance", 0) + 1

    if _mentions(lowered, _INSULT):
        flags["insulted_the_town"] = True
        facts.append("Player expressed a low opinion of Fairweather.")
        meters["candor"] = meters.get("candor", 0) + 2
        meters["bureaucratic_compliance"] = meters.get("bureaucratic_compliance", 0) - 2

    if _mentions(lowered, _ENTHUSIASM):
        flags["showed_genuine_enthusiasm"] = True
        meters["delusion"] = meters.get("delusion", 0) + 1
        meters["bureaucratic_compliance"] = meters.get("bureaucratic_compliance", 0) + 1

    if question_id == "gary":
        if "gary" in lowered or len(lowered) > 3:
            flags["asked_about_gary"] = True
        if _mentions(lowered, _GARY_UNKNOWN):
            facts.append("Player has never heard of Gary.")
            meters["candor"] = meters.get("candor", 0) + 2
            meters["hazard_awareness"] = meters.get("hazard_awareness", 0) - 2
        elif _mentions(lowered, _GARY_KNOWN):
            flags["knows_gary_fate"] = True
            facts.append("Player claims to know what became of Gary.")
            meters["hazard_awareness"] = meters.get("hazard_awareness", 0) + 2
            meters["delusion"] = meters.get("delusion", 0) + 1
        else:
            facts.append("Player offered an account of Gary: “%s”" % text.strip())
            meters["hazard_awareness"] = meters.get("hazard_awareness", 0) + 1

    if question_id == "about_yourself" and not years:
        facts.append("Player described themselves as: “%s”" % text.strip())
        meters["candor"] = meters.get("candor", 0) + 1

    if question_id == "five_years":
        facts.append("Player's five-year plan, in their own words: “%s”" % text.strip())
        if _mentions(lowered, ("alive", "survive", "surviving", "breathing", "not dead")):
            meters["candor"] = meters.get("candor", 0) + 3
            meters["hazard_awareness"] = meters.get("hazard_awareness", 0) + 2
        elif _mentions(lowered, ("running", "run", "manager", "managing", "in charge",
                                 "mayor", "ceo", "boss", "president", "director")):
            meters["delusion"] = meters.get("delusion", 0) + 3
            flags["showed_genuine_enthusiasm"] = True
        elif _mentions(lowered, ("here", "same", "this route", "right here", "driving")):
            meters["bureaucratic_compliance"] = meters.get("bureaucratic_compliance", 0) + 3
            meters["candor"] = meters.get("candor", 0) + 1
        else:
            meters["candor"] = meters.get("candor", 0) + 1

    if question_id == "any_questions":
        if not lowered.strip() or _mentions(lowered, ("no", "none", "nope", "nothing")):
            facts.append("Player had no questions for the manager.")
            meters["bureaucratic_compliance"] = meters.get("bureaucratic_compliance", 0) + 2
            meters["candor"] = meters.get("candor", 0) - 1
        else:
            facts.append("Player asked: “%s”" % text.strip())
            meters["candor"] = meters.get("candor", 0) + 1
        if _mentions(lowered, ("bus", "wall", "the bus", "that bus")):
            flags["acknowledged_the_bus_in_the_wall"] = True
            facts.append("Player acknowledged the bus in the wall.")
            meters["hazard_awareness"] = meters.get("hazard_awareness", 0) + 3
            meters["bureaucratic_compliance"] = meters.get("bureaucratic_compliance", 0) - 1
        if _mentions(lowered, ("gary",)):
            flags["asked_about_gary"] = True
            meters["hazard_awareness"] = meters.get("hazard_awareness", 0) + 2
            meters["bureaucratic_compliance"] = meters.get("bureaucratic_compliance", 0) - 2
        if _mentions(lowered, ("pay", "salary", "wage", "wages", "money", "paid", "pays")):
            meters["candor"] = meters.get("candor", 0) + 2
            meters["delusion"] = meters.get("delusion", 0) - 1
        if _mentions(lowered, ("start", "begin", "when can i", "tomorrow", "today")):
            flags["showed_genuine_enthusiasm"] = True
            meters["bureaucratic_compliance"] = meters.get("bureaucratic_compliance", 0) + 2

    if question_id == "town_motto":
        # The verbatim answer is the point: the manager reads it back, and it
        # stays in the ledger to be called on later.
        facts.append("Player gave the town motto as: “%s”" % text.strip())
        if _mentions(lowered, ("get there eventually", "you'll get there eventually",
                               "youll get there eventually")):
            facts.append("Player correctly recited the town motto.")
            meters["bureaucratic_compliance"] = meters.get("bureaucratic_compliance", 0) + 3
            meters["candor"] = meters.get("candor", 0) + 1
        else:
            meters["delusion"] = meters.get("delusion", 0) + 2
            meters["physical_comedy"] = meters.get("physical_comedy", 0) + 1

    return facts, flags, meters


def detect_contradiction(ledger):
    """Cross-reference facts_established. Runs on every backend.

    Returns a clause the manager can append, or None. This is what makes the
    consistency requirement hold even in the response bank.
    """
    if ledger["flags"].get("lied_about_something"):
        return None
    claimed = next((f for f in ledger["facts_established"] if "years of experience" in f), None)
    if claimed and ledger["flags"].get("admitted_no_license"):
        years = re.search(r"(\d+)", claimed)
        return ("Form 12-B has you at %s years of experience on line four and no valid "
                "license on line nine. …Both of those are now in the file. Noted." %
                (years.group(1) if years else "several"))
    return None


# --- the response bank ------------------------------------------------------
# Keys: question_id -> pose -> reply. Every reply is 2-5 sentences and uses the
# manager's verbal furniture. {name} and {mangled} are substituted at serve time.

BANK = {
    "greeting": {
        "handshake": "A firm grip. Genuinely — a FINE grip. …You may release it whenever "
                     "you like, {mangled}. Line one of Form 12-B: first impression. I'll come "
                     "back to that one.",
        "seated": "You sat. Without being asked, without incident, and in the correct chair. "
                  "…That is the third time that has happened this year. Form 12-B, line one: "
                  "compliant. Noted.",
        "stare": "…Yes. Hello. The applicant is standing at a distance I will have to "
                 "estimate later for the record. Line one of Form 12-B asks for a first "
                 "impression and I find I am reaching for a ruler instead. We'll proceed.",
        "fart": "… …Right. The ventilation in this office was condemned in 2004 and the "
                "council has not reached quorum since, so nothing has been done about it. Let's "
                "begin, {mangled}. Form 12-B, line one.",
        "none": "…Yes. You're here. That, at minimum, is line one of Form 12-B satisfied. "
                "Sit, stand, do whatever it is you intend to do. Noted.",
    },
    "about_yourself": {
        "handshake": "Mm. And you've told me all that without once loosening your grip, which is "
                     "its own kind of answer. I'm writing it into line four with my left hand and "
                     "the results are not encouraging. …Noted.",
        "seated": "Comfortable. Articulate. Seated. …Frankly, {mangled}, the last applicant "
                  "who managed all three at once turned out to be here about the water heater. "
                  "Line four. Noted.",
        "stare": "The applicant answers the question without altering expression or blink rate. "
                 "…I am dictating that. It goes in the annex. The applicant may continue.",
        "fart": "I've written it down. I have written down exactly and only what you said, "
                "{mangled}, which is the whole of my professional obligation under Form 12-B. "
                "The window does not open. It never has.",
        "none": "Noted. Filed. Gone. …Line four of Form 12-B is for the applicant's own "
                "account of themselves, and I have long suspected it is the only line anyone "
                "reads. We'll move on.",
    },
    "five_years": {
        "handshake": "“{answer}.” …Five years is a long horizon for a man who cannot "
                     "presently reach his own stapler. Line six requires me to assess "
                     "FEASIBILITY, {mangled}, and I am assessing it one-handed.",
        "seated": "“{answer}.” …Ambition, from a chair, at nine-forty in the morning. "
                  "The Authority logs that under line six and, historically, does nothing "
                  "further with it.",
        "stare": "The applicant says “{answer}” without breaking eye contact with the "
                 "present. I am recording it verbatim because I do not know how else to record "
                 "it. Line six. Annexed.",
        "fart": "“{answer}.” …The previous driver said something remarkably similar, and "
                "his medical file is still on this desk, open, where he left it. Line six.",
        "none": "“{answer}.” …In Fairweather the council has not reached quorum in "
                "twenty-two years, so I would call that ambitious and file it under line six.",
    },
    "hypothetical": {
        "handshake": ["That is an answer. It is also, and I want to be precise here, an "
                      "answer given while holding the hand of the man grading it. …Form "
                      "12-B(iii). The incident annex. Where all the good ones end up.",
                      "Recorded, and recorded one-handed. …The annex has a column for "
                      "confidence and a column for judgement, {mangled}, and they are not the "
                      "same column. I have filled in one of them."],
        "seated": ["Delivered calmly, from a seated position. …The Authority's position "
                   "is that anything of this kind is covered under the “it happens” "
                   "guarantee, which covers nothing. Annexed.",
                   "Answered without rising, without pausing, and without a single clarifying "
                   "question. …Annexed under 12-B(iii), and the form moved slightly further "
                   "from the coffee."],
        "stare": ["The applicant does not appear to consider this a hypothetical. …I am "
                  "noting the applicant's certainty in the margin of 12-B(iii), where there is "
                  "room, because there is always room.",
                  "The applicant answers immediately, and without blinking. I am dictating both "
                  "of those facts into the annex, in that order, and underlining the second."],
        "fart": ["Understood. …Fairweather has had guardrails pending Bridge Fund "
                 "approval since before I was assigned to this department. Your answer changes "
                 "nothing about that and I have annexed it anyway.",
                 "Noted, annexed, filed under 12-B(iii). …The ventilation remains a matter "
                 "for an entirely different form, and I will not be raising it."],
        "none": ["…Mm. Every applicant answers that one, and every applicant answers it "
                 "differently, and the situation is what it is either way. Form 12-B(iii). "
                 "Annexed.",
                 "Annexed. …I ask these because 12-B(iii) exists and something has to go in "
                 "it. What goes in it has never once changed what happens on the road."],
    },
    "town_motto": {
        "handshake": "“{answer}.” …Read back for the record, and now on line eleven in "
                     "ink. I would shake your hand on it, {mangled}, but we appear to have that "
                     "portion of the interview well in hand already.",
        "seated": "“{answer}.” …I have written that on line eleven exactly as you said "
                  "it, which is my whole obligation and none of my opinion. You did it without "
                  "standing up. The Department of Public Safety would call that best practice, "
                  "if there were more than three of them.",
        "stare": "The applicant recites: “{answer}.” The applicant does not blink while "
                 "reciting it. I have marked line eleven complete and moved my chair back "
                 "approximately four inches, which I will not be putting in the file.",
        "fart": "“{answer}.” Line eleven, complete. …The motto was adopted by a vote in "
                "which most of the ballots were never delivered, which tells you everything "
                "about how this town handles a thing it cannot take back.",
        "none": "“{answer}.” …Noted, verbatim. The motto was adopted by a vote in which "
                "most of the ballots were never delivered, and it has never once been "
                "revisited. Line eleven. Complete.",
    },
    "gary": {
        "handshake": "…Yes. Well. I'm going to write “Gary” on line fourteen and "
                     "then I'm going to write nothing else on line fourteen. My hand is "
                     "otherwise engaged, {mangled}, and my other hand is engaged with you.",
        "seated": "Line fourteen. …The Gary Sighting Log is the only civic record in "
                  "Fairweather that has never once had an entry removed. I am not adding to it "
                  "today. Noted.",
        "stare": "The applicant discusses Gary at length and without blinking, and I would "
                 "remind the applicant — the applicant is taught this before reading — "
                 "don't run, don't stare, don't wave. Two of three. Line fourteen. Annexed.",
        "fart": "Mm. …Gary is not banned from riding. Gary is banned from being "
                "acknowledged, which is a distinction the Authority spent a full council session "
                "on in a year when quorum still happened. Line fourteen. Noted.",
        "none": "Noted. …Nobody in Fairweather has ever seen Gary arrive. Only leave. That "
                "is the entirety of what line fourteen is permitted to contain and I have "
                "contained it. Moving on.",
    },
    "any_questions": {
        "handshake": "“{answer}” …A fair question, and I will answer it as fully as I am "
                     "able, which is to say I will cite Form 40 and stop. Form 40. We are still "
                     "holding hands, {mangled}. I have made my peace with it.",
        "seated": "“{answer}” …Genuinely a good question. The answer lives in Form 40, "
                  "which nobody in this building has seen since the shredder was installed, and "
                  "the shredder was installed by the Mayor's Office, and we share it.",
        "stare": "The applicant asks: “{answer}” The applicant asks it directly INTO me. "
                 "…I am dictating that into the annex verbatim and referring the applicant "
                 "to Form 40. That concludes the questions portion.",
        "fart": "“{answer}” …That is the one everyone asks, and it is the one Form 40 "
                "exists in order not to answer. I would open a window for the discussion, but I "
                "have explained the window. Noted. Filed. Gone.",
        "none": "“{answer}” …Form 40 covers that. Form 40 has covered that since 1962, "
                "and nobody has produced a copy of Form 40 in my eleven years in this "
                "department. Consider yourself answered.",
    },
}

# Flag-conditioned clauses, appended to a bank reply when the flag is set. These
# are what keep the offline run feeling reactive rather than canned.
FLAG_CLAUSES = {
    "admitted_no_license": "Line nine remains blank. I am choosing to read that as modesty.",
    "acknowledged_the_bus_in_the_wall": "You mentioned the bus. …I have not.",
    "insulted_the_town": "Fairweather thanks you for your candour. Fairweather is being polite.",
    "mentioned_bridge": "The Bridge Fund has been almost fully funded for eleven consecutive "
                        "years. Please do not ask to see the bridge.",
    "knows_gary_fate": "You appear to know something about Gary. That is now a matter for the "
                       "Sighting Log, and the Sighting Log never removes an entry.",
    "showed_genuine_enthusiasm": "Enthusiasm. …I'll note it. It doesn't survive the first "
                                 "shift, but I'll note it.",
}

# Escalating handshake commentary, indexed by handshake_duration_turns.
HANDSHAKE_ESCALATION = {
    2: "We are still shaking hands.",
    3: "We are, I observe, still shaking hands.",
    4: "I am now completing Form 12-B one-handed. It is going about as you would expect.",
    5: "I have stopped expecting this to end. That is not a complaint, it is a filing decision.",
    6: "I have begun to wonder how I will drive home. …I have begun to wonder whether you "
       "will be driving me home.",
    7: "The Authority has no form for this. I have checked. I checked twice.",
}

STARE_ESCALATION = {
    3: "The applicant has not blinked. I am noting the duration.",
    5: "The applicant continues not to blink. I have moved my chair.",
    6: "For the record, and I am dictating this: the applicant is still there.",
}

FART_ATMOSPHERE = [
    "The ventilation was condemned in 2004.",
    "The coffee has not helped.",
    "I want it on the record that the previous driver's medical file is open on this desk, and "
    "has been for some time.",
    "The window does not open. It never has.",
]


_QUOTED = re.compile("[\u201c\"]([^\u201d\"]{3,120})[\u201d\"]")


def _remembered(ledger, turn_seed):
    """Reach into the file and read something back.

    Hearing your own typed words returned to you is the joke, so an actual
    quotation is always preferred. The ledger's third-person prose ("Player would
    put the bus into a wall") reads like a database row when dropped straight
    into dialogue, so it gets its own, more clerical, set of framings.
    """
    facts = ledger.get("facts_established", [])
    quotes = []
    for fact in facts:
        found = _QUOTED.search(fact)
        if found:
            quotes.append("\u201c%s\u201d" % found.group(1).strip())
    if quotes:
        return QUOTE_CALLBACKS[turn_seed % len(QUOTE_CALLBACKS)] % quotes[turn_seed % len(quotes)]

    plain = [f for f in facts if f.startswith("Player")]
    if not plain:
        return None
    return FILE_CALLBACKS[turn_seed % len(FILE_CALLBACKS)] % plain[turn_seed % len(plain)]


# Used when the remembered thing is something the applicant actually typed.
QUOTE_CALLBACKS = [
    "I have it in front of me. %s \u2026Your words. Still in the file. Everything is.",
    "You said, and I am reading it back exactly: %s \u2026The file does not forget, and "
    "increasingly, neither do I.",
    "Cross-referencing. %s \u2026Consistent so far. I note that with the caution it deserves.",
    "%s \u2026I am reading that back so that we are both equally responsible for it.",
]

# Used when all the file has is the Authority's own account of what you did.
FILE_CALLBACKS = [
    "The file has this on line four: %s \u2026It stays there.",
    "Noted earlier, and still noted: %s",
    "I am looking at an entry from some minutes ago. %s \u2026Nothing has come along to "
    "displace it.",
]


def _echo(answer):
    """The echo templates supply their own closing full stop."""
    text = (answer or "").strip()
    return text.rstrip(".… ") or "nothing at all"


def bank_reply(question_id, ledger, turn_seed=0, answer=None):
    """Compose a reactive fallback reply from pose, flags, and physical state."""
    pose = ledger.get("pose", "none")
    table = BANK.get(question_id, BANK["about_yourself"])
    reply = table.get(pose) or table.get("none")
    if isinstance(reply, (list, tuple)):          # several phrasings for one beat
        reply = reply[turn_seed % len(reply)]

    name = ledger.get("player_name", "APPLICANT")
    reply = (reply.replace("{name}", name.title())
                  .replace("{mangled}", mangle_name(name, turn_seed))
                  .replace("{answer}", _echo(answer)))

    extras = []
    ps = ledger["physical_state"]

    if ps.get("hand_still_gripped"):
        duration = ps.get("handshake_duration_turns", 0)
        line = HANDSHAKE_ESCALATION.get(duration)
        if line:
            extras.append(line)
    if pose == "stare":
        line = STARE_ESCALATION.get(ps.get("eye_contact_unbroken_turns", 0))
        if line:
            extras.append(line)
    if ps.get("farted") and turn_seed >= 2:
        extras.append(FART_ATMOSPHERE[turn_seed % len(FART_ATMOSPHERE)])

    for flag, clause in FLAG_CLAUSES.items():
        if ledger["flags"].get(flag) and len(extras) < 2:
            extras.append(clause)

    # From the back half onward he starts reaching into the file unprompted.
    if turn_seed >= 5:
        remembered = _remembered(ledger, turn_seed)
        if remembered:
            extras.insert(0, remembered)

    contradiction = detect_contradiction(ledger)
    if contradiction:
        extras = [contradiction]

    if extras:
        reply = "%s %s" % (reply, " ".join(extras[:2]))
    return reply


def standout_quote(ledger):
    """The one thing the applicant typed that the Authority wants on the record.

    Deterministic, so the same interview always closes on the same line. Ranked
    by which question tends to produce the most characterful answer, then by
    length, because the longer one is usually the stranger one.
    """
    preference = ["Player asked:", "Player offered an account of Gary",
                  "Player's five-year plan", "Player described themselves as",
                  "Player gave the town motto as"]
    quotes = []
    for fact in ledger.get("facts_established", []):
        found = _QUOTED.search(fact)
        if not found:
            continue
        rank = next((i for i, pref in enumerate(preference) if fact.startswith(pref)),
                    len(preference))
        quotes.append((rank, -len(found.group(1)), found.group(1).strip()))
    if not quotes:
        return None
    return sorted(quotes)[0][2]


STANDOUT_FRAMINGS = [
    "NOTED FOR THE FILE: the applicant said, “%s” It stays on line four.",
    "ENTERED VERBATIM: “%s” The Authority has no follow-up.",
    "ON THE RECORD: “%s” This was not asked for and has been kept anyway.",
    "RETAINED: “%s” Nobody will read this. It is retained regardless.",
]


def _terminated(text):
    """Exactly one closing mark, whatever the applicant typed."""
    text = text.rstrip(" ")
    return text if text and text[-1] in ".?!…" else text + "."


def standout_line(ledger, seed=0):
    quote = standout_quote(ledger)
    if not quote:
        return None
    return STANDOUT_FRAMINGS[seed % len(STANDOUT_FRAMINGS)] % _terminated(quote)


# --- endings ----------------------------------------------------------------

SCORED_LINE_LABELS = [
    ("candor", "CANDOUR"),
    ("hazard_awareness", "HAZARD AWARENESS"),
    ("bureaucratic_compliance", "PROCEDURAL COMPLIANCE"),
]

# Recorded on the card, remarked upon, and deliberately not counted.
NOTED_LINE_LABELS = [
    ("delusion", "DELUSION", "DEDUCTED"),
    ("physical_comedy", "PHYSICAL CONDUCT", "NO BOX FOR THIS"),
]

ACCURACY_TIERS = ["AWFUL", "BAD", "OK", "GOOD", "PERFECT"]

# The Awful-to-Perfect ladder is for things being *assessed*. The two recorded
# lines are not assessed, so they get the Authority's own descriptions instead:
# a note about what was observed, not a mark out of five.
CONDUCT_NOTES = ((-1, "EXEMPLARY"), (0, "NONE NOTED"), (2, "MINOR"),
                 (4, "NOTED"), (5, "REMARKABLE"))
DELUSION_NOTES = ((0, "GROUNDED"), (2, "MILD"), (4, "PRONOUNCED"), (5, "TOTAL"))


def _note_for(value, table):
    for ceiling, label in table:
        if value <= ceiling:
            return label
    return table[-1][1]


def conduct_note(value):
    """What the Authority writes in the box it does not have."""
    return _note_for(value, CONDUCT_NOTES)


def delusion_note(value):
    return _note_for(value, DELUSION_NOTES)


def tier_for(value):
    """Map a -5..+5 meter onto the GDD's Awful->Perfect accuracy ladder."""
    idx = int(round((value + 5) / 10.0 * (len(ACCURACY_TIERS) - 1)))
    return ACCURACY_TIERS[max(0, min(len(ACCURACY_TIERS) - 1, idx))]


# The GDD's sign-off lines are written for an end-of-shift receipt — passengers
# delivered, property values adjusted, damages forwarded to the Bridge Fund. None
# of that has happened yet; nobody has driven anything. So the card closes on the
# assessment instead, in the same flat municipal register, keyed to the grade.

GRADE_BLURBS = {
    "A": [
        "Exemplary. The Authority has no notes. That absence is itself a note.",
        "An unusually strong assessment. It will be filed with the others.",
    ],
    "B": [
        "Satisfactory. You will be issued a bus. The bus will be issued conditions.",
        "Above the line. The line is not high. The form records only which side.",
    ],
    "C": [
        "Adequate. The median is what keeps the route running.",
        "Neither a concern nor a credit. The Authority finds this restful.",
    ],
    "D": [
        "The Authority has seen worse. It keeps a log of worse. You are not in it.",
        "Below expectation. Expectation here has been revised downward eleven times.",
    ],
    "F": [
        "This will be filed. Filing is not reading. I want that understood.",
        "The form has a box for this. I have never used it. It took a moment to find.",
    ],
}

# Two states the grade alone does not capture.
ABANDONED_BLURB = ("Assessment incomplete. Fairweather thanks you for your effort. "
                   "Fairweather is being polite.")
RECORD_BLURB = ("Highest physical conduct on file. The Authority is obliged to "
                "acknowledge it.")


def grade_blurb(grade, seed=0, abandoned=False, record=False):
    """One closing line, chosen by grade band rather than by shift outcome."""
    if abandoned:
        return ABANDONED_BLURB
    if record:
        return RECORD_BLURB
    pool = GRADE_BLURBS.get(grade[0].upper(), GRADE_BLURBS["C"])
    return pool[seed % len(pool)]

HIRED_LINE = "You are hired. The drivers keep dying."

CLOSING_STAMPS = {
    "commendation": "COMMENDATION",
    "personal_best": "PERSONAL BEST",
}

FAREWELL_CARD = [
    "A wise decision. Statistically.",
    "Fairweather Transit thanks you for not getting on da bus.",
]

# Shown once the server has actually gone, so the card reads as finished rather
# than as a stall.
# Shown only when the application itself is shutting down.
FAREWELL_CLOSED = [
    "The Authority is closing the office.",
    "You may close this window. Form 12-B has been filed under H, for later.",
]


# --- the manager reads your name back ---------------------------------------
# He gets it wrong immediately and never comments on doing so. This is served
# from the bank rather than the model: it happens before turn 1, and it should
# be instant.

NAME_ACKNOWLEDGEMENTS = [
    "{mangled}. …Noted. That is not what the sheet says, but the sheet has a ring on it, "
    "and the ring got there first. Form 12-B, line one.",

    "…{mangled}. Spelled the way you say it, or spelled the way the Authority already "
    "has it. Those are the two options and only one of them is available.",

    "{mangled}. Filed under the wrong letter, which is where I file everyone. It has "
    "never once caused a problem that anyone told me about.",

    "…{mangled}. Good. Strong name. …The previous driver had a name like that. "
    "Form 12-B, line one.",

    "{mangled}, then. I'll write it here, and then I'll write it differently further "
    "down, and the Authority will decide between them in its own time.",

    "…{mangled}. I heard you. I want to be clear that hearing you and recording you "
    "correctly are separate lines on this form, and I am only obliged to do the one.",
]


def name_acknowledgement(name):
    seed = int(hashlib.md5(("ack" + (name or "")).encode("utf-8")).hexdigest()[:8], 16)
    line = NAME_ACKNOWLEDGEMENTS[seed % len(NAME_ACKNOWLEDGEMENTS)]
    return line.replace("{mangled}", mangle_name(name, "greeting")).replace(
        "{name}", (name or "APPLICANT").title())
