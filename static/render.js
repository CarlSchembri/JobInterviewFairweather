/* render.js — every visual in this game, drawn procedurally.
 *
 * Nothing is loaded from disk. No sprite sheets, no images, no fonts. A 320x200
 * buffer is drawn with filled rects and paths out of a hard-coded 16-colour EGA
 * palette, then blitted to the visible canvas with imageSmoothingEnabled = false.
 */

'use strict';

/* ---- the palette. Sixteen constants. Nothing else is ever used. ---- */
const EGA = {
  BLACK:    '#000000', BLUE:     '#0000AA', GREEN:    '#00AA00', CYAN:     '#00AAAA',
  RED:      '#AA0000', MAGENTA:  '#AA00AA', BROWN:    '#AA5500', LGRAY:    '#AAAAAA',
  DGRAY:    '#555555', LBLUE:    '#5555FF', LGREEN:   '#55FF55', LCYAN:    '#55FFFF',
  LRED:     '#FF5555', LMAGENTA: '#FF55FF', YELLOW:   '#FFFF55', WHITE:    '#FFFFFF'
};

const W = 320, H = 200;
const BOX_TOP = 132;          // dialogue box occupies the bottom third

/* ---- 5x7 bitmap font. Each glyph is seven 5-bit rows, MSB leftmost. ---- */
const FONT = {
  'A':[0x0E,0x11,0x11,0x1F,0x11,0x11,0x11], 'B':[0x1E,0x11,0x11,0x1E,0x11,0x11,0x1E],
  'C':[0x0E,0x11,0x10,0x10,0x10,0x11,0x0E], 'D':[0x1E,0x11,0x11,0x11,0x11,0x11,0x1E],
  'E':[0x1F,0x10,0x10,0x1E,0x10,0x10,0x1F], 'F':[0x1F,0x10,0x10,0x1E,0x10,0x10,0x10],
  'G':[0x0E,0x11,0x10,0x17,0x11,0x11,0x0F], 'H':[0x11,0x11,0x11,0x1F,0x11,0x11,0x11],
  'I':[0x0E,0x04,0x04,0x04,0x04,0x04,0x0E], 'J':[0x07,0x02,0x02,0x02,0x02,0x12,0x0C],
  'K':[0x11,0x12,0x14,0x18,0x14,0x12,0x11], 'L':[0x10,0x10,0x10,0x10,0x10,0x10,0x1F],
  'M':[0x11,0x1B,0x15,0x15,0x11,0x11,0x11], 'N':[0x11,0x19,0x19,0x15,0x13,0x13,0x11],
  'O':[0x0E,0x11,0x11,0x11,0x11,0x11,0x0E], 'P':[0x1E,0x11,0x11,0x1E,0x10,0x10,0x10],
  'Q':[0x0E,0x11,0x11,0x11,0x15,0x12,0x0D], 'R':[0x1E,0x11,0x11,0x1E,0x14,0x12,0x11],
  'S':[0x0F,0x10,0x10,0x0E,0x01,0x01,0x1E], 'T':[0x1F,0x04,0x04,0x04,0x04,0x04,0x04],
  'U':[0x11,0x11,0x11,0x11,0x11,0x11,0x0E], 'V':[0x11,0x11,0x11,0x11,0x11,0x0A,0x04],
  'W':[0x11,0x11,0x11,0x15,0x15,0x1B,0x11], 'X':[0x11,0x11,0x0A,0x04,0x0A,0x11,0x11],
  'Y':[0x11,0x11,0x0A,0x04,0x04,0x04,0x04], 'Z':[0x1F,0x01,0x02,0x04,0x08,0x10,0x1F],

  'a':[0x00,0x00,0x0E,0x01,0x0F,0x11,0x0F], 'b':[0x10,0x10,0x1E,0x11,0x11,0x11,0x1E],
  'c':[0x00,0x00,0x0E,0x10,0x10,0x11,0x0E], 'd':[0x01,0x01,0x0F,0x11,0x11,0x11,0x0F],
  'e':[0x00,0x00,0x0E,0x11,0x1F,0x10,0x0E], 'f':[0x06,0x09,0x08,0x1C,0x08,0x08,0x08],
  'g':[0x00,0x00,0x0F,0x11,0x0F,0x01,0x0E], 'h':[0x10,0x10,0x1E,0x11,0x11,0x11,0x11],
  'i':[0x04,0x00,0x0C,0x04,0x04,0x04,0x0E], 'j':[0x04,0x00,0x0C,0x04,0x04,0x14,0x08],
  'k':[0x10,0x10,0x12,0x14,0x18,0x14,0x12], 'l':[0x0C,0x04,0x04,0x04,0x04,0x04,0x0E],
  'm':[0x00,0x00,0x1A,0x15,0x15,0x15,0x15], 'n':[0x00,0x00,0x1E,0x11,0x11,0x11,0x11],
  'o':[0x00,0x00,0x0E,0x11,0x11,0x11,0x0E], 'p':[0x00,0x00,0x1E,0x11,0x1E,0x10,0x10],
  'q':[0x00,0x00,0x0F,0x11,0x0F,0x01,0x01], 'r':[0x00,0x00,0x16,0x19,0x10,0x10,0x10],
  's':[0x00,0x00,0x0F,0x10,0x0E,0x01,0x1E], 't':[0x08,0x08,0x1C,0x08,0x08,0x09,0x06],
  'u':[0x00,0x00,0x11,0x11,0x11,0x13,0x0D], 'v':[0x00,0x00,0x11,0x11,0x11,0x0A,0x04],
  'w':[0x00,0x00,0x11,0x11,0x15,0x15,0x0A], 'x':[0x00,0x00,0x11,0x0A,0x04,0x0A,0x11],
  'y':[0x00,0x00,0x11,0x11,0x0F,0x01,0x0E], 'z':[0x00,0x00,0x1F,0x02,0x04,0x08,0x1F],

  '0':[0x0E,0x11,0x13,0x15,0x19,0x11,0x0E], '1':[0x04,0x0C,0x04,0x04,0x04,0x04,0x0E],
  '2':[0x0E,0x11,0x01,0x02,0x04,0x08,0x1F], '3':[0x1F,0x02,0x04,0x02,0x01,0x11,0x0E],
  '4':[0x02,0x06,0x0A,0x12,0x1F,0x02,0x02], '5':[0x1F,0x10,0x1E,0x01,0x01,0x11,0x0E],
  '6':[0x06,0x08,0x10,0x1E,0x11,0x11,0x0E], '7':[0x1F,0x01,0x02,0x04,0x08,0x08,0x08],
  '8':[0x0E,0x11,0x11,0x0E,0x11,0x11,0x0E], '9':[0x0E,0x11,0x11,0x0F,0x01,0x02,0x0C],

  ' ':[0,0,0,0,0,0,0],
  '.':[0x00,0x00,0x00,0x00,0x00,0x0C,0x0C], ',':[0x00,0x00,0x00,0x00,0x0C,0x04,0x08],
  "'":[0x0C,0x04,0x08,0x00,0x00,0x00,0x00], '"':[0x0A,0x0A,0x00,0x00,0x00,0x00,0x00],
  '?':[0x0E,0x11,0x01,0x02,0x04,0x00,0x04], '!':[0x04,0x04,0x04,0x04,0x04,0x00,0x04],
  ':':[0x00,0x0C,0x0C,0x00,0x0C,0x0C,0x00], ';':[0x00,0x0C,0x0C,0x00,0x0C,0x04,0x08],
  '-':[0x00,0x00,0x00,0x1F,0x00,0x00,0x00], '=':[0x00,0x00,0x1F,0x00,0x1F,0x00,0x00],
  '(':[0x02,0x04,0x08,0x08,0x08,0x04,0x02], ')':[0x08,0x04,0x02,0x02,0x02,0x04,0x08],
  '[':[0x0E,0x08,0x08,0x08,0x08,0x08,0x0E], ']':[0x0E,0x02,0x02,0x02,0x02,0x02,0x0E],
  '{':[0x06,0x08,0x08,0x10,0x08,0x08,0x06], '}':[0x0C,0x02,0x02,0x01,0x02,0x02,0x0C],
  '/':[0x01,0x01,0x02,0x04,0x08,0x10,0x10], '\\':[0x10,0x10,0x08,0x04,0x02,0x01,0x01],
  '$':[0x04,0x0F,0x14,0x0E,0x05,0x1E,0x04], '+':[0x00,0x04,0x04,0x1F,0x04,0x04,0x00],
  '%':[0x18,0x19,0x02,0x04,0x08,0x13,0x03], '&':[0x08,0x14,0x14,0x08,0x15,0x12,0x0D],
  '*':[0x00,0x0A,0x04,0x1F,0x04,0x0A,0x00], '#':[0x0A,0x1F,0x0A,0x0A,0x0A,0x1F,0x0A],
  '@':[0x0E,0x11,0x17,0x15,0x17,0x10,0x0E], '_':[0x00,0x00,0x00,0x00,0x00,0x00,0x1F],
  '<':[0x02,0x04,0x08,0x10,0x08,0x04,0x02], '>':[0x08,0x04,0x02,0x01,0x02,0x04,0x08],
  '|':[0x04,0x04,0x04,0x04,0x04,0x04,0x04], '^':[0x04,0x0A,0x11,0x00,0x00,0x00,0x00],
  '~':[0x00,0x00,0x0A,0x15,0x00,0x00,0x00], '…':[0x00,0x00,0x00,0x00,0x00,0x15,0x00]
};

