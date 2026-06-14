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
    include, name, category, lat, lng, description, hours,
    seasonal, phone, website, googleMaps

Valid categories: restaurant | shop | outdoor | attraction | ski

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

            locations.append({
                "name":        name,
                "category":    category,
                "lat":         lat,
                "lng":         lng,
                "description": nullable("description"),
                "hours":       nullable("hours"),
                "seasonal":    nullable("seasonal"),
                "phone":       nullable("phone"),
                "website":     nullable("website"),
                "googleMaps":  nullable("googleMaps"),
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
