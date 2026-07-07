#!/usr/bin/env python3
"""
rotate_logo_ascii_ultra.py — Ultimate rotating ASCII logo with EVERY effect.

Backgrounds (auto-cycling):
  • Plasma — flowing sinusoidal interference
  • Tunnel — polar-coordinate infinite corridor
  • Julia  — fractal zoom with rotating c

Logo:
  • 2D image rotation (half-block / braille) with pseudo-3D extrusion
  • Layered extruded 3D wordmark (face + side + shadow)

Overlay effects:
  • Starfield (dust / mid / cross-stars / grid / streams)
  • Matrix digital rain (vertical, head-highlighted)
  • Energy rings (expanding, hue-shifted)
  • Physics ring explosions (gravity + damping)
  • Sparkle particles
  • Cog decorations (parametric gears in corners)
  • CRT scanlines (real row-dimming)
  • Noise-from-static boot (TV-tuning signal lock)
  • Multi-style unified palettes (golden / blackgold / cyber / ice / matrix / ember)
"""
from __future__ import annotations

import argparse
import colorsys
import math
import random
import re
import shutil
import sys
import time
from collections import deque
from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt, map_coordinates
from PIL import Image

try:
    RESAMPLE_BICUBIC = Image.Resampling.BICUBIC
    RESAMPLE_BOX = Image.Resampling.BOX
except AttributeError:
    RESAMPLE_BICUBIC = Image.BICUBIC
    RESAMPLE_BOX = Image.BOX

# ════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ════════════════════════════════════════════════════════════════════════

DEFAULT_IMAGE = Path(__file__).resolve().parent / "nexus_logo.png"
DEFAULT_LABEL = "NEXUS"
SIGNATURE_LABEL = "Charles"
SIGNATURE_ART_ROWS = [
    "    / Charles",
    "___/________",
]
DEFAULT_MAX_WIDTH = 100
DEFAULT_MAX_HEIGHT = 26
DEFAULT_ASPECT = 0.94
DEFAULT_THRESHOLD = 160
WORDMARK_GAP_RATIO = 0.18
WORDMARK_STRETCH = 0.86

BLOCKS = {(False, False): " ", (True, False): "▀", (False, True): "▄", (True, True): "█"}

WORDMARK_PATTERNS = {
    "N": ["███      ███","████     ███","█████    ███","██ ███   ███","██  ███  ███","██   ███ ███","██    ██████","██     █████","██      ████","██       ███","██       ███"],
    "E": ["████████████","████████████","███         ","███         ","███████████ ","███████████ ","███         ","███         ","███         ","████████████","████████████"],
    "X": ["███      ███","████    ████"," ████  ████ ","  ████████  ","   ██████   ","    ████    ","   ██████   ","  ████████  "," ████  ████ ","████    ████","███      ███"],
    "U": ["███      ███","███      ███","███      ███","███      ███","███      ███","███      ███","███      ███","███      ███"," ███    ███ ","  ████████  ","   ██████   "],
    "S": [" ██████████ ","████████████","███         ","███         ","██████████  "," ██████████ ","      ██████","         ███","         ███","████████████"," ██████████ "],
}

SIGNATURE_PATTERNS = {
    "C": [" ████","█    ","█    ","█    "," ████"],
    "H": ["█   █","█   █","█████","█   █","█   █"],
    "A": [" ███ ","█   █","█████","█   █","█   █"],
    "R": ["████ ","█   █","████ ","█  █ ","█   █"],
    "L": ["█    ","█    ","█    ","█    ","█████"],
    "E": ["█████","█    ","████ ","█    ","█████"],
    "S": [" ████","█    "," ███ ","    █","████ "],
}

RESET = "\x1b[0m"
HIDE_CURSOR = "\x1b[?25l"
SHOW_CURSOR = "\x1b[?25h"
CLEAR_SCREEN = "\x1b[2J"
HOME = "\x1b[H"
ANSI_RE = re.compile(r"\x1b\[[^m]*m")
CELL_RE = re.compile(r"\x1b\[[^m]*m.\x1b\[0m|.")

# Glyph ramps
PLASMA_GLYPHS = " .:-=+*#%@"
TUNNEL_GLYPHS = " .:oO0@#"
JULIA_GLYPHS  = "  .:rsZE3"
RAYMARCH_GLYPHS = " .:-=+*#%@"

# Default palette values. Legacy names are kept for fallback/reference.
CYAN_HUE   = 0.118  # polished gold
BLUE_HUE   = 0.090  # amber bronze
VIOLET_HUE = 0.065  # dark copper shadow
HUE_RANGE  = 0.018

DEFAULT_STYLE = "golden"
RANDOM_STYLE = "random"
DEFAULT_STYLE_MODE = RANDOM_STYLE
STYLE_RANDOM_FRAMES = 140
STYLE_TRANSITION_FRAMES = 18
ACTIVE_STYLE = DEFAULT_STYLE
STYLE_SOURCE = DEFAULT_STYLE
STYLE_TARGET = DEFAULT_STYLE
STYLE_BLEND_T = 1.0

STYLE_PRESETS = {
    "golden": {
        "name": "GOLDEN",
        "primary_hue": 0.118,
        "secondary_hue": 0.090,
        "shadow_hue": 0.065,
        "hue_range": 0.018,
        "logo_hue_shift": -0.020,
        "logo_hue_span": 0.020,
        "logo_sat_base": 0.48,
        "logo_sat_span": 0.32,
        "logo_val_base": 0.36,
        "logo_val_span": 0.58,
        "aura_hue_shift": -0.015,
        "aura_sat": 0.78,
        "aura_floor": 0.028,
        "aura_scale": 0.90,
        "bg_hue_shift": -0.030,
        "bg_hue_span": 0.025,
        "bg_sat_base": 0.38,
        "bg_sat_span": 0.30,
        "bg_val_base": 0.035,
        "bg_val_span": 0.20,
        "tail_hue_shift": -0.006,
        "hue_jitter_neg": -0.020,
        "hue_jitter_pos": 0.018,
        "noise_jitter_neg": -0.025,
        "noise_jitter_pos": 0.018,
        "wordmark_3d": {
            "side_dark": (44, 28, 7),
            "side_mid": (118, 75, 18),
            "side_hot": (213, 147, 40),
            "side_flash": (255, 236, 174),
            "cast": (18, 12, 4),
            "top": (255, 244, 190),
            "mid": (245, 184, 56),
            "bottom": (157, 96, 21),
            "rim": (255, 252, 223),
            "lowlight": (104, 60, 12),
            "sweep": (255, 249, 211),
            "spark": (255, 225, 112),
            "arc": (255, 191, 44),
        },
    },
    "blackgold": {
        "name": "BLACKGOLD",
        "primary_hue": 0.118,
        "secondary_hue": 0.084,
        "shadow_hue": 0.055,
        "hue_range": 0.010,
        "logo_hue_shift": -0.030,
        "logo_hue_span": 0.014,
        "logo_sat_base": 0.58,
        "logo_sat_span": 0.24,
        "logo_val_base": 0.13,
        "logo_val_span": 0.56,
        "aura_hue_shift": -0.020,
        "aura_sat": 0.90,
        "aura_floor": 0.012,
        "aura_scale": 0.55,
        "bg_hue_shift": -0.035,
        "bg_hue_span": 0.012,
        "bg_sat_base": 0.56,
        "bg_sat_span": 0.18,
        "bg_val_base": 0.006,
        "bg_val_span": 0.085,
        "flat_body_top_v": 0.46,
        "flat_body_bottom_v": 0.24,
        "flat_glow_top_v": 0.18,
        "flat_glow_bottom_v": 0.07,
        "tail_hue_shift": -0.012,
        "hue_jitter_neg": -0.012,
        "hue_jitter_pos": 0.010,
        "noise_jitter_neg": -0.015,
        "noise_jitter_pos": 0.010,
        "wordmark_3d": {
            "side_dark": (3, 2, 0),
            "side_mid": (42, 28, 7),
            "side_hot": (173, 119, 27),
            "side_flash": (255, 226, 122),
            "cast": (0, 0, 0),
            "top": (38, 31, 15),
            "mid": (210, 147, 36),
            "bottom": (8, 6, 2),
            "rim": (255, 219, 88),
            "lowlight": (1, 1, 0),
            "sweep": (255, 207, 62),
            "spark": (255, 239, 156),
            "arc": (255, 170, 24),
        },
    },
    "cyber": {
        "name": "CYBER",
        "primary_hue": 0.525,
        "secondary_hue": 0.820,
        "shadow_hue": 0.700,
        "hue_range": 0.050,
        "logo_hue_shift": -0.020,
        "logo_hue_span": 0.070,
        "logo_sat_base": 0.62,
        "logo_sat_span": 0.26,
        "logo_val_base": 0.32,
        "logo_val_span": 0.62,
        "aura_hue_shift": 0.020,
        "aura_sat": 0.86,
        "aura_floor": 0.026,
        "aura_scale": 0.95,
        "bg_hue_shift": -0.030,
        "bg_hue_span": 0.090,
        "bg_sat_base": 0.48,
        "bg_sat_span": 0.36,
        "bg_val_base": 0.030,
        "bg_val_span": 0.22,
        "tail_hue_shift": 0.040,
        "hue_jitter_neg": -0.045,
        "hue_jitter_pos": 0.050,
        "noise_jitter_neg": -0.050,
        "noise_jitter_pos": 0.050,
        "wordmark_3d": {
            "side_dark": (8, 8, 28),
            "side_mid": (34, 60, 116),
            "side_hot": (0, 214, 255),
            "side_flash": (255, 84, 235),
            "cast": (1, 2, 12),
            "top": (218, 255, 255),
            "mid": (0, 220, 255),
            "bottom": (112, 30, 210),
            "rim": (255, 100, 238),
            "lowlight": (22, 8, 78),
            "sweep": (255, 132, 246),
            "spark": (0, 255, 236),
            "arc": (116, 166, 255),
        },
    },
    "ice": {
        "name": "ICE",
        "primary_hue": 0.560,
        "secondary_hue": 0.610,
        "shadow_hue": 0.660,
        "hue_range": 0.024,
        "logo_hue_shift": -0.010,
        "logo_hue_span": 0.040,
        "logo_sat_base": 0.42,
        "logo_sat_span": 0.28,
        "logo_val_base": 0.34,
        "logo_val_span": 0.62,
        "aura_hue_shift": 0.000,
        "aura_sat": 0.62,
        "aura_floor": 0.024,
        "aura_scale": 0.88,
        "bg_hue_shift": -0.018,
        "bg_hue_span": 0.040,
        "bg_sat_base": 0.34,
        "bg_sat_span": 0.28,
        "bg_val_base": 0.024,
        "bg_val_span": 0.20,
        "tail_hue_shift": 0.018,
        "hue_jitter_neg": -0.030,
        "hue_jitter_pos": 0.034,
        "noise_jitter_neg": -0.030,
        "noise_jitter_pos": 0.034,
        "wordmark_3d": {
            "side_dark": (5, 17, 32),
            "side_mid": (42, 94, 134),
            "side_hot": (112, 218, 255),
            "side_flash": (230, 255, 255),
            "cast": (2, 7, 16),
            "top": (238, 255, 255),
            "mid": (142, 232, 255),
            "bottom": (50, 108, 170),
            "rim": (255, 255, 255),
            "lowlight": (16, 46, 88),
            "sweep": (244, 255, 255),
            "spark": (170, 244, 255),
            "arc": (94, 186, 255),
        },
    },
    "matrix": {
        "name": "MATRIX",
        "primary_hue": 0.340,
        "secondary_hue": 0.275,
        "shadow_hue": 0.400,
        "hue_range": 0.022,
        "logo_hue_shift": -0.015,
        "logo_hue_span": 0.034,
        "logo_sat_base": 0.58,
        "logo_sat_span": 0.30,
        "logo_val_base": 0.26,
        "logo_val_span": 0.62,
        "aura_hue_shift": -0.006,
        "aura_sat": 0.82,
        "aura_floor": 0.022,
        "aura_scale": 0.85,
        "bg_hue_shift": -0.024,
        "bg_hue_span": 0.040,
        "bg_sat_base": 0.46,
        "bg_sat_span": 0.30,
        "bg_val_base": 0.020,
        "bg_val_span": 0.18,
        "tail_hue_shift": 0.000,
        "hue_jitter_neg": -0.030,
        "hue_jitter_pos": 0.030,
        "noise_jitter_neg": -0.032,
        "noise_jitter_pos": 0.032,
        "wordmark_3d": {
            "side_dark": (4, 24, 8),
            "side_mid": (26, 104, 32),
            "side_hot": (72, 236, 79),
            "side_flash": (216, 255, 178),
            "cast": (0, 8, 2),
            "top": (219, 255, 194),
            "mid": (80, 236, 74),
            "bottom": (22, 112, 30),
            "rim": (242, 255, 220),
            "lowlight": (8, 60, 14),
            "sweep": (206, 255, 166),
            "spark": (140, 255, 116),
            "arc": (50, 255, 92),
        },
    },
    "ember": {
        "name": "EMBER",
        "primary_hue": 0.035,
        "secondary_hue": 0.006,
        "shadow_hue": 0.965,
        "hue_range": 0.026,
        "logo_hue_shift": -0.016,
        "logo_hue_span": 0.045,
        "logo_sat_base": 0.62,
        "logo_sat_span": 0.28,
        "logo_val_base": 0.28,
        "logo_val_span": 0.64,
        "aura_hue_shift": -0.012,
        "aura_sat": 0.88,
        "aura_floor": 0.025,
        "aura_scale": 0.92,
        "bg_hue_shift": -0.020,
        "bg_hue_span": 0.045,
        "bg_sat_base": 0.54,
        "bg_sat_span": 0.30,
        "bg_val_base": 0.026,
        "bg_val_span": 0.22,
        "tail_hue_shift": -0.010,
        "hue_jitter_neg": -0.035,
        "hue_jitter_pos": 0.030,
        "noise_jitter_neg": -0.036,
        "noise_jitter_pos": 0.034,
        "wordmark_3d": {
            "side_dark": (32, 5, 0),
            "side_mid": (120, 28, 7),
            "side_hot": (255, 86, 22),
            "side_flash": (255, 220, 134),
            "cast": (12, 0, 0),
            "top": (255, 226, 166),
            "mid": (255, 92, 22),
            "bottom": (138, 18, 5),
            "rim": (255, 244, 204),
            "lowlight": (70, 6, 0),
            "sweep": (255, 210, 112),
            "spark": (255, 150, 44),
            "arc": (255, 52, 16),
        },
    },
}