/* Characters the content uses that share a glyph with something simpler. */
const FONT_ALIAS = {
  '‘': "'", '’': "'", '“': '"', '”': '"',
  '–': '-', '—': '-', ' ': ' ', 'é': 'e', 'û': 'u'
};

const GLYPH_W = 5, GLYPH_H = 7, ADVANCE = 6, LINE_H = 9;

/* ---- buffer plumbing ---- */
const buf = document.createElement('canvas');
buf.width = W; buf.height = H;
const b = buf.getContext('2d');
b.imageSmoothingEnabled = false;

let view = null, vctx = null;

/* Click targets, rebuilt every frame by whichever screen is drawing. */
const hits = [];
function hit(x, y, w, h, meta) {
  const target = { x: x, y: y, w: w, h: h };
  for (const key in meta) target[key] = meta[key];
  hits.push(target);
}

function attach(canvas) {
  view = canvas;
  vctx = canvas.getContext('2d');
  vctx.imageSmoothingEnabled = false;
}

function present() {
  vctx.imageSmoothingEnabled = false;
  vctx.clearRect(0, 0, view.width, view.height);
  vctx.drawImage(buf, 0, 0, W, H, 0, 0, view.width, view.height);
}

/* ---- primitives ---- */
function px(x, y, c) { b.fillStyle = c; b.fillRect(x | 0, y | 0, 1, 1); }
function rect(x, y, w, h, c) { b.fillStyle = c; b.fillRect(x | 0, y | 0, w | 0, h | 0); }
function frame(x, y, w, h, c) {
  rect(x, y, w, 1, c); rect(x, y + h - 1, w, 1, c);
  rect(x, y, 1, h, c); rect(x + w - 1, y, 1, h, c);
}
function hline(x, y, w, c) { rect(x, y, w, 1, c); }
function vline(x, y, h, c) { rect(x, y, 1, h, c); }

/* Checkerboard dither — the only gradient tool available at 16 colours. */
function dither(x, y, w, h, cA, cB, density) {
  const d = density === undefined ? 2 : density;
  rect(x, y, w, h, cA);
  b.fillStyle = cB;
  for (let j = 0; j < h; j++) {
    for (let i = (j % d); i < w; i += d) b.fillRect((x + i) | 0, (y + j) | 0, 1, 1);
  }
}

/* Dots only, no base fill: for light thrown over whatever is already drawn. */
function speckle(x, y, w, h, c, density) {
  b.fillStyle = c;
  for (let j = 0; j < h; j++) {
    for (let i = (j % density); i < w; i += density) b.fillRect((x + i) | 0, (y + j) | 0, 1, 1);
  }
}

function ellipse(cx, cy, rx, ry, c) {
  b.fillStyle = c;
  for (let j = -ry; j <= ry; j++) {
    const span = Math.floor(rx * Math.sqrt(Math.max(0, 1 - (j * j) / (ry * ry))));
    b.fillRect((cx - span) | 0, (cy + j) | 0, span * 2 + 1, 1);
  }
}

function thickSlope(x0, y0, x1, y1, c, weight) {
  for (let k = 0; k < (weight || 3); k++) slope(x0, y0 + k, x1, y1 + k, c);
}

function slope(x0, y0, x1, y1, c) {
  const dx = Math.abs(x1 - x0), dy = Math.abs(y1 - y0);
  const sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1;
  let err = dx - dy, x = x0, y = y0;
  for (;;) {
    px(x, y, c);
    if (x === x1 && y === y1) break;
    const e2 = err * 2;
    if (e2 > -dy) { err -= dy; x += sx; }
    if (e2 < dx) { err += dx; y += sy; }
  }
}

/* ---- text ---- */
function glyph(ch) {
  if (FONT[ch]) return FONT[ch];
  const alias = FONT_ALIAS[ch];
  if (alias && FONT[alias]) return FONT[alias];
  const up = ch.toUpperCase();
  return FONT[up] || FONT['?'];
}

function text(x, y, str, c) {
  let cx = x;
  for (let i = 0; i < str.length; i++) {
    const rows = glyph(str[i]);
    b.fillStyle = c;
    for (let r = 0; r < GLYPH_H; r++) {
      const bits = rows[r];
      if (!bits) continue;
      for (let col = 0; col < GLYPH_W; col++) {
        if (bits & (1 << (GLYPH_W - 1 - col))) b.fillRect(cx + col, y + r, 1, 1);
      }
    }
    cx += ADVANCE;
  }
  return cx;
}

function textCentered(cy, y, str, c) { text(cy - (str.length * ADVANCE) / 2 | 0, y, str, c); }

/* Double-size text for the title card. */
function textBig(x, y, str, c) {
  let cx = x;
  for (let i = 0; i < str.length; i++) {
    const rows = glyph(str[i]);
    b.fillStyle = c;
    for (let r = 0; r < GLYPH_H; r++) {
      const bits = rows[r];
      if (!bits) continue;
      for (let col = 0; col < GLYPH_W; col++) {
        if (bits & (1 << (GLYPH_W - 1 - col))) b.fillRect(cx + col * 2, y + r * 2, 2, 2);
      }
    }
    cx += ADVANCE * 2;
  }
  return cx;
}

function wrap(str, maxChars) {
  const words = String(str).split(/\s+/).filter(Boolean);
  const lines = [];
  let line = '';
  for (const word of words) {
    if (!line.length) { line = word; continue; }
    if (line.length + 1 + word.length <= maxChars) line += ' ' + word;
    else { lines.push(line); line = word; }
  }
  if (line.length) lines.push(line);
  return lines;
}

function paginate(str, maxChars, maxLines) {
  const lines = wrap(str, maxChars);
  const pages = [];
  for (let i = 0; i < lines.length; i += maxLines) pages.push(lines.slice(i, i + maxLines));
  return pages.length ? pages : [['']];
}

/* ---- deterministic noise, so set dressing does not crawl between frames ---- */
function rng(seed) {
  let s = seed >>> 0 || 1;
  return function () {
    s ^= s << 13; s >>>= 0; s ^= s >> 17; s ^= s << 5; s >>>= 0;
    return s / 4294967296;
  };
}

/* =========================================================================
 * THE OFFICE
 * ========================================================================= */

const FLOOR_Y = 104;

function drawWall() {
  dither(0, 0, W, FLOOR_Y, EGA.LGRAY, EGA.DGRAY, 4);
  // grime creeping down from the ceiling, and a water stain
  dither(0, 0, W, 14, EGA.DGRAY, EGA.LGRAY, 2);
  dither(180, 10, 46, 22, EGA.DGRAY, EGA.LGRAY, 3);
  dither(0, FLOOR_Y - 8, W, 8, EGA.LGRAY, EGA.DGRAY, 2);
  hline(0, FLOOR_Y - 1, W, EGA.DGRAY);
}

