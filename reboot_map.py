"""ReBoot Map: give old electronics a second life (single-file Streamlit app).

Run:   py -m pip install streamlit pandas
       py -m streamlit run reboot_map.py

Everything lives in this one file, in parts (search for "PART:"):
  THEMES   colours (light/dark), fonts, sizes      STORAGE  JSON files in ~/ReBoot_Map_data
  ADVISOR  repair / sell / donate / recycle logic  AUTH     sign-up, log-in, password hashing
  MARKET   listings, search, buying, contact       SEED     demo users and 20 Pune listings
  APP      the Streamlit pages
STYLE_CSS (shapes and shadows) is just below the imports.
"""
import hashlib
import hmac
import html
import json
import os
import re
import shutil
import threading
import time
from datetime import datetime

import pandas as pd
import streamlit as st

STYLE_CSS = r'''
/* ReBoot Map: neumorphism, light and dark.
   Neumorphism = one surface colour, with a dark shadow on one side and a light shadow on the other.
   "Raised" shapes look pushed out of the page, "pressed" shapes look pushed in.

   The colours are NOT written here. app.py adds a ':root { --surface: ...; }' block from themes.py
   (the light or the dark one, depending on the Dark mode switch), and every rule below uses those
   variables. To recolour the site, edit themes.py. To change shapes and shadows, edit this file. */

:root {
  --raised: 7px 7px 16px var(--shadow-dark), -7px -7px 16px var(--shadow-light);
  --raised-small: 4px 4px 10px var(--shadow-dark), -4px -4px 10px var(--shadow-light);
  --pressed: inset 4px 4px 9px var(--shadow-dark), inset -4px -4px 9px var(--shadow-light);
}

/* ----- fonts and sizes (the names and sizes are set in themes.py) ----- */
html { font-size: var(--size-base); }
.stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea, .stApp button, .stApp td, .stApp th,
[data-testid="stMarkdownContainer"] { font-family: var(--font-body); }
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .brand,
[data-testid="stMetricValue"], [data-testid="stMetricValue"] * { font-family: var(--font-heading); }
.stApp h1 { font-size: var(--size-h1); font-weight: 700; }
.stApp h2 { font-size: var(--size-h2); font-weight: 600; }
.stApp h3 { font-size: var(--size-h3); font-weight: 600; }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * { font-size: var(--size-small); }

/* ----- page and text ----- */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] { background: var(--surface); color: var(--text); color-scheme: var(--scheme); }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stHeader"] *, [data-testid="stToolbar"] * { color: var(--text); }
[data-testid="stHeader"] svg { fill: var(--text); }
.block-container { padding-top: 2.4rem; max-width: 1200px; }
.stApp p, .stApp li, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5,
[data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"] *, [data-testid="stMetric"] * { color: var(--text); }
h1, h2, h3, h4, h5 { letter-spacing: -0.01em; }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] *, [data-testid="stMetricLabel"] * { color: var(--muted); }
hr { border: none; height: 2px; background: var(--shadow-dark); box-shadow: 0 1px 0 var(--shadow-light); }

/* condition labels (Working / Minor fault / Dead) */
.badge { font-weight: 600; }
.badge.ok { color: var(--ok); }
.badge.warn { color: var(--warn); }
.badge.bad { color: var(--bad); }

/* ----- sidebar (vertical menu) ----- */
[data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child { background: var(--surface); }
[data-testid="stSidebar"] { border-right: none; box-shadow: 8px 0 22px var(--shadow-dark); }
[data-testid="stSidebar"] svg { fill: var(--text); }
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] { gap: 12px; }
[data-testid="stSidebar"] [data-testid="stRadio"] label {
  background: var(--surface); border-radius: 14px; padding: 10px 14px; width: 100%;
  box-shadow: var(--raised-small); cursor: pointer; transition: box-shadow .15s ease;
}
[data-testid="stRadio"] label p { color: inherit; }
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover { color: var(--accent); }
/* the page you are on looks pressed in */
[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) { box-shadow: var(--pressed); color: var(--accent); font-weight: 600; }

/* ----- top bar: brand + search ----- */
.st-key-topbar {
  background: var(--surface); border-radius: 22px; padding: 14px 24px; margin-bottom: 22px;
  box-shadow: var(--raised);
}
.brand { font-size: var(--size-brand); font-weight: 700; color: var(--text); white-space: nowrap; letter-spacing: -0.01em; }
.st-key-topbar [data-baseweb="input"] { border-radius: 999px !important; }
.st-key-topbar input { padding-left: 18px !important; }

/* ----- cards (item cards and the seller's listing rows) ----- */
[class*="st-key-"][class*="_card_"] {
  background: var(--surface); border-radius: 20px; padding: 18px 20px; margin-bottom: 10px;
  box-shadow: var(--raised);
}

/* ----- buttons ----- */
.stButton button, [data-testid="stFormSubmitButton"] button {
  background: var(--surface); color: var(--text); border: none; border-radius: 14px;
  box-shadow: var(--raised-small); transition: box-shadow .15s ease, color .15s ease;
}
.stButton button p, [data-testid="stFormSubmitButton"] button p { color: inherit; }
.stButton button:hover, [data-testid="stFormSubmitButton"] button:hover { color: var(--accent); }
.stButton button:active, [data-testid="stFormSubmitButton"] button:active { box-shadow: var(--pressed); }
/* primary buttons: dark gradient from the palette */
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"],
button[kind="primary"], button[kind="primaryFormSubmit"] {
  background: linear-gradient(145deg, var(--btn-a), var(--btn-b)) !important; color: var(--btn-text) !important;
}
[data-testid="stBaseButton-primary"]:hover, [data-testid="stBaseButton-primaryFormSubmit"]:hover,
button[kind="primary"]:hover, button[kind="primaryFormSubmit"]:hover { color: var(--btn-text) !important; filter: brightness(1.15); }

/* ----- inputs: plain boxes. Light theme: near-white. Dark theme: near-black. ----- */
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"], [data-baseweb="select"] > div,
[data-testid="stTextInputRootElement"], [data-testid="stNumberInputContainer"],
[data-testid="stTextArea"] > div > div, [data-testid="stSelectbox"] [data-baseweb="select"] > div {
  background: var(--field) !important; background-color: var(--field) !important;
  border: 1px solid var(--field-line) !important; border-radius: 14px !important; box-shadow: none !important;
}
[data-baseweb="input"] input, [data-baseweb="textarea"] textarea, [data-baseweb="base-input"] input,
[data-testid="stTextInputRootElement"] input, [data-testid="stNumberInputContainer"] input {
  background: transparent !important; color: var(--text) !important; -webkit-text-fill-color: var(--text);
}
[data-baseweb="input"] input::placeholder, [data-baseweb="textarea"] textarea::placeholder,
[data-testid="stTextInputRootElement"] input::placeholder { color: var(--muted); opacity: 1; -webkit-text-fill-color: var(--muted); }
[data-baseweb="select"] div, [data-baseweb="select"] span, [data-baseweb="select"] input { color: var(--text) !important; background-color: transparent; }
[data-baseweb="select"] > div { background-color: var(--field) !important; }
[data-baseweb="select"] svg, [data-testid="stNumberInputContainer"] svg { fill: var(--text); color: var(--text); }
[data-testid="stNumberInputContainer"] button { background: transparent !important; color: var(--text) !important; }
/* dropdown lists (the menu that opens under a select box) */
[data-baseweb="popover"] > div, [data-baseweb="popover"] ul, [data-baseweb="menu"] { background: var(--field) !important; }
[data-baseweb="popover"] li, [data-baseweb="popover"] li * { background: transparent; color: var(--text) !important; }
[data-baseweb="popover"] li:hover, [data-baseweb="popover"] li[aria-selected="true"] { background: var(--surface-alt) !important; }

/* ----- panels ----- */
[data-testid="stForm"] {
  border: none; border-radius: 22px; padding: 24px; background: var(--surface); box-shadow: var(--raised);
}
[data-testid="stExpander"] { border: none; border-radius: 18px; background: var(--surface); box-shadow: var(--raised); }
[data-testid="stExpander"] details { border: none; }
[data-testid="stExpander"] svg { fill: var(--text); }
[data-testid="stMetric"] { background: var(--surface); border-radius: 18px; padding: 16px 20px; box-shadow: var(--raised); }
[data-testid="stAlert"] { border-radius: 16px; box-shadow: var(--raised-small); }
[data-testid="stAlert"] *, [data-testid="stAlert"] p { color: var(--text); }
[data-testid="stDeckGlJsonChart"] { border-radius: 20px; overflow: hidden; box-shadow: var(--raised); }

/* ----- tables (st.table) ----- */
[data-testid="stTable"] { border-radius: 16px; overflow: hidden; box-shadow: var(--raised-small); }
[data-testid="stTable"] table, [data-testid="stTable"] th, [data-testid="stTable"] td {
  background: transparent; color: var(--text); border-color: var(--line);
}

/* ----- tabs (Log in / Sign up) ----- */
[data-baseweb="tab-list"] { background: var(--surface); border-radius: 16px; padding: 6px; gap: 6px; box-shadow: var(--pressed); }
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"] { display: none; }
button[data-baseweb="tab"] { border-radius: 12px; background: transparent; color: var(--text); }
button[data-baseweb="tab"] p { color: inherit; }
button[data-baseweb="tab"][aria-selected="true"] { background: var(--surface); box-shadow: var(--raised-small); color: var(--accent); font-weight: 600; }

/* ----- switch (Dark mode) ----- */
[data-testid="stToggle"] label p { color: var(--text); }

/* ----- home page banner ----- */
.st-key-hero {
  background:
    radial-gradient(circle at 88% 14%, rgba(255, 255, 255, 0.24), transparent 36%),
    radial-gradient(circle at 72% 118%, rgba(249, 115, 22, 0.26), transparent 46%),
    linear-gradient(135deg, var(--hero-a), var(--hero-b));
  border-radius: 26px; padding: 38px 40px 30px; margin-bottom: 26px; box-shadow: var(--raised);
}
.st-key-hero h1, .st-key-hero p, .st-key-hero .eyebrow { color: var(--btn-text); }
.st-key-hero h1 { max-width: 22ch; line-height: 1.15; }
.st-key-hero p { max-width: 62ch; opacity: 0.95; }
.eyebrow { font-size: var(--size-small); letter-spacing: 0.14em; font-weight: 700; opacity: 0.9; margin-bottom: 6px; }
/* orange call-to-action and a light second button, so both stand out from the banner */
.st-key-hero [data-testid="stBaseButton-primary"] { background: var(--cta) !important; color: #ffffff !important; }
.st-key-hero .stButton button:not([kind="primary"]) { background: var(--surface) !important; color: var(--text) !important; }
.st-key-hero .stButton button:not([kind="primary"]) p { color: var(--text) !important; }

/* ----- category icons: a round raised badge in the category's own colour ----- */
[class*="_cat_smartphone"] { --cat: var(--c-smartphone); }
[class*="_cat_laptop_mac"] { --cat: var(--c-laptop_mac); }
[class*="_cat_tablet_mac"] { --cat: var(--c-tablet_mac); }
[class*="_cat_tv"] { --cat: var(--c-tv); }
[class*="_cat_headphones"] { --cat: var(--c-headphones); }
[class*="_cat_cable"] { --cat: var(--c-cable); }
[class*="_cat_kitchen"] { --cat: var(--c-kitchen); }
[class*="_cat_devices_other"] { --cat: var(--c-devices_other); }
[class*="_card_"] h4 [data-testid="stIconMaterial"], [class*="_card_"] h2 [data-testid="stIconMaterial"] {
  display: inline-flex; align-items: center; justify-content: center; width: 3.4rem; height: 3.4rem;
  border-radius: 50%; font-size: 1.9rem; color: var(--cat, var(--accent)); background: var(--surface);
  box-shadow: var(--raised-small);
}
[class*="_card_"] h4, [class*="_card_"] h2 { padding-bottom: 0; }
/* category shortcut buttons on the home page */
.st-key-cat_smartphone [data-testid="stIconMaterial"] { color: var(--c-smartphone); }
.st-key-cat_laptop_mac [data-testid="stIconMaterial"] { color: var(--c-laptop_mac); }
.st-key-cat_tablet_mac [data-testid="stIconMaterial"] { color: var(--c-tablet_mac); }
.st-key-cat_tv [data-testid="stIconMaterial"] { color: var(--c-tv); }
.st-key-cat_headphones [data-testid="stIconMaterial"] { color: var(--c-headphones); }
.st-key-cat_cable [data-testid="stIconMaterial"] { color: var(--c-cable); }
.st-key-cat_kitchen [data-testid="stIconMaterial"] { color: var(--c-kitchen); }
.st-key-cat_devices_other [data-testid="stIconMaterial"] { color: var(--c-devices_other); }

/* ----- colour touches ----- */
[class*="st-key-"][class*="_card_"] h3 { color: var(--price); }
[class*="st-key-step_card_"] h4 { color: var(--accent); }
[data-testid="stMetricValue"], [data-testid="stMetricValue"] * { color: var(--accent); }
[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) { color: var(--accent); }
.badge { padding: 2px 10px; border-radius: 999px; box-shadow: var(--pressed); font-size: 0.85rem; }
'''