# Background cycle: each background lasts this many frames
BG_CYCLE_FRAMES = 240   # ~12s at 20fps
BG_CROSSFADE    = 20    # crossfade duration

# ════════════════════════════════════════════════════════════════════════
#  COLOR UTILITIES
# ════════════════════════════════════════════════════════════════════════

STYLE_VALUE_DEFAULTS = {
    "flat_shadow_top_v": 0.22,
    "flat_shadow_bottom_v": 0.08,
    "flat_glow_top_v": 0.34,
    "flat_glow_bottom_v": 0.18,
    "flat_body_top_v": 0.98,
    "flat_body_bottom_v": 0.66,
}


def set_style(name):
    global ACTIVE_STYLE, STYLE_SOURCE, STYLE_TARGET, STYLE_BLEND_T
    if name not in STYLE_PRESETS:
        raise ValueError(f"Unknown style: {name}")
    ACTIVE_STYLE = name
    STYLE_SOURCE = name
    STYLE_TARGET = name
    STYLE_BLEND_T = 1.0


def begin_style_transition(name):
    global ACTIVE_STYLE, STYLE_SOURCE, STYLE_TARGET, STYLE_BLEND_T
    if name not in STYLE_PRESETS:
        raise ValueError(f"Unknown style: {name}")
    if name == STYLE_TARGET and STYLE_BLEND_T >= 1.0:
        return
    STYLE_SOURCE = STYLE_TARGET
    STYLE_TARGET = name
    ACTIVE_STYLE = name
    STYLE_BLEND_T = 0.0


def update_style_transition(progress):
    global STYLE_BLEND_T
    STYLE_BLEND_T = smoothstep(progress)


def choose_random_style(exclude=None):
    choices = [name for name in STYLE_PRESETS if name != exclude]
    if not choices:
        choices = list(STYLE_PRESETS.keys())
    return random.choice(choices)


def random_style_interval(base_frames):
    base = max(1, base_frames)
    lo = max(1, int(base * 0.65))
    hi = max(lo, int(base * 1.35))
    return random.randint(lo, hi)


def _blend_hue(a, b, t):
    delta = ((b - a + 0.5) % 1.0) - 0.5
    return a + delta * t


def _blend_number(key, a, b, t):
    if key in ("primary_hue", "secondary_hue", "shadow_hue"):
        return _blend_hue(a, b, t)
    return a + (b - a) * t


def _style_value(style, key):
    if key in style:
        return style[key]
    return STYLE_VALUE_DEFAULTS.get(key)


def blend_styles(source_name, target_name, t):
    t = max(0.0, min(1.0, t))
    if t >= 1.0:
        return STYLE_PRESETS[target_name]
    if t <= 0.0:
        return STYLE_PRESETS[source_name]

    source = STYLE_PRESETS[source_name]
    target = STYLE_PRESETS[target_name]
    out = {"name": f"{source['name']}→{target['name']} {int(t * 100):02d}%"}

    keys = set(source) | set(target) | set(STYLE_VALUE_DEFAULTS)
    keys.discard("name")
    keys.discard("wordmark_3d")
    for key in keys:
        av = _style_value(source, key)
        bv = _style_value(target, key)
        if isinstance(av, (int, float)) and isinstance(bv, (int, float)):
            out[key] = _blend_number(key, av, bv, t)
        elif av is not None and bv is not None:
            out[key] = bv if t >= 0.5 else av

    out["wordmark_3d"] = {}
    source_3d = source["wordmark_3d"]
    target_3d = target["wordmark_3d"]
    for key in set(source_3d) | set(target_3d):
        av = source_3d.get(key, target_3d.get(key))
        bv = target_3d.get(key, source_3d.get(key))
        out["wordmark_3d"][key] = tuple(round(av[i] + (bv[i] - av[i]) * t) for i in range(3))
    return out


def current_style():
    return blend_styles(STYLE_SOURCE, STYLE_TARGET, STYLE_BLEND_T)


def style_get(key, default):
    return current_style().get(key, default)


def style_hues():
    style = current_style()
    return (
        style.get("primary_hue", CYAN_HUE),
        style.get("secondary_hue", BLUE_HUE),
        style.get("shadow_hue", VIOLET_HUE),
        style.get("hue_range", HUE_RANGE),
    )


def hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return f"\x1b[38;2;{int(r*255)};{int(g*255)};{int(b*255)}m"

def hsv_rgb(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return (int(r*255), int(g*255), int(b*255))

def mix_color(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))

def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)

def style_rgb(rgb, bold=False):
    prefix = "1;" if bold else ""
    return f"\x1b[{prefix}38;2;{rgb[0]};{rgb[1]};{rgb[2]}m"

def palette_hue(frame):
    primary_hue, _, _, hue_range = style_hues()
    t = 0.5 + 0.5 * math.sin(frame * 0.006)
    return primary_hue + t * hue_range

def strip_ansi(s):
    return ANSI_RE.sub("", s)


# ════════════════════════════════════════════════════════════════════════
#  IMAGE PROCESSING (from original)
# ════════════════════════════════════════════════════════════════════════

def find_rotation_center(gray, white_threshold=220):
    width, height = gray.size
    white = [[gray.getpixel((x, y)) > white_threshold for x in range(width)] for y in range(height)]
    visited = [[False]*width for _ in range(height)]
    queue = deque()
    for x in range(width):
        for y in (0, height-1):
            if white[y][x] and not visited[y][x]:
                visited[y][x] = True; queue.append((x, y))
    for y in range(height):
        for x in (0, width-1):
            if white[y][x] and not visited[y][x]:
                visited[y][x] = True; queue.append((x, y))
    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
            if 0 <= nx < width and 0 <= ny < height and white[ny][nx] and not visited[ny][nx]:
                visited[ny][nx] = True; queue.append((nx, ny))
    holes = []
    image_center = (width/2.0, height/2.0)
    for y in range(height):
        for x in range(width):
            if not white[y][x] or visited[y][x]:
                continue
            queue.append((x, y)); visited[y][x] = True
            area = 0; sx = 0.0; sy = 0.0
            while queue:
                cx2, cy2 = queue.popleft()
                area += 1; sx += cx2; sy += cy2
                for nx, ny in ((cx2+1,cy2),(cx2-1,cy2),(cx2,cy2+1),(cx2,cy2-1)):
                    if 0 <= nx < width and 0 <= ny < height and white[ny][nx] and not visited[ny][nx]:
                        visited[ny][nx] = True; queue.append((nx, ny))
            holes.append((sx/area, sy/area, area))
    if not holes:
        return image_center
    holes.sort(key=lambda h: (h[0]-image_center[0])**2 + (h[1]-image_center[1])**2)
    return holes[0][0], holes[0][1]

def build_centered_canvas(gray, center, dark_threshold=180):
    cx, cy = center
    dark_points = [(x, y) for y in range(gray.height) for x in range(gray.width) if gray.getpixel((x, y)) < dark_threshold]
    if not dark_points:
        return gray.copy()
    max_dx = max(abs(x-cx) for x, _ in dark_points)
    max_dy = max(abs(y-cy) for _, y in dark_points)
    radius = math.ceil(max(max_dx, max_dy)) + 24
    canvas_size = radius*2 + 1
    canvas = Image.new("L", (canvas_size, canvas_size), 255)
    canvas.paste(gray, (round(radius-cx), round(radius-cy)))
    return canvas

def crop_to_content(gray, threshold=180, pad_percent=0.08):
    px = gray.load(); W, H = gray.size
    minx, miny, maxx, maxy = W, H, 0, 0
    for y in range(H):
        for x in range(W):
            if px[x, y] < threshold:
                minx = min(minx, x); maxx = max(maxx, x)
                miny = min(miny, y); maxy = max(maxy, y)
    if minx >= maxx or miny >= maxy:
        return gray
    pad = int(max(maxx - minx, maxy - miny) * pad_percent)
    minx, miny = max(0, minx - pad), max(0, miny - pad)
    maxx, maxy = min(W, maxx + pad), min(H, maxy + pad)
    return gray.crop((minx, miny, maxx, maxy))

def prepare_canvas(image_path):
    gray = Image.open(image_path).convert("L")
    gray = crop_to_content(gray, threshold=180, pad_percent=0.08)
    center = find_rotation_center(gray)
    return build_centered_canvas(gray, center), center


# ════════════════════════════════════════════════════════════════════════
#  WORDMARK (from original)
# ════════════════════════════════════════════════════════════════════════

def component_columns(image, target_rows, aspect):
    return max(1, int(round((image.width / image.height) * max(2, target_rows*2) * aspect)))

def build_wordmark_letters(label):
    return [WORDMARK_PATTERNS[c] for c in label if c in WORDMARK_PATTERNS]

def letter_columns(rows, target_rows):
    sh = len(rows); sw = max(len(r) for r in rows)
    return max(7, int(round((sw/sh) * target_rows * WORDMARK_STRETCH)))

def wordmark_layout(letter_rows, target_rows):
    gap = max(2, int(round(target_rows * WORDMARK_GAP_RATIO)))
    widths = [letter_columns(r, target_rows) for r in letter_rows]
    total = sum(widths) + gap * max(0, len(widths)-1) + 2
    return widths, gap, total