function drawFloor() {
  dither(0, FLOOR_Y, W, BOX_TOP - FLOOR_Y, EGA.BROWN, EGA.BLACK, 3);
  hline(0, FLOOR_Y, W, EGA.DGRAY);
  // floorboards receding
  for (let i = 1; i < 5; i++) hline(0, FLOOR_Y + i * 6, W, EGA.BLACK);
  // paper drifts
  const r = rng(9001);
  for (let i = 0; i < 60; i++) {
    const x = Math.floor(r() * W), y = FLOOR_Y + 2 + Math.floor(r() * (BOX_TOP - FLOOR_Y - 4));
    rect(x, y, 2 + Math.floor(r() * 5), 1, r() > 0.4 ? EGA.LGRAY : EGA.WHITE);
  }
  // a deeper drift piled against the right wall
  for (let i = 0; i < 34; i++) {
    const x = 252 + Math.floor(r() * 64), y = FLOOR_Y + 6 + Math.floor(r() * 20);
    rect(x, y, 3 + Math.floor(r() * 5), 2, EGA.WHITE);
  }
}

/* The bus. Yellow, cracked, headlight still on, nosed in through the left wall
 * at an angle. Its front bumper reaches almost to the desk. Never explained. */
function drawBus() {
  const r = rng(4242);

  // the hole: a ragged dark opening with brick spilling out of it
  dither(0, 14, 104, 96, EGA.BLACK, EGA.DGRAY, 2);
  for (let i = 0; i < 70; i++) {
    const x = Math.floor(r() * 108), y = 14 + Math.floor(r() * 96);
    rect(x, y, 3, 2, r() > 0.5 ? EGA.RED : EGA.BROWN);
  }

  // --- side of the bus, receding to the upper left ---
  const SX0 = -6, SX1 = 62;
  for (let x = SX0; x < SX1; x++) {
    const t = (x - SX0) / (SX1 - SX0);
    const top = Math.round(24 + t * 20);
    const bot = Math.round(88 + t * 18);
    rect(x, top, 1, bot - top, EGA.YELLOW);
    px(x, top, EGA.WHITE);                       // roof edge
    rect(x, bot - 12, 1, 12, EGA.BROWN);         // skirt in shadow
    px(x, bot, EGA.BLACK);
  }
  // windows along the side, sheared with the body
  for (let wnd = 0; wnd < 3; wnd++) {
    const bx = SX0 + 4 + wnd * 20;
    for (let x = bx; x < bx + 15 && x < SX1 - 2; x++) {
      const t = (x - SX0) / (SX1 - SX0);
      const top = Math.round(30 + t * 20);
      rect(x, top, 1, 18, wnd === 1 ? EGA.BLACK : EGA.CYAN);
    }
    // cracked glass
    slope(bx + 7, 32 + wnd * 6, bx + 1, 48 + wnd * 6, EGA.WHITE);
  }
  // the fleet legend, mostly gone
  text(4, 76, 'FAIRWE', EGA.BLACK);

  // --- front of the bus, facing into the room ---
  rect(62, 44, 32, 60, EGA.YELLOW);
  frame(62, 44, 32, 60, EGA.BROWN);
  // windshield, cracked
  rect(64, 46, 28, 18, EGA.CYAN);
  frame(64, 46, 28, 18, EGA.DGRAY);
  slope(70, 46, 66, 63, EGA.WHITE);
  slope(70, 52, 89, 60, EGA.WHITE);
  slope(78, 46, 84, 63, EGA.WHITE);
  // route board above the windshield
  rect(66, 40, 24, 5, EGA.BLACK);
  // grille
  rect(66, 74, 24, 12, EGA.DGRAY);
  for (let i = 0; i < 5; i++) hline(67, 76 + i * 2, 22, EGA.BLACK);
  // headlights: one still on
  ellipse(69, 70, 4, 3, EGA.LGRAY);
  ellipse(87, 70, 4, 3, EGA.WHITE);
  ellipse(87, 70, 2, 2, EGA.YELLOW);
  // bumper, reaching almost to the desk
  rect(58, 88, 38, 8, EGA.LGRAY);
  frame(58, 88, 38, 8, EGA.DGRAY);
  rect(60, 96, 34, 4, EGA.DGRAY);

  // wheels, half buried in rubble
  ellipse(30, 100, 9, 7, EGA.BLACK);
  ellipse(30, 100, 4, 3, EGA.DGRAY);
  ellipse(74, 104, 8, 6, EGA.BLACK);

  // brick and dust spilling across the floor
  for (let i = 0; i < 46; i++) {
    const x = Math.floor(r() * 130), y = 98 + Math.floor(r() * 28);
    rect(x, y, 3 + Math.floor(r() * 3), 2, r() > 0.5 ? EGA.RED : EGA.LGRAY);
  }

  // the beam from the live headlight, thrown across the office floor
  for (let i = 0; i < 26; i++) {
    const t = i / 26;
    speckle(96 + i * 5, 74 + i * 1.4, 5, 3 + i * 0.7, EGA.YELLOW, 3 + Math.floor(t * 7));
  }
}

/* Filing cabinet: all drawers open and empty, except one. */
function drawCabinet() {
  rect(218, 58, 30, 54, EGA.LGRAY);
  frame(218, 58, 30, 54, EGA.DGRAY);
  for (let d = 0; d < 4; d++) {
    const y = 61 + d * 13;
    const out = [7, 4, 9, 2][d];
    rect(218 - out, y, 30 + out, 10, EGA.DGRAY);
    frame(218 - out, y, 30 + out, 10, EGA.BLACK);
    rect(218 - out + 2, y + 2, 6, 6, EGA.BLACK);       // empty interior
    if (d === 2) {                                     // the one full drawer
      for (let i = 0; i < 7; i++) rect(218 - out + 3 + i * 3, y + 1, 2, 8, EGA.WHITE);
    }
  }
}

function drawFixtures(frameCount, doorOpen) {
  // DAYS SINCE INCIDENT board. It reads 0. It has read 0 for some time.
  rect(106, 6, 66, 38, EGA.GREEN);
  frame(106, 6, 66, 38, EGA.BROWN);
  frame(108, 8, 62, 34, EGA.BLACK);
  text(110, 11, 'DAYS SINCE', EGA.WHITE);
  text(110, 19, 'INCIDENT', EGA.WHITE);
  rect(130, 27, 18, 14, EGA.BLACK);
  textBig(134, 27, '0', EGA.YELLOW);

  // bent transit map — routes that no longer connect
  rect(174, 10, 40, 32, EGA.WHITE);
  frame(174, 10, 40, 32, EGA.DGRAY);
  slope(176, 40, 190, 12, EGA.RED);
  slope(178, 12, 212, 34, EGA.BLUE);
  slope(176, 26, 212, 22, EGA.GREEN);
  rect(196, 10, 18, 32, EGA.LGRAY);                    // the bent corner
  slope(196, 10, 196, 41, EGA.DGRAY);

  // framed portrait, face scratched out
  rect(222, 12, 22, 26, EGA.BROWN);
  rect(224, 14, 18, 22, EGA.CYAN);
  ellipse(233, 22, 5, 6, EGA.WHITE);
  rect(228, 28, 11, 8, EGA.BLUE);
  for (let i = 0; i < 7; i++) slope(226 + i, 16, 240 - i, 28, EGA.BLACK);

  // clock with no hands
  ellipse(258, 22, 9, 9, EGA.WHITE);
  ellipse(258, 22, 7, 7, EGA.LGRAY);
  for (let a = 0; a < 12; a++) {
    const ang = (a / 12) * Math.PI * 2;
    px(258 + Math.round(Math.cos(ang) * 5), 22 + Math.round(Math.sin(ang) * 5), EGA.BLACK);
  }

  // paper taped to the wall
  const r = rng(777);
  for (let i = 0; i < 11; i++) {
    const x = 100 + Math.floor(r() * 160), y = 44 + Math.floor(r() * 22);
    rect(x, y, 8 + Math.floor(r() * 5), 10, EGA.WHITE);
    hline(x + 1, y + 3, 6, EGA.DGRAY);
    hline(x + 1, y + 6, 8, EGA.DGRAY);
  }

  drawCabinet();

  // dead plant
  rect(250, 100, 12, 12, EGA.BROWN);
  frame(250, 100, 12, 12, EGA.DGRAY);
  slope(256, 100, 254, 88, EGA.BROWN);
  slope(256, 100, 259, 90, EGA.BROWN);
  px(254, 88, EGA.BROWN); px(259, 90, EGA.BROWN);
  px(253, 90, EGA.BROWN); px(261, 93, EGA.BROWN);

  drawDoor(doorOpen || 0);
  drawExitSign(frameCount);
}

