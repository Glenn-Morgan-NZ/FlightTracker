#!/usr/bin/env python3
"""
SkiesFifty logo pusher for FlightTracker.

Every INTERVAL seconds, scrolls a logo onto the display, holds it in the
centre, then scrolls it off, using FlightTracker's Image Upload API
(POST /api/image). The tracker's own code is left untouched, so its
web updater keeps working.

The API takes at most 60 frames per upload, so the animation is sent as
several uploads (scroll in, hold, scroll out, each split into chunks of
60 frames or fewer). Each new upload replaces the previous one, so the
next part is sent just before the current one ends.

The API key and port are read from FlightTracker's config.json on every
run, so regenerating the key in the web UI needs no change here.

Usage:
    python3 push_logo.py [--once] [--logo logo.pgm] [--config ~/.local/share/FlightTracker/config.json]
"""

import argparse
import base64
import json
import math
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

WIDTH = 64
HEIGHT = 32

INTERVAL = 60  # seconds between logo showings
COLOUR = (200, 0, 200)  # Same purple as the aircraft-type text
BACKGROUND = (0, 0, 0)
SCROLL_SPEED = 1.5  # pixels per frame (positions are rounded)
FRAME_MS = 80  # FlightTracker renders a frame every 80ms
HOLD_MS = 5000
OVERLAP_S = 0.3  # Send the next part this early so the screen never drops back
MAX_FRAMES = 60  # Image API limit per upload

HERE = Path(__file__).resolve().parent
DEFAULT_LOGO = HERE / "logo.pgm"
DEFAULT_CONFIG = Path.home() / ".local" / "share" / "FlightTracker" / "config.json"


def log(message):
    print(f"[skiesfifty-logo] {message}", flush=True)


def load_pgm(path):
    """Read a plain (P2) greyscale PGM; returns (width, height, levels 0-1)."""
    values = [
        v for line in path.read_text().splitlines() for v in line.split("#")[0].split()
    ]
    if values[0] != "P2":
        raise ValueError(f"{path} must be a plain PGM (P2)")
    width, height, max_value = (int(v) for v in values[1:4])
    levels = [int(v) / max_value for v in values[4 : 4 + width * height]]
    return width, height, levels


def render_frame(logo, x_offset):
    """One 64x32 RGB frame with the logo's left edge at x_offset."""
    width, height, levels = logo
    y_offset = (HEIGHT - height) // 2
    frame = bytearray(bytes(BACKGROUND) * (WIDTH * HEIGHT))

    for y in range(height):
        for x in range(width):
            level = levels[y * width + x]
            px = x + x_offset
            if level and 0 <= px < WIDTH:
                i = ((y + y_offset) * WIDTH + px) * 3
                frame[i : i + 3] = bytes(
                    int(bg + (fg - bg) * level) for fg, bg in zip(COLOUR, BACKGROUND)
                )

    return base64.b64encode(bytes(frame)).decode("ascii")


def scroll_positions(start, end):
    """Evenly spaced x offsets from start to end at about SCROLL_SPEED px/frame."""
    steps = math.ceil(abs(start - end) / SCROLL_SPEED)
    return [round(start + (end - start) * k / steps) for k in range(steps + 1)]


def scroll_uploads(logo, positions):
    """Scroll frames split into uploads the API will accept.

    Every chunk after the first repeats the previous chunk's last frame, which
    is cut short by OVERLAP_S, so no position is skipped.
    """
    pad = int(OVERLAP_S * 1000 / FRAME_MS) + 1
    uploads = []
    while positions:
        chunk = positions[: MAX_FRAMES - pad]
        positions = positions[len(chunk) :]
        if positions:
            # Pad the end so cutting it short by OVERLAP_S doesn't skip frames
            chunk += [chunk[-1]] * pad
        uploads.append(
            {"data": [render_frame(logo, x) for x in chunk], "frame_ms": FRAME_MS}
        )
    return uploads


def build_animation(logo):
    """Return the uploads: scroll in, hold, scroll out."""
    width = logo[0]
    centre = (WIDTH - width) // 2
    pad = int(OVERLAP_S * 1000 / FRAME_MS) + 1

    # Pad the end so cutting it short by OVERLAP_S still lands on the centre
    scroll_in = scroll_positions(WIDTH, centre) + [centre] * pad
    scroll_out = scroll_positions(centre, -width)

    return (
        scroll_uploads(logo, scroll_in)
        + [{"data": [render_frame(logo, centre)], "frame_ms": HOLD_MS}]
        + scroll_uploads(logo, scroll_out)
    )


def read_tracker_config(path):
    config = json.loads(path.read_text())
    return config.get("image_api_key") or "", int(config.get("web_port", 8584))


def push(port, key, payload):
    """Upload one animation; returns how long it will be on screen (seconds)."""
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/image",
        data=json.dumps({**payload, "loops": 1}).encode(),
        headers={"Content-Type": "application/json", "X-API-Key": key},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        result = json.loads(response.read())
    return result["frames"] * result["effective_frame_ms"] / 1000


def show_logo(animation, config_path):
    key, port = read_tracker_config(config_path)
    if not key:
        log("No image API key in config.json yet - generate one in the web UI")
        return False

    parts = len(animation)
    for i, payload in enumerate(animation):
        duration = push(port, key, payload)
        if i < parts - 1:
            time.sleep(max(0, duration - OVERLAP_S))
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--logo", type=Path, default=DEFAULT_LOGO)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--interval", type=int, default=INTERVAL)
    parser.add_argument(
        "--once", action="store_true", help="show the logo once and exit"
    )
    args = parser.parse_args()

    animation = build_animation(load_pgm(args.logo))
    log(f"Loaded {args.logo.name}; showing every {args.interval}s")

    while True:
        started = time.monotonic()
        try:
            show_logo(animation, args.config)
        except (urllib.error.URLError, OSError, ValueError, KeyError) as exc:
            # Tracker restarting, web UI off, or config missing - try again next time
            log(f"Could not show logo: {exc}")

        if args.once:
            return

        time.sleep(max(1, args.interval - (time.monotonic() - started)))


if __name__ == "__main__":
    sys.exit(main())
