import os
import sys
import time

from utilities.animator import Animator
from setup import colours, frames, screen

from rgbmatrix import graphics

# Attempt to load config data
try:
    from config import LOGO_INTERVAL

except (ModuleNotFoundError, NameError, ImportError):
    # If there's no config data
    LOGO_INTERVAL = 300  # seconds

# Setup
DIR_PATH = os.path.dirname(os.path.realpath(__file__))
LOGO_FILE = f"{DIR_PATH}/../assets/logo.pgm"
LOGO_COLOUR = colours.PINK
LOGO_BACKGROUND = colours.BLACK
LOGO_MARGIN = 4
LOGO_SCROLL_STEP = 2
LOGO_HOLD_FRAMES = frames.PER_SECOND * 5


def load_logo(path):
    # Read a plain (P2) greyscale PGM and return the
    # pixels to draw as (x, y, red, green, blue)
    try:
        with open(path) as f:
            values = [
                v for line in f for v in line.split("#")[0].split()
            ]

    except FileNotFoundError:
        return None, 0, 0

    if values[0] != "P2":
        print(f"Logo must be a plain PGM (P2): {path}", file=sys.stderr)
        return None, 0, 0

    width, height, max_value = (int(v) for v in values[1:4])
    levels = [int(v) / max_value for v in values[4:]]

    pixels = []
    for i, level in enumerate(levels):
        if level:
            pixels.append(
                (
                    i % width,
                    i // width,
                    *(
                        int(bg + (fg - bg) * level)
                        for fg, bg in (
                            (LOGO_COLOUR.red, LOGO_BACKGROUND.red),
                            (LOGO_COLOUR.green, LOGO_BACKGROUND.green),
                            (LOGO_COLOUR.blue, LOGO_BACKGROUND.blue),
                        )
                    ),
                )
            )

    return pixels, width, height


class LogoScene(object):
    def __init__(self):
        super().__init__()
        self._logo, self._logo_width, self._logo_height = load_logo(LOGO_FILE)
        self._logo_canvas = None
        self._logo_showing = False
        self._logo_position = screen.WIDTH
        self._logo_hold = 0
        self._logo_stops = []
        self._logo_last_shown = time.monotonic()
        self._logo_loop_mark = 0

    def draw_logo(self):
        self._logo_canvas.Fill(
            LOGO_BACKGROUND.red, LOGO_BACKGROUND.green, LOGO_BACKGROUND.blue
        )
        y_offset = (screen.HEIGHT - self._logo_height) // 2

        for x, y, red, green, blue in self._logo:
            x += self._logo_position
            if 0 <= x < screen.WIDTH:
                self._logo_canvas.SetPixel(x, y + y_offset, red, green, blue)

    @Animator.KeyFrame.add(1)
    def logo(self, count):
        # Guard against no logo file
        if not self._logo:
            return

        if not self._logo_showing:
            if time.monotonic() - self._logo_last_shown < LOGO_INTERVAL:
                self._logo_loop_mark = self._data_loop_count
                return

            # If flights are on screen wait until
            # they've all been shown before interrupting
            if len(self._data) and self._data_loop_count == self._logo_loop_mark:
                return

            if self._logo_canvas is None:
                self._logo_canvas = self.matrix.CreateFrameCanvas()

            self._logo_showing = True
            self._logo_position = screen.WIDTH
            self._logo_hold = 0

            # Pause in the centre, or if the logo is wider
            # than the screen pause on its start then its end
            if self._logo_width <= screen.WIDTH:
                self._logo_stops = [(screen.WIDTH - self._logo_width) // 2]
            else:
                self._logo_stops = [
                    LOGO_MARGIN,
                    screen.WIDTH - self._logo_width - LOGO_MARGIN,
                ]

        target = self._logo_stops[0] if self._logo_stops else -self._logo_width

        # Scroll to each stop, hold, then scroll out
        if self._logo_position > target:
            self._logo_position = max(target, self._logo_position - LOGO_SCROLL_STEP)
        elif self._logo_stops and self._logo_hold < LOGO_HOLD_FRAMES:
            self._logo_hold += 1
            if self._logo_hold > 1:
                return
        elif self._logo_stops:
            self._logo_stops.pop(0)
            self._logo_hold = 0
            return
        else:
            self._logo_showing = False
            self._logo_last_shown = time.monotonic()
            self._logo_loop_mark = self._data_loop_count
            return

        self.draw_logo()