# ======================================================================
# PART: THEMES
# The two colour themes. Edit the hex codes here to recolour the site.
# 
# Both dictionaries must have exactly the same keys. Each key becomes a CSS variable
# (for example "surface" becomes --surface) that style.css uses everywhere.
# 
# Palette: soft blue-grey surface, electric blue and violet buttons, teal banner, orange prices,
# and one colour per product category (the keys that start with c-).
# ======================================================================
LIGHT = {
    "scheme": "light",           # tells the browser to draw its own controls in light colours
    "surface": "#e4e9f4",        # page, cards, buttons, inputs: all the same soft blue-grey
    "surface-alt": "#d6ddec",    # hover rows in dropdowns
    "field": "#f8f9fc",          # text boxes, drop-downs and the search bar (near-white)
    "field-line": "rgba(20, 27, 51, 0.14)",   # thin outline of those boxes
    "shadow-dark": "#b5bfd6",    # shadow on the bottom-right of raised shapes
    "shadow-light": "#ffffff",   # highlight on the top-left of raised shapes
    "text": "#141b33",
    "muted": "#46537a",          # captions and small labels
    "accent": "#1d4ed8",         # links, selected menu item, numbers (electric blue)
    "btn-a": "#2563eb",          # primary button gradient, start (blue)
    "btn-b": "#6d28d9",          # primary button gradient, end (violet)
    "btn-text": "#ffffff",
    "hero-a": "#1d4ed8",         # home banner gradient, start
    "hero-b": "#0e7490",         # home banner gradient, end (teal)
    "cta": "#c2410c",            # orange call-to-action button on the banner
    "price": "#b23a08",          # prices (orange)
    "line": "rgba(20, 27, 51, 0.16)",   # thin lines in tables
    "ok": "#166534",             # "Working" label
    "warn": "#92400e",           # "Minor fault" and "Major fault" labels
    "bad": "#991b1b",            # "Dead" label
    "c-smartphone": "#1d4ed8",
    "c-laptop_mac": "#6d28d9",
    "c-tablet_mac": "#0f766e",
    "c-tv": "#c2410c",
    "c-headphones": "#be185d",
    "c-cable": "#15803d",
    "c-kitchen": "#a16207",
    "c-devices_other": "#475569",
}

DARK = {
    "scheme": "dark",
    "surface": "#222a40",
    "surface-alt": "#2c3652",
    "field": "#0a0d16",          # text boxes, drop-downs and the search bar (near-black)
    "field-line": "rgba(238, 242, 255, 0.16)",
    "shadow-dark": "#151b2c",
    "shadow-light": "#2f3a58",
    "text": "#eef2ff",
    "muted": "#b9c4e4",
    "accent": "#8db4ff",
    "btn-a": "#2563eb",
    "btn-b": "#6d28d9",
    "btn-text": "#ffffff",
    "hero-a": "#1e3a8a",
    "hero-b": "#115e59",
    "cta": "#c2410c",
    "price": "#fdba74",
    "line": "rgba(238, 242, 255, 0.2)",
    "ok": "#86efac",
    "warn": "#fcd34d",
    "bad": "#fca5a5",
    "c-smartphone": "#7db1ff",
    "c-laptop_mac": "#b69cff",
    "c-tablet_mac": "#4fd8c4",
    "c-tv": "#ffa564",
    "c-headphones": "#ff8fc0",
    "c-cable": "#6ee79a",
    "c-kitchen": "#f5c451",
    "c-devices_other": "#a9b6cc",
}


# ---------- typography: the same in both themes ----------
# Fonts come from Google Fonts, so they need an internet connection. Offline, the browser
# falls back to its normal system font and nothing breaks.
# To try another font, change the name and the weights it should download
# (fonts.google.com shows which weights each font has).
FONT_HEADING = "Poppins"          # titles, the brand, big numbers
HEADING_WEIGHTS = "500;600;700"
FONT_BODY = "Nunito"              # everything else
BODY_WEIGHTS = "400;600;700"

SIZES = {
    "base": "17px",     # normal text. Most other sizes scale with this one
    "h1": "2.5rem",     # page titles ("Browse electronics")
    "h2": "1.9rem",
    "h3": "1.4rem",     # prices on the cards
    "small": "0.85rem", # captions and small labels
    "brand": "1.6rem",  # "ReBoot Map" in the top bar
}


