/* game.js — scene graph, state machine, typewriter, input. */

'use strict';

const canvas = document.getElementById('screen');
R.attach(canvas);

const TEXT_SPEEDS = { slow: 18, normal: 40, instant: 9999 };

const S = {
  mode: 'BOOT',
  frame: 0,
  config: null,
  ledger: null,
  question: null,
  report: null,

  selected: 0,
  beats: [],
  beatIndex: 0,
  pageIndex: 0,
  revealed: 0,
  typing: false,
  beatsDone: false,
  queuedInput: null,
  walkDone: false,

  input: null,              // 'choice' | 'text' | 'name' | null
  textValue: '',
  pending: false,
  pendingSince: 0,

  playerX: 292,
  farewellMode: 'leaving',       // 'leaving' | 'closing' | 'closed'
  doorOpen: 0,
  walkT: 0,
  playerVisible: true,
  walkPhase: 0,
  pose: 'none',
  cupCount: 31,
  cups: [],
  fartCue: -1,
  reactUntil: 0,
  finished: false,

  overlay: false,
  overlayScroll: 0,

  settings: { backend: 'cli', speed: 'normal', speech: false },
  optionRows: []
};

S.cups = R.cupLayout(S.cupCount);

/* ---- audio: a soft click for the typewriter, nothing else ---- */
let audio = null;
function click() {
  try {
    if (!audio) audio = new (window.AudioContext || window.webkitAudioContext)();
    const osc = audio.createOscillator(), gain = audio.createGain();
    osc.type = 'square';
    osc.frequency.value = 1100 + Math.random() * 260;
    gain.gain.setValueAtTime(0.016, audio.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.0005, audio.currentTime + 0.02);
    osc.connect(gain); gain.connect(audio.destination);
    osc.start(); osc.stop(audio.currentTime + 0.025);
  } catch (e) { /* audio is a garnish, never a dependency */ }
}

function speak(line) {
  if (!S.settings.speech || !window.speechSynthesis) return;
  try {
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(line.replace(/…/g, '...'));
    utter.pitch = 0.3;
    utter.rate = 0.78;
    window.speechSynthesis.speak(utter);
  } catch (e) { /* garnish */ }
}

/* ---- beats: a queue of paginated text pages ---- */
function pushBeat(str, colour, instant) {
  S.beats.push({
    pages: R.paginate(str, R.MAX_CHARS, R.MAX_LINES),
    colour: colour || R.EGA.WHITE,
    instant: !!instant,
    raw: str
  });
}

function startBeats(input) {
  S.beatIndex = 0; S.pageIndex = 0; S.revealed = 0;
  S.beatsDone = false;
  S.typing = S.beats.length > 0;
  S.input = null;
  S.queuedInput = input || null;
  if (!S.beats.length) openInput();
  else if (S.beats[0].instant) S.revealed = 1e9;
}

function openInput() {
  S.typing = false;
  S.input = S.queuedInput;
  S.selected = 0;
  S.textValue = '';
}

function currentPage() {
  const beat = S.beats[S.beatIndex];
  return beat ? beat.pages[S.pageIndex] : null;
}

function pageLength(page) {
  return page.reduce(function (n, line) { return n + line.length + 1; }, 0);
}

function visibleLines(page, n) {
  const out = [];
  let left = n;
  for (const line of page) {
    if (left <= 0) break;
    out.push(line.slice(0, left));
    left -= line.length + 1;
  }
  return out;
}

function advance() {
  const page = currentPage();
  if (!page) { openInput(); return; }
  if (S.typing && S.revealed < pageLength(page)) { S.revealed = 1e9; return; }
  const beat = S.beats[S.beatIndex];
  if (S.pageIndex + 1 < beat.pages.length) {
    S.pageIndex++; S.revealed = beat.instant ? 1e9 : 0; S.typing = true;
    return;
  }
  if (S.beatIndex + 1 < S.beats.length) {
    S.beatIndex++; S.pageIndex = 0;
    S.revealed = S.beats[S.beatIndex].instant ? 1e9 : 0;
    S.typing = true;
    return;
  }
  // The last page stays on screen; only the input surface changes.
  S.beatsDone = true;
  openInput();
}

/* ---- server ---- */
async function post(path, body) {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {})
  });
  return res.json();
}

async function boot() {
  const res = await fetch('/api/config');
  S.config = await res.json();
  S.settings.backend = S.config.backend;
  buildOptionRows();
  S.mode = 'TITLE';
  S.selected = 0;
}