def scale_text_rows(rows, target_rows, target_columns):
    sh = len(rows); sw = max(len(r) for r in rows)
    norm = [r.ljust(sw) for r in rows]
    scaled = []
    for y in range(target_rows):
        sy = min(sh-1, int(y*sh/target_rows))
        chars = []
        for x in range(target_columns):
            sx = min(sw-1, int(x*sw/target_columns))
            chars.append(norm[sy][sx])
        scaled.append("".join(chars))
    return scaled


def signature_target_rows(target_rows):
    return len(SIGNATURE_ART_ROWS)


def signature_gap_rows(target_rows):
    return 1 if target_rows >= 8 else 0


def build_signature_shape(label=SIGNATURE_LABEL):
    return [row.rstrip() for row in SIGNATURE_ART_ROWS]


def signature_plain_rows(target_rows):
    rows = build_signature_shape()
    sig_rows = signature_target_rows(target_rows)
    width = max(len(r) for r in rows)
    scaled = scale_text_rows(rows, sig_rows, width)
    slanted = []
    for y, row in enumerate(scaled):
        shift = max(0, int(round((sig_rows - 1 - y) * 0.55)))
        slanted.append(" " * shift + row.rstrip())
    return slanted


def signature_width(target_rows):
    return max(len(r) for r in signature_plain_rows(target_rows))


def signature_block_height(target_rows):
    return signature_gap_rows(target_rows) + signature_target_rows(target_rows)


def total_layout_height(target_rows):
    return target_rows + signature_block_height(target_rows)


def render_signature_rows(target_rows, frame, t):
    raw_rows = signature_plain_rows(target_rows)
    width = max(len(r) for r in raw_rows)
    colors = current_style()["wordmark_3d"]
    h = len(raw_rows)
    rows_out = []
    shimmer_center = (frame * 0.62) % (width + 8) - 4
    for y, row in enumerate(raw_rows):
        row_t = smoothstep(y / max(1, h - 1))
        base_rgb = mix_color(colors["rim"], colors["mid"], row_t * 0.45)
        cells = []
        for x in range(width):
            filled = x < len(row) and row[x] != " "
            if not filled:
                cells.append((None, " "))
                continue
            sweep = max(0.0, 1.0 - abs((x + y * 0.8) - shimmer_center) / 4.5)
            pulse = 0.5 + 0.5 * math.sin(t * 3.6 + x * 0.18 + y * 0.9)
            rgb = mix_color(base_rgb, colors["mid"], 0.22 + 0.18 * pulse)
            rgb = mix_color(rgb, colors["sweep"], sweep * 0.55)
            glyph = row[x]
            bold = sweep > 0.25 or y == 0
            cells.append((style_rgb(rgb, bold=bold), glyph))
        rows_out.append(encode_color_row(cells))
    return rows_out, width

def rows_to_mask(rows):
    w = max(len(r) for r in rows)
    return [[x < len(r) and r[x] != " " for x in range(w)] for r in rows]

