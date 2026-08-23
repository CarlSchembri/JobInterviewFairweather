"""Swappable LLM backends.

Three implementations, one signature:

    generate(prompt: str, debug: bool = False) -> str | None

`None` means "this backend could not produce anything" — the caller falls
through to the hand-written response bank. Both live backends hand the *same
string* to the *same parser*; adding a fourth backend must never require
touching interviewer.py.

Standard library only. No `pip install anthropic`, no `requests`.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

from . import content

TIMEOUT_SECONDS = 45
API_URL = "https://api.anthropic.com/v1/messages"
API_MODEL = "claude-opus-5"
API_VERSION = "2023-06-01"

# Adaptive thinking is on by default on Opus 5 and cannot be given a token
# budget, so max_tokens has to cover thinking plus the JSON object.
MAX_TOKENS = 4000

# This is short deadpan dialogue against a strict output contract, and the whole
# reason for using the API backend is latency. Low effort keeps thinking shallow.
API_EFFORT = "low"

# Safety classifiers can decline a request (HTTP 200, stop_reason "refusal").
# The scalar form routes by refusal category with no model list to maintain.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


# --- implementations --------------------------------------------------------

# Windows launches `claude` through a .CMD shim, and cmd.exe truncates any
# command line over 8191 characters. Prompts here run ~17KB, so anything past
# this threshold is handed to the CLI on stdin instead of as an argv.
ARGV_PROMPT_LIMIT = 7000

# The CLI inherits whatever CLAUDE.md and MCP config sit above its working
# directory. This prototype lives inside a large Unreal project, and running the
# subprocess there both slowed each call by ~12s and fed the manager a pile of
# irrelevant Blueprint instructions. An empty scratch directory keeps the prompt
# hermetic: the persona block and world_bible.md are the only context.
_NEUTRAL_CWD = None


def _neutral_cwd():
    global _NEUTRAL_CWD
    if _NEUTRAL_CWD is None or not os.path.isdir(_NEUTRAL_CWD):
        _NEUTRAL_CWD = tempfile.mkdtemp(prefix="fairweather-transit-")
    return _NEUTRAL_CWD


# --- the warm process --------------------------------------------------------
#
# `claude -p` costs ~20s to start, and it boots lazily: spawning it does nothing
# until the first message arrives. But the *second* message on the same process
# comes back in ~6s. So the trick is to spawn one in streaming-input mode and
# immediately feed it the persona and world bible — the half of the prompt that
# never changes — while the player is still on the title screen. Every real turn
# then sends only the ledger and the question, and lands in single digits.
#
# If anything about this goes wrong the caller silently drops back to a one-shot
# `claude -p`, and from there to the response bank. It can only ever be faster.

WARM_BOOT_TIMEOUT = 90
WARM_TURN_TIMEOUT = 60

_warm = {"proc": None, "prefix": None, "ready": False, "dead": False, "lock": threading.Lock()}


class _WarmProcess:
    """One `claude -p --input-format stream-json` that has already booted."""

    def __init__(self, prefix, debug=False):
        self.prefix = prefix
        self.debug = debug
        self.events = []
        self.lock = threading.Lock()
        self.ready = False
        self.failed = False
        self.used = False
        exe = shutil.which("claude")
        self.proc = subprocess.Popen(
            [exe, "-p", "--input-format", "stream-json",
             "--output-format", "stream-json", "--verbose"],
            cwd=_neutral_cwd(),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        try:
            for line in self.proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                with self.lock:
                    self.events.append(event)
        except (ValueError, OSError):
            pass                                    # the process went away
        self.failed = True

    def _exchange(self, text, timeout):
        """Send one message, wait for its result event, return the text."""
        with self.lock:
            seen = len(self.events)
        try:
            self.proc.stdin.write(json.dumps({
                "type": "user",
                "message": {"role": "user", "content": [{"type": "text", "text": text}]},
            }) + "\n")
            self.proc.stdin.flush()
        except (OSError, ValueError):
            self.failed = True
            return None

        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.failed and self.proc.poll() is not None:
                return None
            with self.lock:
                for event in self.events[seen:]:
                    if event.get("type") == "result":
                        if event.get("is_error"):
                            return None
                        return str(event.get("result", "")).strip() or None
            time.sleep(0.05)
        return None

    def boot(self):
        """Prime it with the unchanging half of the prompt."""
        briefing = self.prefix + (
            "\n=== STANDBY ===\n"
            "That is your entire briefing. Do not write any dialogue yet. Reply with the "
            "single word READY and nothing else. Every message after this one is a live "
            "turn of the interview, and each will carry its own ledger, its own rules and "
            "its own output contract. Follow those exactly when they arrive.\n"
        )
        out = self._exchange(briefing, WARM_BOOT_TIMEOUT)
        self.ready = out is not None and not self.failed
        if self.debug:
            print("[backend:cli] warm process %s (%r)" % (
                "ready" if self.ready else "FAILED", (out or "")[:40]))
        return self.ready

    def ask(self, volatile, timeout):
        if not self.ready or self.failed:
            return None
        self.used = True
        return self._exchange(volatile, timeout)

    def close(self):
        try:
            self.proc.stdin.close()
        except Exception:                           # noqa: BLE001
            pass
        try:
            self.proc.terminate()
        except Exception:                           # noqa: BLE001
            pass


def warm_start(prefix, debug=False):
    """Retire any existing warm process and boot a fresh one in the background.

    Called at server launch and again whenever a new interview begins, so no
    ledger from a previous applicant is left sitting in the session context.
    """
    if not shutil.which("claude"):
        return

    def run():
        with _warm["lock"]:
            old = _warm["proc"]
            _warm.update({"proc": None, "ready": False, "prefix": prefix})
        if old:
            old.close()
        try:
            process = _WarmProcess(prefix, debug)
        except Exception as err:                    # noqa: BLE001
            print("[backend:cli] could not start a warm process (%s); using one-shot calls"
                  % type(err).__name__, flush=True)
            return
        ok = process.boot()
        with _warm["lock"]:
            _warm["proc"] = process if ok else None
            _warm["ready"] = ok
        print("[backend:cli] interviewer %s" % (
            "warmed up — turns should land in a few seconds"
            if ok else "warm-up failed; falling back to one-shot calls"), flush=True)

    threading.Thread(target=run, daemon=True).start()


def warm_ensure(prefix, debug=False):
    """Keep a warm process that is already up and has not been used yet.

    Called when a new interview starts. Retiring a clean one there would make
    the very first turn pay full startup for nothing; retiring a used one is
    necessary, so the previous applicant's ledger does not linger in context.
    """
    with _warm["lock"]:
        process = _warm["proc"]
        reusable = (process is not None and _warm["ready"]
                    and _warm["prefix"] == prefix and not process.used)
    if reusable:
        return
    warm_start(prefix, debug)


def warm_stop():
    with _warm["lock"]:
        process, _warm["proc"], _warm["ready"] = _warm["proc"], None, False
    if process:
        process.close()


def _warm_ask(prompt, debug):
    """Use the warm process if one is up and primed with this exact prefix."""
    stable, _, volatile = prompt.partition(content.PROMPT_SPLIT_MARKER)
    if not volatile:
        return None
    with _warm["lock"]:
        process = _warm["proc"]
        primed = _warm["ready"] and _warm["prefix"] == stable
    if not process or not primed:
        return None
    out = process.ask(content.PROMPT_SPLIT_MARKER + volatile, WARM_TURN_TIMEOUT)
    if out is None:
        print("[backend:cli] warm process stopped answering — falling back to a one-shot call")
        with _warm["lock"]:
            _warm["ready"] = False
    elif debug:
        print("[backend:cli] warm turn sent %d chars (instead of %d)" % (len(volatile), len(prompt)))
    return out


def cli_generate(prompt, debug=False):
    """Shell out to the Claude Code CLI. No API key, no billing."""
    warm = _warm_ask(prompt, debug)
    if warm:
        return warm

    exe = shutil.which("claude")
    if not exe:
        if debug:
            print("[backend:cli] 'claude' not found on PATH")
        return None

    if len(prompt) <= ARGV_PROMPT_LIMIT:
        argv, stdin = [exe, "-p", prompt], None
    else:
        argv, stdin = [exe, "-p"], prompt
        if debug:
            print("[backend:cli] prompt is %d chars — sending on stdin" % len(prompt))

    try:
        proc = subprocess.run(
            argv,
            input=stdin,
            capture_output=True,
            text=True,
            # The prompt carries ellipses, em dashes and curly quotes. Without an
            # explicit codec, Windows encodes stdin as cp1252 and the call dies.
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT_SECONDS,
            cwd=_neutral_cwd(),
        )
    except subprocess.TimeoutExpired:
        print("[backend:cli] timed out after %ss — falling through to bank" % TIMEOUT_SECONDS)
        return None
    except OSError as err:
        print("[backend:cli] could not launch: %s" % err)
        return None

    if proc.returncode != 0:
        print("[backend:cli] exit %s — falling through to bank" % proc.returncode)
        if debug and proc.stderr:
            print("[backend:cli] stderr: %s" % proc.stderr.strip()[:500])
        return None

    out = (proc.stdout or "").strip()
    if debug:
        print("[backend:cli] raw output (%d chars):\n%s" % (len(out), out[:1500]))
    return out or None


def api_generate(prompt, debug=False):
    """Raw urllib POST to the Messages API. Standard library only."""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        print("ANTHROPIC_API_KEY is not set — falling back to the cli backend.")
        return cli_generate(prompt, debug)

    # The persona block and the world bible are byte-identical on every turn,
    # while the ledger and the exchanges change. Splitting them lets the stable
    # ~10KB prefix be cached across a session instead of re-read seven times.
    stable, _, volatile = prompt.partition(content.PROMPT_SPLIT_MARKER)
    if volatile:
        system = [{"type": "text", "text": stable,
                   "cache_control": {"type": "ephemeral"}}]
        user = content.PROMPT_SPLIT_MARKER + volatile
    else:
        system, user = [], prompt

    payload = json.dumps({
        "model": API_MODEL,
        "max_tokens": MAX_TOKENS,
        "system": system,
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": API_EFFORT},
        "fallbacks": "default",
        "messages": [{"role": "user", "content": user}],
    }).encode("utf-8")

    request = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "content-type": "application/json",
            "x-api-key": key,
            "anthropic-version": API_VERSION,
            "anthropic-beta": FALLBACK_BETA,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", "replace")[:300] if debug else ""
        print("[backend:api] HTTP %s — falling through to bank. %s" % (err.code, detail))
        return None
    except Exception as err:                                # noqa: BLE001 - never crash a turn
        print("[backend:api] %s: %s — falling through to bank" % (type(err).__name__, err))
        return None

    # A policy decline comes back as HTTP 200, so stop_reason has to be checked
    # before the content is read. The turn just goes to the bank.
    if body.get("stop_reason") == "refusal":
        detail = (body.get("stop_details") or {}).get("category", "unspecified")
        print("[backend:api] request declined (%s) — falling through to bank" % detail)
        return None

    parts = [b.get("text", "") for b in body.get("content", []) if b.get("type") == "text"]
    out = "".join(parts).strip()
    if debug:
        usage = body.get("usage", {})
        print("[backend:api] model=%s in=%s cache_read=%s out=%s" % (
            body.get("model"), usage.get("input_tokens"),
            usage.get("cache_read_input_tokens"), usage.get("output_tokens")))
        print("[backend:api] raw output (%d chars):\n%s" % (len(out), out[:1500]))
    return out or None


def none_generate(prompt, debug=False):
    """Response bank only. Never calls anything."""
    if debug:
        print("[backend:none] skipping model call by request")
    return None


BACKENDS = {
    "cli": cli_generate,
    "api": api_generate,
    "none": none_generate,
}


def get(name):
    """Return the generate() for a backend name, defaulting to `none`."""
    return BACKENDS.get(name, none_generate)


# --- startup detection ------------------------------------------------------

def probe():
    """Report what this machine can actually do. Used by the OPTIONS screen."""
    return {
        "cli": shutil.which("claude") is not None,
        "api": bool(os.environ.get("ANTHROPIC_API_KEY", "").strip()),
        "none": True,
    }


def detect(explicit=None, no_llm=False):
    """Pick the best available backend. An explicit --backend always wins.

    Returns (name, availability_dict).
    """
    available = probe()
    if no_llm:
        return "none", available
    if explicit:
        if explicit in BACKENDS and not available.get(explicit, False):
            print("Requested --backend %s is not available on this machine; using it anyway "
                  "means every turn falls through to the response bank." % explicit)
        return explicit, available
    if available["cli"]:
        return "cli", available
    if available["api"]:
        return "api", available
    return "none", available


def reason_unavailable(name, available):
    if available.get(name):
        return None
    return {"cli": "no CLI found", "api": "no key set"}.get(name, "unavailable")


def announce(name, available):
    """One unmissable line on the console at startup."""
    live = name in ("cli", "api") and available.get(name, False)
    banner = "ONLINE" if live else "DOWN — EMERGENCY PROCEDURES IN EFFECT"
    bar = "=" * 66
    print(bar, file=sys.stderr)
    print("  TRANSIT AUTHORITY NETWORK: %s" % banner, file=sys.stderr)
    print("  interviewer source: %s%s" % (
        name,
        "" if live else "   (all replies served from the response bank)",
    ), file=sys.stderr)
    print(bar, file=sys.stderr)
    return live
