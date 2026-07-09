# ─────────────────────────────────────────────────────────────
# PyPortal Touch Map — Reusable touchscreen configuration
# ─────────────────────────────────────────────────────────────
# Hardware: Adafruit PyPortal (3.2" TFT) / PyPortal Pynt (2.4" TFT)
# Touch:    4-wire resistive, analog
# Display:  320x240 pixels (landscape, default orientation)
#
# Pin order matters! The official Adafruit pin order is:
#   TOUCH_XL, TOUCH_XR, TOUCH_YD, TOUCH_YU
#
# Getting the Y pins backwards (YU before YD) will cause all
# touch reads to return garbage / clamp to a single coordinate.
#
# Calibration values tuned with touch_calibrator.py.
# Adafruit defaults are ((5200, 59000), (5800, 57000)) but
# individual units vary significantly — especially Y_MIN.
# Use touch_calibrator.py to fine-tune for your specific board.
#
# Note: Resistive touchscreens have inherent nonlinearity
# (~15px variance). Use touch targets >= 30px to absorb this.
# ─────────────────────────────────────────────────────────────

import board
import adafruit_touchscreen

# Display dimensions (default landscape orientation)
DISPLAY_WIDTH  = 320
DISPLAY_HEIGHT = 240

# Touch calibration — raw analog range mapped to pixel coordinates
# Format: ((x_min_raw, x_max_raw), (y_min_raw, y_max_raw))
# x_min_raw -> pixel 0 (left edge)
# x_max_raw -> pixel 320 (right edge)
# y_min_raw -> pixel 0 (top edge)
# y_max_raw -> pixel 240 (bottom edge)
TOUCH_CALIBRATION = ((6800, 59600), (22500, 54800))

# Minimum time between accepted taps (seconds)
# Resistive screens can ghost/bounce — this prevents double-taps
TOUCH_DEBOUNCE = 0.3


def create_touchscreen():
    """Create and return a calibrated Touchscreen instance.

    Usage:
        from pyportal_touch_map import create_touchscreen
        ts = create_touchscreen()

        while True:
            point = ts.touch_point
            if point:
                x, y, pressure = point
                print(f"Touch at ({x}, {y})")
    """
    return adafruit_touchscreen.Touchscreen(
        board.TOUCH_XL,
        board.TOUCH_XR,
        board.TOUCH_YD,   # YD before YU — critical!
        board.TOUCH_YU,
        calibration=TOUCH_CALIBRATION,
        size=(DISPLAY_WIDTH, DISPLAY_HEIGHT),
    )


class TouchZone:
    """A rectangular hit-test zone for touch input.

    Usage:
        button = TouchZone("my_button", 50, 100, 120, 40)
        # creates a zone at x=50, y=100, width=120, height=40

        point = ts.touch_point
        if point and button.contains(point[0], point[1]):
            print("Button tapped!")
    """

    def __init__(self, name, x, y, width, height):
        self.name = name
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    def contains(self, px, py):
        """Check if pixel coordinate (px, py) is inside this zone."""
        return (self.x <= px <= self.x + self.width and
                self.y <= py <= self.y + self.height)

    def __repr__(self):
        return "TouchZone('{}', x={}, y={}, w={}, h={})".format(
            self.name, self.x, self.y, self.width, self.height)


class TouchManager:
    """Manages touch polling with debounce and zone hit-testing.

    Usage:
        from pyportal_touch_map import create_touchscreen, TouchManager

        ts = create_touchscreen()
        touch = TouchManager(ts)

        touch.add_zone("start_btn", 100, 80, 120, 40)
        touch.add_zone("settings", 100, 140, 120, 40)

        while True:
            zone, x, y = touch.poll()
            if zone:
                print("Tapped:", zone.name, x, y)
            time.sleep(0.05)
    """

    def __init__(self, touchscreen, debounce=TOUCH_DEBOUNCE):
        self.ts = touchscreen
        self.debounce = debounce
        self.zones = []
        self._last_touch_time = 0

    def add_zone(self, name, x, y, width, height):
        """Register a named touch zone. Returns the TouchZone."""
        zone = TouchZone(name, x, y, width, height)
        self.zones.append(zone)
        return zone

    def clear_zones(self):
        """Remove all registered zones."""
        self.zones = []

    def poll(self):
        """Check for touch. Returns (TouchZone, x, y) or (None, 0, 0).

        Respects debounce timing. If touch is detected but doesn't
        land in any registered zone, returns (None, 0, 0) — the
        tap is consumed by debounce either way.
        """
        import time
        point = self.ts.touch_point
        now = time.monotonic()

        if point is not None and (now - self._last_touch_time > self.debounce):
            x, y, _pressure = point
            self._last_touch_time = now

            for zone in self.zones:
                if zone.contains(x, y):
                    return zone, x, y

        return None, 0, 0

    def poll_raw(self):
        """Check for touch without zone matching. Returns (x, y, pressure) or None.

        Respects debounce timing.
        """
        import time
        point = self.ts.touch_point
        now = time.monotonic()

        if point is not None and (now - self._last_touch_time > self.debounce):
            self._last_touch_time = now
            return point

        return None