/* The door. Hinged at the right, so an open door leaves a gap on the left for
 * the applicant to walk through, and closes behind him as he clears it. */
function drawDoor(open) {
  const D = { x: 272, y: 44, w: 36, h: 68 };
  const swing = Math.round(30 * Math.max(0, Math.min(1, open)));

  // the corridor behind, and the light coming in off it
  rect(D.x, D.y, D.w, D.h, EGA.BLACK);
  if (swing > 2) {
    speckle(D.x + 1, D.y + 2, swing - 1, D.h - 4, EGA.DGRAY, 2);
    speckle(D.x + 1, D.y + 30, swing - 1, D.h - 34, EGA.BROWN, 3);
  }
  frame(D.x, D.y, D.w, D.h, EGA.BLACK);

  // the panel, foreshortening as it swings
  const px0 = D.x + swing;
  const pw = D.w - swing;
  if (pw > 3) {
    rect(px0, D.y, pw, D.h, EGA.BROWN);
    frame(px0, D.y, pw, D.h, EGA.BLACK);
    if (pw > 10) {
      frame(px0 + 3, D.y + 4, pw - 6, D.h - 8, EGA.DGRAY);
      rect(px0 + pw - 8, D.y + 34, 3, 3, EGA.YELLOW);   // the handle
    }
    // the leading edge catches the light from the corridor
    if (swing > 2) vline(px0, D.y + 1, D.h - 2, EGA.LGRAY);
  }
}

/* The EXIT sign — the only clean, bright thing in the room. */
function drawExitSign(frameCount) {
  const glow = 1;
  rect(276, 28, 28, 14, EGA.BLACK);
  frame(276, 28, 28, 14, EGA.LGRAY);
  rect(278, 30, 24, 10, glow ? EGA.GREEN : EGA.BLACK);
  text(279, 32, 'EXIT', EGA.WHITE);
  // light spill onto the wall beneath
  dither(272, 42, 36, 6, EGA.DGRAY, EGA.GREEN, 3);
}

const EXIT_HITBOX = { x: 274, y: 26, w: 32, h: 18 };

/* The desk, and the coffee. */
function cupLayout(count) {
  const r = rng(1312);
  const cups = [];
  for (let i = 0; i < count; i++) {
    const x = 99 + Math.floor(r() * 110);
    const stack = r() > 0.62 ? 1 : 0;
    const tipped = r() > 0.86;
    const h = 5 + Math.floor(r() * 7);
    cups.push({ x: x, h: h, stack: stack, tipped: tipped, grown: i === 6 });
  }
  cups.sort(function (p, q) { return p.x - q.x; });
  return cups;
}

function drawDesk(cups) {
  // top surface
  rect(94, 94, 124, 6, EGA.BROWN);
  hline(94, 94, 124, EGA.LGRAY);
  hline(94, 99, 124, EGA.BLACK);
  // front face
  dither(96, 100, 120, 26, EGA.BROWN, EGA.BLACK, 4);
  frame(96, 100, 120, 26, EGA.BLACK);
  rect(104, 106, 34, 3, EGA.DGRAY);
  rect(160, 106, 34, 3, EGA.DGRAY);

  // the previous driver's medical file, open, never closed
  rect(178, 88, 22, 7, EGA.WHITE);
  hline(180, 90, 18, EGA.DGRAY);
  hline(180, 92, 14, EGA.DGRAY);

  // thirty-plus cups, one more every turn
  for (const cup of cups) {
    const baseY = 94 - cup.h;
    if (cup.tipped) {
      rect(cup.x, 89, 9, 5, EGA.WHITE);
      frame(cup.x, 89, 9, 5, EGA.DGRAY);
      rect(cup.x - 3, 93, 5, 1, EGA.BROWN);
    } else {
      rect(cup.x, baseY, 6, cup.h, EGA.WHITE);
      frame(cup.x, baseY, 6, cup.h, EGA.DGRAY);
      rect(cup.x + 6, baseY + 2, 2, 3, EGA.LGRAY);
      px(cup.x + 7, baseY + 3, EGA.DGRAY);
      rect(cup.x + 1, baseY + 1, 4, 1, cup.grown ? EGA.LGREEN : EGA.BROWN);
      if (cup.grown) { px(cup.x + 2, baseY - 1, EGA.LGREEN); px(cup.x + 1, baseY - 2, EGA.GREEN); }
      if (cup.stack) {
        rect(cup.x, baseY - 5, 6, 5, EGA.LGRAY);
        frame(cup.x, baseY - 5, 6, 5, EGA.DGRAY);
      }
    }
  }
}

/* =========================================================================
 * THE MANAGER
 * ========================================================================= */

const MGR = { x: 150, headY: 42 };

function managerIdle(frameCount, waiting, reacting) {
  // Slow blink: shut for 10 frames roughly every 200.
  const cycle = frameCount % 200;
  const blink = cycle > 186;
  // Head tilt: a very long sine, one pixel of travel.
  const tilt = Math.round(Math.sin(frameCount / 95) * 1.4);
  // Hand reaching for a cup that is already empty.
  const reachPhase = (frameCount % 320) / 320;
  const reaching = reachPhase > 0.55 && reachPhase < 0.82;
  const reach = reaching ? Math.sin((reachPhase - 0.55) / 0.27 * Math.PI) : 0;
  return {
    blink: reacting ? false : blink,
    tilt: reacting ? 0 : tilt,
    reach: reach,
    paperwork: waiting > 10,
    slump: reacting ? -2 : 0
  };
}

function drawManager(state, idle, pose) {
  const x = MGR.x, top = MGR.headY + idle.slump;
  const hx = x + idle.tilt;

  // neck, behind everything
  rect(hx - 3, top + 14, 7, 8, EGA.LGRAY);

  // --- left arm: the one that does the paperwork ---
  const penY = idle.paperwork ? top + 44 + Math.round(Math.sin(Date.now() / 110) * 2) : top + 46;
  rect(x - 24, top + 22, 8, 20, EGA.BLUE);
  frame(x - 24, top + 22, 8, 20, EGA.BLACK);
  thickSlope(x - 21, top + 40, x - 12, penY, EGA.BLUE, 4);
  rect(x - 13, penY - 1, 5, 4, EGA.WHITE);
  frame(x - 13, penY - 1, 5, 4, EGA.BLACK);
  if (idle.paperwork) {
    rect(x - 34, top + 46, 20, 11, EGA.WHITE);                      // he has found a form
    frame(x - 34, top + 46, 20, 11, EGA.DGRAY);
    hline(x - 32, top + 49, 14, EGA.DGRAY);
    hline(x - 32, top + 52, 11, EGA.DGRAY);
    slope(x - 12, penY, x - 16, penY - 6, EGA.BLACK);               // the pen
  }

  // --- torso: rumpled suit, done up one button over ---
  rect(x - 17, top + 18, 34, 34, EGA.BLUE);
  frame(x - 17, top + 18, 34, 34, EGA.BLACK);
  dither(x - 16, top + 38, 32, 13, EGA.BLUE, EGA.BLACK, 4);         // creases
  rect(x - 5, top + 18, 11, 34, EGA.WHITE);                         // shirt
  vline(x - 6, top + 18, 34, EGA.BLACK);
  vline(x + 6, top + 18, 34, EGA.BLACK);
  rect(x - 16, top + 19, 7, 33, EGA.LBLUE);                         // lapel
  vline(x - 9, top + 19, 33, EGA.BLACK);
  px(x + 3, top + 28, EGA.DGRAY); px(x + 4, top + 36, EGA.DGRAY); px(x + 3, top + 44, EGA.DGRAY);
  // tie, loose and off-centre
  rect(x + 1, top + 20, 4, 5, EGA.RED);
  rect(x + 2, top + 25, 4, 14, EGA.RED);
  frame(x + 2, top + 25, 4, 14, EGA.BLACK);

  // --- head ---
  rect(hx - 9, top, 18, 18, EGA.WHITE);
  frame(hx - 9, top, 18, 18, EGA.BLACK);
  rect(hx - 8, top + 14, 16, 3, EGA.LGRAY);                         // jaw shadow
  // hair, in disarray
  rect(hx - 10, top - 3, 20, 6, EGA.BLACK);
  px(hx - 7, top - 5, EGA.BLACK); px(hx - 1, top - 6, EGA.BLACK);
  px(hx + 4, top - 5, EGA.BLACK); px(hx + 7, top - 4, EGA.BLACK);
  // the 2px dark band under the eyes
  rect(hx - 7, top + 9, 15, 2, EGA.DGRAY);
  // eyes
  if (idle.blink) {
    hline(hx - 6, top + 8, 4, EGA.BLACK);
    hline(hx + 2, top + 8, 4, EGA.BLACK);
  } else {
    rect(hx - 6, top + 6, 4, 3, EGA.WHITE);
    rect(hx + 2, top + 6, 4, 3, EGA.WHITE);
    rect(hx - 5, top + 7, 2, 2, EGA.BLACK);
    rect(hx + 3, top + 7, 2, 2, EGA.BLACK);
    frame(hx - 6, top + 6, 4, 3, EGA.BLACK);
    frame(hx + 2, top + 6, 4, 3, EGA.BLACK);
  }
  // mouth: a flat line. It is always a flat line.
  hline(hx - 4, top + 14, 8, EGA.BLACK);

  return { x: x, top: top, shoulderX: x + 16, shoulderY: top + 26, reach: idle.reach };
}