def typography():
    """The font and size variables (--font-body, --size-h1, ...)."""
    variables = {
        "font-heading": f"'{FONT_HEADING}', system-ui, sans-serif",
        "font-body": f"'{FONT_BODY}', system-ui, sans-serif",
    }
    variables.update({f"size-{name}": value for name, value in SIZES.items()})
    return variables


def variable_names():
    """Every CSS variable that css_variables() creates."""
    return set(LIGHT) | set(typography())


def font_import():
    """The @import line that loads the two fonts. It must be the very first CSS rule."""
    def family(name, weights):
        return f"family={name.replace(' ', '+')}:wght@{weights}"
    return ("@import url('https://fonts.googleapis.com/css2?"
            f"{family(FONT_HEADING, HEADING_WEIGHTS)}&{family(FONT_BODY, BODY_WEIGHTS)}&display=swap');")


def css_variables(dark):
    """Return the ':root { --surface: ...; }' block (colours and typography) for the chosen theme."""
    variables = dict(DARK if dark else LIGHT)
    variables.update(typography())
    lines = "\n".join(f"  --{name}: {value};" for name, value in variables.items())
    return f":root {{\n{lines}\n}}"


# ======================================================================
# PART: STORAGE
# File storage: every table (users, items, orders, centers) is one JSON file.
# 
# Python concepts used here: file handling (open / json), functions,
# exception handling (try / except), a lock so two writes never collide,
# and retrying when Windows briefly locks a file.
# 
# ======================================================================


def default_dir():
    """The normal data folder: ReBoot_Map_data inside the user's home folder."""
    return os.path.join(os.path.expanduser("~"), "ReBoot_Map_data")


DATA_DIR = os.environ.get("REBOOT_DATA_DIR") or default_dir()
_lock = threading.Lock()

print(f"[ReBoot Map] Saving data in: {DATA_DIR}", flush=True)


def data_dir():
    return DATA_DIR


def _path(table):
    return os.path.join(DATA_DIR, f"{table}.json")


def load(table):
    """Return the list of records (dictionaries) stored for a table."""
    path = _path(table)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        # The file is damaged. Keep a copy so nothing is lost for good, then start the table empty.
        try:
            shutil.copy2(path, f"{path}.broken-{datetime.now():%Y%m%d-%H%M%S}")
        except OSError:
            pass
        return []


def save(table, records):
    """Write the records to disk. A temp file + replace avoids half-written data."""
    os.makedirs(DATA_DIR, exist_ok=True)
    path = _path(table)
    tmp = path + ".tmp"
    with _lock:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())          # make sure the bytes really reach the disk
        for attempt in range(6):          # Windows can lock a file for a moment (antivirus, sync)
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if attempt == 5:
                    raise
                time.sleep(0.2)


def next_id(records):
    """Next free numeric id for a list of records."""
    return max((r["id"] for r in records), default=0) + 1


def find(records, record_id):
    """Return the record with this id, or None."""
    for record in records:
        if record["id"] == record_id:
            return record
    return None


# ======================================================================
# PART: ADVISOR
# Decision-support logic: what should happen to an unused electronic item?
# 
# Python concepts used here: dictionaries, functions, if-elif-else decision
# trees, arithmetic and string formatting.
# ======================================================================
CONDITIONS = ["Working", "Minor fault", "Major fault", "Dead"]

# One dictionary per category. The numbers are rough, illustrative estimates
# (typical weight, typical manufacturing CO2 and expected lifespan).
CATEGORIES = {
    "Smartphone":     {"weight_kg": 0.2, "co2_kg": 70,  "lifespan": 4,  "valuable": True},
    "Laptop":         {"weight_kg": 2.0, "co2_kg": 250, "lifespan": 6,  "valuable": True},
    "Tablet":         {"weight_kg": 0.5, "co2_kg": 100, "lifespan": 5,  "valuable": True},
    "Television":     {"weight_kg": 10,  "co2_kg": 350, "lifespan": 8,  "valuable": False},
    "Earphones":      {"weight_kg": 0.05, "co2_kg": 10, "lifespan": 3,  "valuable": False},
    "Charger/Cable":  {"weight_kg": 0.1, "co2_kg": 5,   "lifespan": 3,  "valuable": False},
    "Home appliance": {"weight_kg": 8,   "co2_kg": 200, "lifespan": 10, "valuable": False},
    "Other":          {"weight_kg": 1,   "co2_kg": 40,  "lifespan": 5,  "valuable": False},
}


def repair_vs_replace(category, age_years, repair_cost, new_price):
    """Compare the cost per year of repairing against buying new."""
    info = CATEGORIES.get(category, CATEGORIES["Other"])
    lifespan = info["lifespan"]
    years_left = max(1, lifespan - age_years)          # extra life a repair buys
    repair_per_year = repair_cost / years_left
    new_per_year = new_price / lifespan
    return {
        "years_left": years_left,
        "lifespan": lifespan,
        "repair_per_year": round(repair_per_year),
        "new_per_year": round(new_per_year),
        "saving_now": round(new_price - repair_cost),
        "winner": "Repair" if repair_per_year < new_per_year else "Replace",
    }


def recommend(category, condition, age_years, repair_cost, new_price):
    """Decision tree built with if / elif / else. Returns a dictionary."""
    info = CATEGORIES.get(category, CATEGORIES["Other"])
    ratio = repair_cost / new_price if new_price else 1

    if condition == "Working":
        if age_years <= 6:
            action, tone = "Sell it", "good"
            reason = "It works and is still fairly young, so a buyer will pay for it."
            steps = ["Factory reset and remove your accounts.",
                     "Take clear photos and list it on ReBoot Map.",
                     "Price it at roughly 30-50% of the new price."]
        else:
            action, tone = "Donate it", "good"
            reason = "It works but is old, so resale value is low. Someone can still use it."
            steps = ["Factory reset the device.",
                     "Donate to a school, NGO or neighbour.",
                     "Keep the charger and cable with it."]

    elif condition in ("Minor fault", "Major fault"):
        if ratio <= 0.35:
            action, tone = "Repair it", "good"
            reason = f"Repair costs only {ratio:.0%} of a new one, so fixing is clearly cheaper."
            steps = ["Get a written quote from a local repair shop.",
                     "Ask for a warranty on the repair.",
                     "Use or sell it after the repair."]
        elif ratio <= 0.6:
            if age_years <= 4:
                action, tone = "Repair it", "good"
                reason = (f"Repair costs {ratio:.0%} of a new one, but the device is only "
                          f"{age_years} years old, so a repair still pays off.")
                steps = ["Compare two repair quotes.",
                         "Repair only if the quote stays under 60% of the new price."]
            else:
                action, tone = "Sell it as repairable", "warn"
                reason = (f"Repair costs {ratio:.0%} of a new one and the device is "
                          f"{age_years} years old. Let a buyer who likes fixing take it.")
                steps = ["List it on ReBoot Map with the condition 'Repairable'.",
                         "Describe the fault honestly.",
                         "Price it low."]
        else:
            if info["valuable"]:
                action, tone = "Sell for parts", "warn"
                reason = (f"Repair costs {ratio:.0%} of a new one, which is too much. "
                          "Its parts are still valuable.")
                steps = ["List it for parts on ReBoot Map.",
                         "Or hand it to a refurbisher."]
            else:
                action, tone = "Recycle it", "bad"
                reason = f"Repair costs {ratio:.0%} of a new one and the parts have little resale value."
                steps = ["Take it to an authorised e-waste collection point.",
                         "Never throw it in household waste."]

    else:  # Dead
        if info["valuable"]:
            action, tone = "Sell for parts", "warn"
            reason = "It no longer works, but the board, screen and battery have value."
            steps = ["Wipe or remove the storage first.",
                     "List it for parts or give it to a refurbisher."]
        else:
            action, tone = "Recycle it", "bad"
            reason = "It is dead and has little resale value, so recycling is the responsible step."
            steps = ["Take it to an authorised e-waste collection point.",
                     "Remove batteries and keep them separate."]

    return {"action": action, "tone": tone, "reason": reason, "steps": steps,
            "compare": repair_vs_replace(category, age_years, repair_cost, new_price)}


def impact_of(category):
    """Estimated e-waste kept out of landfill and CO2 saved when one item is reused."""
    info = CATEGORIES.get(category, CATEGORIES["Other"])
    return info["weight_kg"], info["co2_kg"]


def total_impact(items):
    """Add up the impact of every sold item."""
    waste = co2 = 0
    for item in items:
        if item["status"] == "sold":
            w, c = impact_of(item["category"])
            waste += w
            co2 += c
    return {"waste_kg": round(waste, 1), "co2_kg": round(co2)}


# ======================================================================
# PART: AUTH
# Accounts: sign-up, log-in and password hashing (no Streamlit code in here).
# 
# Python concepts used here: functions that return (result, error), hashing with
# hashlib, constant-time comparison, string cleaning and list searching.
# Passwords are never stored. Only a random salt plus a PBKDF2 hash is saved.
# ======================================================================


