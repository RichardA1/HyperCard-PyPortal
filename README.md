# HyperCard V1

A cyberpunk-styled portable card display for the Adafruit PyPortal, running CircuitPython. Display business cards, QR codes, and checklists on a 320×240 resistive touchscreen with tab-based navigation.

## Features

- **Three card types**: Business/Contact, QR Code, and Checklist
- **Dynamic tabs**: Only display tabs that have data on the SD card
- **On-device QR generation**: Create scannable QR codes from text strings
- **Checklist persistence**: Toggle items on/off; state is saved to SD card
- **Touch-optimized interface**: Large touch targets (30–42px) for resistive screens
- **Offline-first**: All data stored on SD card; boot sequence reads once and holds in memory
- **Contact photo support**: Display 80×80 BMP image on the contact card
- **Adjustable brightness**: 0.1–1.0 range, persists across reboots

## Hardware

- Adafruit PyPortal (ATSAMD51 + ESP32, 320×240 TFT, resistive touch)
- microSD card (FAT32 formatted, 4GB recommended)

## File Structure

### CIRCUITPY Drive (PyPortal internal flash)

```
CIRCUITPY/
├── code.py                    ← main application
├── pyportal_touch_map.py      ← reusable touch calibration & utilities
├── sd/                        ← empty folder (mount point, required)
└── lib/                       ← CircuitPython libraries
    ├── adafruit_touchscreen.mpy
    ├── adafruit_miniqr.mpy
    ├── adafruit_display_text/
    └── adafruit_display_shapes/
```

### SD Card (microSD, FAT32)

```
/
├── device.json          ← device name, version, brightness
├── contact.json         ← business card data (name, title, email, phone, custom fields)
├── qrcode.json          ← QR code entries (max 4 items)
├── checklist.json       ← checklist items with checked state
└── contact_photo.bmp    ← optional 80×80 BMP image for contact card
```

## Setup

1. Flash CircuitPython 9.x or 10.x onto the PyPortal
2. Copy required libraries into `CIRCUITPY/lib/` from the [Adafruit CircuitPython Bundle](https://circuitpython.org/libraries):
   - `adafruit_touchscreen.mpy`
   - `adafruit_miniqr.mpy`
   - `adafruit_display_text/` (directory)
   - `adafruit_display_shapes/` (directory)
3. Create an empty `sd/` folder on CIRCUITPY (required mount point)
4. Copy `code.py` and `pyportal_touch_map.py` to CIRCUITPY root
5. Format a microSD card as FAT32
6. Copy the JSON files from the `sd_card/` directory to the SD card root
7. Optionally: add `contact_photo.bmp` (80×80 BMP) to the SD card root
8. Edit the JSON files with your data
9. Insert SD card and power on

## JSON File Formats

### device.json

```json
{
    "name": "HyperCard",
    "version": "1.0",
    "brightness": 0.2
}
```

**Fields:**
- `name` (string): Device display name shown in header (max ~10 chars)
- `version` (string): Firmware version (informational)
- `brightness` (float): Backlight brightness 0.1–1.0 (default 0.2)

### contact.json

```json
{
    "name": "Your Name",
    "title": "Your Title",
    "email": "you@example.com",
    "phone": "+1 555-0000",
    "custom1_label": "Discord",
    "custom1_value": "yourname#1234",
    "custom2_label": "Location",
    "custom2_value": "City, ST"
}
```

**Fields:**
- `name` (string): Full name (displayed large, cyan)
- `title` (string): Job title or role
- `email`, `phone` (strings): Contact info
- `custom1_label`, `custom1_value` (strings): User-defined field 1
- `custom2_label`, `custom2_value` (strings): User-defined field 2

### qrcode.json

```json
{
    "items": [
        {"label": "Website", "data": "https://example.com"},
        {"label": "WiFi", "data": "WIFI:T:WPA;S:NetworkName;P:password;;"},
        {"label": "vCard", "data": "BEGIN:VCARD\nVERSION:3.0\nN:Last;First\nEND:VCARD"},
        {"label": "GitHub", "data": "https://github.com/yourname"}
    ]
}
```

**Fields:**
- `items` (array): Up to 4 QR code entries
  - `label` (string): Display name for the QR
  - `data` (string): Any text/URL that becomes a scannable QR code

### checklist.json

```json
{
    "title": "My Checklist",
    "items": [
        {"id": 1, "text": "First task", "checked": false},
        {"id": 2, "text": "Second task", "checked": false},
        {"id": 3, "text": "Third task", "checked": true}
    ]
}
```

**Fields:**
- `title` (string): Checklist name
- `items` (array): List of tasks
  - `id` (integer): Unique identifier
  - `text` (string): Task description
  - `checked` (boolean): Completion state (persists on SD)

## Touch Interaction

- **Tabs**: Tap the left sidebar to switch between cards
- **QR list**: Tap an entry to view its QR code; tap BACK to return
- **Checklist**: Tap an item to toggle checked/unchecked; tap PREV/NEXT to paginate
- **Brightness**: (contact card only) Use the − and + buttons at the bottom

## Architecture

**Boot sequence:**
1. Display splash screen
2. Mount SD card
3. Parse all JSON files into memory
4. Unmount SD card
5. Determine which tabs have data
6. Build persistent UI (header + tab bar)
7. Swap content based on active tab
8. Enter main loop

**Touch handling:**
- 350ms debounce between accepted taps
- Touch zones are registered during UI build
- Only content area rebuilds on tab switch; header and tabs stay in memory
- Checklist state writes back to SD with 3-second idle debounce

**Memory optimization:**
- Uses persistent display groups for header/tabs
- Only content group is rebuilt on interaction
- QR generation uses on-device `adafruit_miniqr` library
- Contact photo uses `OnDiskBitmap` for zero RAM overhead

## Customization

**Touch calibration:**
If touches register in the wrong location, adjust these values in `pyportal_touch_map.py`:

```python
TOUCH_CALIBRATION = ((6800, 59600), (22500, 54800))
```

The format is `((x_min_raw, x_max_raw), (y_min_raw, y_max_raw))`. Use the `touch_calibrator.py` utility to find values for your specific device.

**Color scheme:**
Edit the `COLOR_*` constants in `code.py` to customize the cyberpunk aesthetic.

**Display brightness on boot:**
Set `brightness` in `device.json` (range 0.1–1.0).

## Known Limitations

- Maximum 4 QR code entries
- Resistive touchscreen has ~15px inherent nonlinearity (design accounts for this with generous touch targets)
- QR generation disabled if `adafruit_miniqr` library is not installed
- Contact photo is optional; if missing, contact card renders without it
- Memory-constrained (256KB SAMD51 RAM); large JSON files may cause issues

## Future Enhancements (V2)

- MQTT/API integration for remote data updates
- WiFi sync to cloud storage
- Additional card types
- Custom fonts (BDF format)
- Bitmap backgrounds from SD card
- Sound feedback on taps

## License

MIT

## Author

Created for the CyberDeck / portable computing community.

---

**Contact:** See the `contact.json` on your HyperCard for my info, or open an issue on GitHub.