/* The manager's right arm. When the handshake is live it is drawn to the clasp
 * point in EVERY frame, including while the other hand does paperwork. */
function drawManagerRightArm(m, pose, clasp) {
  if (pose === 'handshake') {
    rect(m.x + 16, m.top + 22, 8, 12, EGA.BLUE);
    frame(m.x + 16, m.top + 22, 8, 12, EGA.BLACK);
    thickSlope(m.x + 18, m.top + 33, clasp.x - 5, clasp.y - 2, EGA.BLACK, 6);
    thickSlope(m.x + 18, m.top + 34, clasp.x - 5, clasp.y - 1, EGA.BLUE, 4);
    slope(m.x + 18, m.top + 34, clasp.x - 5, clasp.y - 1, EGA.LBLUE);
    return;
  }
  // reaching, periodically, for a cup that is already empty
  const drop = Math.round(m.reach * 10);
  rect(m.x + 16, m.top + 22, 8, 22 - drop, EGA.BLUE);
  frame(m.x + 16, m.top + 22, 8, 22 - drop, EGA.BLACK);
  rect(m.x + 17, m.top + 43 - drop, 6, 4, EGA.WHITE);
  frame(m.x + 17, m.top + 43 - drop, 6, 4, EGA.BLACK);
}

/* =========================================================================
 * THE APPLICANT — four locked poses, four different base rigs
 * ========================================================================= */

/* How far from the desk each pose stands. STARE keeps a distance the manager
 * will later describe in writing. */
const POSE_OFFSET = { handshake: -6, seated: 0, stare: 12, fart: 4, none: 0 };

function drawPlayer(baseX, pose, frameCount, walkPhase) {
  const isWalk = walkPhase !== undefined && walkPhase !== null;
  const x = baseX + (isWalk ? 0 : (POSE_OFFSET[pose] || 0));
  let top = 56, legLen = 26;

  if (pose === 'seated') { top = 62; legLen = 14; }

  // the chair, which is wrong somehow
  if (pose === 'seated') {
    rect(x - 13, top + 6, 27, 36, EGA.DGRAY);       // backrest, behind him
    frame(x - 13, top + 6, 27, 36, EGA.BLACK);
    hline(x - 11, top + 12, 23, EGA.BLACK);
    rect(x - 17, 102, 35, 6, EGA.DGRAY);            // seat, visible either side
    frame(x - 17, 102, 35, 6, EGA.BLACK);
    rect(x - 15, 108, 4, 17, EGA.DGRAY);            // legs
    frame(x - 15, 108, 4, 17, EGA.BLACK);
    rect(x + 12, 108, 4, 12, EGA.DGRAY);            // this one is shorter
    frame(x + 12, 108, 4, 12, EGA.BLACK);
    rect(x + 10, 120, 8, 5, EGA.WHITE);             // propped up on a stack of forms
    frame(x + 10, 120, 8, 5, EGA.DGRAY);
    hline(x + 11, 122, 6, EGA.DGRAY);
  }

  // head
  const hx = x;
  rect(hx - 7, top, 15, 16, EGA.WHITE);
  frame(hx - 7, top, 15, 16, EGA.BLACK);
  rect(hx - 8, top - 3, 17, 5, EGA.BROWN);          // neat, hopeful hair
  frame(hx - 8, top - 3, 17, 5, EGA.BLACK);
  if (pose === 'stare') {
    // never blinks
    rect(hx - 6, top + 6, 4, 4, EGA.WHITE); frame(hx - 6, top + 6, 4, 4, EGA.BLACK);
    rect(hx + 2, top + 6, 4, 4, EGA.WHITE); frame(hx + 2, top + 6, 4, 4, EGA.BLACK);
    rect(hx - 5, top + 7, 2, 2, EGA.BLACK); rect(hx + 3, top + 7, 2, 2, EGA.BLACK);
  } else {
    const blink = (frameCount % 150) > 144;
    if (blink) { hline(hx - 6, top + 8, 4, EGA.BLACK); hline(hx + 2, top + 8, 4, EGA.BLACK); }
    else { rect(hx - 6, top + 6, 3, 3, EGA.BLACK); rect(hx + 3, top + 6, 3, 3, EGA.BLACK); }
  }
  // an eager mouth
  if (pose === 'fart') hline(hx - 2, top + 12, 5, EGA.BLACK);
  else { hline(hx - 4, top + 12, 8, EGA.BLACK); px(hx - 5, top + 11, EGA.BLACK); px(hx + 4, top + 11, EGA.BLACK); }

  // cheap eager suit
  const bodyTop = top + 16;
  rect(hx - 11, bodyTop, 23, 24, EGA.BROWN);
  frame(hx - 11, bodyTop, 23, 24, EGA.BLACK);
  rect(hx - 3, bodyTop, 7, 24, EGA.WHITE);          // shirt
  vline(hx - 4, bodyTop, 24, EGA.BLACK);
  vline(hx + 4, bodyTop, 24, EGA.BLACK);
  rect(hx - 1, bodyTop + 2, 3, 12, EGA.GREEN);      // tie
  frame(hx - 1, bodyTop + 2, 3, 12, EGA.BLACK);
  rect(hx - 10, bodyTop + 1, 6, 22, EGA.YELLOW);    // cheap lapel sheen

  // legs
  if (pose === 'seated') {
    rect(hx - 10, bodyTop + 24, 20, 7, EGA.DGRAY);  // thighs, forward
    frame(hx - 10, bodyTop + 24, 20, 7, EGA.BLACK);
    rect(hx - 9, bodyTop + 24, 8, legLen, EGA.DGRAY);
    frame(hx - 9, bodyTop + 24, 8, legLen, EGA.BLACK);
    rect(hx + 1, bodyTop + 24, 8, legLen, EGA.DGRAY);
    frame(hx + 1, bodyTop + 24, 8, legLen, EGA.BLACK);
    rect(hx - 11, bodyTop + 24 + legLen, 11, 4, EGA.BLACK);
    rect(hx + 0, bodyTop + 24 + legLen, 11, 4, EGA.BLACK);
  } else {
    const stride = isWalk ? [0, 3, 0, -3][walkPhase % 4] : 0;
    rect(hx - 9 - stride, bodyTop + 24, 8, legLen, EGA.DGRAY);
    frame(hx - 9 - stride, bodyTop + 24, 8, legLen, EGA.BLACK);
    rect(hx + 2 + stride, bodyTop + 24, 8, legLen, EGA.DGRAY);
    frame(hx + 2 + stride, bodyTop + 24, 8, legLen, EGA.BLACK);
    rect(hx - 11 - stride, bodyTop + 24 + legLen, 11, 4, EGA.BLACK);
    rect(hx + 1 + stride, bodyTop + 24 + legLen, 11, 4, EGA.BLACK);
  }

  const rig = {
    x: hx, top: top, bodyTop: bodyTop,
    shoulderX: hx - 11, shoulderY: bodyTop + 5
  };

  // arms and briefcase, per pose
  if (pose === 'handshake') {
    drawCaseArm(hx, bodyTop, 0);                                       // trailing arm
  } else if (pose === 'stare') {
    rect(hx - 15, bodyTop + 2, 5, 22, EGA.BROWN);                      // right arm rigid
    frame(hx - 15, bodyTop + 2, 5, 22, EGA.BLACK);
    drawCaseArm(hx, bodyTop, 0);
  } else if (pose === 'fart') {
    rect(hx - 15, bodyTop + 2, 5, 18, EGA.BROWN);                      // right hand behind him
    frame(hx - 15, bodyTop + 2, 5, 18, EGA.BLACK);
    rect(hx - 17, bodyTop + 18, 7, 5, EGA.WHITE);
    frame(hx - 17, bodyTop + 18, 7, 5, EGA.BLACK);
    drawCaseArm(hx, bodyTop, 0);
  } else if (pose === 'seated') {
    rect(hx - 15, bodyTop + 2, 5, 18, EGA.BROWN);
    frame(hx - 15, bodyTop + 2, 5, 18, EGA.BLACK);
    rect(hx + 11, bodyTop + 2, 5, 18, EGA.BROWN);
    frame(hx + 11, bodyTop + 2, 5, 18, EGA.BLACK);
    rect(hx - 9, bodyTop + 20, 19, 9, EGA.BROWN);                      // case on the lap
    frame(hx - 9, bodyTop + 20, 19, 9, EGA.BLACK);
    hline(hx - 8, bodyTop + 24, 17, EGA.DGRAY);
  } else {
    const swing = isWalk ? [0, 2, 0, -2][walkPhase % 4] : 0;
    rect(hx - 15, bodyTop + 2 + swing, 5, 20, EGA.BROWN);
    frame(hx - 15, bodyTop + 2 + swing, 5, 20, EGA.BLACK);
    drawCaseArm(hx, bodyTop, -swing);
  }
  return rig;
}