function buildOptionRows() {
  const reasons = S.config.reasons || {};
  S.optionRows = [
    {
      key: 'backend', label: 'INTERVIEWER SOURCE', kind: 'toggle3',
      options: [
        { value: 'cli', label: 'CLI', reason: S.config.available.cli ? null : (reasons.cli || 'no CLI found') },
        { value: 'api', label: 'API', reason: S.config.available.api ? null : (reasons.api || 'no key set') },
        { value: 'none', label: 'BANK', reason: null }
      ]
    },
    {
      key: 'speed', label: 'TEXT SPEED', kind: 'slider',
      options: [
        { value: 'slow', label: 'SLOW' },
        { value: 'normal', label: 'NORMAL' },
        { value: 'instant', label: 'INSTANT' }
      ]
    },
    { key: 'speech', label: 'SPEECH', kind: 'onoff' },
    { key: 'back', label: 'BACK TO TITLE', kind: 'action' }
  ];
}

/* ---- flow ---- */
function goIn() {
  S.mode = 'WALKIN';
  S.walkDone = false;
  S.walkT = 0;
  S.playerX = 292;
  S.doorOpen = 0;
  S.playerVisible = false;
  S.pose = 'none';
  S.beats = [];
  S.finished = false;
  S.report = null;
  S.cupCount = 31;
  S.cups = R.cupLayout(S.cupCount);
  S.fartCue = -1;
  S.ledger = null;
}

function walkInDone() {
  S.mode = 'SCENE';
  S.beats = [];
  for (const line of (S.config.intro || [])) pushBeat(line, R.EGA.LGRAY);
  pushBeat('The Transit Authority requires a name for Form 12-B. Fifteen characters. '
    + 'It will be entered incorrectly regardless.', R.EGA.WHITE);
  S.queuedInput = 'name';
  startBeats('name');
}

async function submitName() {
  const name = (S.textValue || 'APPLICANT').toUpperCase();
  const data = await post('/api/start', { name: name });
  S.ledger = data.ledger;
  S.question = data.question;
  S.beats = [];
  if (data.acknowledgement) {
    pushBeat(data.acknowledgement, R.EGA.WHITE);
    speak(data.acknowledgement);
  }
  pushBeat(S.question.prompt, R.EGA.WHITE);
  S.queuedInput = 'choice';
  startBeats('choice');
}

async function submitAnswer() {
  if (S.pending) return;
  const q = S.question;
  const payload = { question_id: q.id };
  let shown;
  if (q.format === 'text') {
    payload.text = S.textValue;
    shown = S.textValue || '(no answer)';
  } else {
    payload.choice_id = q.choices[S.selected].id;
    shown = q.choices[S.selected].label;
    if (q.id === 'greeting') {
      S.pose = q.choices[S.selected].pose;
      if (S.pose === 'fart') S.fartCue = 0;
    }
  }

  // The player's own line goes up instantly; then the room simply carries on.
  S.beats = [];
  pushBeat('> ' + shown, R.EGA.YELLOW, true);
  startBeats(null);
  S.input = null;
  S.pending = true;
  S.pendingSince = performance.now();

  let data;
  try {
    data = await post('/api/turn', payload);
  } catch (err) {
    data = { reply: 'The line has gone. It does that. Form 12-B, line one.', source: 'bank' };
  }
  if (S.finished) return;                    // the player left through the EXIT mid-call
  S.pending = false;

  if (data.ledger) {
    S.ledger = data.ledger;
    S.pose = data.ledger.pose === 'none' ? S.pose : data.ledger.pose;
  }
  S.cupCount += 1;
  S.cups = R.cupLayout(S.cupCount);
  if (data.callback) S.reactUntil = S.frame + 60;

  S.beats = [];
  pushBeat(data.reply, R.EGA.WHITE);
  speak(data.reply);

  if (data.report) {
    S.report = data.report;
    S.queuedInput = 'report';
    startBeats('report');
  } else {
    // If the server could not name the next question, stay on the current one
    // rather than stranding the player with a dead dialogue box.
    if (data.question) S.question = data.question;
    pushBeat(S.question.prompt, R.EGA.LCYAN);
    S.queuedInput = S.question.format === 'text' ? 'text' : 'choice';
    startBeats(S.queuedInput);
  }
}

async function takeTheExit() {
  if (S.finished || S.mode !== 'SCENE') return;
  S.finished = true;
  S.pending = false;
  let data;
  try { data = await post('/api/exit', {}); }
  catch (err) { data = { reply: 'You may go. Form 12-B is incomplete. So is everything else.' }; }
  if (data.ledger) S.ledger = data.ledger;
  S.beats = [];
  pushBeat(data.reply, R.EGA.WHITE);
  speak(data.reply);
  S.queuedInput = 'exited';
  startBeats('exited');
}

