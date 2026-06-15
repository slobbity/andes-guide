#!/usr/bin/env python3
"""
Andes Map Builder
-----------------
Reads locations.csv and injects the data into index.html.

Usage:
    python3 build.py

Edit locations.csv to add, remove, or update places.
Then run this script and refresh index.html in your browser.

CSV columns (header row, exact names):
    include, name, category, lat, lng, description,
    mon, tue, wed, thu, fri, sat, sun, hours,
    seasonal, phone, website, googleMaps, instagram

Valid categories: restaurant | cafe | bar | food | shop | outdoor | attraction | ski

HOURS — the seven day columns (mon … sun) are the source of truth.
Put that day's hours in the cell, e.g. "9am-3pm", or two blocks
"9am-3pm, 5pm-9pm", or "open" if open with no fixed time. Leave a day
blank to mean CLOSED that day. From these, the build:
  • auto-generates the display text (collapsing runs, e.g. "Thu-Sun: 9am-3pm")
  • drives the grey-out (a place is dimmed when it's closed right now)
The "hours" column is an OPTIONAL display override — leave it blank to
use the auto-generated text; fill it only when you want custom wording
(e.g. a place with two venues). Places with no day columns (towns,
trails, ski resorts) just keep free text in "hours" and are never dimmed.

The "include" column controls what appears on the map: leave it blank
or set yes / y / true / 1 to show a place; set no / n / false / 0 to
hide it without deleting the row. Any extra columns you add (e.g. a
private "note" column) are ignored by the build, so the CSV is a safe
place to keep your own working notes.

Leave a field blank to omit it (it will become null in the map).
"""

import csv
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
CSV_FILE  = HERE / "locations.csv"
HTML_FILE = HERE / "index.html"

# Markers that delimit the locations block in index.html
START_MARKER = "const locations = ["
END_MARKER   = "]; // ← End of locations array."

VALID_CATEGORIES = {"restaurant", "cafe", "bar", "food", "shop", "outdoor", "attraction", "ski"}

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_LABEL = {"mon": "Mon", "tue": "Tue", "wed": "Wed", "thu": "Thu",
             "fri": "Fri", "sat": "Sat", "sun": "Sun"}
NDASH = "–"   # – for ranges
MIDDOT = " · "  # · between blocks


def fmt_times(cell):
    """Prettify a day cell's time list: '9am-3pm, 5pm-9pm' → '9am–3pm, 5pm–9pm'."""
    parts = [p.strip().replace("-", NDASH) for p in cell.split(",")]
    return ", ".join(parts)


def rotation_start(vals):
    """Index to start the week at, so open stretches don't split across the
    Mon/Sun boundary — i.e. the day right after the longest run of closed days."""
    n = len(vals)
    blanks = [i for i, v in enumerate(vals) if not v]
    if not blanks:
        return 0
    total_blank = len(blanks)
    best_len = best_start = 0
    cur_len = cur_start = 0
    for idx in range(2 * n):
        d = idx % n
        if not vals[d]:
            if cur_len == 0:
                cur_start = d
            cur_len += 1
            if cur_len > best_len:
                best_len, best_start = cur_len, cur_start
        else:
            cur_len = 0
        if best_len == total_blank:
            break
    return (best_start + best_len) % n


def generate_hours_text(days):
    """Build a display string from the seven day cells, collapsing consecutive
    days with identical hours (e.g. 'Thu–Sun: 9am–3pm · Sun: 10am–3pm')."""
    vals = [days.get(d, "").strip() for d in DAYS]
    if not any(vals):
        return None

    nonblank = [v for v in vals if v]
    if len(nonblank) == 7 and len(set(nonblank)) == 1:
        v = nonblank[0]
        return "Open daily" if v.lower() == "open" else f"Daily: {fmt_times(v)}"

    start = rotation_start(vals)
    order = [(start + k) % 7 for k in range(7)]

    groups = []  # each: [list_of_day_indices, value]
    for d in order:
        v = vals[d]
        if not v:
            continue
        if groups and groups[-1][1] == v and (groups[-1][0][-1] + 1) % 7 == d:
            groups[-1][0].append(d)
        else:
            groups.append([[d], v])

    parts = []
    for didx, v in groups:
        if len(didx) == 1:
            label = DAY_LABEL[DAYS[didx[0]]]
        else:
            label = f"{DAY_LABEL[DAYS[didx[0]]]}{NDASH}{DAY_LABEL[DAYS[didx[-1]]]}"
        parts.append(label if v.lower() == "open" else f"{label}: {fmt_times(v)}")
    return MIDDOT.join(parts)