ROUNDS = 200_000


def hash_password(password):
    """Return 'salt$hash' (both as hex text) for the given password."""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ROUNDS)
    return f"{salt.hex()}${digest.hex()}"


def check_password(password, stored):
    """True if the password matches a value made by hash_password()."""
    try:
        salt_hex, digest_hex = stored.split("$")
        salt, expected = bytes.fromhex(salt_hex), bytes.fromhex(digest_hex)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ROUNDS)
    return hmac.compare_digest(digest, expected)


def clean_phone(phone):
    """Return the phone number tidied up, or None if it does not look like a phone number.

    Accepts digits with optional +, spaces, dashes and brackets, with 10 to 13 digits in total.
    """
    phone = " ".join(str(phone).split())
    digits = [c for c in phone if c.isdigit()]
    if phone and all(c.isdigit() or c in "+- ()" for c in phone) and 10 <= len(digits) <= 13:
        return phone
    return None


ADMIN_CODE = os.environ.get("REBOOT_ADMIN_CODE", "reboot-admin")   # needed to sign up as an admin


def register_user(name, email, password, role, city="", phone="", address="", area="", admin_code=""):
    """Create an account. Returns (user, error). Exactly one of them is None.

    role is "buyer", "seller" or "admin". Admins must also give the secret admin access code.
    The phone number and address of buyers and sellers are only shown to the other person
    in a deal AFTER a purchase, so they can arrange the pickup.
    """
    name, email, city = name.strip(), email.strip().lower(), city.strip()
    area, address = area.strip(), address.strip()

    if len(name) < 2:
        return None, "Enter your full name."
    if "@" not in email or "." not in email.split("@")[-1]:
        return None, "Enter a valid email address."
    if len(password) < 6:
        return None, "Password needs at least 6 characters."
    if role not in ("buyer", "seller", "admin"):
        return None, "Choose a valid account type."

    tidy_phone = ""
    if role == "admin":
        if not hmac.compare_digest(admin_code.encode("utf-8"), ADMIN_CODE.encode("utf-8")):
            return None, "Wrong admin access code."
    else:
        tidy_phone = clean_phone(phone)
        if not city:
            return None, "Enter your city."
        if tidy_phone is None:
            return None, "Enter a valid phone number (10 digits). It is shared only after a purchase."
        if role == "seller" and len(address) < 8:
            return None, "Sellers must enter a pickup address (it is shared with the buyer after a purchase)."

    users = load("users")
    if any(u["email"] == email and u["role"] == role for u in users):
        return None, f"A {role} account with this email already exists. Log in instead."
    user = {"id": next_id(users), "name": name, "email": email, "role": role,
            "city": city, "area": area, "phone": tidy_phone, "address": address,
            "blocked": False, "password": hash_password(password)}
    users.append(user)
    save("users", users)
    return user, None


def authenticate(email, password, role=None):
    """Return the user dictionary if the email and password are right, else None.

    The same email may own one buyer, one seller and one admin account, so the login tab
    passes the role it is for. With role=None any account type matches."""
    email = email.strip().lower()
    for user in load("users"):
        if user["email"] == email and (role is None or user["role"] == role) \
                and check_password(password, user["password"]):
            return user
    return None


def ensure_admin():
    """Make sure at least one admin account exists (older data folders have none)."""
    users = load("users")
    if not users or any(u.get("role") == "admin" for u in users):
        return
    users.append({"id": next_id(users), "name": "Site Admin", "email": "admin@demo.com", "role": "admin",
                  "city": "Pune", "area": "Camp", "phone": "+91 90000 00007",
                  "address": "ReBoot Map Office, Camp, Pune 411001", "blocked": False,
                  "password": hash_password("demo123")})
    save("users", users)


# ======================================================================
# PART: MARKET
# Buying and selling rules: validation, search/filter and purchase.
# 
# Python concepts used here: dictionaries, list comprehensions, sorting with
# lambda, functions that return (result, errors), and file storage.
# ======================================================================


SORT_KEYS = {
    "new": lambda i: -i["id"],
    "low": lambda i: i["price"],
    "high": lambda i: -i["price"],
}


def validate_listing(form):
    """Check the seller's form. Returns (clean_dict, list_of_errors)."""
    errors = []
    name = form.get("name", "").strip()
    category = form.get("category", "")
    condition = form.get("condition", "")
    city = form.get("city", "").strip()
    area = form.get("area", "").strip()[:40]
    description = form.get("description", "").strip()

    if len(name) < 3:
        errors.append("Product name must be at least 3 characters.")
    if category not in CATEGORIES:
        errors.append("Choose a category.")
    if condition not in CONDITIONS:
        errors.append("Choose the condition.")
    if not city:
        errors.append("Enter your city.")
    try:
        price = int(float(form.get("price", "")))
        if price <= 0:
            raise ValueError
    except ValueError:
        price = 0
        errors.append("Price must be a number greater than zero.")

    clean = {"name": name, "category": category, "condition": condition,
             "city": city, "area": area, "description": description[:300], "price": price}
    return clean, errors


def create_item(seller_id, clean):
    items = load("items")
    item = dict(clean, id=next_id(items), seller_id=seller_id,
                status="available", buyer_id=None,
                created=datetime.now().strftime("%Y-%m-%d"))
    items.append(item)
    save("items", items)
    return item


def search_items(items, q="", category="", condition="", max_price=0, city="", sort="new", area=""):
    """Filter available items, then sort them.

    The search words are matched against the name, description, category and area,
    so searching "laptop" finds every laptop and "baner" finds everything in Baner.
    """
    q, city, area = q.lower().strip(), city.lower().strip(), area.lower().strip()

    def matches_text(i):
        text = " ".join([i["name"], i["description"], i["category"], i.get("area", "")]).lower()
        return q in text

    result = [
        i for i in items
        if i["status"] == "available"
        and (not q or matches_text(i))
        and (not category or i["category"] == category)
        and (not condition or i["condition"] == condition)
        and (not city or city in i["city"].lower())
        and (not area or area == i.get("area", "").lower())
        and (not max_price or i["price"] <= max_price)
    ]
    return sorted(result, key=SORT_KEYS.get(sort, SORT_KEYS["new"]))


def buy_item(item_id, buyer_id):
    """Mark an item as sold and record the order. Returns (order, error)."""
    items = load("items")
    item = find(items, item_id)
    if item is None:
        return None, "That item does not exist."
    if item["status"] != "available":
        return None, "Sorry, this item has already been sold."
    if item["seller_id"] == buyer_id:
        return None, "You cannot buy your own item."

    item["status"], item["buyer_id"] = "sold", buyer_id
    save("items", items)

    orders = load("orders")
    order = {"id": next_id(orders), "item_id": item_id, "buyer_id": buyer_id,
             "price": item["price"], "date": datetime.now().strftime("%Y-%m-%d")}
    orders.append(order)
    save("orders", orders)
    return order, None


def delete_item(item_id, seller_id):
    """A seller may remove only their own unsold listing."""
    items = load("items")
    item = find(items, item_id)
    if item and item["seller_id"] == seller_id and item["status"] == "available":
        items.remove(item)
        save("items", items)
        return True
    return False


def contact_details(user):
    """What the other person in a deal may see AFTER a purchase: name, phone, email, address.

    Accounts made before phone numbers existed simply show "Not provided".
    """
    if user is None:
        return None
    return {
        "name": user["name"],
        "phone": user.get("phone") or "Not provided",
        "email": user.get("email") or "Not provided",
        "address": user.get("address") or ", ".join(p for p in (user.get("area"), user.get("city")) if p) or "Not provided",
    }


def admin_remove_item(item_id):
    """Admin: remove a listing that has not been sold yet. Returns True if it was removed."""
    items = load("items")
    item = find(items, item_id)
    if item and item["status"] == "available":
        items.remove(item)
        save("items", items)
        return True
    return False


def set_blocked(user_id, blocked):
    """Admin: block or unblock a buyer or seller. Admin accounts cannot be blocked. Returns True if changed."""
    users = load("users")
    user = find(users, user_id)
    if user is None or user["role"] == "admin":
        return False
    user["blocked"] = bool(blocked)
    save("users", users)
    return True


