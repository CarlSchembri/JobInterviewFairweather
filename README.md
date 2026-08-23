# Job Interview at Fairweather Transit

A single-scene Sierra-style adventure game. You are applying for a bus driver
position with the Fairweather Transit Authority. The manager has not slept in a
very long time. Python serves it, the browser draws it, and a Claude subprocess
writes his half of the conversation.

Assignment 8 — Narrative Engine Prototype.

---

## For the grader, in one screen

| The brief asks for | Where it is |
|---|---|
| A description of the world | [§1 The world](#1-the-world) |
| What the ledger tracks | [§2 What the ledger tracks](#2-what-the-ledger-tracks) |
| One moment the agent surprised me | [§3 A moment from testing](#3-a-moment-from-testing) |
| Ledger visible in output or logs | Console prints a diff **every turn**; `ledger.json` rewritten every turn; `F1` shows it live in-game; `logs/` holds 58 session transcripts |
| Reactive to ledger, not just last input | The entire ledger JSON goes into every prompt. Play two different poses and compare turn 4 |
| Consistency over 5+ turns | Every interview runs **8 or 9 turns**. `facts_established` is append-only and never pruned |

**Python, calling Claude, two ways.** `engine/backends.py` has one function
signature and three implementations. `--backend api` is the **Claude Messages
API** — a raw `urllib` POST to `https://api.anthropic.com/v1/messages` with
`ANTHROPIC_API_KEY`, no SDK, no `pip install`. `--backend cli` shells out to the
Claude Code CLI instead, which needs no API key and is the default so the game
runs on a machine that has Claude Code but no billing set up. Both return the
same string to the same parser. `--backend none` plays the whole game from a
hand-written response bank with no model at all.

**Fastest way to see it working:** run it, take `SHAKE HAND` on turn 1, claim
some years of experience on turn 2, and watch the console. Every turn prints
which ledger fields changed, and the manager stops being able to talk about
anything else.

---

## 1. The world

Fairweather is a sleepy hill town founded in 1962 by a bus company that arrived
before the town did. Every bridge in it collapsed years ago, and the city cannot
afford to rebuild them — so the Fairweather Transit Authority instituted Express
Delivery, on the reasoning that if you cannot drive a passenger all the way
around, you can at least launch them the last hundred feet. The town motto,
"You'll Get There Eventually," was adopted after a vote in which most ballots
were never delivered. The Bridge Fund has been almost fully funded for eleven
consecutive years.

The Transit Authority shares a building, a budget and a shredder with the Mayor's
Office. It is hiring, and it is hiring urgently, because the drivers keep dying —
a fact stated exactly once in this game and never elaborated on. The man
conducting your interview has been in the wrong department for eleven years. He
is not cruel and he is not zany. He is narrating a slow disaster in the register
of a man reading out a form, and the form is 12-B.

A school bus has come through the left wall of his office at an angle. Its front
bumper reaches almost to his desk. He will not mention it unless you do.

All of the above was mined from the project's `GDD.md` at build time and written
into `world_bible.md`, which is the **only** lore the running game reads. The
prototype never touches a path outside its own folder at runtime — copy the
folder anywhere on disk and it still runs.

### The shape of an interview

Eight or nine turns, and not the same eight twice. The fixed beats always
appear — the greeting that locks your pose, tell me about yourself, where you
see yourself in five years, the town motto, Gary, and any questions for me — and
two or three **hypotheticals are drawn from a pool of six**: the brakeless
descent of Switchback Ridge, a dispatch order to cross a bridge that isn't
there, a passenger who has been aboard two hours and will not name a
destination, a fare box on fire eleven stops from the depot, arriving eleven
minutes early, and a cow.

Five of the beats are **typed rather than picked**, and the manager reads your
own words back to you: what you said about yourself, your five-year plan, the
motto exactly as you recited it, whatever you claim to know about Gary, and
whatever you ask him at the end. Those verbatim answers go into
`facts_established` in quotation marks, which is what lets him quote them at you
six turns later — and what lets the report card close by entering one of them
into the record.

`content.build_interview()` assembles the sequence and numbers the turns, so the
length is free to vary — nothing downstream assumes a fixed count.

---

## 2. What the ledger tracks

`ledger.json` is the single source of truth, and it is rewritten to disk after
every single turn, so you can leave the file open during a demo and watch it
change. Five sections:

**`physical_state`** — what your body is doing. Turn 1 locks a pose for the whole
game, and the pose is a *rendering* fact rather than a text fact: it changes the
base sprite composition of every frame afterwards. `hand_still_gripped`,
`handshake_duration_turns`, `seated`, `farted`, `eye_contact_unbroken_turns`,
`left_early`.

**`facts_established`** — an append-only list of short third-person statements.
Nothing is ever deleted from it. This is the thing that enforces consistency:
the whole list goes into every prompt, so a claim made in turn 2 is still sitting
there in turn 7.

**`flags`** — eight booleans that latch on and never off (`asked_about_gary`,
`admitted_no_license`, `acknowledged_the_bus_in_the_wall`, and so on). The model
can set them but cannot un-set them; it doesn't get to make the manager forget.

**`meters`** — five integers clamped to −5..+5. Each choice carries a
deterministic baseline delta that is applied whatever the backend does, and the
model may nudge them by at most ±2 per turn. The model never supplies a grade,
so the same answers always produce the same grade.

Only **three** of them are assessed — `candor`, `hazard_awareness` and
`bureaucratic_compliance` — with `delusion` subtracted, giving a score from −20
to +20 that maps onto the GDD's fifteen-tier ladder. `physical_comedy` is
recorded, remarked upon, and deliberately **not scored**: the Authority has no
box for what you did. That is the joke, and it also means the funniest choice in
the game never costs you the grade. The report card shows the arithmetic — three
scored lines, an assessed total, then the two it wrote down anyway under
`RECORDED. NOT SCORED.`

**`answers`** — one entry per turn, each tagged `"source": "cli" | "api" | "bank"`.
This matters more than it sounds: a mid-session timeout silently falls through to
the response bank, and without the tag you cannot tell which lines were generated
and which were canned. The same tag is written into `transcript.txt` on every
manager line, and the console prints a count of each at the end of the session.

### Three concrete examples of a tracked fact changing later dialogue

- **`hand_still_gripped`.** Take the manager's hand in turn 1 and you never let
  go. By `handshake_duration_turns` 4 he is completing Form 12-B one-handed; by 6
  he has stopped expecting it to end and has begun working out how he will drive
  home. Both sprites stay arm-linked across the desk in every frame from turn 1
  onward, including while his other hand does paperwork.
- **A claim of experience versus `admitted_no_license`.** Say you have eleven
  years' experience in turn 2 and then admit you have no licence in turn 6, and
  the manager cross-references `facts_established` and comments on the
  discrepancy without breaking the deadpan. This is caught by the engine itself
  in `content.detect_contradiction()`, so it fires on the response bank too —
  it does not depend on the model noticing.
- **`pose == "stare"`.** Stand there unblinking and he starts narrating his own
  discomfort out loud, then shifts to talking about you in the third person as
  though dictating a report. He also gets your name wrong a different way every
  single turn, because `player_name` is folded into the prompt with an
  instruction to misfile it.

### Seeing the ledger

Three ways, on purpose:

1. **Console diff, every turn, unconditionally** — turn number, the action taken,
   and each changed field in `old -> new` form.
2. **`ledger.json` on disk** — rewritten atomically after every turn.
3. **`F1` in game** — a scrolling monospace pretty-print of the live JSON in the
   corner of the screen.

---

## 3. A surprise moment from testing


I had put in some instructions to get the interviewee's name a little wrong each time.   What I did not ask for was a filing clerk.

I typed `CARL` for the name. The manager called me Carla for two turns. Then, on turn three, in the
middle of a sentence about the DAYS SINCE INCIDENT board...

> "The board behind me reads zero days since incident, Carl — **Karl, the sheet
> now insists, someone has crossed out Carla** — and it will read zero again
> tomorrow regardless of what you decide here."

And then he called me Karl for the remaining five turns and never said Carla
again.

The instruction in the style block was *get the name wrong, differently each
time*. Nothing tells it to remember which wrong versions it has already used,
and nothing tells it to explain the inconsistency. It invented an off-screen
third party amending the form — there is no clerk in `world_bible.md` —
and then treated that invention as binding for the rest of the session. It took
a rule about being unreliable and gave the unreliability a consistency.

The full run is in `logs/20260823-135256_handshake.txt`.


---

## 4. Rubric mapping

| Criterion | Where it lives | How to see it |
|---|---|---|
| State Tracking (4.0) | `engine/ledger.py`, `ledger.json` | Console diff every turn, F1 overlay, file on disk |
| Reactive Dialogue (3.0) | `engine/interviewer.py` §4 rules | Play two poses and compare turn 4 |
| Consistency (2.0) | append-only `facts_established` | The contradiction run in `logs/` |
| ReadMe (1.0) | this file | — |

---

## 5. Running it

```bash
python game.py
```

That starts a local HTTP server, prints the URL, and opens your default browser.
**No `pip install` is required** — the entire thing is Python standard library
(`http.server`, `json`, `subprocess`, `webbrowser`, `threading`, `argparse`,
`urllib`). There is no `requirements.txt` because there is nothing to require.

| Flag | What it does |
|---|---|
| `--no-llm` | Skip the subprocess entirely. Every line comes from the hand-written response bank. Plays start to finish with no CLI installed. |
| `--backend cli` | Force the Claude Code CLI backend (`claude -p`). This is the default when `claude` is on your PATH. |
| `--backend api` | Force the raw `urllib` Messages API backend, reading `ANTHROPIC_API_KEY` from the environment. No `pip install anthropic`. If the key is missing it prints one line and falls back to `cli`. |
| `--backend none` | Same as `--no-llm`. |
| `--port N` | HTTP port. Default `8137`. |
| `--patience N` | Seconds to wait for a live reply before serving that turn from the bank. Default 20. |
| `--debug` | Verbose subprocess, prompt and raw-output logging to the console. |
| `--no-browser` | Don't open a browser. Useful when driving the HTTP API directly. |

The game auto-detects the best backend at startup — `claude` on PATH first, then
`ANTHROPIC_API_KEY`, then the bank — and prints the result in one unmissable
line. An explicit `--backend` always wins.

**Windows note.** If `python` opens the Microsoft Store instead of running,
use `py game.py`. Windows ships a stub named `python.exe` that does that when
no real Python is on the PATH ahead of it.

### Or just double-click it

**`FairweatherTransit.exe` is already in this repository.** Download or clone,
double-click it, and the game starts its own server and opens your browser. No
Python install, no terminal, no `pip`.

> **Windows will warn you about it.** Executables downloaded from the internet
> get flagged by SmartScreen: *"Windows protected your PC."* Click **More info →
> Run anyway**. The file is a PyInstaller bundle of the Python source sitting
> next to it in this repo — you can read every line of what it runs, or skip it
> entirely and use `python game.py`, which needs no build at all.

To rebuild it yourself:

```bash
python -m pip install pyinstaller && python build_exe.py
```

That writes `FairweatherTransit.exe` beside the source. PyInstaller is a
**build-time tool only** — the executable it produces still has zero runtime
dependencies, and `python game.py` keeps working exactly as before.

The console window that opens alongside the game is deliberate: the per-turn
ledger diff prints there and it is grading evidence, so it has to stay visible.
Closing it closes the game. `ledger.json`, `transcript.txt` and `logs/` are
written next to the executable rather than into the temporary unpack directory
PyInstaller wipes on exit, so the evidence lands somewhere you can find it.

**In-game keys:** arrows / `1`–`4` / `Enter` to choose, click or `Space` to skip
the typewriter, `F1` to toggle the live ledger overlay, `PgDn` to scroll it. The
`EXIT` sign above the door is clickable on every turn, including while a reply
is still being generated.

**Leaving versus quitting are two different things.** `GO HOME` on the report
card leaves the office: you get a farewell card and then you are back at the
title, with the game still running. `DON'T GET ON DA BUS` on the title screen is
the one that closes the application — it shuts the server down so the Python
process actually exits, and the card waits for the server to go before saying
`THE OFFICE IS CLOSED`, so it reads as finished rather than stuck. The `EXIT`
sign mid-interview also returns you to the title.

---

## 6. How it is put together

```
game.py            server, routing, per-turn ledger persistence, transcript
world_bible.md     canon extracted from the GDD at build time — the only lore source at runtime
engine/
  ledger.py        schema, validation, safe merge, diffing, the grade formula
  backends.py      cli / api / none — one signature, swappable
  interviewer.py   prompt assembly, defensive JSON parse, fallback, endings
  content.py       questions, choices, persona block, the fallback response bank
logs/              per-session transcripts from playtesting
static/            index.html, game.js (state machine), render.js (all the art), style.css
ledger.json        rewritten every turn
transcript.txt     human-readable session log, source-tagged per line
```

Each manager reply is one call assembled from a persona block, the verbatim
ledger JSON, the last four exchanges, the question and your exact answer, and an
output contract demanding a single JSON object. Parsing strips markdown fences,
finds the outermost `{...}` by brace matching with string-awareness, and
`json.loads`. Any failure at any point — unparseable output, a raising backend, a
missing CLI, a timeout — routes to the response bank without crashing or stalling
the dialogue box. The bank is not a degraded mode: it keys on pose and on the
load-bearing flags, with at least four variants per question plus escalating
handshake and stare commentary, so an offline playthrough still reads as authored.

The model can only ever propose *deltas*. `ledger.py` validates and merges them,
and an unknown key, a wrong type or an out-of-range value is dropped silently
while the rest of the payload is kept. The model cannot corrupt the ledger, can
not overwrite `session_id` or `turn`, and cannot un-set a flag.

Nothing visual is loaded from disk. There are no image files, no sprite sheets,
no CDN links and no web fonts. Every frame — the crashed bus, the thirty-plus
coffee cups, both figures, the 5×7 text you are reading in the dialogue box — is
drawn with filled rectangles and lines into a 320×200 buffer out of sixteen
hard-coded EGA hex constants, then blitted to the visible canvas with
`imageSmoothingEnabled = false`.

### Two things that differ from a naive reading of the spec

Both were forced by measurement, and both are commented at the point of the
change:

- **Long prompts go to the CLI on stdin, not as an argv.** The spec's
  `subprocess.run(["claude", "-p", prompt])` is still the path taken for prompts
  under 7000 characters. Real prompts here run about 17KB, and on Windows the
  `claude` command is a `.CMD` shim: `cmd.exe` truncates any command line over
  8191 characters, so the argv form fails outright. Over the threshold the prompt
  is piped in instead. Same backend, same parser, same output.
- **The 20-second fall-through deadline raises itself once.** The spec assumes a
  3–8 second call. A fixed 20s deadline would send *every* turn to the bank if
  the machine is slower than that, and the live backend would never be used at
  all. So the default stays at 20, and the first call that overruns it teaches
  the engine what this machine is actually like: the abandoned worker is still
  timed, and the deadline rises to cover the next turn. `--patience N` pins it
  up front and skips the learning turn.

### The warm interviewer

`claude -p` cost about 37 seconds a turn on the machine this was built on, and
roughly 20 of those were process startup rather than generation — so two of
seven turns were still falling through to the bank on a good run, and the wait
was long enough to drive a player off.

It turns out `claude -p` boots *lazily* — spawning it does nothing until the
first message arrives — but the second message on the same process comes back in
about six seconds. So the game now spawns one in `--input-format stream-json`
mode at launch and immediately feeds it the persona block and the world bible,
the half of the prompt that never changes, while the player is still on the
title screen. Every real turn then sends only the ledger and the question.

Measured on the same machine: **37s → 5.2s a turn, with 7 of 7 served live and
nothing falling through to the bank.** A new applicant gets a new process so the
previous ledger cannot linger in the session, except that an already-warmed,
never-used one is reused rather than thrown away — otherwise the first turn of
the first interview would pay full startup for nothing. If any of it fails the
call drops back to a one-shot `claude -p`, and from there to the bank; it can
only ever be faster. `--no-warm` disables it entirely.

The subprocess is also run in an empty scratch directory rather than in place,
which keeps the manager's prompt hermetic and cut about twelve seconds per call
on its own.
