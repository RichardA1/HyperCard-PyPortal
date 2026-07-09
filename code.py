# SPDX-License-Identifier: MIT
# HyperCard V1 — PyPortal CircuitPython Application
# Memory-optimized: header/tabs built once, only content swaps

import time
import json
import os
import gc
import board
import displayio
import terminalio
import storage
import sdcardio
from adafruit_display_text import label as text_label
from adafruit_display_shapes.rect import Rect
from adafruit_display_shapes.line import Line
from pyportal_touch_map import create_touchscreen, TouchManager

try:
    import adafruit_miniqr
    HAS_QR = True
except ImportError:
    HAS_QR = False
    print("WARN: adafruit_miniqr not found, QR tab disabled")

# ─── COLORS ─────────────────────────────────────────────────
COLOR_BG         = 0x0A0E27
COLOR_BG_HEADER  = 0x1A1F3A
COLOR_CYAN       = 0x00FFFF
COLOR_MAGENTA    = 0xFF00FF
COLOR_GREEN      = 0x00FF41
COLOR_TEXT        = 0xA0AEC0
COLOR_MUTED      = 0x6A7A8C
COLOR_TAB_ACTIVE = 0x0A1A2A
COLOR_WHITE      = 0xFFFFFF
COLOR_BLACK      = 0x000000

# ─── LAYOUT ─────────────────────────────────────────────────
DISPLAY_W = 320
DISPLAY_H = 240
HEADER_H  = 24
TAB_W     = 30
CONTENT_X = TAB_W
CONTENT_Y = HEADER_H
CONTENT_W = DISPLAY_W - TAB_W
CONTENT_H = DISPLAY_H - HEADER_H

ITEMS_PER_PAGE = 5
CHECKLIST_WRITE_DELAY = 3.0

# ─── DISPLAY ────────────────────────────────────────────────
display = board.DISPLAY
display.brightness = 0.2
display.auto_refresh = False
font = terminalio.FONT

# ─── TOUCH ──────────────────────────────────────────────────
ts = create_touchscreen()
touch = TouchManager(ts, debounce=0.35)

# ─── STATE ──────────────────────────────────────────────────
device_name = "HyperCard"
brightness = 0.2
contact_data = None
qr_data = None
checklist_data = None

tabs = []
active_tab = 0
checklist_page = 0
qr_detail_index = -1

checklist_dirty = False
checklist_last_change = 0

# Display groups — persistent
root = displayio.Group()
header_group = None
tab_group = None
content_group = None


# ─── SD CARD ────────────────────────────────────────────────

def ensure_sd_mountpoint():
    try:
        os.stat("/sd")
    except OSError:
        try:
            os.mkdir("/sd")
        except OSError:
            pass