def load_locations():
    locations = []
    with open(CSV_FILE, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=2):  # row 1 is header
            name = row["name"].strip()
            if not name:
                continue  # skip blank rows

            # "include" column — hide a place without deleting its row.
            # Blank or yes/true/1 → shown; no/false/0 → skipped.
            include = row.get("include", "").strip().lower()
            if include in {"no", "n", "false", "0", "hide", "exclude", "off"}:
                print(f"  Skipping row {i}: '{name}' (include = '{include}')")
                continue

            category = row["category"].strip().lower()
            if category not in VALID_CATEGORIES:
                print(f"  Warning row {i}: unknown category '{category}' for '{name}' — skipping")
                continue

            try:
                lat = float(row["lat"])
                lng = float(row["lng"])
            except ValueError:
                print(f"  Warning row {i}: bad lat/lng for '{name}' — skipping")
                continue

            # Nullable string fields — empty CSV cell → null in JS
            def nullable(key):
                v = row.get(key, "").strip()
                return v if v else None

            # Driving time as integer (or null if blank)
            driving_time = None
            try:
                dt = row.get("driving_time_minutes", "").strip()
                if dt:
                    driving_time = int(dt)
            except ValueError:
                pass

            # Seven day columns → structured `days` map + display `hours`.
            day_cells = {d: row.get(d, "").strip() for d in DAYS}
            has_days = any(day_cells.values())
            override = row.get("hours", "").strip()
            if has_days:
                days_out = day_cells
                hours_out = override if override else generate_hours_text(day_cells)
            else:
                days_out = None
                hours_out = override if override else None

            locations.append({
                "name":        name,
                "category":    category,
                "lat":         lat,
                "lng":         lng,
                "description": nullable("description"),
                "days":        days_out,
                "hours":       hours_out,
                "seasonal":    nullable("seasonal"),
                "phone":       nullable("phone"),
                "website":     nullable("website"),
                "googleMaps":  nullable("googleMaps"),
                "instagram":   nullable("instagram"),
                "driving_time_minutes": driving_time,
            })

    return locations


def render_js(locations):
    """Render the locations list as a nicely formatted JS array literal."""
    lines = []
    for loc in locations:
        # json.dumps handles escaping and null → null correctly
        lines.append("      " + json.dumps(loc, ensure_ascii=False) + ",")
    return "\n".join(lines)


def inject(locations):
    html = HTML_FILE.read_text(encoding="utf-8")

    start_idx = html.find(START_MARKER)
    end_idx   = html.find(END_MARKER)

    if start_idx == -1 or end_idx == -1:
        print("ERROR: Could not find the locations block markers in index.html.")
        print("  Expected to find:")
        print(f"    {START_MARKER!r}")
        print(f"    {END_MARKER!r}")
        sys.exit(1)

    end_idx += len(END_MARKER)

    new_block = (
        START_MARKER + "\n"
        + render_js(locations) + "\n"
        + "    " + END_MARKER
    )

    new_html = html[:start_idx] + new_block + html[end_idx:]
    HTML_FILE.write_text(new_html, encoding="utf-8")


def main():
    print(f"Reading  {CSV_FILE.name} ...")
    locations = load_locations()
    print(f"  Loaded {len(locations)} location(s)")

    print(f"Writing  {HTML_FILE.name} ...")
    inject(locations)
    print("  Done — refresh index.html in your browser.")


if __name__ == "__main__":
    main()