# ======================================================================
# PART: SEED
# Creates demo data the first time the app runs, so the site is never empty.
# 
# Everything here is made up: the names, phone numbers (+91 90000 000xx) and addresses are
# fictional, only the Pune area names are real. Replace them with your own demo data if you like.
# ======================================================================
# name, email, role, city, area, phone, address   (every password is demo123)
USERS = [
    ("Demo Seller", "seller@demo.com", "seller", "Pune", "Baner", "+91 90000 00001",
     "Flat 4B, Sunrise Apartments, Baner Road, Pune 411045"),
    ("Demo Buyer", "buyer@demo.com", "buyer", "Pune", "Kothrud", "+91 90000 00002",
     "12, Lotus Residency, Kothrud, Pune 411038"),
    ("Aarav Kulkarni", "seller2@demo.com", "seller", "Pune", "Kothrud", "+91 90000 00003",
     "Shop 6, Ganesh Plaza, Karve Road, Kothrud, Pune 411038"),
    ("Meera Deshmukh", "seller3@demo.com", "seller", "Pune", "Viman Nagar", "+91 90000 00004",
     "B-203, Green Park Society, Viman Nagar, Pune 411014"),
    ("Rohan Patil", "buyer2@demo.com", "buyer", "Pune", "Hinjewadi", "+91 90000 00005",
     "Wing C, Skyline Heights, Hinjewadi Phase 1, Pune 411057"),
    ("Sneha Joshi", "buyer3@demo.com", "buyer", "Pune", "Aundh", "+91 90000 00006",
     "7, Orchid Villa, Aundh, Pune 411007"),
]

# name, category, condition, price (Rs.), seller email, description, date listed
ITEMS = [
    ("Redmi Note 8 (cracked screen)", "Smartphone", "Minor fault", 2500, "seller@demo.com",
     "Touch works, screen glass cracked. Battery holds a full day.", "2026-10-20"),
    ("Dell Inspiron 15", "Laptop", "Working", 14500, "seller@demo.com",
     "8 GB RAM, 256 GB SSD. Used for college work, charger included.", "2026-10-20"),
    ("boAt Rockerz Headphones", "Earphones", "Working", 600, "seller@demo.com",
     "Left ear louder than right. Everything else is fine.", "2026-10-21"),
    ("Samsung 32-inch LED TV", "Television", "Major fault", 3000, "seller@demo.com",
     "Panel is fine, power board is faulty. Good for a repair hobbyist. Pickup only.", "2026-10-21"),
    ("iPad 6th Gen", "Tablet", "Working", 11000, "seller@demo.com",
     "32 GB, small scratch on the back. Original charger.", "2026-10-22"),
    ("HP Laptop (no display)", "Laptop", "Dead", 1800, "seller@demo.com",
     "Does not start. Good for parts: RAM, keyboard and battery.", "2026-10-22"),
    ("Mixed chargers (5 pieces)", "Charger/Cable", "Working", 300, "seller@demo.com",
     "Type-C and micro-USB chargers, all tested.", "2026-10-23"),
    ("Mi Mixer Grinder", "Home appliance", "Minor fault", 900, "seller@demo.com",
     "One jar lid does not lock. Motor runs well.", "2026-10-23"),
    ("OnePlus 9R (8 GB / 128 GB)", "Smartphone", "Working", 17500, "seller@demo.com",
     "Carbon black, battery health good. Original box and 65W charger included. Light scuffs on the frame.", "2026-10-26"),
    ("Samsung Galaxy M31 (6 GB / 128 GB)", "Smartphone", "Working", 8500, "seller@demo.com",
     "No scratches on the screen. Comes with a case, charger and cable.", "2026-10-27"),
    ("Lenovo ThinkPad T480", "Laptop", "Working", 22500, "seller2@demo.com",
     "Core i5 8th gen, 16 GB RAM, 512 GB SSD. Solid keyboard, ideal for coding. Battery lasts around 3 hours.", "2026-10-28"),
    ("HP Pavilion 14 (weak battery)", "Laptop", "Minor fault", 16000, "seller2@demo.com",
     "Core i5, 8 GB RAM, 512 GB SSD. Battery drains in about 30 minutes, runs fine on the charger.", "2026-10-29"),
    ("Samsung Galaxy Tab A7", "Tablet", "Working", 9500, "seller2@demo.com",
     "10.4-inch, 3 GB RAM, 32 GB storage. Screen guard fitted, charger included.", "2026-10-30"),
    ("LG 43-inch 4K Smart TV", "Television", "Working", 21000, "seller2@demo.com",
     "2021 model with remote and wall mount. Works perfectly. Pickup only, no delivery.", "2026-10-31"),
    ("Anker 65W USB-C Charger", "Charger/Cable", "Working", 1800, "seller2@demo.com",
     "Compact GaN charger that powers laptops and phones. Cable included.", "2026-11-02"),
    ("iPhone 11 (64 GB, Face ID faulty)", "Smartphone", "Minor fault", 19000, "seller3@demo.com",
     "Face ID is not working, everything else works. Battery health about 82%. Box included.", "2026-11-04"),
    ("Sony WH-CH510 Wireless Headphones", "Earphones", "Working", 1800, "seller3@demo.com",
     "Around 35 hours of battery. Ear cushions in good shape. Carry pouch included.", "2026-11-06"),
    ("Realme Buds Air (right bud not charging)", "Earphones", "Major fault", 500, "seller3@demo.com",
     "Left bud and case work. Right bud does not charge. Good for spares.", "2026-11-08"),
    ("Philips Air Fryer HD9200", "Home appliance", "Working", 2500, "seller3@demo.com",
     "Used a handful of times, basket in good shape. Original manual included.", "2026-11-10"),
    ("Canon EOS 1500D with 18-55 mm lens", "Other", "Working", 19500, "seller3@demo.com",
     "About 8,000 shutter count. Includes battery, charger, strap and a camera bag.", "2026-11-12"),
]

CENTERS = [
    ("Kothrud E-Waste Collection Point (sample)", "Pune", "Kothrud", 18.5074, 73.8077, "Phones, laptops, chargers"),
    ("Hinjewadi Recycling Hub (sample)", "Pune", "Hinjewadi", 18.5913, 73.7389, "All electronics"),
    ("Shivajinagar Drop-off (sample)", "Pune", "Shivajinagar", 18.5308, 73.8474, "Small electronics, batteries"),
    ("Hadapsar Collection Centre (sample)", "Pune", "Hadapsar", 18.5089, 73.9260, "Appliances, TVs"),
    ("Pimpri Repair & Recycle (sample)", "Pune", "Pimpri", 18.6279, 73.8009, "Phones, laptops, repair help"),
    ("Katraj Battery Drop-off (sample)", "Pune", "Katraj", 18.4575, 73.8677, "Batteries, chargers, cables"),
]


def seed_if_empty():
    """Fill the data folder with demo users, items and centres, but only when there are no users yet."""
    if load("users"):
        return
    users = []
    for i, (name, email, role, city, area, phone, address) in enumerate(USERS, start=1):
        users.append({"id": i, "name": name, "email": email, "role": role, "city": city, "area": area,
                      "phone": phone, "address": address, "password": hash_password("demo123")})
    save("users", users)
    by_email = {u["email"]: u for u in users}

    items = []
    for i, (name, cat, cond, price, seller_email, desc, created) in enumerate(ITEMS, start=1):
        seller = by_email[seller_email]
        items.append({"id": i, "seller_id": seller["id"], "name": name, "category": cat, "condition": cond,
                      "price": price, "city": seller["city"], "area": seller["area"], "description": desc,
                      "status": "available", "buyer_id": None, "created": created})
    save("items", items)
    save("orders", [])
    save("centers", [
        {"id": i, "name": n, "city": c, "area": a, "lat": la, "lon": lo, "accepts": acc}
        for i, (n, c, a, la, lo, acc) in enumerate(CENTERS, start=1)])


# ======================================================================
# PART: APP
# ReBoot Map - Streamlit app: a pre-owned electronics marketplace for Pune.
# 
# Run it with:   py -m streamlit run reboot_map.py
# 
# This file is only the screen. The real rules live in modules that know nothing
# about Streamlit, so they could be reused by any other front end:
# ======================================================================



# This must be the first Streamlit command in the script.
st.set_page_config(page_title="ReBoot Map", page_icon="♻️", layout="wide")

seed_if_empty()
ensure_admin()

SORTS = {"Newest": "new", "Price: low to high": "low", "Price: high to low": "high"}
BADGE_CLASSES = {"Working": "ok", "Minor fault": "warn", "Major fault": "warn", "Dead": "bad"}
# Material icon names (they are drawn by Streamlit itself, so no internet is needed for them)
CATEGORY_ICONS = {"Smartphone": "smartphone", "Laptop": "laptop_mac", "Tablet": "tablet_mac",
                  "Television": "tv", "Earphones": "headphones", "Charger/Cable": "cable",
                  "Home appliance": "kitchen", "Other": "devices_other"}
ALL_AREAS, ANY_CONDITION, ALL_CATEGORIES = "All areas", "Any", "All"


# ---------- small helpers ----------
def money(amount):
    return f"₹{int(amount):,}"


def esc(text):
    """Make user-typed text safe to place inside HTML."""
    return html.escape(str(text))


def md(text):
    """Make user-typed text safe to place inside Markdown (no surprise links, bold or icons)."""
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|<>~$:])", r"\\\1", str(text))