def read_json(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        print("Skip:", path, "-", e)
        return None

def mount_sd():
    try:
        ensure_sd_mountpoint()
        sd = sdcardio.SDCard(board.SPI(), board.SD_CS)
        vfs = storage.VfsFat(sd)
        storage.mount(vfs, "/sd")
        return True
    except OSError as e:
        print("SD mount failed:", e)
        return False

def unmount_sd():
    try:
        storage.umount("/sd")
    except OSError:
        pass

def load_all_data():
    global device_name, brightness, contact_data, qr_data, checklist_data
    if not mount_sd():
        return
    dev = read_json("/sd/device.json")
    if dev:
        device_name = dev.get("name", "HyperCard")
        brightness = dev.get("brightness", 0.2)
    contact_data = read_json("/sd/contact.json")
    qr_data = read_json("/sd/qrcode.json")
    checklist_data = read_json("/sd/checklist.json")
    unmount_sd()
    display.brightness = brightness

def save_checklist():
    global checklist_dirty
    if not checklist_dirty:
        return
    if time.monotonic() - checklist_last_change < CHECKLIST_WRITE_DELAY:
        return
    try:
        mount_sd()
        with open("/sd/checklist.json", "w") as f:
            json.dump(checklist_data, f)
        unmount_sd()
        checklist_dirty = False
        print("Checklist saved")
    except OSError as e:
        print("Save failed:", e)


# ─── TAB LOGIC ──────────────────────────────────────────────

def determine_tabs():
    global tabs
    tabs = []
    if contact_data and contact_data.get("name"):
        tabs.append({"id": "contact", "label": "CONTACT"})
    if qr_data and qr_data.get("items"):
        tabs.append({"id": "qr", "label": "QR CODE"})
    if checklist_data and checklist_data.get("items"):
        tabs.append({"id": "checklist", "label": "CHECK"})
    if not tabs:
        tabs.append({"id": "empty", "label": "EMPTY"})


# ─── SPLASH ─────────────────────────────────────────────────

def show_splash():
    splash = displayio.Group()
    splash.append(Rect(0, 0, DISPLAY_W, DISPLAY_H, fill=COLOR_BG))
    splash.append(text_label.Label(
        font, text="HYPERCARD", color=COLOR_CYAN,
        x=DISPLAY_W // 2 - 45, y=DISPLAY_H // 2 - 20, scale=2,
    ))
    splash.append(text_label.Label(
        font, text="V1.0", color=COLOR_MAGENTA,
        x=DISPLAY_W // 2 - 12, y=DISPLAY_H // 2 + 10,
    ))
    splash.append(text_label.Label(
        font, text="LOADING...", color=COLOR_MUTED,
        x=DISPLAY_W // 2 - 30, y=DISPLAY_H // 2 + 35,
    ))
    display.root_group = splash
    display.refresh()
    return splash


# ─── BUILD HEADER (once) ────────────────────────────────────

def build_header():
    g = displayio.Group()
    g.append(Rect(0, 0, DISPLAY_W, HEADER_H, fill=COLOR_BG_HEADER))
    g.append(Line(0, HEADER_H - 1, DISPLAY_W - 1, HEADER_H - 1, color=COLOR_MAGENTA))
    
    # Battery
    g.append(Rect(6, 7, 18, 10, outline=COLOR_CYAN))
    g.append(Rect(24, 9, 2, 6, fill=COLOR_CYAN))
    g.append(Rect(7, 8, 13, 8, fill=COLOR_GREEN))
    g.append(text_label.Label(font, text="85%", color=COLOR_GREEN, x=28, y=12))
    g.append(text_label.Label(font, text="OFFLINE", color=COLOR_MUTED, x=55, y=12))
    
    # Device name
    nx = DISPLAY_W - (len(device_name) * 6) - 8
    g.append(text_label.Label(font, text=device_name, color=COLOR_MAGENTA, x=nx, y=12))
    return g


# ─── BUILD TAB BAR (once, but update colors on switch) ──────

def build_tab_bar():
    """Build initial tab bar. Returns group and list of label refs."""
    g = displayio.Group()
    g.append(Rect(0, HEADER_H, TAB_W, CONTENT_H, fill=COLOR_BG))
    g.append(Line(TAB_W - 1, HEADER_H, TAB_W - 1, DISPLAY_H - 1, color=COLOR_MUTED))

    num_tabs = len(tabs)
    tab_h = CONTENT_H // num_tabs
    tab_labels = []
    tab_bgs = []
    tab_indicators = []

    for i, tab in enumerate(tabs):
        y_start = HEADER_H + (i * tab_h)

        # Background rect (will toggle fill)
        is_active = (i == active_tab)
        bg_fill = COLOR_TAB_ACTIVE if is_active else COLOR_BG
        bg = Rect(0, y_start, TAB_W - 1, tab_h, fill=bg_fill)
        g.append(bg)
        tab_bgs.append(bg)

        # Active indicator
        ind_fill = COLOR_MAGENTA if is_active else COLOR_BG
        ind = Rect(TAB_W - 3, y_start, 3, tab_h, fill=ind_fill)
        g.append(ind)
        tab_indicators.append(ind)

        # Separator
        if i > 0:
            g.append(Line(2, y_start, TAB_W - 4, y_start, color=COLOR_MUTED))

        # Vertical label chars
        label_text = tab["label"]
        text_color = COLOR_CYAN if is_active else COLOR_MUTED
        ch_h = 10
        total = len(label_text) * ch_h
        ty = y_start + (tab_h - total) // 2
        char_labels = []

        for ci, ch in enumerate(label_text):
            lbl = text_label.Label(
                font, text=ch, color=text_color,
                x=TAB_W // 2 - 3, y=ty + (ci * ch_h) + 5,
            )
            g.append(lbl)
            char_labels.append(lbl)
        tab_labels.append(char_labels)

        # Register touch zone
        touch.add_zone("tab_{}".format(i), 0, y_start, TAB_W, tab_h)

    return g, tab_labels, tab_bgs, tab_indicators


def update_tab_visuals():
    """Update tab colors without rebuilding. Uses stored refs."""
    global tab_labels_ref, tab_bgs_ref, tab_inds_ref
    for i in range(len(tabs)):
        is_active = (i == active_tab)
        # Update label colors
        color = COLOR_CYAN if is_active else COLOR_MUTED
        for lbl in tab_labels_ref[i]:
            lbl.color = color
        # Update background and indicator fills
        tab_bgs_ref[i].fill = COLOR_TAB_ACTIVE if is_active else COLOR_BG
        tab_inds_ref[i].fill = COLOR_MAGENTA if is_active else COLOR_BG


# ─── CONTENT BUILDERS ──────────────────────────────────────

def clear_content_zones():
    """Remove all non-tab touch zones."""
    tab_zones = [z for z in touch.zones if z.name.startswith("tab_")]
    touch.zones = tab_zones


def build_contact():
    g = displayio.Group(x=CONTENT_X, y=CONTENT_Y)
    c = contact_data
    y = 6

    g.append(text_label.Label(font, text="CONTACT CARD", color=COLOR_MAGENTA, x=6, y=y + 4))
    y += 14
    g.append(Line(6, y, CONTENT_W - 8, y, color=COLOR_CYAN))
    y += 10
    g.append(text_label.Label(font, text=c.get("name", ""), color=COLOR_CYAN, x=6, y=y + 6, scale=2))
    y += 24

    title = c.get("title", "")
    if title:
        g.append(text_label.Label(font, text=title, color=COLOR_TEXT, x=6, y=y + 4))
        y += 16

    fields = []
    if c.get("email"):
        fields.append(("EMAIL", c["email"]))
    if c.get("phone"):
        fields.append(("PHONE", c["phone"]))
    if c.get("custom1_label") and c.get("custom1_value"):
        fields.append((c["custom1_label"].upper(), c["custom1_value"]))
    if c.get("custom2_label") and c.get("custom2_value"):
        fields.append((c["custom2_label"].upper(), c["custom2_value"]))

    for fl, fv in fields:
        g.append(text_label.Label(font, text=fl, color=COLOR_MAGENTA, x=6, y=y + 4))
        g.append(text_label.Label(font, text=fv, color=COLOR_CYAN, x=62, y=y + 4))
        y += 14

    # Photo
    try:
        photo_x = CONTENT_W - 84 - 25
        photo_y = CONTENT_H - 84 - 25
        
        photo_file = open("/sd/contact_photo.bmp", "rb")
        photo_bitmap = displayio.OnDiskBitmap(photo_file)
        photo_grid = displayio.TileGrid(photo_bitmap, pixel_shader=displayio.ColorConverter())
        photo_group = displayio.Group(x=photo_x, y=photo_y)
        photo_group.append(photo_grid)
        
        photo_group.append(Line(0, 0, 79, 0, color=COLOR_CYAN))
        photo_group.append(Line(0, 79, 79, 79, color=COLOR_CYAN))
        photo_group.append(Line(0, 0, 0, 79, color=COLOR_CYAN))
        photo_group.append(Line(79, 0, 79, 79, color=COLOR_CYAN))
        
        g.append(photo_group)
        print("Contact photo loaded")
    except (OSError, Exception) as e:
        print("No contact photo or load error:", e)

    # Brightness controls at bottom
    brightness_area_h = 30
    brightness_y = CONTENT_H - brightness_area_h
    
    # Minus button at x=53 in content space (absolute x=83)
    minus_x = 53
    g.append(text_label.Label(
        font, text="−", color=COLOR_CYAN,
        x=minus_x, y=brightness_y + 10,
    ))
    touch.add_zone("brightness_down_contact", 
                   CONTENT_X + minus_x - 15, CONTENT_Y + brightness_y, 
                   40, brightness_area_h)
    
    # Plus button (keep existing)
    plus_x = CONTENT_W - 25
    g.append(text_label.Label(
        font, text="+", color=COLOR_CYAN,
        x=plus_x, y=brightness_y + 10,
    ))
    touch.add_zone("brightness_up_contact", 
                   CONTENT_X + CONTENT_W - 65, CONTENT_Y + brightness_y, 
                   60, brightness_area_h)

    return g


def build_qr_list():
    g = displayio.Group(x=CONTENT_X, y=CONTENT_Y)
    y = 6

    g.append(text_label.Label(font, text="QR CODES", color=COLOR_MAGENTA, x=6, y=y + 4))
    y += 14
    g.append(Line(6, y, CONTENT_W - 8, y, color=COLOR_CYAN))
    y += 6

    items = qr_data.get("items", [])[:4]
    for i, item in enumerate(items):
        item_h = 42
        g.append(Rect(4, y, CONTENT_W - 12, item_h, outline=COLOR_MUTED))
        g.append(text_label.Label(
            font, text=item.get("label", "QR {}".format(i + 1)),
            color=COLOR_CYAN, x=12, y=y + 13,
        ))
        data_str = item.get("data", "")
        if len(data_str) > 35:
            data_str = data_str[:35] + "..."
        g.append(text_label.Label(font, text=data_str, color=COLOR_MUTED, x=12, y=y + 28))
        g.append(text_label.Label(font, text=">", color=COLOR_MUTED, x=CONTENT_W - 20, y=y + 20))
        touch.add_zone("qr_item_{}".format(i), CONTENT_X + 4, CONTENT_Y + y, CONTENT_W - 12, item_h)
        y += item_h + 4

    return g


def build_qr_detail(index):
    g = displayio.Group(x=CONTENT_X, y=CONTENT_Y)
    item = qr_data["items"][index]
    y = 6

    g.append(Rect(4, y, 60, 26, outline=COLOR_MAGENTA))
    g.append(text_label.Label(font, text="< BACK", color=COLOR_MAGENTA, x=10, y=y + 13))
    touch.add_zone("qr_back", CONTENT_X + 4, CONTENT_Y + y, 60, 26)
    y += 32

    lbl = item.get("label", "QR Code")
    g.append(text_label.Label(
        font, text=lbl, color=COLOR_MAGENTA,
        x=CONTENT_W // 2 - len(lbl) * 3, y=y + 4,
    ))
    y += 16

    if HAS_QR:
        try:
            gc.collect()
            print("MEM before QR: {}".format(gc.mem_free()))

            qr = adafruit_miniqr.QRCode()
            qr.add_data(bytes(item.get("data", ""), "utf-8"))
            qr.make()

            matrix = qr.matrix
            qr_size = matrix.width
            scale = 120 // qr_size
            if scale < 1:
                scale = 1
            bmp_size = qr_size * scale

            qr_bitmap = displayio.Bitmap(qr_size, qr_size, 2)
            qr_palette = displayio.Palette(2)
            qr_palette[0] = COLOR_WHITE
            qr_palette[1] = COLOR_BLACK

            for qxp in range(qr_size):
                for qyp in range(qr_size):
                    qr_bitmap[qxp, qyp] = 1 if matrix[qxp, qyp] else 0

            del qr, matrix
            gc.collect()

            qr_x = (CONTENT_W - bmp_size) // 2
            bx = qr_x - 3
            by = y - 3
            bw = bmp_size + 5
            bh = bmp_size + 5
            g.append(Line(bx, by, bx + bw, by, color=COLOR_CYAN))
            g.append(Line(bx, by + bh, bx + bw, by + bh, color=COLOR_CYAN))
            g.append(Line(bx, by, bx, by + bh, color=COLOR_CYAN))
            g.append(Line(bx + bw, by, bx + bw, by + bh, color=COLOR_CYAN))

            qr_group = displayio.Group(scale=scale, x=qr_x, y=y)
            qr_group.append(displayio.TileGrid(qr_bitmap, pixel_shader=qr_palette, x=0, y=0))
            g.append(qr_group)
            y += bmp_size + 8

        except Exception as e:
            print("QR render error:", e)
            g.append(text_label.Label(font, text="QR ERROR", color=COLOR_MAGENTA, x=80, y=y + 40))
            y += 60
    else:
        g.append(text_label.Label(font, text="QR LIB MISSING", color=COLOR_MAGENTA, x=70, y=y + 40))
        y += 60

    data_str = item.get("data", "")
    if len(data_str) > 42:
        data_str = data_str[:42] + "..."
    g.append(text_label.Label(font, text=data_str, color=COLOR_MUTED, x=4, y=y + 4))
    return g


def build_checklist():
    g = displayio.Group(x=CONTENT_X, y=CONTENT_Y)
    items = checklist_data.get("items", [])
    total = len(items)
    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    start = checklist_page * ITEMS_PER_PAGE
    page_items = items[start:start + ITEMS_PER_PAGE]
    done = sum(1 for it in items if it.get("checked"))

    y = 6
    title_text = checklist_data.get("title", "CHECKLIST").upper()
    g.append(text_label.Label(font, text=title_text, color=COLOR_MAGENTA, x=6, y=y + 4))
    g.append(text_label.Label(
        font, text="{}/{}".format(done, total),
        color=COLOR_GREEN, x=CONTENT_W - 42, y=y + 4,
    ))
    y += 14
    g.append(Line(6, y, CONTENT_W - 8, y, color=COLOR_CYAN))
    y += 6

    for idx, item in enumerate(page_items):
        global_idx = start + idx
        item_h = 32
        checked = item.get("checked", False)

        if checked:
            g.append(Line(4, y, 4, y + item_h, color=COLOR_CYAN))

        bx, by2 = 12, y + 8
        g.append(Line(bx, by2, bx + 13, by2, color=COLOR_CYAN))
        g.append(Line(bx, by2 + 13, bx + 13, by2 + 13, color=COLOR_CYAN))
        g.append(Line(bx, by2, bx, by2 + 13, color=COLOR_CYAN))
        g.append(Line(bx + 13, by2, bx + 13, by2 + 13, color=COLOR_CYAN))

        if checked:
            g.append(Line(bx + 2, by2 + 2, bx + 11, by2 + 11, color=COLOR_GREEN))
            g.append(Line(bx + 11, by2 + 2, bx + 2, by2 + 11, color=COLOR_GREEN))

        text_color = COLOR_GREEN if checked else COLOR_TEXT
        g.append(text_label.Label(
            font, text=item.get("text", ""),
            color=text_color, x=32, y=y + 15,
        ))

        touch.add_zone("check_{}".format(global_idx),
                        CONTENT_X + 4, CONTENT_Y + y, CONTENT_W - 12, item_h)
        y += item_h + 2

    nav_y = CONTENT_H - 26
    g.append(Line(6, nav_y - 4, CONTENT_W - 8, nav_y - 4, color=COLOR_MUTED))

    can_prev = checklist_page > 0
    prev_c = COLOR_CYAN if can_prev else COLOR_MUTED
    g.append(text_label.Label(font, text="< PREV", color=prev_c, x=8, y=nav_y + 11))
    if can_prev:
        touch.add_zone("cl_prev", CONTENT_X + 4, CONTENT_Y + nav_y, 58, 22)

    g.append(text_label.Label(
        font, text="{}/{}".format(checklist_page + 1, total_pages),
        color=COLOR_MUTED, x=CONTENT_W // 2 - 10, y=nav_y + 11,
    ))

    can_next = checklist_page < total_pages - 1
    next_c = COLOR_CYAN if can_next else COLOR_MUTED
    g.append(text_label.Label(font, text="NEXT >", color=next_c, x=CONTENT_W - 55, y=nav_y + 11))
    if can_next:
        touch.add_zone("cl_next", CONTENT_X + CONTENT_W - 62, CONTENT_Y + nav_y, 58, 22)

    return g


def build_empty():
    g = displayio.Group(x=CONTENT_X, y=CONTENT_Y)
    g.append(text_label.Label(
        font, text="NO DATA FOUND", color=COLOR_MAGENTA,
        x=CONTENT_W // 2 - 42, y=CONTENT_H // 2 - 20,
    ))
    g.append(text_label.Label(
        font, text="Add JSON to SD card", color=COLOR_MUTED,
        x=CONTENT_W // 2 - 57, y=CONTENT_H // 2 + 5,
    ))
    return g


# ─── SWAP CONTENT ───────────────────────────────────────────

def swap_content():
    """Replace only the content group. Header and tabs stay."""
    global content_group

    if content_group is not None and content_group in root:
        root.remove(content_group)
        while len(content_group) > 0:
            content_group.pop()
    content_group = None
    gc.collect()

    clear_content_zones()

    tab_id = tabs[active_tab]["id"]
    if tab_id == "contact":
        content_group = build_contact()
    elif tab_id == "qr":
        if qr_detail_index >= 0:
            content_group = build_qr_detail(qr_detail_index)
        else:
            content_group = build_qr_list()
    elif tab_id == "checklist":
        content_group = build_checklist()
    elif tab_id == "empty":
        content_group = build_empty()

    root.append(content_group)
    display.refresh()
    print("MEM after swap: {}".format(gc.mem_free()))


# ─── TOUCH HANDLING ─────────────────────────────────────────

def handle_touch():
    global active_tab, qr_detail_index, checklist_page
    global checklist_dirty, checklist_last_change, brightness

    zone, x, y = touch.poll()
    if zone is None:
        return

    name = zone.name
    print("TOUCH -> {}  x={} y={}".format(name, x, y))

    # Brightness controls
    if name == "brightness_down" or name == "brightness_down_contact":
        brightness = max(0.1, brightness - 0.1)
        display.brightness = brightness
        print("Brightness: {:.1f}".format(brightness))
        return

    if name == "brightness_up" or name == "brightness_up_contact":
        brightness = min(1.0, brightness + 0.1)
        display.brightness = brightness
        print("Brightness: {:.1f}".format(brightness))
        return

    if name.startswith("tab_"):
        idx = int(name.split("_")[1])
        if idx != active_tab:
            active_tab = idx
            qr_detail_index = -1
            checklist_page = 0
            update_tab_visuals()
            swap_content()
        return

    if name.startswith("qr_item_"):
        idx = int(name.split("_")[2])
        qr_detail_index = idx
        swap_content()
        return

    if name == "qr_back":
        qr_detail_index = -1
        swap_content()
        return

    if name.startswith("check_"):
        idx = int(name.split("_")[1])
        items = checklist_data.get("items", [])
        if 0 <= idx < len(items):
            items[idx]["checked"] = not items[idx]["checked"]
            checklist_dirty = True
            checklist_last_change = time.monotonic()
            swap_content()
        return

    if name == "cl_prev" and checklist_page > 0:
        checklist_page -= 1
        swap_content()
        return

    if name == "cl_next":
        items = checklist_data.get("items", [])
        total_pages = max(1, (len(items) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
        if checklist_page < total_pages - 1:
            checklist_page += 1
            swap_content()
        return


# ─── BOOT ────────────────────────────────────────────────────

print("HyperCard V1 booting...")
gc.collect()
print("MEM at start: {}".format(gc.mem_free()))

splash = show_splash()
time.sleep(0.8)

load_all_data()
determine_tabs()
print("Tabs:", [t["label"] for t in tabs])

display.root_group = displayio.CIRCUITPYTHON_TERMINAL
while len(splash) > 0:
    splash.pop()
del splash
gc.collect()
print("MEM after splash freed: {}".format(gc.mem_free()))

root = displayio.Group()
root.append(Rect(0, 0, DISPLAY_W, DISPLAY_H, fill=COLOR_BG))

header_group = build_header()
root.append(header_group)

tab_group, tab_labels_ref, tab_bgs_ref, tab_inds_ref = build_tab_bar()
root.append(tab_group)

display.root_group = root
gc.collect()
print("MEM after header+tabs: {}".format(gc.mem_free()))

content_group = None
swap_content()
print("Ready.")

# ─── MAIN LOOP ──────────────────────────────────────────────

while True:
    handle_touch()
    save_checklist()
    time.sleep(0.05)
