#!/usr/bin/env python3
"""Job Interview at Fairweather Transit — server, routing, ledger persistence.

    python game.py                 # auto-detect the best backend
    python game.py --no-llm        # response bank only
    python game.py --backend api   # force the raw-urllib Messages API backend
    python game.py --port 9000
    python game.py --debug         # verbose subprocess / prompt logging

Standard library only. No pip install required.
"""

import argparse
import datetime
import json
import mimetypes
import os
import posixpath
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from engine import backends, content, interviewer
from engine import ledger as ledger_mod

# Two different roots, because a PyInstaller build separates them. Running from
# source they are the same directory and nothing changes.
#
#   BASE_DIR   read-only assets — static/ and world_bible.md. When frozen these
#              are unpacked into a temp folder that is wiped on exit.
#   OUTPUT_DIR everything the game writes — ledger.json, transcript.txt, logs/.
#              When frozen this is the folder the .exe sits in, so the grading
#              evidence lands somewhere the player can actually find it.
BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
              else os.path.dirname(os.path.abspath(__file__)))

STATIC_DIR = os.path.join(BASE_DIR, "static")
LOGS_DIR = os.path.join(OUTPUT_DIR, "logs")
LEDGER_PATH = os.path.join(OUTPUT_DIR, "ledger.json")
TRANSCRIPT_PATH = os.path.join(OUTPUT_DIR, "transcript.txt")


class Session:
    """One interview. The whole game is single-player and local, so one is enough."""

    def __init__(self):
        self.reset("APPLICANT")

    def reset(self, name):
        # Each interview draws its own sequence, so the hypotheticals differ and
        # the length varies. Nothing downstream may assume a fixed turn count.
        self.questions = content.build_interview()
        self.by_id = {q["id"]: q for q in self.questions}
        self.ledger = ledger_mod.new_ledger(name)
        self.history = []
        self.source_counts = {"cli": 0, "api": 0, "bank": 0}
        self.finished = False
        self.transcript_lines = []


SESSION = Session()
CONFIG = {"backend": "none", "live": False, "available": {}, "debug": False,
          "warm": True}


# --- transcript -------------------------------------------------------------