def dilate_mask(mask):
    h = len(mask); w = len(mask[0])
    out = [[False]*w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if not mask[y][x]: continue
            for ny in range(max(0,y-1), min(h,y+2)):
                for nx in range(max(0,x-1), min(w,x+2)):
                    out[ny][nx] = True
    return out

def widen_mask(mask, radius):
    if radius <= 0: return [r[:] for r in mask]
    h = len(mask); w = len(mask[0])
    out = [[False]*w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if not mask[y][x]: continue
            for nx in range(max(0,x-radius), min(w,x+radius+1)):
                out[y][nx] = True
    return out

def shift_mask(mask, dx, dy):
    h = len(mask); w = len(mask[0])
    out = [[False]*w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if not mask[y][x]: continue
            nx, ny = x+dx, y+dy
            if 0 <= nx < w and 0 <= ny < h:
                out[ny][nx] = True
    return out

def stamp_mask(canvas, mask, ox, oy=0):
    ch = len(canvas); cw = len(canvas[0])
    for y, row in enumerate(mask):
        for x, c in enumerate(row):
            if not c: continue
            dx, dy = ox+x, oy+y
            if 0 <= dx < cw and 0 <= dy < ch:
                canvas[dy][dx] = True

def wordmark_palette_rainbow(frame, breath):
    bh = palette_hue(frame)
    primary_hue, secondary_hue, shadow_hue, _ = style_hues()
    return {
        "shadow_top": hsv_rgb(shadow_hue, 0.82, style_get("flat_shadow_top_v", 0.22)),
        "shadow_bottom": hsv_rgb(shadow_hue, 0.88, style_get("flat_shadow_bottom_v", 0.08)),
        "glow_top": hsv_rgb(bh, 0.78, style_get("flat_glow_top_v", 0.34) + breath * 0.12),
        "glow_bottom": hsv_rgb(secondary_hue, 0.84, style_get("flat_glow_bottom_v", 0.18) + breath * 0.08),
        "body_top": hsv_rgb(primary_hue, 0.46, min(1.0, style_get("flat_body_top_v", 0.98) + breath * 0.02)),
        "body_bottom": hsv_rgb(secondary_hue, 0.78, min(1.0, style_get("flat_body_bottom_v", 0.66) + breath * 0.06)),
        "highlight": hsv_rgb(primary_hue + 0.015, 0.10, 1.0),
    }

def encode_color_row(cells):
    out = []
    for style, char in cells:
        if style is not None:
            out.append(f"{style}{char}{RESET}")
        else:
            out.append(char)
    return "".join(out)

def render_wordmark_rows(letter_rows, target_rows, frame):
    breath = 0.5 + 0.5 * math.sin(frame * 0.32)
    palette = wordmark_palette_rainbow(frame, breath)
    widths, gap, cw = wordmark_layout(letter_rows, target_rows)
    body = [[False]*cw for _ in range(target_rows)]
    glow = [[False]*cw for _ in range(target_rows)]
    shadow = [[False]*cw for _ in range(target_rows)]
    cursor = 0
    for rows, w in zip(letter_rows, widths):
        scaled = scale_text_rows(rows, target_rows, w)
        lb = widen_mask(rows_to_mask(scaled), 1)
        lg = dilate_mask(lb)
        ls = shift_mask(lg, 2, 1)
        stamp_mask(body, lb, cursor)
        stamp_mask(glow, lg, cursor)
        stamp_mask(shadow, ls, cursor)
        cursor += w + gap
    h = len(body); w = len(body[0])
    rows_out = []
    denom = max(1, h - 1)
    for y in range(h):
        row_t = smoothstep(y / denom)
        body_rgb = mix_color(palette["body_top"], palette["body_bottom"], row_t)
        glow_rgb = mix_color(palette["glow_top"], palette["glow_bottom"], row_t)
        shadow_rgb = mix_color(palette["shadow_top"], palette["shadow_bottom"], row_t)
        edge_strength = max(0.0, 1.0 - (y / max(1.0, h * 0.65)))
        hi_rgb = mix_color(body_rgb, palette["highlight"], 0.22 + 0.46 * edge_strength)
        body_style = style_rgb(body_rgb)
        glow_style = style_rgb(glow_rgb)
        shadow_style = style_rgb(shadow_rgb)
        hi_style = style_rgb(hi_rgb, bold=edge_strength > 0.35)
        cells = []
        for x in range(w):
            if body[y][x]:
                to = y == 0 or not body[y-1][x]
                lo = x == 0 or not body[y][x-1]
                do = y == 0 or x == 0 or not body[y-1][x-1]
                if to and (lo or do):
                    s = hi_style
                else:
                    s = body_style
                cells.append((s, "█"))
            elif glow[y][x]:
                cells.append((glow_style, "▓"))
            elif shadow[y][x]:
                cells.append((shadow_style, "▒"))
            else:
                cells.append((None, " "))
        rows_out.append(encode_color_row(cells))
    return rows_out, w


def wordmark_3d_depth(target_rows):
    return max(3, min(6, int(round(target_rows * 0.28))))


def build_wordmark_body_mask(letter_rows, target_rows, stroke_expand=0):
    widths, gap, cw = wordmark_layout(letter_rows, target_rows)
    body = [[False] * cw for _ in range(target_rows)]
    cursor = 0
    for rows, w in zip(letter_rows, widths):
        scaled = scale_text_rows(rows, target_rows, w)
        mask = rows_to_mask(scaled)
        if stroke_expand > 0:
            mask = widen_mask(mask, stroke_expand)
        stamp_mask(body, mask, cursor)
        cursor += w + gap
    return body, cw


def render_wordmark_face_rows(letter_rows, target_rows, frame):
    """Render a crisp front-face overlay for the 3D wordmark."""
    body, cw = build_wordmark_body_mask(letter_rows, target_rows)

    h = len(body)
    w = len(body[0])
    denom = max(1, h - 1)
    bh = palette_hue(frame)
    primary_hue, secondary_hue, _, _ = style_hues()
    top_rgb = hsv_rgb(primary_hue + 0.012, 0.16, 1.0)
    mid_rgb = hsv_rgb(bh, 0.35, 0.95)
    bottom_rgb = hsv_rgb(secondary_hue, 0.72, 0.68)
    rim_rgb = hsv_rgb(primary_hue + 0.02, 0.08, 1.0)
    rows_out = []
    for y in range(h):
        row_t = smoothstep(y / denom)
        row_rgb = mix_color(top_rgb, bottom_rgb, row_t)
        cells = []
        for x in range(w):
            if not body[y][x]:
                cells.append(" ")
                continue
            col_t = x / max(1, w - 1)
            rgb = mix_color(row_rgb, mid_rgb, 0.16 + 0.16 * (1.0 - col_t))
            top_open = y == 0 or not body[y - 1][x]
            left_open = x == 0 or not body[y][x - 1]
            diag_open = y == 0 or x == 0 or not body[y - 1][x - 1]
            if top_open and (left_open or diag_open):
                rgb = mix_color(rgb, rim_rgb, 0.42)
            cells.append(f"{style_rgb(rgb, bold=top_open)}█{RESET}")
        rows_out.append("".join(cells))
    return rows_out, w


def render_layered_3d_wordmark_rows(letter_rows, target_rows, frame, t):
    """Terminal-friendly 3D wordmark: readable face plus visible extrusion."""
    face, cw = build_wordmark_body_mask(letter_rows, target_rows)
    h = len(face)
    depth = wordmark_3d_depth(target_rows)
    w = cw + depth + 2
    cells = [[(None, " ") for _ in range(w)] for _ in range(h)]

    colors = current_style()["wordmark_3d"]
    side_dark = colors["side_dark"]
    side_mid = colors["side_mid"]
    side_hot = colors["side_hot"]
    side_flash = colors["side_flash"]
    cast_rgb = colors["cast"]
    sweep_center = (frame * 1.35) % (cw + depth + 14) - 7
    scan_center = (frame * 0.34) % (h + 6) - 3
    pulse = 0.5 + 0.5 * math.sin(t * 5.0)
    active_depth = max(2, depth - (1 if pulse < 0.22 else 0))

    # Back-to-front offset layers — full depth, edges only (no muddy fill)
    for d in range(active_depth + 1, 0, -1):
        ox = d + 1
        oy = int(round(d * 0.42))
        layer_t = d / max(1, active_depth + 1)
        rgb = mix_color(side_mid, side_dark, layer_t)
        ch = "▓" if d <= 2 else "▒"
        if d == active_depth + 1:
            rgb = mix_color(cast_rgb, side_mid, pulse * 0.18)
            ch = "░"
        for y in range(h):
            ty = y + oy
            if ty >= h:
                continue
            for x in range(cw):
                if not face[y][x]:
                    continue
                # Only draw edge pixels (neighbour is empty)
                right_open = x == cw - 1 or not face[y][x + 1]
                bottom_open = y == h - 1 or not face[y + 1][x]
                if not (right_open or bottom_open):
                    continue
                tx = x + ox
                if tx < w:
                    side_wave = 0.5 + 0.5 * math.sin(t * 4.0 + d * 0.9 + y * 0.55 + x * 0.08)
                    band = max(0.0, 1.0 - abs((x + d * 1.4 + y * 0.35) - sweep_center) / 6.5)
                    layer_rgb = mix_color(rgb, side_hot, side_wave * 0.30)
                    layer_rgb = mix_color(layer_rgb, side_flash, band * 0.55)
                    layer_ch = "█" if d <= 2 and side_wave > 0.78 else ch
                    cells[ty][tx] = (style_rgb(layer_rgb, bold=band > 0.55), layer_ch)

    # A brighter right/bottom bevel — single pixel outline
    for y in range(h):
        row_t = y / max(1, h - 1)
        bevel_rgb = mix_color(side_hot, side_mid, row_t)
        for x in range(cw):
            if not face[y][x]:
                continue
            right_open = x == cw - 1 or not face[y][x + 1]
            bottom_open = y == h - 1 or not face[y + 1][x]
            if right_open and x + 1 < w:
                cells[y][x + 1] = (style_rgb(mix_color(bevel_rgb, side_dark, 0.16)), "▓")
            if bottom_open and y + 1 < h:
                cells[y + 1][x] = (style_rgb(mix_color(bevel_rgb, side_dark, 0.36)), "▒")

    top_rgb = colors["top"]
    mid_rgb = colors["mid"]
    bottom_rgb = colors["bottom"]
    rim_rgb = colors["rim"]
    lowlight_rgb = colors["lowlight"]
    sweep_rgb = colors["sweep"]
    spark_rgb = colors["spark"]
    arc_rgb = colors["arc"]

    for y in range(h):
        row_t = smoothstep(y / max(1, h - 1))
        row_rgb = mix_color(top_rgb, bottom_rgb, row_t)
        for x in range(cw):
            if not face[y][x]:
                continue
            col_t = x / max(1, cw - 1)
            rgb = mix_color(row_rgb, mid_rgb, 0.18 + 0.18 * math.sin(t * 0.8 + col_t * math.pi))
            top_open = y == 0 or not face[y - 1][x]
            left_open = x == 0 or not face[y][x - 1]
            right_open = x == cw - 1 or not face[y][x + 1]
            bottom_open = y == h - 1 or not face[y + 1][x]
            if top_open or left_open:
                rgb = mix_color(rgb, rim_rgb, 0.42)
            elif right_open or bottom_open:
                rgb = mix_color(rgb, lowlight_rgb, 0.28)
            sweep = max(0.0, 1.0 - abs((x + y * 0.62) - sweep_center) / 5.8)
            scan = max(0.0, 1.0 - abs(y - scan_center) / 1.45)
            edge_pulse = 0.0
            if top_open or left_open or right_open or bottom_open:
                edge_pulse = 0.5 + 0.5 * math.sin(t * 7.5 + x * 0.7 + y * 0.45)
            trace = ((x * 7 + y * 11 + frame * 5) % 53) / 53.0
            arc = 0.0
            if (top_open or left_open or right_open or bottom_open) and trace < 0.10:
                arc = 1.0 - trace / 0.10
            rgb = mix_color(rgb, sweep_rgb, sweep * 0.72)
            rgb = mix_color(rgb, spark_rgb, edge_pulse * pulse * 0.28)
            rgb = mix_color(rgb, arc_rgb, arc * 0.86)
            rgb = mix_color(rgb, rim_rgb, scan * 0.22)
            bold = top_open or left_open or sweep > 0.22 or edge_pulse > 0.88 or arc > 0.0
            cells[y][x] = (style_rgb(rgb, bold=bold), "█")

    return [encode_color_row(row) for row in cells], w


def overlay_rows(base_rows, overlay_rows):
    """Overlay non-empty cells from overlay_rows on top of base_rows."""
    height = max(len(base_rows), len(overlay_rows))
    out = []
    for y in range(height):
        base_cells = CELL_RE.findall(base_rows[y]) if y < len(base_rows) else []
        over_cells = CELL_RE.findall(overlay_rows[y]) if y < len(overlay_rows) else []
        width = max(len(base_cells), len(over_cells))
        row = []
        for x in range(width):
            over = over_cells[x] if x < len(over_cells) else " "
            if strip_ansi(over).strip():
                row.append(over)
            elif x < len(base_cells):
                row.append(base_cells[x])
            else:
                row.append(" ")
        out.append("".join(row))
    return out


def fixed_ansi_cells(row, width):
    cells = CELL_RE.findall(row)
    if len(cells) < width:
        cells.extend(" " for _ in range(width - len(cells)))
    return cells[:width]


def masked_neighbor_count(mask, x, y):
    height = len(mask)
    width = len(mask[0]) if height else 0
    count = 0
    for ny in range(max(0, y - 1), min(height, y + 2)):
        for nx in range(max(0, x - 1), min(width, x + 2)):
            if mask[ny][nx]:
                count += 1
    return count


def mask_silhouette_spans(mask):
    height = len(mask)
    width = len(mask[0]) if height else 0
    row_min = [width] * height
    row_max = [-1] * height
    col_min = [height] * width
    col_max = [-1] * width
    for y, row in enumerate(mask):
        for x, filled in enumerate(row):
            if not filled:
                continue
            row_min[y] = min(row_min[y], x)
            row_max[y] = max(row_max[y], x)
            col_min[x] = min(col_min[x], y)
            col_max[x] = max(col_max[x], y)
    return row_min, row_max, col_min, col_max


def outside_mask_silhouette(spans, x, y):
    row_min, row_max, col_min, col_max = spans
    if not row_min or not col_min:
        return True
    if y < 0 or y >= len(row_min) or x < 0 or x >= len(col_min):
        return True
    outside_row = row_max[y] < 0 or x < row_min[y] or x > row_max[y]
    outside_col = col_max[x] < 0 or y < col_min[x] or y > col_max[x]
    return outside_row or outside_col


# ════════════════════════════════════════════════════════════════════════
#  2D LOGO RENDERERS (from original, enhanced)
# ════════════════════════════════════════════════════════════════════════

def image_to_block_rows_hue(image, target_rows, aspect, threshold, frame):
    oh = max(2, target_rows*2)
    ow = component_columns(image, target_rows, aspect)
    resized = image.resize((ow, oh), RESAMPLE_BOX)
    pixels = resized.tobytes()
    rows = []
    bh = palette_hue(frame)
    style = current_style()
    for y in range(0, oh, 2):
        chars = []
        rs = y * ow; nrs = (y+1) * ow
        for x in range(ow):
            tv = pixels[rs+x]; bv = pixels[nrs+x]
            td = tv < threshold; bd = bv < threshold
            if not td and not bd:
                chars.append(" ")
                continue
            tb = 1.0 - (tv/255.0) if td else 0
            bb = 1.0 - (bv/255.0) if bd else 0
            ab = (tb+bb)/2
            edge_factor = 1.0 - ab
            ph = bh + style["logo_hue_shift"] + edge_factor * style["logo_hue_span"]
            sat = style["logo_sat_base"] + style["logo_sat_span"] * ab
            val = style["logo_val_base"] + style["logo_val_span"] * ab
            color = hsv(ph, sat, val)
            chars.append(f"{color}{BLOCKS[(td,bd)]}{RESET}")
        rows.append("".join(chars))
    return rows

BRAILLE_BASE = 0x2800
BRAILLE_DOTS = [[0x01, 0x08], [0x02, 0x10], [0x04, 0x20], [0x40, 0x80]]

def image_to_braille_rows_hue(image, target_rows, aspect, threshold, frame):
    cols = max(1, int(round((image.width / image.height) * target_rows * aspect)))
    subpx_w, subpx_h = cols * 2, target_rows * 4
    resized = image.resize((subpx_w, subpx_h), RESAMPLE_BICUBIC)
    px = resized.load()
    bh = palette_hue(frame)
    style = current_style()
    rows = []
    for cy in range(target_rows):
        chars = []
        for cx in range(cols):
            bits, count = 0, 0
            total_brightness = 0
            for dy in range(4):
                for dx in range(2):
                    x, y = cx * 2 + dx, cy * 4 + dy
                    if x < subpx_w and y < subpx_h:
                        val = px[x, y]
                        if val < threshold:
                            bits |= BRAILLE_DOTS[dy][dx]
                            count += 1
                            total_brightness += (255 - val)
            if bits == 0:
                chars.append(" ")
            else:
                avg_brightness = total_brightness / max(1, count) / 255.0
                edge_factor = 1.0 - avg_brightness
                ph = bh + style["logo_hue_shift"] + edge_factor * style["logo_hue_span"]
                sat = style["logo_sat_base"] + style["logo_sat_span"] * avg_brightness
                val = style["logo_val_base"] + style["logo_val_span"] * avg_brightness
                color = hsv(ph, sat, val)
                chars.append(f"{color}{chr(BRAILLE_BASE + bits)}{RESET}")
        rows.append("".join(chars))
    return rows


def render_logo_3d_rows(logo_rows, frame, t, logo_width):
    """Add terminal-friendly 3D extrusion to the rotating logo mask."""
    height = len(logo_rows)
    if height == 0 or logo_width <= 0:
        return logo_rows

    parsed_rows = [fixed_ansi_cells(row, logo_width) for row in logo_rows]
    raw_rows = [[strip_ansi(cell) for cell in row] for row in parsed_rows]
    mask = [[cell.strip() != "" for cell in row] for row in raw_rows]
    spans = mask_silhouette_spans(mask)
    cells = [[(None, " ") for _ in range(logo_width)] for _ in range(height)]

    colors = current_style()["wordmark_3d"]
    side_dark = colors["side_dark"]
    side_mid = colors["side_mid"]
    side_hot = colors["side_hot"]
    side_flash = colors["side_flash"]
    cast_rgb = colors["cast"]
    # The atom logo is line art; deep extrusion destroys its negative space.
    depth = max(1, min(2, max(1, logo_width // 13), max(1, height // 8)))
    sweep_center = (frame * 1.08) % (logo_width + depth + 10) - 5
    scan_center = (frame * 0.42) % (height + 5) - 2
    pulse = 0.5 + 0.5 * math.sin(t * 5.4)

    # Draw shifted edge/cast layers first; the original face is stamped last.
    for d in range(depth + 1, 0, -1):
        ox = d
        oy = int(round(d * 0.45))
        layer_t = d / max(1, depth + 1)
        is_cast = d == depth + 1
        base_rgb = mix_color(side_mid, side_dark, layer_t)
        glyph = "▓" if d <= 2 else "▒"
        if is_cast:
            base_rgb = mix_color(cast_rgb, side_dark, 0.35 + 0.20 * pulse)
            glyph = "░"

        for y in range(height):
            ty = y + oy
            if ty >= height:
                continue
            for x in range(logo_width):
                if not mask[y][x]:
                    continue
                right_open = x == logo_width - 1 or not mask[y][x + 1]
                bottom_open = y == height - 1 or not mask[y + 1][x]
                if not (right_open or bottom_open):
                    continue
                tx = x + ox
                if tx >= logo_width or mask[ty][tx]:
                    continue
                if not outside_mask_silhouette(spans, tx, ty):
                    continue
                neighbour_limit = 2 if is_cast else 3
                if masked_neighbor_count(mask, tx, ty) > neighbour_limit:
                    continue

                wave = 0.5 + 0.5 * math.sin(t * 4.6 + d * 0.85 + y * 0.52 + x * 0.10)
                band = max(0.0, 1.0 - abs((x + d * 1.35 + y * 0.38) - sweep_center) / 5.8)
                rgb = mix_color(base_rgb, side_hot, wave * (0.20 if is_cast else 0.34))
                rgb = mix_color(rgb, side_flash, band * (0.24 if is_cast else 0.62))
                layer_glyph = "█" if not is_cast and d <= 2 and wave > 0.82 else glyph
                cells[ty][tx] = (style_rgb(rgb, bold=band > 0.55), layer_glyph)

    # Single-pixel bevel on visible right/bottom edges to sell the thickness.
    for y in range(height):
        row_t = y / max(1, height - 1)
        bevel_rgb = mix_color(side_hot, side_mid, row_t)
        for x in range(logo_width):
            if not mask[y][x]:
                continue
            right_open = x == logo_width - 1 or not mask[y][x + 1]
            bottom_open = y == height - 1 or not mask[y + 1][x]
            if (right_open and x + 1 < logo_width and not mask[y][x + 1]
                    and outside_mask_silhouette(spans, x + 1, y)
                    and masked_neighbor_count(mask, x + 1, y) <= 3):
                band = max(0.0, 1.0 - abs((x + y * 0.35) - sweep_center) / 6.0)
                rgb = mix_color(bevel_rgb, side_flash, band * 0.42)
                cells[y][x + 1] = (style_rgb(rgb, bold=band > 0.35), "▓")
            if (bottom_open and y + 1 < height and not mask[y + 1][x]
                    and outside_mask_silhouette(spans, x, y + 1)
                    and masked_neighbor_count(mask, x, y + 1) <= 3):
                rgb = mix_color(bevel_rgb, side_dark, 0.36)
                cells[y + 1][x] = (style_rgb(rgb), "▒")

    top_rgb = colors["top"]
    mid_rgb = colors["mid"]
    bottom_rgb = colors["bottom"]
    rim_rgb = colors["rim"]
    lowlight_rgb = colors["lowlight"]
    sweep_rgb = colors["sweep"]
    spark_rgb = colors["spark"]
    arc_rgb = colors["arc"]

    # Repaint only the edge pixels of the original face; interiors keep image detail.
    for y in range(height):
        row_t = smoothstep(y / max(1, height - 1))
        face_rgb = mix_color(top_rgb, bottom_rgb, row_t)
        for x in range(logo_width):
            if not mask[y][x]:
                continue
            top_open = y == 0 or not mask[y - 1][x]
            left_open = x == 0 or not mask[y][x - 1]
            right_open = x == logo_width - 1 or not mask[y][x + 1]
            bottom_open = y == height - 1 or not mask[y + 1][x]
            is_edge = top_open or left_open or right_open or bottom_open
            if not is_edge:
                cells[y][x] = (None, parsed_rows[y][x])
                continue

            col_t = x / max(1, logo_width - 1)
            rgb = mix_color(face_rgb, mid_rgb, 0.16 + 0.16 * math.sin(t * 0.9 + col_t * math.pi))
            if top_open or left_open:
                rgb = mix_color(rgb, rim_rgb, 0.48)
            if right_open or bottom_open:
                rgb = mix_color(rgb, lowlight_rgb, 0.24)
            sweep = max(0.0, 1.0 - abs((x + y * 0.58) - sweep_center) / 5.3)
            scan = max(0.0, 1.0 - abs(y - scan_center) / 1.35)
            edge_pulse = 0.5 + 0.5 * math.sin(t * 7.8 + x * 0.62 + y * 0.47)
            trace = ((x * 11 + y * 17 + frame * 4) % 61) / 61.0
            arc = 1.0 - trace / 0.08 if trace < 0.08 else 0.0
            rgb = mix_color(rgb, sweep_rgb, sweep * 0.68)
            rgb = mix_color(rgb, spark_rgb, edge_pulse * pulse * 0.26)
            rgb = mix_color(rgb, arc_rgb, arc * 0.80)
            rgb = mix_color(rgb, rim_rgb, scan * 0.22)
            glyph = raw_rows[y][x] if raw_rows[y][x].strip() else "█"
            bold = top_open or left_open or sweep > 0.22 or arc > 0.0
            cells[y][x] = (style_rgb(rgb, bold=bold), glyph)

    return [encode_color_row(row) for row in cells]


def render_glow_aura(logo_rows, target_rows, frame, logo_width):
    height = len(logo_rows)
    parsed_rows = [CELL_RE.findall(r) for r in logo_rows]
    mask = []
    for cells in parsed_rows:
        raw = [ANSI_RE.sub("", c) for c in cells]
        mask.append([c.strip() != "" for c in raw])
        while len(mask[-1]) < logo_width:
            mask[-1].append(False)
    glow = dilate_mask(mask)
    spans = mask_silhouette_spans(mask)
    style = current_style()
    aura_hue = palette_hue(frame) + style["aura_hue_shift"]
    new_rows = []
    for y in range(height):
        out = []
        cells = parsed_rows[y] if y < len(parsed_rows) else []
        for x in range(logo_width):
            if x < len(mask[y]) and mask[y][x]:
                out.append(cells[x] if x < len(cells) else " ")
            elif x < len(glow[y]) and glow[y][x]:
                if (not outside_mask_silhouette(spans, x, y)
                        or masked_neighbor_count(mask, x, y) > 3
                        or (x * 3 + y * 5 + frame) % 3 == 0):
                    out.append(" ")
                    continue
                alpha = 0.07 + 0.04 * math.sin(frame*0.1 + x*0.3 + y*0.2)
                color = hsv(aura_hue, style["aura_sat"], max(style["aura_floor"], alpha * style["aura_scale"]))
                out.append(f"{color}░{RESET}")
            else:
                out.append(" ")
        new_rows.append("".join(out))
    return new_rows


# ════════════════════════════════════════════════════════════════════════
#  EXPERIMENTAL RAYMARCHED TEXT (kept for reference)
# ════════════════════════════════════════════════════════════════════════

def build_wordmark_sdf(letter_rows, target_rows, supersample=2, stroke_expand=0):
    """Build a 2D signed distance field from the wordmark mask.

    Returns (sdf_array, width) where sdf_array is a supersampled 2D SDF:
    negative inside text, positive outside. Width is the character-column
    width of the wordmark (for layout).  Height is target_rows*2*supersample
    so it matches the half-block output grid exactly.
    """
    widths, gap, cw = wordmark_layout(letter_rows, target_rows)
    # Build mask at 2x height (= oh) so it matches the half-block output grid
    mask_h = target_rows * 2
    mask = np.zeros((mask_h, cw), dtype=bool)
    cursor = 0
    for rows, w in zip(letter_rows, widths):
        # Scale to full output height (2x target_rows for half-blocks)
        scaled = scale_text_rows(rows, mask_h, w)
        lb = rows_to_mask(scaled)
        if stroke_expand > 0:
            lb = widen_mask(lb, stroke_expand)
        for y, row in enumerate(lb):
            for x, c in enumerate(row):
                if c and 0 <= x + cursor < cw and y < mask_h:
                    mask[y, x + cursor] = True
        cursor += w + gap

    # Supersample for smoother distances
    if supersample > 1:
        mask_ss = np.repeat(np.repeat(mask, supersample, axis=0), supersample, axis=1)
    else:
        mask_ss = mask

    # Signed distance: positive outside, negative inside
    outside = distance_transform_edt(~mask_ss)
    inside  = distance_transform_edt(mask_ss)
    sdf = outside - inside
    return sdf, cw


def _sample_sdf(sdf, xs, ys):
    """Bilinear sample of a 2D SDF at float coordinates (xs, ys)."""
    h, w = sdf.shape
    # Don't clamp — let out-of-bounds return large positive (far outside)
    coords = np.array([ys, xs])
    return map_coordinates(sdf, coords, order=1, mode='constant', cval=999.0)


def render_3d_wordmark_rows(sdf, label_width, target_rows, frame, t):
    """Render extruded 3D text with raymarching + diffuse/specular/fresnel.

    The 2D SDF is extruded along Z with rounded bevels.  Camera does a
    gentle Y-wobble + X-tilt so the 3D depth is visible.  Output uses
    the same half-block + unified-palette mapping as the 2D logo.
    """
    oh = target_rows * 2               # subpixel rows (half-block)
    sdf_h, sdf_w = sdf.shape
    # The SDF height is built from the half-block grid (oh), not target_rows.
    # Using target_rows here doubles the extrusion thickness and makes letters merge.
    ss = max(1, sdf_h // oh)           # supersample factor
    ow = label_width                   # output columns

    # Pixel grid → SDF coordinates (centred at origin)
    ys, xs = np.mgrid[0:oh, 0:ow].astype(np.float64)
    # sdf_h = mask_h * supersample = oh * supersample
    # Map oh output rows → sdf_h SDF rows (scale = sdf_h/oh = supersample)
    px_s = (xs + 0.5) * sdf_w / ow
    py_s = (ys + 0.5) * (sdf_h / oh)
    cx = sdf_w / 2.0
    cy = sdf_h / 2.0
    px_w = px_s - cx
    py_w = py_s - cy

    # Orthographic camera (avoids perspective distortion filling letter gaps)
    cam_dist = sdf_w * 0.6
    ox = px_w.copy()
    oy = py_w.copy()
    oz = np.full_like(px_w, cam_dist)
    # All rays point straight into -Z
    dx = np.zeros_like(px_w)
    dy = np.zeros_like(px_w)
    dz = np.full_like(px_w, -1.0)

    # Keep a persistent oblique angle so the extrusion stays legible.
    ay = 0.30 + math.sin(t * 0.48) * 0.09
    ax = -0.12 + math.sin(t * 0.34 + 0.9) * 0.05
    cay, say = math.cos(ay), math.sin(ay)
    cax, sax = math.cos(ax), math.sin(ax)

    # Extrusion parameters (in SDF-pixel units)
    half_thick = 1.35 * ss
    bevel      = 0.38 * ss

    def scene_sdf(px, py, pz):
        """Extruded SDF with rounded bevel, scene rotated."""
        # Inverse-rotate the sample point (rotate scene → inverse-rotate query)
        # Inverse Y: x' = x*cos + z*sin, z' = -x*sin + z*cos
        rx = px * cay + pz * say
        rz = -px * say + pz * cay
        # Inverse X: y' = y*cos + z*sin, z' = -y*sin + z*cos
        ry = py * cax + rz * sax
        rz2 = -py * sax + rz * cax
        d2 = _sample_sdf(sdf, rx + cx, ry + cy)
        z_d = np.abs(rz2) - half_thick
        d2c = np.maximum(d2, 0.0)
        zc  = np.maximum(z_d, 0.0)
        corner = np.sqrt(d2c*d2c + zc*zc) - bevel
        return np.minimum(np.maximum(d2, z_d), corner)

    # ── Raymarch (orthographic: rays are parallel) ────────────
    px, py, pz = ox.copy(), oy.copy(), oz.copy()
    depth = np.zeros_like(px_w)
    hit   = np.zeros_like(px_w, dtype=bool)

    for _ in range(48):
        dist = scene_sdf(px, py, pz)
        close = dist < 0.18 * ss
        hit = hit | close
        far = depth > cam_dist * 2.5
        active = ~hit & ~far
        depth = np.where(active, depth + np.maximum(dist, 0.10 * ss), depth)
        px = ox + dx * depth
        py = oy + dy * depth
        pz = oz + dz * depth

    # ── Normal estimation (finite differences) ────────────────
    e = 0.35 * ss
    nx = scene_sdf(px+e, py, pz) - scene_sdf(px-e, py, pz)
    ny = scene_sdf(px, py+e, pz) - scene_sdf(px, py-e, pz)
    nz = scene_sdf(px, py, pz+e) - scene_sdf(px, py, pz-e)
    nlen = np.sqrt(nx*nx + ny*ny + nz*nz) + 1e-8
    nx, ny, nz = nx/nlen, ny/nlen, nz/nlen

    # ── Lighting ──────────────────────────────────────────────
    # Light points from the surface toward the light source.
    lx, ly, lz = -0.42, -0.28, 0.86
    llen = math.sqrt(lx*lx + ly*ly + lz*lz)
    lx, ly, lz = lx/llen, ly/llen, lz/llen

    diffuse = np.maximum(0.0, nx*lx + ny*ly + nz*lz)

    # Specular (Blinn-Phong half-vector)
    hx, hy, hz = lx, ly, lz + 1.0
    hlen = math.sqrt(hx*hx + hy*hy + hz*hz)
    hx, hy, hz = hx/hlen, hy/hlen, hz/hlen
    spec = np.maximum(0.0, nx*hx + ny*hy + nz*hz) ** 26

    # Camera looks down +Z from the hit point's perspective.
    view_dot = np.clip(nz, 0.0, 1.0)
    fresnel = (1.0 - view_dot) ** 2.6

    # Vertical gradient (top brighter, bottom darker) — matches 2D wordmark
    grad_y = np.linspace(1.0, 0.55, oh).reshape(-1, 1)
    front_facing = np.clip(nz, 0.0, 1.0)
    side_facing = 1.0 - front_facing
    gradient = grad_y * front_facing
    depth_fade = np.clip(
        (depth - (cam_dist - half_thick * 2.0)) / (half_thick * 6.0 + 1e-8),
        0.0,
        1.0,
    )

    brightness = np.where(hit,
        np.clip(
            0.14
            + diffuse * 0.46
            + spec * 0.72
            + fresnel * 0.18
            + gradient * 0.20
            - side_facing * 0.12
            - depth_fade * 0.08,
            0,
            1,
        ),
        0.0)

    # ── Map to half-block characters with unified palette ─────
    # Hard cutoff: anything below 0.15 is invisible — kills the muddy edge haze
    brightness = np.where(brightness < 0.15, 0.0, brightness)

    # ── Map to half-block characters with unified palette ─────
    bh = palette_hue(frame)
    primary_hue, _, shadow_hue, _ = style_hues()
    face_rgb = hsv_rgb(bh + 0.004, 0.18, 1.0)
    side_rgb = hsv_rgb(bh - 0.030, 0.78, 0.45)
    shadow_rgb = hsv_rgb(shadow_hue, 0.76, 0.14)
    rim_rgb = hsv_rgb(primary_hue + 0.018, 0.07, 1.0)
    rows_out = []
    for y in range(0, oh, 2):
        chars = []
        for x in range(ow):
            tb = brightness[y, x]
            bb = brightness[y+1, x]
            if tb < 0.15 and bb < 0.15:
                chars.append(" ")
                continue
            td = tb > 0.15
            bd = bb > 0.15
            samples = []
            if td and bd:
                ch = "█"
                samples = [(tb, front_facing[y, x], spec[y, x], fresnel[y, x]),
                           (bb, front_facing[y+1, x], spec[y+1, x], fresnel[y+1, x])]
            elif td:
                ch = "▀"
                samples = [(tb, front_facing[y, x], spec[y, x], fresnel[y, x])]
            else:
                ch = "▄"
                samples = [(bb, front_facing[y+1, x], spec[y+1, x], fresnel[y+1, x])]

            ab = sum(v for v, _, _, _ in samples) / len(samples)
            face = sum(v for _, v, _, _ in samples) / len(samples)
            shine = max(v for _, _, v, _ in samples)
            rim = max(v for _, _, _, v in samples)

            body_rgb = mix_color(side_rgb, face_rgb, face)
            rgb = mix_color(shadow_rgb, body_rgb, 0.30 + ab * 0.70)
            rgb = mix_color(rgb, rim_rgb, min(1.0, shine * 0.85 + rim * 0.28))
            chars.append(f"{style_rgb(rgb, bold=(face > 0.62 and ab > 0.72) or shine > 0.45)}{ch}{RESET}")
        rows_out.append("".join(chars))
    return rows_out, ow


# ════════════════════════════════════════════════════════════════════════
#  BACKGROUND RENDERERS — Plasma / Tunnel / Julia
# ════════════════════════════════════════════════════════════════════════

def render_plasma(canvas, w, h, frame, t):
    """Flowing sinusoidal interference — vivid, not muddy."""
    bh = palette_hue(frame)
    style = current_style()
    for y in range(h):
        for x in range(w):
            if canvas[y][x] != " ":
                continue
            fx, fy = x / w, y / h
            v = (math.sin(fx*10 + t)
               + math.sin((fy*10 + t) * 0.5)
               + math.sin((fx*10 + fy*10 + t) * 0.5))
            cx2 = fx + 0.5 * math.sin(t / 3)
            cy2 = fy + 0.5 * math.cos(t / 2)
            v += math.sin(math.hypot(cx2, cy2) * 14 + t)
            v = (v + 4) / 8
            v = max(0.0, min(1.0, v))
            idx = int(v * (len(PLASMA_GLYPHS) - 1))
            sat = style["bg_sat_base"] + style["bg_sat_span"] * v
            val = style["bg_val_base"] + style["bg_val_span"] * v
            hue = bh + style["bg_hue_shift"] + v * style["bg_hue_span"]
            color = hsv(hue, sat, val)
            canvas[y][x] = f"{color}{PLASMA_GLYPHS[idx]}{RESET}"


def render_tunnel(canvas, w, h, frame, t):
    """Polar-coordinate infinite tunnel."""
    bh = palette_hue(frame)
    style = current_style()
    cx, cy = w / 2.0, h / 2.0
    for y in range(h):
        for x in range(w):
            if canvas[y][x] != " ":
                continue
            dx = (x - cx) / (w / 2.0)
            dy = (y - cy) / (h / 2.0) * 0.5
            dist = math.sqrt(dx*dx + dy*dy) + 1e-6
            ang = math.atan2(dy, dx)
            u = 0.4 / dist + t
            v = ang / math.pi + math.sin(t * 0.5)
            shade = (math.sin(u * 10) * math.cos(v * 6) + 1.0) / 2.0
            shade = max(0.0, min(1.0, shade))
            idx = int(shade * (len(TUNNEL_GLYPHS) - 1))
            # Brighter near tunnel edges (small dist)
            edge = min(1.0, dist * 1.5)
            sat = style["bg_sat_base"] + style["bg_sat_span"] * shade * (1 - edge * 0.5)
            val = style["bg_val_base"] + style["bg_val_span"] * 1.08 * shade
            hue = bh + style["bg_hue_shift"] + shade * style["bg_hue_span"] * 0.88
            color = hsv(hue, sat, val)
            canvas[y][x] = f"{color}{TUNNEL_GLYPHS[idx]}{RESET}"


def render_julia(canvas, w, h, frame, t):
    """Julia set fractal with rotating c and zoom."""
    bh = palette_hue(frame)
    style = current_style()
    cr = -0.8 + 0.15 * math.sin(t * 0.3)
    ci = 0.156 + 0.15 * math.cos(t * 0.2)
    scale = 3.0 + 0.6 * math.sin(t * 0.08)
    max_iter = 18
    for y in range(h):
        for x in range(w):
            if canvas[y][x] != " ":
                continue
            zx = scale * (x / w - 0.5)
            zy = scale * (y / h - 0.5)
            n = 0
            while n < max_iter:
                zx2 = zx * zx - zy * zy + cr
                zy = 2 * zx * zy + ci
                zx = zx2
                if zx * zx + zy * zy > 10:
                    break
                n += 1
            if n < max_iter:
                v = n / max_iter
                idx = int(v * (len(JULIA_GLYPHS) - 1))
                sat = style["bg_sat_base"] + style["bg_sat_span"] * 0.72 * v
                val = style["bg_val_base"] + style["bg_val_span"] * 0.90 * v
                hue = bh + style["bg_hue_shift"] + v * style["bg_hue_span"]
                color = hsv(hue, sat, val)
                canvas[y][x] = f"{color}{JULIA_GLYPHS[idx]}{RESET}"


# ════════════════════════════════════════════════════════════════════════
#  STARFIELD (from original, enhanced)
# ════════════════════════════════════════════════════════════════════════

class Starfield:
    def __init__(self, width, height):
        self.width = width; self.height = height
        rng = random.Random(42)
        self.dust = [{
            "x": rng.uniform(0, width), "y": rng.uniform(0, height),
            "b": rng.uniform(0.15, 0.5), "sp": rng.uniform(0.3, 0.8),
            "tp": rng.uniform(0, math.tau), "ts": rng.uniform(0.3, 1.0),
            "ch": rng.choice("·⋅."),
        } for _ in range(max(60, width * height // 10))]
        self.mid = [{
            "x": rng.uniform(0, width), "y": rng.uniform(0, height),
            "b": rng.uniform(0.4, 0.85), "sp": rng.uniform(1.0, 2.0),
            "tp": rng.uniform(0, math.tau), "ts": rng.uniform(0.5, 1.5),
            "ch": rng.choice("∙+∘°"),
        } for _ in range(max(20, width * height // 24))]
        self.bright = [{
            "x": rng.uniform(0, width), "y": rng.uniform(0, height),
            "b": rng.uniform(0.7, 1.0), "sp": rng.uniform(2.0, 3.5),
            "tp": rng.uniform(0, math.tau), "ts": rng.uniform(0.8, 2.0),
        } for _ in range(max(6, width // 8))]
        self.grid_nodes = []
        for fy in range(3, height, max(2, height // 4)):
            for fx in range(6, width, max(4, width // 8)):
                self.grid_nodes.append({
                    "x": fx + rng.uniform(-0.5, 0.5),
                    "y": fy + rng.uniform(-0.3, 0.3),
                    "tp": rng.uniform(0, math.tau),
                })
        self.streams = [{
            "x": rng.uniform(0, width), "y": rng.uniform(0, height),
            "len": rng.uniform(3, 8), "sp": rng.uniform(3, 6),
            "b": rng.uniform(0.3, 0.6),
        } for _ in range(max(2, width // 18))]

    def update(self, dt, frame):
        for layer in (self.dust, self.mid, self.bright):
            for s in layer:
                s["x"] -= s["sp"] * dt * 6
                if s["x"] < 0:
                    s["x"] += self.width
                    s["y"] = random.uniform(0, self.height)
        for s in self.streams:
            s["x"] -= s["sp"] * dt * 10
            if s["x"] + s["len"] < 0:
                s["x"] = self.width
                s["y"] = random.uniform(0, self.height)

    def render(self, canvas, cw, ch, frame):
        bh = palette_hue(frame)
        for g in self.grid_nodes:
            tw = 0.4 + 0.6 * math.sin(frame * 0.03 + g["tp"])
            alpha = 0.15 * tw
            if alpha < 0.06: continue
            gx, gy = int(g["x"]) % cw, int(g["y"]) % ch
            color = hsv(bh, 0.50, alpha)
            if canvas[gy][gx] == " ":
                canvas[gy][gx] = f"{color}╋{RESET}"
        for s in self.dust:
            tw = 0.4 + 0.6 * math.sin(frame * 0.04 * s["ts"] + s["tp"])
            alpha = s["b"] * tw
            if alpha < 0.06: continue
            sx, sy = int(s["x"]) % cw, int(s["y"]) % ch
            color = hsv(bh, 0.35, alpha * 1.5)
            if canvas[sy][sx] == " ":
                canvas[sy][sx] = f"{color}{s['ch']}{RESET}"
        for s in self.mid:
            tw = 0.5 + 0.5 * math.sin(frame * 0.05 * s["ts"] + s["tp"])
            alpha = s["b"] * tw
            if alpha < 0.08: continue
            sx, sy = int(s["x"]) % cw, int(s["y"]) % ch
            color = hsv(bh, 0.55, alpha * 1.4)
            if canvas[sy][sx] == " ":
                canvas[sy][sx] = f"{color}{s['ch']}{RESET}"
        for s in self.streams:
            sx, sy = int(s["x"]), int(s["y"]) % ch
            length = int(s["len"])
            for i in range(length):
                px = (sx + i) % cw
                if 0 <= px < cw and 0 <= sy < ch:
                    fade = 1.0 - (i / max(1, length))
                    alpha = s["b"] * fade * 0.8
                    if alpha < 0.10: continue
                    color = hsv(bh, 0.60, alpha * 1.3)
                    ch_char = "─" if i < length - 1 else "▸"
                    if canvas[sy][px] == " ":
                        canvas[sy][px] = f"{color}{ch_char}{RESET}"
        for s in self.bright:
            tw = 0.6 + 0.4 * math.sin(frame * 0.06 * s["ts"] + s["tp"])
            alpha = s["b"] * tw
            if alpha < 0.15: continue
            sx, sy = int(s["x"]) % cw, int(s["y"]) % ch
            color = hsv(bh, 0.30, alpha)
            core = hsv(bh - 0.02, 0.15, min(1.0, alpha + 0.3))
            if canvas[sy][sx] == " ":
                canvas[sy][sx] = f"{core}✦{RESET}"
            for dx, dy, ac in ((-1, 0, "─"), (1, 0, "─"), (0, -1, "│"), (0, 1, "│")):
                ax, ay = sx + dx, sy + dy
                if 0 <= ax < cw and 0 <= ay < ch:
                    arm_alpha = alpha * 0.5
                    arm_color = hsv(bh, 0.40, arm_alpha)
                    if canvas[ay][ax] == " ":
                        canvas[ay][ax] = f"{arm_color}{ac}{RESET}"


# ════════════════════════════════════════════════════════════════════════
#  MATRIX DIGITAL RAIN (vertical, head-highlighted)
# ════════════════════════════════════════════════════════════════════════

class MatrixRain:
    def __init__(self, width, height):
        self.width = width; self.height = height
        rng = random.Random(99)
        self.trails = []
        for x in range(width):
            if rng.random() < 0.55:
                self.trails.append({
                    "x": x,
                    "y": rng.uniform(-height, height),
                    "speed": rng.uniform(4, 10),
                    "length": rng.randint(4, 9),
                })

    def update(self, dt):
        for tr in self.trails:
            tr["y"] += tr["speed"] * dt
            if tr["y"] - tr["length"] > self.height:
                tr["y"] = -random.randint(0, self.height // 2)
                tr["speed"] = random.uniform(4, 10)
                tr["length"] = random.randint(4, 9)

    def render(self, canvas, w, h, frame):
        bh = palette_hue(frame)
        style = current_style()
        glyphs = "01ｱｲｳｴｵｶｷｸｹｺ#@$%&<>/\\|+=*-"
        for tr in self.trails:
            x = int(tr["x"])
            head_y = int(tr["y"])
            for i in range(tr["length"]):
                y = head_y - i
                if 0 <= y < h and 0 <= x < w:
                    if canvas[y][x] == " ":
                        alpha = 1.0 - (i / tr["length"])
                        if i == 0:
                            color = hsv(bh - 0.02, 0.10, 1.0)
                            ch = random.choice(glyphs)
                        elif i <= 2:
                            color = hsv(bh, 0.35, alpha * 0.95)
                            ch = random.choice(glyphs)
                        else:
                            color = hsv(bh + style["tail_hue_shift"], 0.62, alpha * 0.70)
                            ch = random.choice(glyphs)
                        canvas[y][x] = f"{color}{ch}{RESET}"


# ════════════════════════════════════════════════════════════════════════
#  SPARKLE + EXPLOSION PARTICLE SYSTEMS
# ════════════════════════════════════════════════════════════════════════

class SparkleSystem:
    def __init__(self):
        self.sparkles = []

    def spawn(self, count, cx, cy, radius):
        style = current_style()
        for _ in range(count):
            a = random.uniform(0, math.tau)
            d = random.uniform(radius * 0.7, radius * 1.4)
            self.sparkles.append({
                "x": cx + math.cos(a) * d, "y": cy + math.sin(a) * d * 0.5,
                "life": random.uniform(0.3, 1.0), "max_life": 1.0,
                "hue_off": random.uniform(style["hue_jitter_neg"], style["hue_jitter_pos"]),
                "char": random.choice("✦✧⋆✶"),
            })

    def update(self, dt):
        for s in self.sparkles:
            s["life"] -= dt * 1.5
        self.sparkles = [s for s in self.sparkles if s["life"] > 0]

    def render(self, canvas, cw, ch, frame):
        bh = palette_hue(frame)
        for s in self.sparkles:
            sx = int(s["x"]) % cw; sy = int(s["y"]) % ch
            alpha = s["life"] / s["max_life"]
            if alpha < 0.1: continue
            color = hsv(bh + s["hue_off"], 0.75, min(1.0, alpha * 1.4))
            if canvas[sy][sx] == " " or (canvas[sy][sx].startswith("\x1b") and "·" in canvas[sy][sx]):
                canvas[sy][sx] = f"{color}{s['char']}{RESET}"


class ExplosionSystem:
    """Physics-based ring explosion: gravity + damping + trail chars."""

    def __init__(self):
        self.particles = []
        self._last_trigger = -999

    def explode(self, cx, cy, radius, count=24, frame=0):
        self._last_trigger = frame
        style = current_style()
        for _ in range(count):
            direction = random.uniform(0, math.tau)
            speed = random.uniform(3, 7)
            life = random.uniform(0.4, 0.9)
            self.particles.append({
                "x": cx, "y": cy,
                "dx": math.sin(direction) * speed,
                "dy": math.cos(direction) * speed * 0.5,
                "life": life, "max_life": life,
                "char": random.choice("*+✦⋆#:."),
                "hue_off": random.uniform(style["hue_jitter_neg"], style["hue_jitter_pos"]),
            })

    def update(self, dt):
        damping = 0.94
        gravity = 0.12
        for p in self.particles:
            p["dy"] = p["dy"] * damping + gravity
            p["dx"] *= damping
            p["x"] += p["dx"] * dt * 6
            p["y"] += p["dy"] * dt * 6
            p["life"] -= dt
        self.particles = [p for p in self.particles if p["life"] > 0]

    def render(self, canvas, cw, ch, frame):
        bh = palette_hue(frame)
        for p in self.particles:
            x, y = int(p["x"]), int(p["y"])
            if 0 <= x < cw and 0 <= y < ch:
                alpha = p["life"] / p["max_life"]
                if alpha < 0.05: continue
                color = hsv(bh + p["hue_off"], 0.80, min(1.0, alpha * 1.5))
                if canvas[y][x] == " ":
                    canvas[y][x] = f"{color}{p['char']}{RESET}"


# ════════════════════════════════════════════════════════════════════════
#  ENERGY RINGS (from original)
# ════════════════════════════════════════════════════════════════════════

def render_energy_rings(canvas, cw, ch, cx, cy, frame, max_radius):
    bh = palette_hue(frame)
    style = current_style()
    for i in range(3):
        phase = (frame * 0.04 + i / 3) % 1.0
        radius = phase * max_radius
        if radius < 2: continue
        alpha = (1.0 - phase) * 0.65
        if alpha < 0.05: continue
        hue = bh + style["bg_hue_shift"] + phase * style["bg_hue_span"]
        color = hsv(hue, 0.72, alpha)
        steps = max(8, int(radius * 6))
        for j in range(steps):
            a = j / steps * math.tau
            rx = cx + math.cos(a) * radius
            ry = cy + math.sin(a) * radius * 0.5
            ix, iy = int(rx), int(ry)
            if 0 <= ix < cw and 0 <= iy < ch:
                if canvas[iy][ix] == " ":
                    canvas[iy][ix] = f"{color}·{RESET}"


# ════════════════════════════════════════════════════════════════════════
#  COG DECORATIONS (parametric spinning gears in corners)
# ════════════════════════════════════════════════════════════════════════

def render_cogs(canvas, w, h, frame):
    """Draw small spinning cogs in the four corners."""
    bh = palette_hue(frame)
    corners = [
        (4, 2, 1), (w - 5, 2, -1),
        (4, h - 3, -1), (w - 5, h - 3, 1),
    ]
    for cx, cy, direction in corners:
        radius = 2
        color = hsv(bh, 0.60, 0.60)
        for p in range(40):
            angle = (frame * direction + p) * math.pi / 20
            r = radius + (0.6 if (p // 4 % 2) else 0)
            x = cx + r * math.sin(angle)
            y = cy + r * 0.5 * math.cos(angle)
            ix, iy = int(x), int(y)
            if 0 <= ix < w and 0 <= iy < h:
                if canvas[iy][ix] == " ":
                    canvas[iy][ix] = f"{color}●{RESET}"


# ════════════════════════════════════════════════════════════════════════
#  CANVAS UTILITIES
# ════════════════════════════════════════════════════════════════════════

def make_canvas(w, h):
    return [[" " for _ in range(w)] for _ in range(h)]

def stamp_rows(canvas, rows, ox, oy=0):
    for y, row in enumerate(rows):
        ty = oy + y
        if ty < 0 or ty >= len(canvas): continue
        cells = CELL_RE.findall(row)
        for x, cell in enumerate(cells):
            dx = ox + x
            if 0 <= dx < len(canvas[0]):
                raw = ANSI_RE.sub("", cell)
                if raw.strip():
                    canvas[ty][dx] = cell


def clear_rect(canvas, x, y, w, h):
    for yy in range(max(0, y), min(len(canvas), y + h)):
        for xx in range(max(0, x), min(len(canvas[0]), x + w)):
            canvas[yy][xx] = " "


def apply_scanlines_real(canvas, w, h, frame):
    """Real CRT scanlines: dim odd rows by scaling RGB."""
    dim = 0.82
    for y in range(1, h, 2):
        for x in range(w):
            cell = canvas[y][x]
            if cell == " " or "38;2;" not in cell:
                continue
            m = re.search(r'38;2;(\d+);(\d+);(\d+)', cell)
            if m:
                r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
                nr, ng, nb = int(r * dim), int(g * dim), int(b * dim)
                canvas[y][x] = cell.replace(
                    f"38;2;{r};{g};{b}", f"38;2;{nr};{ng};{nb}")


def apply_noise_boot(canvas, w, h, boot_alpha, frame):
    """TV-tuning boot: overlay random static chars that fade as signal locks.

    boot_alpha: 0 = pure noise, 1 = clean signal.
    """
    noise_strength = 1.0 - boot_alpha
    if noise_strength < 0.02:
        return
    jitter = max(0, int(5 * noise_strength))
    bh = palette_hue(frame)
    style = current_style()
    noise_glyphs = "".join(chr(c) for c in range(33, 127))
    for y in range(h):
        offset = (jitter - 2 * random.randint(0, jitter)) if jitter > 0 else 0
        for x in range(w):
            cell = canvas[y][x]
            raw = ANSI_RE.sub("", cell).strip()
            if raw:
                # Signal pixel: occasionally replace with noise
                if random.random() < noise_strength * 0.7:
                    ch = random.choice(noise_glyphs)
                    hue = bh + random.uniform(style["noise_jitter_neg"], style["noise_jitter_pos"])
                    color = hsv(hue, 0.22, random.uniform(0.20, 0.50))
                    jx = max(0, min(w - 1, x + offset))
                    canvas[y][jx] = f"{color}{ch}{RESET}"
            else:
                # Empty pixel: sparse noise
                if random.random() < 0.20 * noise_strength:
                    ch = random.choice(noise_glyphs)
                    hue = bh + random.uniform(style["noise_jitter_neg"], style["noise_jitter_pos"])
                    color = hsv(hue, 0.18, random.uniform(0.12, 0.34))
                    canvas[y][x] = f"{color}{ch}{RESET}"


# ════════════════════════════════════════════════════════════════════════
#  LAYOUT
# ════════════════════════════════════════════════════════════════════════

def side_by_side_width(logo_canvas, wl, target_rows, aspect):
    text_width = wordmark_layout(wl, target_rows)[2] + wordmark_3d_depth(target_rows) + 2
    label_block_width = max(text_width, signature_width(target_rows))
    return component_columns(logo_canvas, target_rows, aspect) + max(2, target_rows//4) + label_block_width

def resolve_layout(logo_canvas, wl, width_limit, height_limit, aspect):
    tw, th = shutil.get_terminal_size((100, 40))
    mw = width_limit or max(48, min(tw, DEFAULT_MAX_WIDTH))
    mh = height_limit or max(10, min(th-2, DEFAULT_MAX_HEIGHT))
    baseline = 4
    for tr in range(mh, 3, -1):
        if total_layout_height(tr) <= mh and side_by_side_width(logo_canvas, wl, tr, aspect) <= mw:
            baseline = tr; break
    rr = max(4, min(baseline, mh))
    for tr in range(rr, baseline-1, -1):
        if total_layout_height(tr) <= mh and side_by_side_width(logo_canvas, wl, tr, aspect) <= mw:
            return component_columns(logo_canvas, tr, aspect), tr, max(2, tr//4), side_by_side_width(logo_canvas, wl, tr, aspect)
    # Fallback
    logo_w = component_columns(logo_canvas, baseline, aspect)
    total = logo_w + max(2, baseline//4) + wordmark_layout(wl, baseline)[2] + wordmark_3d_depth(baseline) + 2
    return logo_w, baseline, max(2, baseline//4), total


# ════════════════════════════════════════════════════════════════════════
#  MAIN ANIMATION LOOP
# ════════════════════════════════════════════════════════════════════════

def animate(logo_canvas, fps, step, frames, width_limit, height_limit, aspect, threshold,
            use_braille, use_3d_text, bg_mode,
            no_scanlines, no_glow, no_hud,
            boot_frames, bg_cycle, style_mode, style_cycle, style_transition):

    wl = build_wordmark_letters(DEFAULT_LABEL)
    logo_w, target_rows, gap, total_width = resolve_layout(
        logo_canvas, wl, width_limit, height_limit, aspect)
    total_height = total_layout_height(target_rows)
    spacer = " " * gap

    # Background renderers
    bg_renderers = {
        "plasma": render_plasma,
        "tunnel": render_tunnel,
        "julia":  render_julia,
    }
    bg_list = list(bg_renderers.keys())
    random_style_mode = style_mode == RANDOM_STYLE
    transition_frames = max(1, style_transition)
    if random_style_mode:
        set_style(choose_random_style())
        next_style_frame = random_style_interval(style_cycle)
        transition_start_frame = -1
    else:
        set_style(style_mode)
        next_style_frame = 0
        transition_start_frame = -1

    sys.stdout.write(CLEAR_SCREEN + HOME + HIDE_CURSOR)
    sys.stdout.flush()

    try:
        frame = 0
        angle = 0.0
        last_time = time.perf_counter()
        actual_fps = 0.0

        while frames <= 0 or frame < frames:
            start = time.perf_counter()
            dt = start - last_time; last_time = start
            t = frame * 0.05  # time parameter for effects
            if random_style_mode and frame >= next_style_frame:
                begin_style_transition(choose_random_style(ACTIVE_STYLE))
                transition_start_frame = frame
                next_style_frame = frame + max(
                    random_style_interval(style_cycle),
                    transition_frames + 1,
                )
            if random_style_mode and transition_start_frame >= 0:
                update_style_transition((frame - transition_start_frame) / transition_frames)

            # ── Render rotating logo face, then add pseudo-3D extrusion ──
            rotated = logo_canvas.rotate(angle, resample=RESAMPLE_BICUBIC,
                                         expand=False, fillcolor=255)
            logo_rows = (image_to_braille_rows_hue(rotated, target_rows, aspect,
                                                   threshold, frame)
                         if use_braille else
                         image_to_block_rows_hue(rotated, target_rows, aspect,
                                                 threshold, frame))
            logo_rows = render_logo_3d_rows(logo_rows, frame, t, logo_w)
            if not no_glow:
                logo_rows = render_glow_aura(logo_rows, target_rows, frame, logo_w)

            # ── Render wordmark (layered 3D or 2D flat) ────────────
            if use_3d_text:
                label_rows, label_width = render_layered_3d_wordmark_rows(
                    wl, target_rows, frame, t)
            else:
                label_rows, label_width = render_wordmark_rows(wl, target_rows, frame)
            if not no_glow and not use_3d_text:
                label_rows = render_glow_aura(label_rows, target_rows, frame, label_width)
            signature_rows, signature_w = render_signature_rows(target_rows, frame, t)

            # ── Build canvas ───────────────────────────────────────────
            canvas = make_canvas(total_width, total_height)

            # Background (cycling or fixed)
            if bg_mode == "cycle" and bg_cycle:
                ci = (frame // bg_cycle) % len(bg_list)
                ni = (ci + 1) % len(bg_list)
                phase = (frame % bg_cycle) / bg_cycle
                if phase > 1.0 - BG_CROSSFADE / bg_cycle:
                    bg_renderers[bg_list[ci]](canvas, total_width, total_height, frame, t)
                    bg_renderers[bg_list[ni]](canvas, total_width, total_height, frame, t)
                else:
                    bg_renderers[bg_list[ci]](canvas, total_width, total_height, frame, t)
            elif bg_mode in bg_renderers:
                bg_renderers[bg_mode](canvas, total_width, total_height, frame, t)

            # Keep the boot noise behind the logo/wordmark so the intro remains legible.
            if frame < boot_frames:
                boot_alpha = smoothstep(frame / max(1, boot_frames))
                apply_noise_boot(canvas, total_width, total_height, boot_alpha, frame)

            # Keep the line-art logo readable: do not let background glyphs
            # show through its negative space.
            clear_rect(canvas, 0, 0, logo_w, len(logo_rows))

            # Stamp logo + wordmark
            frame_rows = [f"{left}{spacer}{right}" for left, right in zip(logo_rows, label_rows)]
            stamp_rows(canvas, frame_rows, 0, 0)

            # CRT scanlines
            if not no_scanlines:
                apply_scanlines_real(canvas, total_width, total_height, frame)

            # Keep the small signature sharp; scanlines make it too hard to read.
            signature_x = logo_w + gap + max(0, (label_width - signature_w) // 2)
            signature_x = min(signature_x, max(0, total_width - signature_w))
            signature_y = target_rows + signature_gap_rows(target_rows)
            clear_rect(
                canvas,
                max(0, signature_x - 2),
                signature_y,
                min(total_width, signature_w + 4),
                len(signature_rows),
            )
            stamp_rows(canvas, signature_rows, signature_x, signature_y)

            # ── Output ─────────────────────────────────────────────────
            output = "\n".join("".join(r) for r in canvas)
            sys.stdout.write(HOME)
            sys.stdout.write(output)

            if not no_hud:
                style_name = current_style()["name"]
                if random_style_mode:
                    style_name = f"{RANDOM_STYLE.upper()}:{style_name}"
                hud = (
                    f"\n{hsv(palette_hue(frame), 0.6, 0.7)}"
                    f" FRAME {frame:6d} | ANGLE {angle:6.1f}° | "
                    f"FPS {actual_fps:5.1f} | ROT {step:.0f}°/f"
                    f" | BG {bg_mode} | STYLE {style_name}"
                    f"{'| 3D-TEXT' if use_3d_text else '| 2D-TEXT'}"
                    f"{RESET}"
                )
                sys.stdout.write(hud)

            sys.stdout.write("\n")
            sys.stdout.flush()

            frame += 1
            angle = (angle + step) % 360.0
            elapsed = time.perf_counter() - start
            if fps > 0:
                delay = max(0.0, (1.0/fps) - elapsed)
                time.sleep(delay)
                actual_fps = 1.0 / max(0.001, time.perf_counter() - start)
            else:
                actual_fps = 1.0 / max(0.001, elapsed)

    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write(SHOW_CURSOR + "\n")
        sys.stdout.flush()


# ════════════════════════════════════════════════════════════════════════
#  CLI
# ════════════════════════════════════════════════════════════════════════

def parse_args():
    p = argparse.ArgumentParser(
        description="Ultimate rotating ASCII logo with ALL effects.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Background modes:
  cycle   Auto-cycle plasma → tunnel → julia (default)
  plasma  Sinusoidal interference
  tunnel  Polar infinite corridor
  julia   Fractal zoom
  none    No background

Styles:
  random     Randomly switch styles during animation (default)
  golden     Bright gold / amber
  blackgold  Near-black body with gold edges
  cyber      Cyan / magenta neon
  ice        Blue-white crystalline
  matrix     Green terminal glow
  ember      Red-orange heat

Examples:
  python3 rotate_logo_ascii_ultra.py                     # 2D logo + layered 3D text, all effects
  python3 rotate_logo_ascii_ultra.py --style random       # randomly change color styles
  python3 rotate_logo_ascii_ultra.py --style-transition 10 # faster style gradients
  python3 rotate_logo_ascii_ultra.py --style blackgold    # darker black/gold style
  python3 rotate_logo_ascii_ultra.py --style cyber        # cyan/magenta tech style
  python3 rotate_logo_ascii_ultra.py --bg plasma          # plasma background
  python3 rotate_logo_ascii_ultra.py --2d-text            # flat 2D wordmark
  python3 rotate_logo_ascii_ultra.py --braille            # braille 2D logo rendering
""")
    p.add_argument("image", nargs="?", type=Path, default=DEFAULT_IMAGE,
                   help="Logo image")
    p.add_argument("--fps", type=float, default=20.0)
    p.add_argument("--step", type=float, default=8.0, help="Rotation degrees per frame")
    p.add_argument("--frames", type=int, default=0, help="0 = infinite")
    p.add_argument("--width", type=int, default=None)
    p.add_argument("--height", type=int, default=None)
    p.add_argument("--aspect", type=float, default=DEFAULT_ASPECT)
    p.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD)
    p.add_argument("--style", choices=[RANDOM_STYLE] + list(STYLE_PRESETS.keys()),
                   default=DEFAULT_STYLE_MODE, help="Color style")
    p.add_argument("--style-cycle", type=int, default=STYLE_RANDOM_FRAMES,
                   help="Average frames between random style changes")
    p.add_argument("--style-transition", type=int, default=STYLE_TRANSITION_FRAMES,
                   help="Frames used for random style gradient transitions")
    p.add_argument("--boot", type=int, default=18, help="Boot noise frames")
    p.add_argument("--bg", choices=["cycle","plasma","tunnel","julia","none"],
                   default="cycle", help="Background mode")
    p.add_argument("--bg-cycle", type=int, default=BG_CYCLE_FRAMES,
                   help="Frames per background when cycling")
    p.add_argument("--2d-text", action="store_true",
                   help="Use flat 2D wordmark instead of layered 3D text")
    p.add_argument("--braille", action="store_true", help="Braille 2D logo rendering (4x detail)")
    # Disable flags
    p.add_argument("--no-scanlines", action="store_true")
    p.add_argument("--no-glow", action="store_true")
    p.add_argument("--no-hud", action="store_true")
    p.add_argument("--print-center", action="store_true")
    return p.parse_args()


def main():
    args = parse_args()
    if args.style != RANDOM_STYLE:
        set_style(args.style)

    if not args.image.exists():
        print(f"Image not found: {args.image}", file=sys.stderr)
        return 1
    logo_canvas, center = prepare_canvas(args.image)
    if args.print_center:
        print(f"rotation center: ({center[0]:.2f}, {center[1]:.2f})", file=sys.stderr)

    try:
        animate(
            logo_canvas, args.fps, args.step, args.frames,
            args.width, args.height, args.aspect, args.threshold,
            args.braille, not args.__dict__.get("2d_text", False), args.bg,
            args.no_scanlines, args.no_glow, args.no_hud,
            args.boot, args.bg_cycle, args.style, args.style_cycle,
            args.style_transition)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