def icon(category):
    return f":material/{CATEGORY_ICONS.get(category, 'devices_other')}:"


def place(item):
    """'Baner, Pune' (or just 'Pune' when the listing has no area)."""
    return ", ".join(part for part in (item.get("area"), item.get("city")) if part)


def badge(condition):
    """Coloured condition label as HTML. Use it only inside st.markdown(..., unsafe_allow_html=True)."""
    return f'<span class="badge {BADGE_CLASSES.get(condition, "ok")}">{esc(condition)}</span>'


def show_table(frame):
    """Show a DataFrame as an HTML table (so style.css can colour it) without the 0, 1, 2 index column."""
    frame = frame.copy()
    frame.index = [""] * len(frame)
    st.table(frame)


def is_dark():
    return bool(st.session_state.get("dark_mode"))


def load_css():
    """Inject the colours of the chosen theme (py) plus the shapes and shadows (style.css)."""
    css = STYLE_CSS
    css = "\n".join(line for line in css.splitlines() if line.strip())
    st.markdown(f"<style>\n{font_import()}\n{css_variables(is_dark())}\n{css}\n</style>",
                unsafe_allow_html=True)


def save_theme():
    """Runs when the Dark mode switch is flipped. Remembers the choice in the page address (?theme=dark)."""
    st.query_params["theme"] = "dark" if is_dark() else "light"


def current_user():
    """Return the logged-in user dictionary, or None."""
    user_id = st.session_state.get("user_id")
    user = find(load("users"), user_id) if user_id else None
    return None if user and user.get("blocked") else user


def flash(message, kind="success"):
    """Queue a message (kind: success, info, warning, error) to show on the next run."""
    st.session_state.setdefault("flash", []).append((kind, message))


def show_flash():
    messages = st.session_state.get("flash", [])
    st.session_state["flash"] = []
    for kind, message in messages:
        getattr(st, kind)(message)


def contact_block(title, user):
    """Name, phone, email and address of the other person in a deal (only shown after a purchase)."""
    c = contact_details(user)
    st.markdown(f"**{title}**  \n{md(c['name'])}  \n:material/call: {md(c['phone'])}  \n"
                f":material/mail: {md(c['email'])}  \n:material/location_on: {md(c['address'])}")


# ---------- callbacks: they run when a button is pressed, before the page redraws ----------
def go_to(page):
    st.session_state["nav"] = page


def view_item(item_id):
    st.session_state["open_item"] = item_id
    go_to("Browse")


def close_item():
    st.session_state["open_item"] = None


def show_category(category):
    """Category shortcut on the home page: open Browse with that category selected."""
    st.session_state["browse_category"] = category
    close_item()
    go_to("Browse")


def reset_filters():
    s = st.session_state
    s["browse_q"], s["browse_category"], s["browse_condition"] = "", ALL_CATEGORIES, ANY_CONDITION
    s["browse_area"], s["browse_price"], s["browse_sort"] = ALL_AREAS, 0, "Newest"


def do_search():
    """Runs when Enter is pressed in the top search bar: show the results on Browse."""
    close_item()
    go_to("Browse")


def do_login(role):
    """Log in from the Buyer, Seller or Admin tab. The account type must match the tab."""
    s = st.session_state
    email, password = s.get(f"{role}_login_email", ""), s.get(f"{role}_login_password", "")
    user = authenticate(email, password, role)
    if user is None:
        other = authenticate(email, password)
        if other is not None:
            flash(f"This email has a {other['role']} account, not a {role} account. "
                  f"Use the {other['role'].title()} tab, or sign up here.", "error")
        else:
            flash("Wrong email or password.", "error")
    elif user.get("blocked"):
        flash("This account has been blocked by the admin.", "error")
    elif user["role"] != role:
        flash(f"This is a {user['role']} account. Please use the {user['role'].title()} tab.", "error")
    else:
        s["user_id"] = user["id"]
        flash(f"Welcome back, {user['name']}!")
        go_to("My Dashboard")


def do_register(role):
    s = st.session_state
    p = f"{role}_reg_"
    user, error = register_user(
        s.get(p + "name", ""), s.get(p + "email", ""), s.get(p + "password", ""), role,
        s.get(p + "city", ""), s.get(p + "phone", ""), s.get(p + "address", ""), s.get(p + "area", ""),
        s.get(p + "code", ""))
    if error:
        flash(error, "error")
        return
    s["user_id"] = user["id"]
    flash(f"Welcome to ReBoot Map, {user['name']}!")
    go_to("My Dashboard")


def do_logout():
    st.session_state["user_id"] = None
    st.session_state["open_item"] = None
    st.session_state["last_order"] = None
    flash("You have been logged out.")
    go_to("Home")


def do_sell(seller_id):
    s = st.session_state
    form = {"name": s["sell_name"], "category": s["sell_category"], "condition": s["sell_condition"],
            "price": s["sell_price"], "city": s["sell_city"], "area": s["sell_area"],
            "description": s["sell_desc"]}
    clean, errors = validate_listing(form)
    if errors:
        for error in errors:
            flash(error, "error")
        return
    item = create_item(seller_id, clean)
    flash("Your item has been listed and saved.")
    view_item(item["id"])


def do_buy(item_id, buyer_id):
    order, error = buy_item(item_id, buyer_id)
    if error:
        flash(error, "error")
        return
    st.session_state["last_order"] = order["id"]
    flash("Order placed! The seller's contact details are shown below.")
    close_item()
    go_to("My Dashboard")


def do_delete(item_id, seller_id):
    if delete_item(item_id, seller_id):
        flash("Listing removed.")
    else:
        flash("You can only remove your own unsold listings.", "error")


def _admin_only():
    user = current_user()
    return user if user and user["role"] == "admin" else None


def do_admin_remove():
    if _admin_only() is None:
        flash("Admins only.", "error")
        return
    item_id = st.session_state.get("admin_remove_pick")
    flash("Listing removed." if admin_remove_item(item_id) else "That listing could not be removed.",
          "success" if item_id else "error")


def do_admin_block(blocked):
    if _admin_only() is None:
        flash("Admins only.", "error")
        return
    user_id = st.session_state.get("admin_user_pick")
    if set_blocked(user_id, blocked):
        flash("Account blocked." if blocked else "Account unblocked.")
    else:
        flash("That account cannot be changed.", "error")


# ---------- reusable piece: a grid of item cards ----------
def show_items(items, prefix):
    if not items:
        st.info("Nothing matches. Try fewer filters.")
        return
    for start in range(0, len(items), 3):
        columns = st.columns(3)
        for column, item in zip(columns, items[start:start + 3]):
            with column.container(key=f"{prefix}_card_{item['id']}_cat_{CATEGORY_ICONS.get(item['category'], 'devices_other')}"):
                st.markdown(f"#### {icon(item['category'])}")
                st.caption(item["category"])
                st.markdown(f"**{md(item['name'])}**")
                st.markdown(f"### {money(item['price'])}")
                st.markdown(f"{badge(item['condition'])} · {esc(place(item))}", unsafe_allow_html=True)
                st.button("View details", key=f"{prefix}_view_{item['id']}",
                          on_click=view_item, args=(item["id"],))


# ---------- pages ----------
def page_home():
    items = load("items")
    available = search_items(items)
    impact = total_impact(items)

    with st.container(key="hero"):
        st.markdown('<div class="eyebrow">PRE-OWNED ELECTRONICS · PUNE</div>', unsafe_allow_html=True)
        st.title("Good electronics deserve a second life")
        st.write("Buy tested pre-owned phones, laptops and appliances from sellers across Pune, "
                 "or find out whether your own old device is worth repairing, selling or recycling.")
        a, b, _ = st.columns([1, 1, 2])
        a.button("Browse electronics", type="primary", on_click=go_to, args=("Browse",))
        b.button("Repair or replace?", on_click=go_to, args=("Repair or Replace?",))

    st.markdown("### Shop by category")
    counts = {c: sum(1 for i in available if i["category"] == c) for c in CATEGORIES}
    names = list(CATEGORIES)
    for start in range(0, len(names), 4):
        for column, name in zip(st.columns(4), names[start:start + 4]):
            column.button(f"{name} ({counts[name]})", key=f"cat_{CATEGORY_ICONS[name]}", icon=icon(name),
                          on_click=show_category, args=(name,))

    st.markdown("### Latest listings")
    show_items(available[:6], "home")
    st.button("View all listings", on_click=go_to, args=("Browse",))

    st.markdown("### How ReBoot Map works")
    for column, (number, title, text) in zip(st.columns(3), [
            ("1", "List", "Sellers add a device with an honest condition label and a fair price."),
            ("2", "Connect", "Buyers browse and buy. After a purchase, buyer and seller see each other's contact details."),
            ("3", "Reuse", "The device gets a second life and the site tracks the e-waste and CO₂ it kept out of landfill.")]):
        with column.container(key=f"step_card_{number}"):
            st.markdown(f"#### {number}. {title}")
            st.write(text)

    a, b, c, d = st.columns(4)
    a.metric("Items listed", len(items))
    b.metric("Available now", len(available))
    c.metric("Found a new owner", sum(1 for i in items if i["status"] == "sold"))
    d.metric("CO₂ saved (kg)", impact["co2_kg"])
    st.caption(f"About {impact['waste_kg']} kg of e-waste kept out of landfill. Impact figures are rough estimates.")