/* His left arm, the fist at the end of it, and the case hanging from the fist.
 * The handle has to rise INTO the hand: drawing the case alongside the arm was
 * what made it read as floating off to the side. */
function drawCaseArm(hx, bodyTop, dy) {
  const ax = hx + 11, ay = bodyTop + 2 + dy;
  rect(ax, ay, 5, 17, EGA.BROWN);
  frame(ax, ay, 5, 17, EGA.BLACK);
  const fistY = ay + 16;
  rect(ax - 1, fistY, 7, 6, EGA.WHITE);
  frame(ax - 1, fistY, 7, 6, EGA.BLACK);
  drawBriefcase(ax + 2, fistY + 3);            // centred directly under the fist
}

function drawBriefcase(cx, y) {
  rect(cx - 3, y, 2, 5, EGA.DGRAY);            // handle, gripped in the fist above
  rect(cx + 2, y, 2, 5, EGA.DGRAY);
  rect(cx - 7, y + 4, 15, 11, EGA.BROWN);
  frame(cx - 7, y + 4, 15, 11, EGA.BLACK);
  hline(cx - 6, y + 9, 13, EGA.DGRAY);
  rect(cx - 1, y + 7, 3, 3, EGA.YELLOW);       // the clasp
}

/* The clasp. Once taken, both figures are joined across the desk forever. */
function drawClasp(m, p, frameCount) {
  const bob = Math.round(Math.sin(frameCount / 70) * 1.2);
  const clasp = { x: 198, y: 88 + bob };
  drawManagerRightArm(m, 'handshake', clasp);
  // the applicant's arm reaches back to the same point
  thickSlope(p.shoulderX, p.shoulderY - 1, clasp.x + 7, clasp.y - 1, EGA.BLACK, 6);
  thickSlope(p.shoulderX, p.shoulderY, clasp.x + 7, clasp.y, EGA.BROWN, 4);
  // the hands
  rect(clasp.x - 4, clasp.y - 3, 11, 8, EGA.WHITE);
  frame(clasp.x - 4, clasp.y - 3, 11, 8, EGA.BLACK);
  hline(clasp.x - 3, clasp.y, 9, EGA.LGRAY);
  hline(clasp.x - 3, clasp.y + 2, 9, EGA.LGRAY);
  return clasp;
}

/* One clean animation cue, then permanent silence on the subject. */
function drawFartCue(x, progress) {
  const rise = Math.floor(progress * 32);
  const spread = 6 + Math.floor(progress * 16);
  const density = 2 + Math.floor(progress * 6);
  // Off his right and above the briefcase, which he now never puts down.
  const cx = x + 28 - spread / 2;
  const base = 96;
  speckle(cx, base - rise, spread, 12, EGA.GREEN, density);
  speckle(cx, base - rise, spread, 12, EGA.LGREEN, density + 3);
}

/* =========================================================================
 * THE DIALOGUE BOX
 * ========================================================================= */

const BOX = { x: 4, y: BOX_TOP, w: W - 8, h: H - BOX_TOP - 4 };
const TEXT_X = BOX.x + 6, TEXT_Y = BOX.y + 7;
const MAX_CHARS = Math.floor((BOX.w - 12) / ADVANCE);
const MAX_LINES = Math.floor((BOX.h - 14) / LINE_H);

function drawBox() {
  rect(BOX.x, BOX.y, BOX.w, BOX.h, EGA.BLUE);
  frame(BOX.x, BOX.y, BOX.w, BOX.h, EGA.WHITE);
  frame(BOX.x + 2, BOX.y + 2, BOX.w - 4, BOX.h - 4, EGA.LGRAY);
}

function drawBoxLines(lines, colour) {
  for (let i = 0; i < lines.length; i++) text(TEXT_X, TEXT_Y + i * LINE_H, lines[i], colour || EGA.WHITE);
}

function drawMorePrompt(frameCount) {
  if ((frameCount % 40) < 22) text(BOX.x + BOX.w - 40, BOX.y + BOX.h - 11, 'MORE', EGA.YELLOW);
}

function drawChoices(prompt, choices, selected, frameCount) {
  // The full question was just typed out as its own beat; this is the terse
  // restatement that sits above the options.
  const header = wrap(prompt, MAX_CHARS);
  const room = Math.max(1, MAX_LINES - choices.length - 1);
  const shown = header.slice(0, room);
  if (header.length > room) shown[room - 1] = shown[room - 1].slice(0, MAX_CHARS - 2) + '…';
  drawBoxLines(shown, EGA.LCYAN);
  let y = TEXT_Y + (shown.length + 0.4) * LINE_H;
  for (let i = 0; i < choices.length; i++) {
    const on = i === selected;
    const label = (i + 1) + '. ' + choices[i].label;
    const clipped = label.length > MAX_CHARS - 2 ? label.slice(0, MAX_CHARS - 3) + '…' : label;
    if (on) rect(TEXT_X - 2, y - 1, BOX.w - 12, LINE_H, EGA.DGRAY);
    text(TEXT_X, y, clipped, on ? EGA.YELLOW : EGA.LGRAY);
    if (on && (frameCount % 30) < 18) text(TEXT_X - 6, y, '>', EGA.WHITE);
    hit(TEXT_X - 4, y - 1, BOX.w - 12, LINE_H, { kind: 'choice', index: i });
    y += LINE_H;
  }
}

function drawTextEntry(prompt, value, placeholder, frameCount) {
  const header = wrap(prompt, MAX_CHARS).slice(0, MAX_LINES - 2);
  drawBoxLines(header, EGA.LCYAN);
  const y = TEXT_Y + (header.length + 0.6) * LINE_H;
  rect(TEXT_X - 2, y - 2, BOX.w - 12, LINE_H + 2, EGA.BLACK);
  frame(TEXT_X - 2, y - 2, BOX.w - 12, LINE_H + 2, EGA.DGRAY);
  const shown = value.length ? value : placeholder;
  text(TEXT_X + 1, y, shown.slice(0, MAX_CHARS - 2), value.length ? EGA.WHITE : EGA.DGRAY);
  if ((frameCount % 30) < 16) {
    rect(TEXT_X + 1 + Math.min(value.length, MAX_CHARS - 2) * ADVANCE, y, 4, GLYPH_H, EGA.YELLOW);
  }
  text(TEXT_X, BOX.y + BOX.h - 11, 'ENTER TO SUBMIT', EGA.DGRAY);
}

/* =========================================================================
 * TITLE / OPTIONS / REPORT
 * ========================================================================= */