def transcript_write(line):
    SESSION.transcript_lines.append(line)
    with open(TRANSCRIPT_PATH, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def transcript_begin(led):
    header = [
        "=" * 74,
        "JOB INTERVIEW AT FAIRWEATHER TRANSIT",
        "session %s   applicant: %s   backend: %s" % (
            led["session_id"], led["player_name"], CONFIG["backend"]),
        "=" * 74,
    ]
    with open(TRANSCRIPT_PATH, "w", encoding="utf-8") as handle:
        handle.write("\n".join(header) + "\n")
    SESSION.transcript_lines = list(header)


def save_log(led):
    """Copy the finished transcript into logs/ tagged with the pose."""
    os.makedirs(LOGS_DIR, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    pose = led.get("pose", "none")
    if led["physical_state"].get("left_early"):
        pose += "-earlyexit"
    path = os.path.join(LOGS_DIR, "%s_%s.txt" % (stamp, pose))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(SESSION.transcript_lines) + "\n\n")
        handle.write("--- FINAL LEDGER ---\n")
        handle.write(json.dumps(led, indent=2, ensure_ascii=False) + "\n")
    return path


def print_source_summary():
    counts = SESSION.source_counts
    total = sum(counts.values())
    print("")
    print("+-- SESSION SUMMARY ---------------------------------------")
    print("|   turns served: %d" % total)
    for key in ("cli", "api", "bank"):
        print("|     %-5s %d" % (key + ":", counts[key]))
    print("|   grade: %s" % SESSION.ledger["running_grade"])
    print("+----------------------------------------------------------")


# --- turn processing --------------------------------------------------------

def resolve_answer(question, payload):
    """Turn a client payload into (label, text, choice_dict|None)."""
    if question["format"] == "text":
        text = ledger_mod.sanitize_text(payload.get("text", ""), question.get("max_length", 60))
        return (text or "(no answer)"), text, None
    choice_id = payload.get("choice_id")
    for choice in question["choices"]:
        if choice["id"] == choice_id:
            return choice["label"], None, choice
    fallback = question["choices"][0]
    return fallback["label"], None, fallback


def play_turn(question, payload):
    before = ledger_mod.snapshot(SESSION.ledger)

    # Work on a detached copy for the whole turn. A live call can be in flight
    # for the better part of a minute, and the EXIT sign stays clickable that
    # entire time — so if the player leaves mid-call, the turn is thrown away
    # instead of landing in a ledger that already records them as gone.
    led = ledger_mod.snapshot(SESSION.ledger)

    label, text, choice = resolve_answer(question, payload)
    led["turn"] = question["turn"]

    # 1. Deterministic, engine-authored ledger movement. This runs on every
    #    backend, which is what keeps the grade reproducible and the consistency
    #    checks alive when the model is absent.
    if choice:
        if choice.get("pose"):
            ledger_mod.lock_pose(led, choice["pose"], question["turn"])
        ledger_mod.add_fact(led, choice.get("fact", ""))
        ledger_mod.apply_meters(led, choice.get("meters"))
        for flag, value in (choice.get("flags") or {}).items():
            if value:
                led["flags"][flag] = True
    else:
        facts, flags, meters = content.read_free_text(question["id"], text)
        for fact in facts:
            ledger_mod.add_fact(led, fact)
        for flag, value in flags.items():
            if value:
                led["flags"][flag] = True
        ledger_mod.apply_meters(led, meters)

    if question["turn"] > 1:
        ledger_mod.advance_physical_state(led)

    # 2. The reply.
    reply, updates, grade_note, callback, source = interviewer.ask(
        BASE_DIR, CONFIG["backend"], led, SESSION.history,
        question, label, text, CONFIG["debug"],
    )
    if SESSION.finished:
        print("[server] turn %d discarded — the player took the EXIT before it came back"
              % question["turn"])
        return None

    ledger_mod.merge_updates(led, updates, CONFIG["debug"])

    # The contradiction flag latches only *after* the reply exists. Setting it
    # first suppressed detect_contradiction() on the very turn it was meant to
    # fire, so the bank never got to call the discrepancy out. The conflicting
    # facts are already in the prompt either way, which is what the model reads.
    if content.detect_contradiction(led):
        led["flags"]["lied_about_something"] = True

    # 3. Record.
    SESSION.source_counts[source] = SESSION.source_counts.get(source, 0) + 1
    led["answers"].append({
        "turn": question["turn"],
        "question_id": question["id"],
        "choice": choice["id"] if choice else None,
        "text": text,
        "source": source,
    })
    ledger_mod.refresh_grade(led)

    # Commit the copy back into the live ledger, in place so every existing
    # reference to it stays valid.
    SESSION.ledger.clear()
    SESSION.ledger.update(led)
    led = SESSION.ledger

    SESSION.history.append({"answer": label if not text else text, "reply": reply})

    transcript_write("")
    transcript_write("[turn %d] %s" % (question["turn"], question["prompt"]))
    transcript_write("  %s: %s" % (led["player_name"], label if not text else text))
    transcript_write("  MANAGER (%s): %s" % (source, reply))
    if grade_note:
        transcript_write("  note: %s" % grade_note)

    ledger_mod.print_diff(before, led, "%s -> %s" % (question["id"], label), CONFIG["debug"])
    ledger_mod.save(led, LEDGER_PATH)

    return {
        "reply": reply,
        "source": source,
        "callback": callback,
        "grade_note": grade_note,
        "ledger": led,
    }


# --- HTTP -------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    server_version = "FairweatherTransit/1.0"

    def log_message(self, fmt, *args):
        if CONFIG["debug"]:
            super().log_message(fmt, *args)

    # -- helpers --
    def send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        except (ConnectionError, OSError):
            # The player closed the tab or reloaded mid-turn. The ledger is
            # already written; there is nobody left to tell.
            if CONFIG["debug"]:
                print("[server] client went away before the reply was sent")

    def send_file(self, path, content_type):
        try:
            with open(path, "rb") as handle:
                body = handle.read()
        except OSError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_payload(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return {}
        if length <= 0 or length > 64_000:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8")) or {}
        except (ValueError, UnicodeDecodeError):
            return {}

    # -- routes --
    def do_GET(self):
        route = self.path.split("?", 1)[0]
        if route in ("/", "/index.html"):
            self.send_file(os.path.join(STATIC_DIR, "index.html"), "text/html; charset=utf-8")
            return
        if route.startswith("/static/"):
            name = posixpath.basename(route)           # never escapes static/
            path = os.path.join(STATIC_DIR, name)
            if not os.path.isfile(path):
                self.send_error(404)
                return
            ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype.endswith("javascript"):
                ctype += "; charset=utf-8"
            self.send_file(path, ctype)
            return
        if route == "/api/config":
            self.send_json({
                "backend": CONFIG["backend"],
                "live": CONFIG["live"],
                "available": CONFIG["available"],
                "reasons": {
                    key: backends.reason_unavailable(key, CONFIG["available"])
                    for key in ("cli", "api", "none")
                },
                "questions": SESSION.questions,
                "intro": content.INTRO_LINES,
                "farewell": content.FAREWELL_CARD,
                "farewell_closed": content.FAREWELL_CLOSED,
                "final_turn": len(SESSION.questions),
            })
            return
        if route == "/api/ledger":
            self.send_json(SESSION.ledger)
            return
        self.send_error(404)

    def do_POST(self):
        route = self.path.split("?", 1)[0]
        payload = self.read_payload()

        if route == "/api/quit":
            self.send_json({"ok": True, "farewell": content.FAREWELL_CARD})
            print("\nGO HOME selected. Shutting down.")
            backends.warm_stop()
            print_source_summary()
            threading.Timer(1.5, self.server.shutdown).start()
            return

        if route == "/api/backend":
            # Only reachable from the title screen; the client enforces that too.
            name = payload.get("backend")
            if name in backends.BACKENDS:
                CONFIG["backend"] = name
                CONFIG["live"] = name != "none" and CONFIG["available"].get(name, False)
                print("[config] interviewer source switched to %r" % name)
            self.send_json({"backend": CONFIG["backend"], "live": CONFIG["live"]})
            return

        # Deliberately not serialised behind SESSION.lock: a turn can be in flight
        # for up to 20 seconds, and the EXIT sign has to stay live the whole time.
        try:
            if route == "/api/start":
                self.send_json(self.route_start(payload))
                return
            if route == "/api/turn":
                self.send_json(self.route_turn(payload))
                return
            if route == "/api/exit":
                self.send_json(self.route_exit())
                return
        except Exception as err:                        # noqa: BLE001 - never blank the box
            print("[server] %s: %s" % (type(err).__name__, err))
            if CONFIG["debug"]:
                import traceback
                traceback.print_exc()
            # Always hand back something the client can move on from, or the
            # interview stalls with no way forward.
            recovery = {
                "reply": "…The form has jammed. It does that. Form 12-B, line one. "
                         "We'll proceed as though nothing happened, which is policy.",
                "source": "bank",
                "ledger": SESSION.ledger,
            }
            nxt = next((q for q in SESSION.questions if q["turn"] > SESSION.ledger["turn"]), None)
            if nxt:
                recovery["question"] = nxt
            else:
                recovery["report"] = interviewer.compose_report(SESSION.ledger)
            self.send_json(recovery, status=200)
            return
        self.send_error(404)

    # -- route bodies --
    def route_start(self, payload):
        name = ledger_mod.sanitize_name(payload.get("name", ""))
        SESSION.reset(name)
        # A new applicant gets a new warm process, so no previous ledger is left
        # sitting in the session context. It primes while they read the greeting.
        if CONFIG["backend"] == "cli" and CONFIG["warm"]:
            backends.warm_ensure(interviewer.stable_prefix(BASE_DIR), CONFIG["debug"])
        led = SESSION.ledger
        transcript_begin(led)

        # He reads the name back, wrongly, before the interview starts.
        acknowledgement = content.name_acknowledgement(name)
        ledger_mod.add_fact(led, "Applicant gave the name %s." % name)
        transcript_write("")
        transcript_write("[name] %s" % name)
        transcript_write("  MANAGER (bank): %s" % acknowledgement)

        ledger_mod.print_diff(ledger_mod.new_ledger(name), led, "session start", CONFIG["debug"])
        ledger_mod.save(led, LEDGER_PATH)
        print("\nApplicant: %s   (interviewer source: %s)" % (name, CONFIG["backend"]))
        return {
            "ledger": led,
            "question": SESSION.questions[0],
            "acknowledgement": acknowledgement,
        }

    def route_turn(self, payload):
        question = SESSION.by_id.get(payload.get("question_id"))
        if question is None or SESSION.finished:
            return {"error": "unknown question", "ledger": SESSION.ledger}

        result = play_turn(question, payload)

        if result is None or SESSION.finished:
            # The player took the EXIT while this turn was still in flight. The
            # client discards this reply; the ledger never saw it at all.
            return {"discarded": True, "source": "bank", "reply": "",
                    "ledger": SESSION.ledger}

        if question["turn"] >= len(SESSION.questions):
            SESSION.finished = True
            report = interviewer.compose_report(SESSION.ledger)
            ledger_mod.save(SESSION.ledger, LEDGER_PATH)
            self.write_report_to_transcript(report)
            result["report"] = report
            result["log"] = os.path.basename(save_log(SESSION.ledger))
            print_source_summary()
        else:
            nxt = SESSION.questions[question["turn"]]      # turn N -> index N
            result["question"] = nxt
        return result

    def route_exit(self):
        led = SESSION.ledger
        before = ledger_mod.snapshot(led)
        led["physical_state"]["left_early"] = True
        ledger_mod.add_fact(led, "Player left through the EXIT before the interview concluded.")
        ledger_mod.refresh_grade(led)
        send_off = interviewer.compose_exit(led)

        transcript_write("")
        transcript_write("[EXIT] player left after turn %d" % led["turn"])
        transcript_write("  MANAGER (bank): %s" % send_off)

        ledger_mod.print_diff(before, led, "EXIT SIGN clicked", CONFIG["debug"])
        ledger_mod.save(led, LEDGER_PATH)
        SESSION.finished = True
        log = save_log(led)
        print_source_summary()
        return {"reply": send_off, "source": "bank", "ledger": led,
                "log": os.path.basename(log), "exited": True}

    def write_report_to_transcript(self, report):
        transcript_write("")
        transcript_write("--- END OF INTERVIEW REPORT ---")
        for row in report["rows"]:
            transcript_write("  %-24s %-4s %s" % (row["label"], row["display"], row["tier"]))
        transcript_write("  %-24s %-4s  (of %s)" % (
            "ASSESSED TOTAL", report["total_display"], report["total_range"]))
        for row in report["noted"]:
            transcript_write("  %-24s %-4s %-8s [%s]" % (
                row["label"], row["display"], row["tier"], row["note"]))
        transcript_write("  FINAL GRADE: %s" % report["grade"])
        if report["stamp"]:
            transcript_write("  STAMPED: %s" % report["stamp"])
        if report["standout"]:
            transcript_write("  %s" % report["standout"])
        transcript_write("  %s" % report["sign_off"])
        transcript_write("  %s" % report["hired_line"])


# --- entry point ------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Job Interview at Fairweather Transit")
    parser.add_argument("--backend", choices=sorted(backends.BACKENDS), default=None,
                        help="force an interviewer source (default: auto-detect)")
    parser.add_argument("--no-llm", action="store_true",
                        help="skip the subprocess entirely; response bank only")
    parser.add_argument("--port", type=int, default=8137, help="HTTP port (default 8137)")
    parser.add_argument("--debug", action="store_true",
                        help="verbose subprocess and prompt logging to console")
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser")
    parser.add_argument("--no-warm", action="store_true",
                        help="do not keep a pre-booted CLI process; pay full startup every turn")
    parser.add_argument("--patience", type=int, default=None,
                        help="seconds to wait for a live reply before serving the turn from the "
                             "response bank (default 20, then self-raising if the CLI is slower)")
    args = parser.parse_args()

    if args.patience:
        interviewer.set_patience(args.patience)

    name, available = backends.detect(args.backend, args.no_llm)
    CONFIG.update({
        "backend": name,
        "available": available,
        "debug": args.debug,
        "warm": not args.no_warm,
        "live": backends.announce(name, available),
    })

    # Boot one now, while the player is still on the title screen. `claude -p`
    # costs ~20s to start but only ~6s a turn once it is up, and it boots lazily,
    # so this is the difference between a 40-second wait and a 7-second one.
    if name == "cli" and CONFIG["warm"]:
        print("Warming up the interviewer in the background…", flush=True)
        backends.warm_start(interviewer.stable_prefix(BASE_DIR), args.debug)

    os.makedirs(LOGS_DIR, exist_ok=True)

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = "http://127.0.0.1:%d/" % args.port
    print("Fairweather Transit Authority, applicant entrance: %s" % url, flush=True)
    print("Ctrl+C to close the office.\n", flush=True)

    if not args.no_browser:
        threading.Timer(0.4, webbrowser.open, args=(url,)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nOffice closed.")
        print_source_summary()
    finally:
        backends.warm_stop()
        server.server_close()


if __name__ == "__main__":
    main()