/* GO HOME: you leave the office, but the game is still running. The card shows,
 * then you are back at the title. */
function goHome() {
  S.mode = 'FAREWELL';
  S.farewellMode = 'leaving';
  setTimeout(function () {
    if (S.mode === 'FAREWELL' && S.farewellMode === 'leaving') backToTitle();
  }, 4000);
}

/* DON'T GET ON DA BUS: this one really does close the application. */
async function quitApp() {
  S.mode = 'FAREWELL';
  S.farewellMode = 'closing';
  try { await post('/api/quit', {}); } catch (err) { /* already closed */ }
  // The server goes ~1.5s after acknowledging. Wait for it, then say so, so the
  // card reads as finished rather than as a stall.
  setTimeout(function () { S.farewellMode = 'closed'; }, 2600);
}

function backToTitle() {
  S.mode = 'TITLE';
  S.selected = 0;
  S.beats = [];
  S.input = null;
  S.finished = false;
  S.report = null;
  S.ledger = null;
  S.pose = 'none';
}

/* ---- input ---- */
function optionAdjust(dir) {
  const row = S.optionRows[S.selected];
  if (!row) return;
  if (row.kind === 'action') { backToTitle(); return; }
  if (row.kind === 'onoff') { S.settings.speech = !S.settings.speech; return; }
  const opts = row.options;
  let idx = opts.findIndex(function (o) { return o.value === S.settings[row.key]; });
  for (let step = 0; step < opts.length; step++) {
    idx = (idx + dir + opts.length) % opts.length;
    if (!opts[idx].reason) break;                 // skip anything unavailable here
  }
  S.settings[row.key] = opts[idx].value;
  if (row.key === 'backend') {
    post('/api/backend', { backend: opts[idx].value }).then(function (res) {
      S.config.backend = res.backend;
      S.config.live = res.live;
    });
  }
}

function onKey(e) {
  const key = e.key;
  // The leaving card is dismissible; the closing one is not, because the
  // process is on its way out and there is nothing to go back to.
  if (S.mode === 'FAREWELL') {
    if (S.farewellMode === 'leaving') { e.preventDefault(); backToTitle(); }
    return;
  }
  if (key === 'F1') { e.preventDefault(); S.overlay = !S.overlay; S.overlayScroll = 0; return; }
  if (S.overlay && (key === 'PageDown' || key === 'PageUp')) {
    e.preventDefault();
    S.overlayScroll = Math.max(0, S.overlayScroll + (key === 'PageDown' ? 18 : -18));
    return;
  }

  if (S.mode === 'TITLE') {
    if (key === 'ArrowUp') S.selected = (S.selected + 2) % 3;
    else if (key === 'ArrowDown') S.selected = (S.selected + 1) % 3;
    else if (key === 'Enter' || key === ' ') {
      e.preventDefault();
      if (S.selected === 0) goIn();
      else if (S.selected === 1) { S.mode = 'OPTIONS'; S.selected = 0; }
      else quitApp();
    } else if (key >= '1' && key <= '3') { S.selected = +key - 1; onKey({ key: 'Enter', preventDefault: function () {} }); }
    return;
  }

  if (S.mode === 'OPTIONS') {
    if (key === 'ArrowUp') S.selected = (S.selected + S.optionRows.length - 1) % S.optionRows.length;
    else if (key === 'ArrowDown') S.selected = (S.selected + 1) % S.optionRows.length;
    else if (key === 'ArrowLeft') optionAdjust(-1);
    else if (key === 'ArrowRight') optionAdjust(1);
    else if (key === 'Escape') backToTitle();
    else if (key === 'Enter') {
      if (S.optionRows[S.selected].kind === 'action') backToTitle();
      else optionAdjust(1);
    }
    return;
  }

  if (S.mode === 'WALKIN') {
    if (key === ' ' || key === 'Enter') { S.walkT = 999; S.playerVisible = true; S.playerX = 238; }
    return;
  }

  if (S.mode === 'SCENE') {
    if (S.input === 'name') {
      if (key === 'Enter') { submitName(); return; }
      if (key === 'Backspace') { e.preventDefault(); S.textValue = S.textValue.slice(0, -1); return; }
      if (key.length === 1 && /[A-Za-z0-9 ]/.test(key) && S.textValue.length < 15) {
        S.textValue += key.toUpperCase(); click();
      }
      return;
    }
    if (S.input === 'text') {
      if (key === 'Enter') { submitAnswer(); return; }
      if (key === 'Backspace') { e.preventDefault(); S.textValue = S.textValue.slice(0, -1); return; }
      const max = S.question.max_length || 60;
      if (key.length === 1 && S.textValue.length < max) { S.textValue += key; click(); }
      return;
    }
    if (S.input === 'choice') {
      const n = S.question.choices.length;
      if (key === 'ArrowUp') S.selected = (S.selected + n - 1) % n;
      else if (key === 'ArrowDown') S.selected = (S.selected + 1) % n;
      else if (key >= '1' && key <= String(n)) { S.selected = +key - 1; submitAnswer(); }
      else if (key === 'Enter' || key === ' ') { e.preventDefault(); submitAnswer(); }
      return;
    }
    if (S.input === 'report' || S.input === 'exited') {
      if (S.input === 'exited') { if (key === 'Enter' || key === ' ') backToTitle(); return; }
      if (key === 'ArrowLeft' || key === 'ArrowRight') S.selected = 1 - S.selected;
      else if (key === 'Enter' || key === ' ') { e.preventDefault(); if (S.selected === 0) goIn(); else goHome(); }
      return;
    }
    if (key === ' ' || key === 'Enter') { e.preventDefault(); if (!S.pending) advance(); }
  }
}