function drawTitleBus(cx, y) {
  rect(cx - 46, y, 92, 22, EGA.YELLOW);
  rect(cx - 46, y + 18, 92, 4, EGA.BROWN);
  hline(cx - 46, y, 92, EGA.WHITE);
  for (let i = 0; i < 4; i++) rect(cx - 40 + i * 22, y + 4, 16, 9, EGA.CYAN);
  ellipse(cx - 30, y + 24, 6, 5, EGA.DGRAY);
  ellipse(cx + 28, y + 24, 6, 5, EGA.DGRAY);
  ellipse(cx - 30, y + 24, 3, 2, EGA.LGRAY);
  ellipse(cx + 28, y + 24, 3, 2, EGA.LGRAY);
  rect(cx + 44, y + 8, 4, 5, EGA.WHITE);
}

function drawTitle(state, frameCount) {
  dither(0, 0, W, H, EGA.BLUE, EGA.BLACK, 3);
  dither(0, 0, W, 60, EGA.BLACK, EGA.BLUE, 2);

  textBig(28, 12, 'JOB INTERVIEW', EGA.YELLOW);
  textBig(52, 30, 'AT FAIRWEATHER', EGA.YELLOW);
  textBig(88, 48, 'TRANSIT', EGA.WHITE);
  hline(24, 66, 272, EGA.DGRAY);

  drawTitleBus(160, 72);

  const buttons = ['GO IN', 'OPTIONS', "DON'T GET ON DA BUS"];
  for (let i = 0; i < buttons.length; i++) {
    const y = 108 + i * 14, on = state.selected === i;
    const label = buttons[i];
    const bx = 160 - (label.length * ADVANCE) / 2 - 8;
    const bw = label.length * ADVANCE + 24;
    if (on) { rect(bx - 4, y - 3, bw, 13, EGA.DGRAY); frame(bx - 4, y - 3, bw, 13, EGA.LGRAY); }
    text(bx + 8, y, label, on ? EGA.YELLOW : EGA.LGRAY);
    if (on && (frameCount % 30) < 18) text(bx, y, '>', EGA.WHITE);
    hit(bx - 4, y - 3, bw, 13, { kind: 'title', index: i });
  }

  // the blinking cursor
  if ((frameCount % 44) < 24) rect(160 - 3, 152, 6, 8, EGA.LGREEN);

  drawNoticeBoard(state.config);
}

/* The status disclosure. A municipal notice board, in the Authority's own voice. */
function drawNoticeBoard(config) {
  const x = 4, y = H - 47, w = 136, h = 45;
  rect(x, y, w, h, EGA.BROWN);
  frame(x, y, w, h, EGA.BLACK);
  rect(x + 2, y + 2, w - 4, h - 4, EGA.LGRAY);
  hline(x + 4, y + 13, w - 8, EGA.DGRAY);
  const live = config && config.live;
  text(x + 5, y + 4, 'TRANSIT AUTH. NETWORK:', EGA.BLACK);
  if (live) {
    text(x + 5, y + 17, 'ONLINE', EGA.GREEN);
  } else {
    text(x + 5, y + 17, 'DOWN. EMERGENCY', EGA.RED);
    text(x + 5, y + 25, 'PROCEDURES IN EFFECT.', EGA.RED);
  }
  text(x + 5, y + 34, '(' + (config ? config.backend : '?') + ')', EGA.DGRAY);
}

function drawOptions(state, frameCount) {
  dither(0, 0, W, H, EGA.CYAN, EGA.BLUE, 4);
  // a clipboard
  rect(30, 10, 260, 180, EGA.BROWN);
  rect(34, 14, 252, 172, EGA.WHITE);
  rect(130, 4, 60, 12, EGA.DGRAY);
  frame(130, 4, 60, 12, EGA.BLACK);
  rect(150, 2, 20, 8, EGA.LGRAY);

  text(44, 24, 'FAIRWEATHER TRANSIT AUTHORITY', EGA.BLACK);
  text(44, 33, 'FORM 12-B  -  APPLICANT PREFERENCES', EGA.DGRAY);
  hline(44, 42, 232, EGA.DGRAY);

  const rows = state.optionRows;
  let y = 52;
  for (let i = 0; i < rows.length; i++) {
    const row = rows[i], on = state.selected === i;
    if (on && row.kind !== 'action') rect(40, y - 2, 240, 13, EGA.YELLOW);
    if (row.kind !== 'action') text(44, y, row.label, EGA.BLACK);
    if (on && (frameCount % 30) < 18 && row.kind !== 'action') text(38, y, '>', EGA.RED);

    if (row.kind === 'toggle3') {
      let ox = 150;
      for (const opt of row.options) {
        const disabled = !!opt.reason;
        const chosen = state.settings[row.key] === opt.value;
        rect(ox, y - 1, 9, 9, chosen ? EGA.BLACK : EGA.WHITE);
        frame(ox, y - 1, 9, 9, EGA.BLACK);
        if (chosen) { rect(ox + 3, y + 2, 3, 3, EGA.WHITE); }
        text(ox + 12, y, opt.label, disabled ? EGA.LGRAY : EGA.BLACK);
        if (!disabled) hit(ox - 2, y - 2, opt.label.length * ADVANCE + 16, 11,
                           { kind: 'toggle3', index: i, value: opt.value });
        ox += 12 + opt.label.length * ADVANCE + 8;
      }
      y += 11;
      const notes = row.options.filter(function (o) { return o.reason; })
        .map(function (o) { return o.label + ': ' + o.reason; });
      if (notes.length) { text(150, y, notes.join('   '), EGA.LGRAY); y += 10; }
      else y += 3;
    } else if (row.kind === 'slider') {
      const idx = row.options.findIndex(function (o) { return o.value === state.settings[row.key]; });
      const track = 78;
      hline(148, y + 3, track, EGA.DGRAY);
      for (let s = 0; s < row.options.length; s++) {
        vline(148 + s * (track / (row.options.length - 1)), y + 1, 5, EGA.DGRAY);
      }
      const kx = 148 + idx * (track / (row.options.length - 1));
      rect(kx - 2, y - 1, 5, 9, EGA.RED);
      text(148 + track + 8, y, row.options[idx].label, EGA.BLACK);
      y += 14;
    } else if (row.kind === 'onoff') {
      const on2 = state.settings[row.key];
      rect(150, y - 1, 9, 9, on2 ? EGA.BLACK : EGA.WHITE);
      frame(150, y - 1, 9, 9, EGA.BLACK);
      if (on2) { rect(153, y + 2, 3, 3, EGA.WHITE); }
      text(164, y, on2 ? 'ON' : 'OFF', EGA.BLACK);
      hit(148, y - 2, 46, 11, { kind: 'onoff', index: i });
      y += 14;
    } else {
      // An actual button, because as a plain row nobody could tell it was one.
      const bw = row.label.length * ADVANCE + 22;
      rect(44, y - 3, bw, 14, on ? EGA.YELLOW : EGA.LGRAY);
      frame(44, y - 3, bw, 14, EGA.BLACK);
      text(55, y, row.label, EGA.BLACK);
      if (on && (frameCount % 30) < 18) text(47, y, '>', EGA.RED);
      hit(44, y - 3, bw, 14, { kind: 'action', index: i });
      y += 18;
    }
  }

  hline(44, 168, 232, EGA.DGRAY);
  text(44, 174, 'ARROWS OR MOUSE.  ESC TO GO BACK.', EGA.DGRAY);
}

const FAREWELL_BOX = { x: 26, y: 56, w: 268, h: 92 };
const FAREWELL_CHARS = Math.floor((FAREWELL_BOX.w - 20) / ADVANCE);