def page_item(item_id):
    st.button("← Back to results", on_click=close_item)
    item = find(load("items"), item_id)
    if item is None:
        st.error("That item does not exist.")
        return
    seller = find(load("users"), item["seller_id"])

    left, right = st.columns([3, 2])
    with left.container(key=f"item_card_main_cat_{CATEGORY_ICONS.get(item['category'], 'devices_other')}"):
        st.markdown(f"## {icon(item['category'])}")
        st.title(md(item["name"]))
        st.markdown(f"{badge(item['condition'])} · {esc(item['category'])}", unsafe_allow_html=True)
        st.markdown("#### Description")
        st.write(md(item["description"]) if item["description"] else "No description given.")
        st.markdown("#### Pickup area")
        st.write(place(item))
        if seller:
            st.caption(f"Listed by {seller['name'].split()[0]} on {item['created']}")

    with right.container(key="item_card_buy"):
        st.markdown(f"### {money(item['price'])}")
        if item["status"] != "available":
            st.warning("Sorry, this item has already been sold.")
            return
        user = current_user()
        if user is None:
            st.info("Log in as a buyer to purchase this item.")
        elif user["role"] != "buyer":
            st.info("Only buyer accounts can purchase items.")
        elif user["id"] == item["seller_id"]:
            st.info("This is your own listing.")
        else:
            st.button("Buy this item", type="primary", on_click=do_buy, args=(item["id"], user["id"]))
        st.caption("After you buy, the seller's phone number and pickup address are shown to you. "
                   "Payment is arranged directly with the seller.")
        with st.expander("Tips for a safe pickup"):
            st.markdown("- Test the device before you pay.\n- Meet at the pickup address, or a public place, "
                        "and bring a friend if you can.\n- Ask for the original box, bill and charger.\n"
                        "- Pay on pickup, using cash or UPI.")


def page_browse():
    open_id = st.session_state.get("open_item")
    if open_id:
        page_item(open_id)
        return

    items = load("items")
    areas = sorted({i["area"] for i in items if i.get("area") and i["status"] == "available"})
    if st.session_state.get("browse_area", ALL_AREAS) not in [ALL_AREAS] + areas:
        st.session_state["browse_area"] = ALL_AREAS   # that area has no listings left
    st.title("Browse electronics")
    q = st.session_state.get("browse_q", "").strip()   # typed in the top search bar
    with st.expander("Filters", expanded=True):
        c1, c2, c3 = st.columns(3)
        category = c1.selectbox("Category", [ALL_CATEGORIES] + list(CATEGORIES), key="browse_category")
        condition = c2.selectbox("Condition", [ANY_CONDITION] + CONDITIONS, key="browse_condition")
        area = c3.selectbox("Area in Pune", [ALL_AREAS] + areas, key="browse_area")
        c4, c5, c6 = st.columns([2, 2, 1])
        max_price = c4.number_input("Max price (₹, 0 means no limit)", min_value=0, step=500, key="browse_price")
        sort = c5.selectbox("Sort", list(SORTS), key="browse_sort")
        c6.write("")
        c6.button("Reset", on_click=reset_filters)
    if q:
        st.write(f"Showing results for **{md(q)}**")

    found = search_items(
        items, q, "" if category == ALL_CATEGORIES else category,
        "" if condition == ANY_CONDITION else condition, int(max_price), "", SORTS[sort],
        "" if area == ALL_AREAS else area)
    st.caption(f"{len(found)} item{'' if len(found) == 1 else 's'} found")
    show_items(found, "browse")


def show_recommendation(result, condition):
    tone = {"good": st.success, "warn": st.warning, "bad": st.error}[result["tone"]]
    tone(f"**{result['action']}**")
    st.write(result["reason"])
    st.markdown("\n".join(f"{n}. {step}" for n, step in enumerate(result["steps"], start=1)))

    if condition in ("Minor fault", "Major fault"):
        c = result["compare"]
        st.markdown("#### Repair vs replace: cost per year of use")
        years = "year" if c["years_left"] == 1 else "years"
        st.table({
            "Option": [f"Repair (about {c['years_left']} more {years})",
                       f"Buy new ({c['lifespan']}-year life)"],
            "Cost per year": [money(c["repair_per_year"]), money(c["new_per_year"])],
        })
        st.caption(f"Cheaper per year: **{c['winner']}**. "
                   f"Upfront saving from repairing: {money(c['saving_now'])}.")


def page_advisor():
    st.title("Repair or replace?")
    st.write("Tell us about the item. The advisor recommends the most responsible next step.")
    left, right = st.columns(2)

    with left.form("advisor_form"):
        category = st.selectbox("Type", list(CATEGORIES))
        condition = st.selectbox("Condition", CONDITIONS)
        age = st.number_input("Age (years)", min_value=0, value=3, step=1)
        repair_cost = st.number_input("Repair quote (₹)", min_value=0, value=0, step=100)
        new_price = st.number_input("Price of a new one (₹)", min_value=0, value=0, step=500)
        submitted = st.form_submit_button("Get recommendation", type="primary")

    if submitted:
        with right:
            if new_price <= 0:
                st.warning("Enter what a new one would cost.")
            else:
                result = recommend(category, condition, int(age), int(repair_cost), int(new_price))
                show_recommendation(result, condition)
                st.button("Find a recycling point", on_click=go_to, args=("Recycling Map",))


def page_centers():
    st.title("Recycling map")
    centers = load("centers")
    cities = sorted({c["city"] for c in centers})
    city = st.selectbox("City", ["All"] + cities)
    found = [c for c in centers if city == "All" or c["city"] == city]
    if not found:
        st.info("No collection points are listed for this city yet.")
        return
    table = pd.DataFrame(found)
    st.map(table[["lat", "lon"]])
    show_table(table[["name", "city", "area", "accepts"]].rename(columns={
        "name": "Collection point", "city": "City", "area": "Area", "accepts": "Accepts"}))
    st.caption("Collection points are sample data. Replace them with verified locations.")


ROLE_INFO = {
    "buyer": ("Buyer", "Find pre-owned electronics near you.",
              "Demo buyers (password demo123): buyer@demo.com, buyer2@demo.com, buyer3@demo.com."),
    "seller": ("Seller", "List your old electronics and reach buyers in Pune.",
               "Demo sellers (password demo123): seller@demo.com, seller2@demo.com, seller3@demo.com."),
    "admin": ("Admin", "Manage listings, accounts and orders.",
              "Demo admin (password demo123): admin@demo.com. Creating a new admin needs the secret access code."),
}


def login_form(role):
    with st.form(f"{role}_login_form"):
        st.text_input("Email", key=f"{role}_login_email")
        st.text_input("Password", type="password", key=f"{role}_login_password")
        st.form_submit_button(f"Log in as {ROLE_INFO[role][0].lower()}", type="primary",
                              on_click=do_login, args=(role,))
    st.caption(ROLE_INFO[role][2])


def signup_form(role):
    p = f"{role}_reg_"
    with st.form(f"{role}_signup_form"):
        st.text_input("Full name", key=p + "name")
        st.text_input("Email", key=p + "email")
        st.text_input("Password (at least 6 characters)", type="password", key=p + "password")
        if role == "admin":
            st.text_input("Admin access code", type="password", key=p + "code")
            st.caption("Ask the project owner for the access code. Without it, an admin account cannot be created.")
        else:
            c1, c2 = st.columns(2)
            c1.text_input("City", value="Pune", key=p + "city")
            c2.text_input("Area (for example Baner)", key=p + "area")
            st.text_input("Phone number", key=p + "phone", placeholder="+91 98765 43210")
            if role == "seller":
                st.text_input("Pickup address (required)", key=p + "address")
            st.caption("Your phone number and address are shown only to the other person in a deal, "
                       "after a purchase. They are never shown on listings.")
        st.form_submit_button("Create account", type="primary", on_click=do_register, args=(role,))


def page_account():
    st.title("Log in or sign up")
    tabs = st.tabs([ROLE_INFO[r][0] for r in ("buyer", "seller", "admin")])
    for tab, role in zip(tabs, ("buyer", "seller", "admin")):
        with tab:
            st.markdown(f"### {ROLE_INFO[role][0]} area")
            st.write(ROLE_INFO[role][1])
            login_tab, signup_tab = st.tabs(["Log in", "Sign up"])
            with login_tab:
                login_form(role)
            with signup_tab:
                signup_form(role)