function toScene(evt) {
  const box = canvas.getBoundingClientRect();
  return {
    x: (evt.clientX - box.left) / box.width * R.W,
    y: (evt.clientY - box.top) / box.height * R.H
  };
}

function inRect(p, r) { return p.x >= r.x && p.x <= r.x + r.w && p.y >= r.y && p.y <= r.y + r.h; }

function onClick(evt) {
  const p = toScene(evt);

  if (S.mode === 'FAREWELL') {
    if (S.farewellMode === 'leaving') backToTitle();
    return;
  }

  // The EXIT sign is live from the moment you walk in, including mid-call.
  if (S.mode === 'SCENE' && !S.finished && S.input !== 'report' && inRect(p, R.EXIT_HITBOX)) {
    takeTheExit();
    return;
  }

  for (const hit of R.hits) {
    if (!inRect(p, hit)) continue;
    if (S.mode === 'TITLE') {
      S.selected = hit.index;
      if (hit.index === 0) goIn(); else if (hit.index === 1) { S.mode = 'OPTIONS'; S.selected = 0; } else quitApp();
      return;
    }
    if (S.mode === 'OPTIONS') {
      S.selected = hit.index;
      if (hit.kind === 'action') backToTitle();
      else if (hit.value !== undefined) {
        const row = S.optionRows[hit.index];
        const opt = row.options && row.options.find(function (o) { return o.value === hit.value; });
        if (opt && opt.reason) return;                    // greyed out: not selectable
        S.settings[row.key] = hit.value;
        if (row.key === 'backend') {
          post('/api/backend', { backend: hit.value }).then(function (res) {
            S.config.backend = res.backend; S.config.live = res.live;
          });
        }
      } else if (hit.kind === 'onoff') S.settings.speech = !S.settings.speech;
      return;
    }
    if (S.mode === 'SCENE' && S.input === 'choice' && hit.kind === 'choice') {
      S.selected = hit.index; submitAnswer(); return;
    }
    if (S.mode === 'SCENE' && S.input === 'report' && hit.kind === 'report') {
      S.selected = hit.index;
      if (hit.index === 0) goIn(); else goHome();
      return;
    }
  }

  if (S.mode === 'WALKIN') { S.walkT = 999; S.playerVisible = true; S.playerX = 238; return; }
  if (S.mode === 'SCENE') {
    if (S.input === 'exited') { backToTitle(); return; }
    if (!S.input && !S.pending) advance();
  }
}

window.addEventListener('keydown', onKey);
canvas.addEventListener('mousedown', onClick);

/* ---- the loop ---- */
let last = performance.now();

function frameTick(now) {
  const dt = Math.min(0.1, (now - last) / 1000);
  last = now;
  S.frame++;
  R.hits.length = 0;

  // typewriter
  if (S.typing) {
    const page = currentPage();
    if (page) {
      const total = pageLength(page);
      if (S.revealed < total) {
        const before = S.revealed;
        S.revealed += TEXT_SPEEDS[S.settings.speed] * dt;
        if (Math.floor(S.revealed / 3) !== Math.floor(before / 3)) click();
      }
    }
  }

  if (S.fartCue >= 0 && S.fartCue < 1) S.fartCue = Math.min(1, S.fartCue + dt / 2.2);

  draw();
  R.present();
  requestAnimationFrame(frameTick);
}