function drawFarewellCard(lines, frameCount, mode) {
  dither(0, 0, W, H, EGA.BLACK, EGA.BLUE, 3);
  const B = FAREWELL_BOX;
  rect(B.x, B.y, B.w, B.h, EGA.BLUE);
  frame(B.x, B.y, B.w, B.h, EGA.WHITE);
  frame(B.x + 2, B.y + 2, B.w - 4, B.h - 4, EGA.LGRAY);

  const cx = B.x + B.w / 2;
  let y = B.y + 12;
  for (const line of wrap(lines[0] || '', FAREWELL_CHARS)) {
    textCentered(cx, y, line, EGA.YELLOW); y += LINE_H;
  }
  y += 5;
  for (const line of wrap(lines[1] || '', FAREWELL_CHARS)) {
    textCentered(cx, y, line, EGA.WHITE); y += LINE_H;
  }

  hline(B.x + 10, B.y + B.h - 20, B.w - 20, EGA.DGRAY);
  const footer = { closed: 'THE OFFICE IS CLOSED',
                   closing: 'CLOSING THE OFFICE…',
                   leaving: 'PRESS ANY KEY' }[mode];
  if (mode === 'closed') {
    textCentered(cx, B.y + B.h - 14, footer, EGA.LGRAY);
  } else if ((frameCount % 40) < 22) {
    textCentered(cx, B.y + B.h - 14, footer, EGA.LGRAY);
  }
}

/* The report card, in the style of the end-of-shift card. */
/* The pose chosen in turn 1 is a rendering fact, so it has to survive to the
 * last frame of the game. The report card is a full-page document, so the pose
 * comes with it: a photograph of the applicant, in pose, stapled to the form.
 * It is a pixel-exact clipped window onto the same drawPlayer rig the scene
 * uses — no scaling, so it stays crisp. */
function drawPosePhoto(x, y, w, h, pose, frameCount) {
  rect(x - 2, y - 2, w + 4, h + 10, EGA.WHITE);
  frame(x - 2, y - 2, w + 4, h + 10, EGA.BLACK);
  b.save();
  b.beginPath();
  b.rect(x, y, w, h);
  b.clip();
  dither(x, y, w, h, EGA.LGRAY, EGA.WHITE, 3);
  b.translate(x - 214, y - 50);
  drawPlayer(238, pose, frameCount, null);
  b.restore();
  frame(x, y, w, h, EGA.DGRAY);
  // the staple
  rect(x + w / 2 - 3, y - 4, 7, 3, EGA.DGRAY);
  textCentered(x + w / 2, y + h + 2, 'ON FILE', EGA.DGRAY);
}

function drawReport(report, state, frameCount) {
  dither(0, 0, W, H, EGA.DGRAY, EGA.BLACK, 4);
  rect(14, 4, 292, 192, EGA.WHITE);
  frame(14, 4, 292, 192, EGA.BLACK);
  frame(16, 6, 288, 188, EGA.DGRAY);

  text(22, 11, 'FAIRWEATHER TRANSIT AUTHORITY  -  FORM 12-B', EGA.BLACK);
  text(22, 20, 'APPLICANT: ' + report.name, EGA.DGRAY);
  hline(22, 28, 276, EGA.BLACK);

  // The photograph sits in the top right, so every column left of it has to
  // stop at PHOTO_X or the two collide.
  const PHOTO_X = 244, VAL_X = 166, TIER_X = 194;

  let y = 33;
  for (const row of report.rows) {
    text(22, y, row.label, EGA.BLACK);
    text(VAL_X, y, row.display, row.value >= 0 ? EGA.GREEN : EGA.RED);
    text(TIER_X, y, row.tier, EGA.BLACK);
    y += 10;
  }

  hline(22, y, 214, EGA.DGRAY);
  y += 4;
  text(22, y, 'ASSESSED TOTAL', EGA.BLACK);
  text(VAL_X, y, report.total_display, report.total >= 0 ? EGA.GREEN : EGA.RED);
  y += 12;

  // recorded, remarked upon, deliberately not counted
  text(22, y, 'RECORDED. NOT SCORED.', EGA.DGRAY);
  y += 9;
  // These descriptors run longer than the Awful-to-Perfect tiers, so this block
  // uses its own narrower columns to stay clear of the photograph.
  for (const row of report.noted) {
    text(22, y, row.label, EGA.DGRAY);
    text(150, y, row.display, EGA.DGRAY);
    text(172, y, row.tier, EGA.DGRAY);
    y += 10;
  }

  hline(22, y, 276, EGA.BLACK);
  y += 5;
  text(22, y + 4, 'FINAL GRADE', EGA.BLACK);
  textBig(112, y, report.grade, EGA.RED);
  if (report.stamp) {
    const sx = 176, sy = y - 2;
    frame(sx, sy, 108, 19, EGA.RED);
    frame(sx + 2, sy + 2, 104, 15, EGA.RED);
    textCentered(sx + 54, sy + 6, report.stamp, EGA.RED);
  }
  y += 18;

  // The closing block is tight: standout, blurb and the hired line all have to
  // land above the buttons, so it runs at 8px rather than the usual 9.
  const CLOSE_H = 8;
  if (report.standout) {
    const all = wrap(report.standout, 45);
    const shown = all.slice(0, 2);
    if (all.length > 2) shown[1] = shown[1].slice(0, 43) + '…';
    for (const line of shown) {
      text(22, y, line, EGA.BLUE);
      y += CLOSE_H;
    }
  }
  for (const line of wrap(report.sign_off, 45).slice(0, 2)) {
    text(22, y, line, EGA.BLACK);
    y += CLOSE_H;
  }
  text(22, y, report.hired_line, EGA.RED);

  drawPosePhoto(PHOTO_X, 33, 46, 54, report.pose || 'none', frameCount);

  const buttons = ['PLAY AGAIN', 'GO HOME'];
  for (let i = 0; i < buttons.length; i++) {
    const bx = 40 + i * 130, by = 179, on = state.selected === i;
    if (on) { rect(bx - 4, by - 3, 104, 12, EGA.YELLOW); frame(bx - 4, by - 3, 104, 12, EGA.BLACK); }
    text(bx + 4, by, buttons[i], EGA.BLACK);
    if (on && (frameCount % 30) < 18) text(bx - 2, by, '>', EGA.RED);
    hit(bx - 4, by - 3, 104, 12, { kind: 'report', index: i });
  }
}

/* ---- the F1 ledger overlay ---- */
function drawLedgerOverlay(led, scroll) {
  if (!led) return;
  const lines = JSON.stringify(led, null, 1).split('\n');
  const w = 150, h = 190, x = W - w - 3, y = 3;
  rect(x, y, w, h, EGA.BLACK);
  frame(x, y, w, h, EGA.LGREEN);
  text(x + 4, y + 4, 'LEDGER.JSON  [F1]', EGA.LGREEN);
  hline(x + 3, y + 13, w - 6, EGA.GREEN);
  const rows = Math.floor((h - 20) / 8);
  const start = Math.max(0, Math.min(scroll, Math.max(0, lines.length - rows)));
  for (let i = 0; i < rows && start + i < lines.length; i++) {
    const line = lines[start + i].slice(0, 24);
    text(x + 4, y + 17 + i * 8, line, EGA.LGREEN);
  }
  if (lines.length > rows) {
    text(x + w - 46, y + h - 10, start + rows >= lines.length ? 'END' : 'PGDN', EGA.GREEN);
  }
}

window.R = {
  EGA: EGA, W: W, H: H, BOX: BOX, MAX_CHARS: MAX_CHARS, MAX_LINES: MAX_LINES,
  LINE_H: LINE_H, ADVANCE: ADVANCE, EXIT_HITBOX: EXIT_HITBOX,
  attach: attach, present: present, buf: buf, ctx: b, hits: hits,
  px: px, rect: rect, frame: frame, hline: hline, vline: vline,
  dither: dither, speckle: speckle, ellipse: ellipse, slope: slope, thickSlope: thickSlope,
  text: text, textBig: textBig, textCentered: textCentered,
  wrap: wrap, paginate: paginate,
  drawWall: drawWall, drawFloor: drawFloor, drawBus: drawBus, drawFixtures: drawFixtures,
  cupLayout: cupLayout, drawDesk: drawDesk,
  managerIdle: managerIdle, drawManager: drawManager, drawManagerRightArm: drawManagerRightArm,
  drawPlayer: drawPlayer, drawClasp: drawClasp, drawFartCue: drawFartCue,
  POSE_OFFSET: POSE_OFFSET,
  drawBox: drawBox, drawBoxLines: drawBoxLines, drawMorePrompt: drawMorePrompt,
  drawChoices: drawChoices, drawTextEntry: drawTextEntry,
  drawTitle: drawTitle, drawOptions: drawOptions,
  drawFarewellCard: drawFarewellCard, drawReport: drawReport,
  drawLedgerOverlay: drawLedgerOverlay
};