def page_sell():
    user = current_user()
    if user is None or user["role"] != "seller":
        st.info("Only seller accounts can list items. Log in as a seller first.")
        return
    st.title("Sell an item")
    with st.form("sell_form"):
        st.text_input("Item name", key="sell_name", placeholder="Brand, model and key spec")
        c1, c2 = st.columns(2)
        c1.selectbox("Category", list(CATEGORIES), key="sell_category")
        c2.selectbox("Condition", CONDITIONS, key="sell_condition")
        c3, c4, c5 = st.columns(3)
        c3.number_input("Price (₹)", min_value=1, value=1000, step=100, key="sell_price")
        c4.text_input("City", value=user["city"], key="sell_city")
        c5.text_input("Area", value=user.get("area", ""), key="sell_area")
        st.text_area("Description (max 300 characters)", max_chars=300, key="sell_desc",
                     placeholder="Age, what is included, any faults")
        st.form_submit_button("List item", type="primary", on_click=do_sell, args=(user["id"],))
    st.caption("Listings are saved to disk straight away and stay after you close the app.")


def page_dashboard():
    user = current_user()
    if user is None:
        st.info("Please log in first.")
        return
    st.title(f"Hello, {user['name']}")
    if user["role"] == "admin":
        page_admin()
        return
    items = load("items")
    users = load("users")

    if user["role"] == "seller":
        mine = [i for i in items if i["seller_id"] == user["id"]]
        orders = {o["item_id"]: o for o in load("orders")}
        sold = [i for i in mine if i["status"] == "sold"]
        a, b, c, d = st.columns(4)
        a.metric("Your listings", len(mine))
        b.metric("Sold", len(sold))
        c.metric("Earned", money(sum(i["price"] for i in sold)))
        d.metric("CO₂ saved (kg)", total_impact(mine)["co2_kg"])
        st.subheader("Your listings")
        if not mine:
            st.info("You have not listed anything yet. Use 'Sell an item' in the menu.")
        for item in sorted(mine, key=lambda i: (i["status"] != "sold", -i["id"])):
            with st.container(key=f"listing_card_{item['id']}"):
                x, y, z = st.columns([4, 2, 2])
                x.markdown(f"**{md(item['name'])}**  \n{item['category']} · {place(item)}")
                y.markdown(f"{money(item['price'])}  \n{item['status'].title()}")
                if item["status"] == "available":
                    z.button("Remove", key=f"del_{item['id']}", on_click=do_delete, args=(item["id"], user["id"]))
                else:
                    buyer = find(users, item["buyer_id"])
                    date = orders.get(item["id"], {}).get("date", "")
                    st.success(f"Sold on {date}. Contact the buyer to arrange the pickup.")
                    contact_block("Buyer", buyer)
        return

    orders = sorted((o for o in load("orders") if o["buyer_id"] == user["id"]), key=lambda o: -o["id"])
    bought = [dict(o, item=find(items, o["item_id"])) for o in orders]
    a, b, c = st.columns(3)
    a.metric("Orders", len(orders))
    b.metric("Spent", money(sum(o["price"] for o in orders)))
    c.metric("CO₂ saved (kg)", total_impact([o["item"] for o in bought if o["item"]])["co2_kg"])
    st.subheader("Your orders")
    if not bought:
        st.info("No orders yet. Find something in Browse.")
    for order in bought:
        item = order["item"]
        seller = find(users, item["seller_id"]) if item else None
        with st.container(key=f"order_card_{order['id']}"):
            x, y = st.columns([3, 3])
            x.markdown(f"**{md(item['name']) if item else '(removed)'}**  \n"
                       f"{money(order['price'])} · ordered on {order['date']}")
            with y:
                contact_block("Seller", seller)
            if order["id"] == st.session_state.get("last_order"):
                st.success("Next step: call or message the seller to agree a time to collect the item.")


def page_admin():
    users, items, orders = load("users"), load("items"), load("orders")
    by_id = {u["id"]: u for u in users}
    name_of = lambda uid: by_id[uid]["name"] if uid in by_id else "(removed)"
    sold = [i for i in items if i["status"] == "sold"]

    a, b, c, d = st.columns(4)
    a.metric("Buyers and sellers", sum(1 for u in users if u["role"] != "admin"))
    b.metric("Listings available", len(items) - len(sold))
    c.metric("Items sold", len(sold))
    d.metric("Sales value", money(sum(o["price"] for o in orders)))

    listings_tab, users_tab, orders_tab = st.tabs(["Listings", "Users", "Orders"])

    with listings_tab:
        if items:
            show_table(pd.DataFrame([
                {"ID": i["id"], "Item": i["name"], "Seller": name_of(i["seller_id"]), "Price": money(i["price"]),
                 "Status": i["status"].title(), "Area": place(i)} for i in sorted(items, key=lambda i: -i["id"])]))
        available = [i["id"] for i in items if i["status"] == "available"]
        if available:
            st.selectbox("Remove a listing", available, key="admin_remove_pick",
                         format_func=lambda i: f"#{i}  {find(items, i)['name']}")
            st.button("Remove selected listing", on_click=do_admin_remove)
        st.caption("Sold listings stay, because they belong to an order.")

    with users_tab:
        show_table(pd.DataFrame([
            {"ID": u["id"], "Name": u["name"], "Type": u["role"].title(), "Email": u["email"],
             "Phone": u.get("phone") or "-", "Area": place(u) or "-",
             "Status": "Blocked" if u.get("blocked") else "Active"} for u in users]))
        others = [u["id"] for u in users if u["role"] != "admin"]
        if others:
            st.selectbox("Account", others, key="admin_user_pick",
                         format_func=lambda i: f"{by_id[i]['name']} ({by_id[i]['role']})")
            x, y, _ = st.columns([1, 1, 3])
            x.button("Block", on_click=do_admin_block, args=(True,))
            y.button("Unblock", on_click=do_admin_block, args=(False,))
        st.caption("A blocked person cannot log in. Admin accounts cannot be blocked.")

    with orders_tab:
        if orders:
            show_table(pd.DataFrame([
                {"Order": o["id"], "Item": (find(items, o["item_id"]) or {}).get("name", "(removed)"),
                 "Buyer": name_of(o["buyer_id"]),
                 "Seller": name_of((find(items, o["item_id"]) or {}).get("seller_id")),
                 "Price": money(o["price"]), "Date": o["date"]} for o in sorted(orders, key=lambda o: -o["id"])]))
        else:
            st.info("No orders yet.")


PAGES = {
    "Home": page_home,
    "Browse": page_browse,
    "Repair or Replace?": page_advisor,
    "Recycling Map": page_centers,
    "Log in / Sign up": page_account,
    "Sell an item": page_sell,
    "My Dashboard": page_dashboard,
}


def top_bar():
    """Horizontal bar across the top: the brand and the search box, nothing else."""
    with st.container(key="topbar"):
        brand, search = st.columns([1, 2.4], vertical_alignment="center")
        brand.markdown('<div class="brand">♻️ ReBoot Map</div>', unsafe_allow_html=True)
        search.text_input("Search listings", key="browse_q", on_change=do_search,
                          placeholder="🔍  Search phones, laptops, chargers...",
                          label_visibility="collapsed")


def footer():
    st.divider()
    a, b, c = st.columns([2, 1, 1])
    a.markdown("**♻️ ReBoot Map**  \nA marketplace and repair-or-recycle advisor for pre-owned electronics in Pune.")
    b.markdown("**Marketplace**  \nBrowse electronics  \nSell an item  \nRepair or replace?")
    c.markdown("**Good to know**  \nPayment is arranged directly between buyer and seller.  \nCollection points and impact figures are samples and estimates.")
    st.caption(f"Demo project. Listings and accounts are saved in {data_dir()}")


def main():
    user = current_user()
    pages = ["Home", "Browse", "Repair or Replace?", "Recycling Map"]
    if user is None:
        pages.append("Log in / Sign up")
    else:
        if user["role"] == "seller":
            pages.append("Sell an item")
        pages.append("My Dashboard")
    if st.session_state.get("nav") not in pages:
        st.session_state["nav"] = "Home"
    if "dark_mode" not in st.session_state:   # first visit: use the theme from the page address
        st.session_state["dark_mode"] = st.query_params.get("theme") == "dark"

    load_css()
    top_bar()

    with st.sidebar:
        st.caption("MENU")
        st.radio("Go to", pages, key="nav", on_change=close_item, label_visibility="collapsed")
        st.divider()
        if user:
            st.write(f"Signed in as **{md(user['name'])}** ({user['role']})")
            st.button("Log out", on_click=do_logout)
        else:
            st.caption("You are not logged in.")
        st.divider()
        st.toggle("Dark mode", key="dark_mode", on_change=save_theme)

    show_flash()
    PAGES[st.session_state["nav"]]()
    footer()


if __name__ == "__main__":
    main()