function draw() {
  if (S.mode === 'BOOT') {
    R.rect(0, 0, R.W, R.H, R.EGA.BLACK);
    R.textCentered(160, 96, 'FAIRWEATHER TRANSIT AUTHORITY', R.EGA.LGRAY);
    return;
  }
  if (S.mode === 'TITLE') { R.drawTitle(S, S.frame); drawOverlay(); return; }
  if (S.mode === 'OPTIONS') { R.drawOptions(S, S.frame); drawOverlay(); return; }
  if (S.mode === 'FAREWELL') {
    const lines = S.farewellMode === 'leaving'
      ? (S.config.farewell || [])
      : (S.config.farewell_closed || ['The Authority is closing the office.', '']);
    R.drawFarewellCard(lines, S.frame, S.farewellMode);
    return;
  }
  if (S.mode === 'SCENE' && S.input === 'report' && S.report) {
    R.drawReport(S.report, S, S.frame); drawOverlay(); return;
  }

  drawOffice();
  drawBoxContents();
  drawOverlay();
}

function drawOffice() {
  R.drawWall();
  R.drawFloor();
  R.drawBus();
  R.drawFixtures(S.frame, S.doorOpen);

  const waited = S.pending ? (performance.now() - S.pendingSince) / 1000 : 0;
  const reacting = S.frame < S.reactUntil;
  const idle = R.managerIdle(S.frame, waited, reacting);
  const mgr = R.drawManager(S, idle, S.pose);

  // Walk-in, in three beats: the door swings open on an empty doorway, he steps
  // through it, and it shuts behind him as he clears it.
  if (S.mode === 'WALKIN') {
    S.walkT++;
    if (S.walkT < 28) {
      S.doorOpen = S.walkT / 27;
      S.playerVisible = false;
    } else {
      S.playerVisible = true;
      if (S.playerX > 238) {
        S.playerX -= 0.7;
        S.walkPhase = Math.floor(S.frame / 7) % 4;
      } else {
        S.playerX = 238;
        if (!S.walkDone) { S.walkDone = true; setTimeout(walkInDone, 900); }
      }
      S.doorOpen = Math.max(0, Math.min(1, (S.playerX - 250) / 38));
    }
  }

  R.drawDesk(S.cups);

  // one clean cue, behind him, and then nobody mentions it again
  if (S.fartCue >= 0 && S.fartCue < 1) R.drawFartCue(S.playerX, S.fartCue);

  const walking = S.mode === 'WALKIN' && S.playerX > 238;
  if (!S.playerVisible) { R.drawManagerRightArm(mgr, S.pose, null); return; }
  const player = R.drawPlayer(S.playerX, S.pose, S.frame, walking ? S.walkPhase : null);

  if (S.pose === 'handshake') R.drawClasp(mgr, player, S.frame);
  else R.drawManagerRightArm(mgr, S.pose, null);
}

function drawBoxContents() {
  R.drawBox();

  if (S.input === 'choice' && S.question) {
    R.drawChoices(S.question.short || S.question.prompt, S.question.choices, S.selected, S.frame);
    return;
  }
  if (S.input === 'text' && S.question) {
    R.drawTextEntry(S.question.prompt, S.textValue, S.question.placeholder || '', S.frame);
    return;
  }
  if (S.input === 'name') {
    R.drawTextEntry('NAME. For Form 12-B.', S.textValue, 'APPLICANT', S.frame);
    return;
  }

  const page = currentPage();
  if (!page) return;                            // the wait is part of the joke: no spinner

  const beat = S.beats[S.beatIndex];
  const total = pageLength(page);
  const done = S.revealed >= total;
  R.drawBoxLines(done ? page : visibleLines(page, Math.floor(S.revealed)), beat.colour);
  if (!done) return;

  S.typing = false;
  if (S.input === 'exited') {
    R.text(R.BOX.x + 8, R.BOX.y + R.BOX.h - 11, 'PRESS ENTER', R.EGA.YELLOW);
  } else if (!S.beatsDone && !S.pending) {
    R.drawMorePrompt(S.frame);
  }
}

function drawOverlay() {
  if (S.overlay) R.drawLedgerOverlay(S.ledger, S.overlayScroll);
}

boot().then(function () { requestAnimationFrame(frameTick); });
