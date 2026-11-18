"""
Krishi AI design system.

A light, natural palette (forest greens on warm off-white), Inter typography,
Lucide outline icons (1.5px stroke), reusable HTML components, restrained
motion and a shared Plotly chart theme. Everything visual in app.py comes
from here so the hierarchy stays consistent across modules.
"""
from typing import Dict, Iterable, Optional, Sequence
from urllib.parse import quote

import plotly.graph_objects as go

# ------------------------------------------------------------------------------
# Palette
# ------------------------------------------------------------------------------
COLORS: Dict[str, str] = {
    "forest": "#142D22",          # Deep Forest - brand, emphasis
    "accent": "#26734D",          # Emerald Green - primary actions, focus, positive
    "accent_hover": "#1F5F40",
    "accent_text": "#1F5F40",     # text on tinted emerald backgrounds
    "sage": "#A8C3AD",            # Soft Sage - quiet data, bands, tracks
    "bg": "#F5F5F0",              # app background
    "bg_raised": "#FAFAF7",       # sidebar, inset wells
    "surface": "#FFFFFF",         # cards
    "surface_hover": "#F8F9F5",
    "border": "#E6E9E3",
    "border_strong": "#D6DBD3",
    "grid": "#EEF0EB",            # chart gridlines
    "text": "#202720",            # primary text
    "text_secondary": "#777F78",  # secondary text
    "text_muted": "#8A918B",      # axis ticks, tertiary metadata
    "historical": "#777F78",      # observed prices - solid line
    "forecast": "#26734D",        # AI forecast - dashed line
    "original": "#A8C3AD",        # unadjusted forecast in comparison overlay
    "positive": "#26734D",
    "risk": "#C65B52",            # error
    "warning": "#D69A32",
    "info": "#142D22",
}

TONES = {
    "neutral": COLORS["text_secondary"],
    "accent": COLORS["accent"],
    "forecast": COLORS["accent"],
    "positive": COLORS["positive"],
    "risk": COLORS["risk"],
    "warning": COLORS["warning"],
    "info": COLORS["forest"],
}

FONT_STACK = "Inter, -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif"


def hex_alpha(hex_color: str, alpha: float) -> str:
    """rgba() string for a #RRGGBB color at the given opacity."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


# ------------------------------------------------------------------------------
# Icons (Lucide, 24x24 grid, stroke-width 1.5)
# ------------------------------------------------------------------------------
ICON_PATHS: Dict[str, str] = {
    "house": '<path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8"/><path d="M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "settings": '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
    "layout-dashboard": '<rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/>',
    "sprout": '<path d="M7 20h10"/><path d="M10 20c5.5-2.5.8-6.4 3-10"/><path d="M9.5 9.4c1.1.8 1.8 2.2 2.3 3.7-2 .4-3.5.4-4.8-.3-1.2-.6-2.3-1.9-3-4.2 2.8-.5 4.4 0 5.5.8z"/><path d="M14.1 6a7 7 0 0 0-1.1 4c1.9-.1 3.3-.6 4.3-1.4 1-1 1.6-2.3 1.7-4.6-2.7.1-4 1-4.9 2z"/>',
    "leaf": '<path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/><path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>',
    "package": '<path d="M11 21.73a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73z"/><path d="M12 22V12"/><path d="m3.3 7 7.703 4.734a2 2 0 0 0 1.994 0L20.7 7"/><path d="m7.5 4.27 9 5.15"/>',
    "chart-column": '<path d="M3 3v16a2 2 0 0 0 2 2h16"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
    "chart-line": '<path d="M3 3v16a2 2 0 0 0 2 2h16"/><path d="m19 9-5 5-4-4-3 3"/>',
    "truck": '<path d="M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2"/><path d="M15 18H9"/><path d="M19 18h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.624l-3.48-4.35A1 1 0 0 0 17.52 8H14"/><circle cx="17" cy="18" r="2"/><circle cx="7" cy="18" r="2"/>',
    "trending-up": '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
    "trending-down": '<polyline points="22 17 13.5 8.5 8.5 13.5 2 7"/><polyline points="16 17 22 17 22 11"/>',
    "shield": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
    "shield-check": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
    "shield-alert": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="M12 8v4"/><path d="M12 16h.01"/>',
    "file-text": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/>',
    "user": '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "user-plus": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" x2="19" y1="8" y2="14"/><line x1="22" x2="16" y1="11" y2="11"/>',
    "log-in": '<path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" x2="3" y1="12" y2="12"/>',
    "log-out": '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/>',
    "key-round": '<path d="M2.586 17.414A2 2 0 0 0 2 18.828V21a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h.172a2 2 0 0 0 1.414-.586l.814-.814a6.5 6.5 0 1 0-4-4z"/><circle cx="16.5" cy="7.5" r=".5"/>',
    "lock": '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    "map-pin": '<path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"/><circle cx="12" cy="10" r="3"/>',
    "zap": '<path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/>',
    "history": '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>',
    "save": '<path d="M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/><path d="M17 21v-7a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v7"/><path d="M7 3v4a1 1 0 0 0 1 1h7"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>',
    "award": '<path d="m15.477 12.89 1.515 8.526a.5.5 0 0 1-.81.47l-3.58-2.687a1 1 0 0 0-1.197 0l-3.586 2.686a.5.5 0 0 1-.81-.469l1.514-8.526"/><circle cx="12" cy="8" r="6"/>',
    "lightbulb": '<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/>',
    "scale": '<path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="M7 21h10"/><path d="M12 3v18"/><path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/>',
    "triangle-alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "activity": '<path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2"/>',
    "circle-check": '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    "arrow-right": '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
    "chevron-right": '<path d="m9 18 6-6-6-6"/>',
    "store": '<path d="m2 7 4.41-4.41A2 2 0 0 1 7.83 2h8.34a2 2 0 0 1 1.42.59L22 7"/><path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/><path d="M15 22v-4a2 2 0 0 0-2-2h-2a2 2 0 0 0-2 2v4"/><path d="M2 7h20"/><path d="M22 7v3a2 2 0 0 1-2 2a2.7 2.7 0 0 1-1.59-.63.7.7 0 0 0-.82 0A2.7 2.7 0 0 1 16 12a2.7 2.7 0 0 1-1.59-.63.7.7 0 0 0-.82 0A2.7 2.7 0 0 1 12 12a2.7 2.7 0 0 1-1.59-.63.7.7 0 0 0-.82 0A2.7 2.7 0 0 1 8 12a2.7 2.7 0 0 1-1.59-.63.7.7 0 0 0-.82 0A2.7 2.7 0 0 1 4 12a2 2 0 0 1-2-2V7"/>',
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "send": '<path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z"/><path d="m21.854 2.147-10.94 10.939"/>',
    "phone": '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "x": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "plus": '<path d="M5 12h14"/><path d="M12 5v14"/>',
    "factory": '<path d="M2 20a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V8l-7 5V8l-7 5V4a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z"/><path d="M17 18h1"/><path d="M12 18h1"/><path d="M7 18h1"/>',
    "inbox": '<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
    "database": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5V19A9 3 0 0 0 21 19V5"/><path d="M3 12A9 3 0 0 0 21 12"/>',
    "calendar": '<path d="M8 2v4"/><path d="M16 2v4"/><rect width="18" height="18" x="3" y="4" rx="2"/><path d="M3 10h18"/>',
    "target": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    "refresh-cw": '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
    "sliders-horizontal": '<line x1="21" x2="14" y1="4" y2="4"/><line x1="10" x2="3" y1="4" y2="4"/><line x1="21" x2="12" y1="12" y2="12"/><line x1="8" x2="3" y1="12" y2="12"/><line x1="21" x2="16" y1="20" y2="20"/><line x1="12" x2="3" y1="20" y2="20"/><line x1="14" x2="14" y1="2" y2="6"/><line x1="8" x2="8" y1="10" y2="14"/><line x1="16" x2="16" y1="18" y2="22"/>',
    "gauge": '<path d="m12 14 4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/>',
    "landmark": '<line x1="3" x2="21" y1="22" y2="22"/><line x1="6" x2="6" y1="18" y2="11"/><line x1="10" x2="10" y1="18" y2="11"/><line x1="14" x2="14" y1="18" y2="11"/><line x1="18" x2="18" y1="18" y2="11"/><polygon points="12 2 20 7 4 7"/>',
    "thermometer": '<path d="M14 4v10.54a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0Z"/>',
    "clipboard-list": '<rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="M12 11h4"/><path d="M12 16h4"/><path d="M8 11h.01"/><path d="M8 16h.01"/>',
    "circle-dot": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="1"/>',
    "droplets": '<path d="M7 16.3c2.2 0 4-1.83 4-4.05 0-1.16-.57-2.26-1.71-3.19S7.29 6.75 7 5.3c-.29 1.45-1.14 2.84-2.29 3.76S3 11.1 3 12.25c0 2.22 1.8 4.05 4 4.05z"/><path d="M12.56 6.6A10.97 10.97 0 0 0 14 3.02c.5 2.5 2 4.9 4 6.5s3 3.5 3 5.5a6.98 6.98 0 0 1-11.91 4.97"/>',
    "wind": '<path d="M12.8 19.6A2 2 0 1 0 14 16H2"/><path d="M17.5 8a2.5 2.5 0 1 1 2 4H2"/><path d="M9.8 4.4A2 2 0 1 1 11 8H2"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>',
    "cloud": '<path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"/>',
    "cloud-sun": '<path d="M12 2v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="M20 12h2"/><path d="m19.07 4.93-1.41 1.41"/><path d="M15.947 12.65a4 4 0 0 0-5.925-4.128"/><path d="M13 22H7a5 5 0 1 1 4.9-6H13a3 3 0 0 1 0 6Z"/>',
    "cloud-rain": '<path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"/><path d="M16 14v6"/><path d="M8 14v6"/><path d="M12 16v6"/>',
    "cloud-drizzle": '<path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"/><path d="M8 19v1"/><path d="M8 14v1"/><path d="M16 19v1"/><path d="M16 14v1"/><path d="M12 21v1"/><path d="M12 16v1"/>',
    "cloud-lightning": '<path d="M6 16.326A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 .5 8.973"/><path d="m13 12-3 5h4l-3 5"/>',
    "cloud-fog": '<path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"/><path d="M16 17H7"/><path d="M17 21H9"/>',
}


def icon_svg(name: str, size: int = 24, color: str = "currentColor", stroke: float = 1.5) -> str:
    """Raw SVG markup for a Lucide outline icon."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" '
        f'fill="none" stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" '
        f'stroke-linejoin="round">{ICON_PATHS[name]}</svg>'
    )


def svg_data_uri(svg: str) -> str:
    """Percent-encoded data URI (no quotes or parentheses, safe in an unquoted url())."""
    return "data:image/svg+xml;charset=utf-8," + quote(svg, safe="")


def icon_data_uri(name: str, stroke: float = 1.5) -> str:
    return svg_data_uri(icon_svg(name, color="#000", stroke=stroke))


def icon(name: str, size: int = 16, color: str = "currentColor", stroke: float = 1.5, cls: str = "ki-icon") -> str:
    """
    Inline icon. st.html sanitizes away <svg>, so the icon is a span masked by
    the SVG; it is filled with `color` (defaults to the surrounding text color).
    """
    uri = icon_data_uri(name, stroke)
    return (
        f'<span class="{cls}" aria-hidden="true" style="width:{size}px; height:{size}px; '
        f'background-color:{color}; -webkit-mask:url({uri}) center / contain no-repeat; '
        f'mask:url({uri}) center / contain no-repeat;"></span>'
    )


def button_icon_css(mapping: Dict[str, str], size: int = 16) -> str:
    """
    CSS that prefixes Streamlit buttons with outline icons. Streamlit tags every
    keyed widget's container with `st-key-<key>`, so `mapping` is {widget_key: icon}.
    """
    if not mapping:
        return ""
    selectors = ", ".join(f".st-key-{k} button::before" for k in mapping)
    rules = [
        f"{selectors} {{content: ''; display: inline-block; width: {size}px; height: {size}px; "
        f"flex: 0 0 {size}px; margin-right: 10px; background-color: currentColor; "
        f"-webkit-mask-repeat: no-repeat; mask-repeat: no-repeat; -webkit-mask-position: center; "
        f"mask-position: center; -webkit-mask-size: contain; mask-size: contain;}}"
    ]
    for key, name in mapping.items():
        uri = icon_data_uri(name)
        rules.append(f".st-key-{key} button::before {{-webkit-mask-image: url({uri}); mask-image: url({uri});}}")
    return "\n".join(rules)


# ------------------------------------------------------------------------------
# Motion helpers
# ------------------------------------------------------------------------------
def count(value: float, decimals: int = 0, prefix: str = "", suffix: str = "",
          key: Optional[str] = None, signed: bool = False) -> str:
    """
    A number that eases to its value (and between values on later reruns).
    The final text is rendered server-side, so it is correct without JavaScript.
    """
    v = float(value)
    sign = "−" if v < 0 else ("+" if signed and v > 0 else "")
    text = f"{sign}{prefix}{abs(v):,.{decimals}f}{suffix}"
    attrs = (f'data-value="{v}" data-decimals="{decimals}" data-prefix="{prefix}" '
             f'data-suffix="{suffix}" data-signed="{1 if signed else 0}"')
    if key:
        attrs += f' data-key="{key}"'
    return f'<span class="ki-count ki-num" {attrs}>{text}</span>'


COUNT_UP_SCRIPT = """
<script>
(function () {
  if (window.__kiCount) { window.__kiCount.scan(); return; }
  var last = new Map();
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  function fmt(el, v) {
    var d = parseInt(el.dataset.decimals || '0', 10);
    var sign = v < 0 ? '\\u2212' : (el.dataset.signed === '1' && v > 0 ? '+' : '');
    return sign + (el.dataset.prefix || '') + Math.abs(v).toLocaleString('en-US',
      {minimumFractionDigits: d, maximumFractionDigits: d}) + (el.dataset.suffix || '');
  }
  function run(el) {
    var target = parseFloat(el.dataset.value);
    if (isNaN(target) || el.__kiDone === el.dataset.value) return;
    el.__kiDone = el.dataset.value;
    var key = el.dataset.key;
    var from = (key && last.has(key)) ? last.get(key) : target * 0.82;
    if (key) last.set(key, target);
    if (reduce || from === target) { el.textContent = fmt(el, target); return; }
    var t0 = performance.now(), dur = (key && last.has(key)) ? 520 : 760;
    function step(now) {
      var p = Math.min(1, (now - t0) / dur);
      var e = 1 - Math.pow(1 - p, 3);
      el.textContent = fmt(el, from + (target - from) * e);
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }
  function scan() { document.querySelectorAll('.ki-count').forEach(run); }
  var pending = false;
  new MutationObserver(function () {
    if (pending) return; pending = true;
    requestAnimationFrame(function () { pending = false; scan(); });
  }).observe(document.body, {childList: true, subtree: true, characterData: true});
  window.__kiCount = {scan: scan};
  scan();
})();
</script>
"""


def page_transition_css(page_slugs: Iterable[str]) -> str:
    """
    Fade-up when the page changes. Each page container gets its own (identical)
    keyframes name, so the animation restarts only when the page switches, not
    on reruns triggered by widgets within the same page.
    """
    rules = []
    for slug in page_slugs:
        rules.append(
            f"@keyframes ki-in-{slug} {{ from {{ opacity: 0; transform: translateY(6px); }} "
            f"to {{ opacity: 1; transform: none; }} }}\n"
            f".st-key-page_{slug} {{ animation: ki-in-{slug} .42s cubic-bezier(.2,.7,.2,1) both; }}"
        )
    return "\n".join(rules)


def sparkline_uri(values: Sequence[float], color: str, width: int = 120, height: int = 36) -> Optional[str]:
    """Tiny line chart as an SVG data URI (used as a CSS background image)."""
    vals = [float(v) for v in values if v is not None]
    if len(vals) < 2:
        return None
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    pad = 3
    pts = []
    for i, v in enumerate(vals):
        x = pad + i * (width - 2 * pad) / (len(vals) - 1)
        y = pad + (1 - (v - lo) / span) * (height - 2 * pad)
        pts.append(f"{x:.1f},{y:.1f}")
    lx, ly = pts[-1].split(",")
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="1.5" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
        f'<circle cx="{lx}" cy="{ly}" r="2.5" fill="{color}"/></svg>'
    )
    return svg_data_uri(svg)


# ------------------------------------------------------------------------------
# HTML components
# ------------------------------------------------------------------------------
def page_header(icon_name: str, title: str, subtitle: Optional[str] = None,
                right_html: str = "", eyebrow: Optional[str] = None) -> str:
    eb = (f'<div class="ki-page-eyebrow">{icon(icon_name, 14)}<span>{eyebrow}</span></div>'
          if eyebrow else "")
    sub = f'<p class="ki-page-sub">{subtitle}</p>' if subtitle else ""
    return f"""
    <div class="ki-page-header">
        <div class="ki-page-header__lead">{eb}<h1 class="ki-page-title">{title}</h1>{sub}</div>
        {right_html}
    </div>"""


def card_title(icon_name: Optional[str], title: str, subtitle: Optional[str] = None, right_html: str = "") -> str:
    sub = f'<div class="ki-card-sub">{subtitle}</div>' if subtitle else ""
    ic = f'<span class="ki-card-icon">{icon(icon_name, 17)}</span>' if icon_name else ""
    return f"""
    <div class="ki-card-head">
        <div class="ki-card-head__lead">{ic}<div><div class="ki-card-title">{title}</div>{sub}</div></div>
        {right_html}
    </div>"""


def badge(text: str, tone: str = "neutral", icon_name: Optional[str] = None, color: Optional[str] = None) -> str:
    c = color or TONES.get(tone, TONES["neutral"])
    ic = icon(icon_name, 13) if icon_name else ""
    return (f'<span class="ki-badge" style="color:{c}; background:{hex_alpha(c, 0.09)}; '
            f'border-color:{hex_alpha(c, 0.22)};">{ic}{text}</span>')


def kpi_card(label: str, value: str, sub: Optional[str] = None, tone: str = "neutral",
             icon_name: Optional[str] = None, highlight: bool = False, tag_html: str = "",
             spark_uri: Optional[str] = None) -> str:
    sub_color = TONES.get(tone, TONES["neutral"])
    label_color = TONES.get(tone, COLORS["text_secondary"]) if icon_name and tone != "neutral" else COLORS["text_secondary"]
    ic = f'<span class="ki-kpi-icon" style="color:{label_color};">{icon(icon_name, 15)}</span>' if icon_name else ""
    sub_html = f'<div class="ki-kpi-sub ki-num" style="color:{sub_color};">{sub}</div>' if sub else ""
    spark = (f'<div class="ki-spark" style="background-image:url({spark_uri});"></div>' if spark_uri else "")
    cls = "ki-kpi ki-kpi--highlight" if highlight else "ki-kpi"
    return f"""
    <div class="{cls}">
        <div class="ki-kpi-label">{ic}<span>{label}</span>{tag_html}</div>
        <div class="ki-kpi-row"><div class="ki-kpi-value ki-num">{value}</div>{spark}</div>
        {sub_html}
    </div>"""


def callout(icon_name: str, title: str, body: str, tone: str = "info") -> str:
    c = TONES.get(tone, TONES["info"])
    return f"""
    <div class="ki-callout" style="background:{hex_alpha(c, 0.05)}; border-color:{hex_alpha(c, 0.18)};">
        <span class="ki-callout-icon" style="color:{c};">{icon(icon_name, 18)}</span>
        <div><div class="ki-callout-title">{title}</div><div class="ki-callout-body">{body}</div></div>
    </div>"""


def empty_state(icon_name: str, title: str, body: str) -> str:
    return f"""
    <div class="ki-empty">
        <div class="ki-empty-icon">{icon(icon_name, 20)}</div>
        <div class="ki-empty-title">{title}</div>
        <div class="ki-empty-body">{body}</div>
    </div>"""


def hero(eyebrow: str, value: str, body_html: str = "", right_html: str = "") -> str:
    """Large headline result block."""
    return f"""
    <div class="ki-hero">
        <div class="ki-hero-top"><div class="ki-eyebrow">{eyebrow}</div>{right_html}</div>
        <div class="ki-hero-value ki-num">{value}</div>
        {body_html}
    </div>"""


def meter(pct: float, color: str) -> str:
    """Thin horizontal progress meter (0-100)."""
    w = max(0.0, min(100.0, float(pct)))
    return f'<div class="ki-meter"><div class="ki-meter-fill" style="width:{w:.1f}%; background:{color};"></div></div>'


def stat_list(items, compact: bool = False) -> str:
    """Label / value rows with tabular numerals. items: [(label, value, color_or_None)]."""
    rows = ""
    for label, value, color in items:
        style = f' style="color:{color};"' if color else ""
        rows += (f'<div class="ki-stat"><span class="ki-stat-label">{label}</span>'
                 f'<span class="ki-stat-value ki-num"{style}>{value}</span></div>')
    cls = "ki-stats ki-stats--compact" if compact else "ki-stats"
    return f'<div class="{cls}">{rows}</div>'


# ------------------------------------------------------------------------------
# Plotly theme
# ------------------------------------------------------------------------------
def style_figure(fig: go.Figure, height: Optional[int] = None, title: Optional[str] = None) -> go.Figure:
    """Quiet chart theme: transparent canvas, hairline grid, small muted labels."""
    axis = dict(
        gridcolor=COLORS["grid"],
        linecolor=COLORS["border"],
        showline=False,
        zeroline=False,
        tickfont=dict(color=COLORS["text_muted"], size=11),
        title_font=dict(color=COLORS["text_secondary"], size=12),
        showspikes=False,
    )
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT_STACK, color=COLORS["text_secondary"], size=12),
        margin=dict(l=4, r=4, t=44 if title else 12, b=4),
        hoverlabel=dict(
            bgcolor=COLORS["surface"],
            bordercolor=COLORS["border"],
            font=dict(family=FONT_STACK, color=COLORS["text"], size=12),
        ),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=COLORS["text_secondary"], size=11)),
    )
    if title:
        fig.update_layout(title=dict(text=title, x=0, xanchor="left",
                                     font=dict(color=COLORS["text"], size=14)))
    if height:
        fig.update_layout(height=height)
    fig.update_xaxes(**axis)
    fig.update_yaxes(**axis)
    return fig


PLOTLY_CONFIG = {"displaylogo": False, "displayModeBar": False}


# ------------------------------------------------------------------------------
# Global stylesheet
# ------------------------------------------------------------------------------
def global_css() -> str:
    c = COLORS
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400..700&display=swap');

:root {{
    --ki-forest: {c['forest']};
    --ki-accent: {c['accent']};
    --ki-accent-hover: {c['accent_hover']};
    --ki-accent-soft: {hex_alpha(c['accent'], 0.09)};
    --ki-sage: {c['sage']};
    --ki-bg: {c['bg']};
    --ki-bg-raised: {c['bg_raised']};
    --ki-surface: {c['surface']};
    --ki-surface-hover: {c['surface_hover']};
    --ki-border: {c['border']};
    --ki-border-strong: {c['border_strong']};
    --ki-text: {c['text']};
    --ki-text-2: {c['text_secondary']};
    --ki-text-3: {c['text_muted']};
    --ki-positive: {c['positive']};
    --ki-risk: {c['risk']};
    --ki-warning: {c['warning']};
    --ki-radius: 12px;
    --ki-radius-sm: 8px;
    --ki-shadow: 0 1px 2px rgba(20, 45, 34, 0.04);
    --ki-shadow-hover: 0 1px 2px rgba(20, 45, 34, 0.04), 0 10px 24px -14px rgba(20, 45, 34, 0.22);
    --ki-ease: cubic-bezier(.2, .7, .2, 1);
    --ki-font: {FONT_STACK};
}}

/* ---------- Base ---------- */
html, body, .stApp, [data-testid="stAppViewContainer"] {{
    background-color: var(--ki-bg) !important;
    color: var(--ki-text);
    font-family: var(--ki-font) !important;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}}
.stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea, .stApp button {{ font-family: var(--ki-font) !important; }}
[data-testid="stHeader"] {{ background: transparent !important; }}
.block-container {{ padding-top: 2.5rem !important; padding-bottom: 7rem !important; max-width: 1320px; }}
.stApp p, .stApp li {{ color: var(--ki-text-2); }}
.stApp strong {{ color: var(--ki-text); font-weight: 600; }}
.ki-num, .ki-num * {{ font-variant-numeric: tabular-nums; font-feature-settings: "tnum" 1; }}
.js-plotly-plot .plotly text {{ font-variant-numeric: tabular-nums; font-feature-settings: "tnum" 1; }}
.ki-icon {{ flex-shrink: 0; display: inline-block; vertical-align: middle; }}
::selection {{ background: {hex_alpha(c['accent'], 0.18)}; }}

/* Thin indeterminate progress line while the script runs */
@keyframes ki-loading {{ 0% {{ transform: translateX(-100%); }} 100% {{ transform: translateX(100%); }} }}
[data-test-script-state="running"]::after {{
    content: ""; position: fixed; top: 0; left: 0; right: 0; height: 2px; z-index: 1000000;
    background: linear-gradient(90deg, transparent, var(--ki-accent), transparent);
    animation: ki-loading 1.1s var(--ki-ease) infinite; pointer-events: none;
}}
.stElementContainer[data-stale="true"] {{ transition: opacity .25s ease; }}

/* ---------- Widgets ---------- */
[data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] label {{
    color: var(--ki-text-2) !important; font-size: 0.8125rem !important; font-weight: 500 !important;
}}
div[data-baseweb="input"], div[data-baseweb="select"] > div, div[data-baseweb="textarea"] {{
    border-radius: var(--ki-radius-sm) !important;
    transition: border-color .15s ease, box-shadow .15s ease;
}}
div[data-baseweb="input"] input, div[data-baseweb="textarea"] textarea {{
    color: var(--ki-text) !important; -webkit-text-fill-color: var(--ki-text) !important;
    font-variant-numeric: tabular-nums; font-size: 0.875rem !important;
}}
div[data-baseweb="input"]:focus-within, div[data-baseweb="select"] > div:focus-within, div[data-baseweb="textarea"]:focus-within {{
    border-color: var(--ki-accent) !important; box-shadow: 0 0 0 3px {hex_alpha(c['accent'], 0.14)} !important;
}}
input::placeholder, textarea::placeholder {{ color: var(--ki-text-3) !important; -webkit-text-fill-color: var(--ki-text-3) !important; }}
span[data-baseweb="tag"] {{ background-color: var(--ki-accent-soft) !important; border: 1px solid {hex_alpha(c['accent'], 0.25)} !important; }}
span[data-baseweb="tag"] span {{ color: var(--ki-accent-hover) !important; }}
[data-testid="stSliderTickBarMin"], [data-testid="stSliderTickBarMax"] {{ font-variant-numeric: tabular-nums; color: var(--ki-text-3) !important; font-size: 0.75rem; }}
[data-testid="stSliderThumbValue"] {{ font-variant-numeric: tabular-nums; color: var(--ki-text) !important; font-weight: 500; font-size: 0.75rem; }}
[data-testid="stCaptionContainer"], .stCaption {{ color: var(--ki-text-3) !important; }}

/* ---------- Buttons ---------- */
.stButton > button, .stDownloadButton > button {{
    display: inline-flex; align-items: center; justify-content: center;
    border-radius: var(--ki-radius-sm) !important; min-height: 40px; padding: 8px 16px !important;
    box-shadow: none !important;
    transition: background-color .18s ease, border-color .18s ease, color .18s ease, transform .12s ease;
}}
.stButton > button p, .stDownloadButton > button p {{ font-size: 0.875rem !important; font-weight: 500 !important; color: inherit !important; }}
.stButton > button > div, .stDownloadButton > button > div {{ width: auto !important; flex: 0 1 auto !important; min-width: 0; }}
.stButton > button:active, .stDownloadButton > button:active {{ transform: scale(0.985); }}
.stButton > button[kind="primary"], button[data-testid="stBaseButton-primary"] {{
    background-color: var(--ki-accent) !important; border: 1px solid var(--ki-accent) !important; color: #FFFFFF !important;
}}
.stButton > button[kind="primary"]:hover, button[data-testid="stBaseButton-primary"]:hover {{
    background-color: var(--ki-accent-hover) !important; border-color: var(--ki-accent-hover) !important;
}}
.stButton > button[kind="secondary"], button[data-testid="stBaseButton-secondary"], .stDownloadButton > button {{
    background-color: var(--ki-surface) !important; border: 1px solid var(--ki-border) !important; color: var(--ki-text) !important;
}}
.stButton > button[kind="secondary"]:hover, button[data-testid="stBaseButton-secondary"]:hover, .stDownloadButton > button:hover {{
    background-color: var(--ki-surface-hover) !important; border-color: var(--ki-border-strong) !important; color: var(--ki-text) !important;
}}
.stButton > button:focus-visible, .stDownloadButton > button:focus-visible {{
    outline: none !important; box-shadow: 0 0 0 3px {hex_alpha(c['accent'], 0.25)} !important;
}}

/* ---------- Cards (keyed bordered containers) ---------- */
[class*="st-key-card_"] {{
    background-color: var(--ki-surface) !important; border: 1px solid var(--ki-border) !important;
    border-radius: var(--ki-radius) !important; box-shadow: var(--ki-shadow) !important; padding: 24px !important;
    transition: box-shadow .25s var(--ki-ease), border-color .25s var(--ki-ease);
}}
[class*="st-key-card_"]:hover {{ border-color: var(--ki-border-strong) !important; }}

/* ---------- Sidebar (Settings-style list) ---------- */
section[data-testid="stSidebar"] {{ background-color: var(--ki-bg-raised) !important; border-right: 1px solid var(--ki-border) !important; }}
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{ gap: 2px; }}
section[data-testid="stSidebar"] .stButton > button {{
    justify-content: flex-start !important; background-color: transparent !important; border: 1px solid transparent !important;
    color: var(--ki-text) !important; min-height: 36px; padding: 6px 10px !important;
}}
section[data-testid="stSidebar"] .stButton > button p {{ font-weight: 450 !important; }}
section[data-testid="stSidebar"] .stButton > button::before {{ color: var(--ki-text-2); background-color: var(--ki-text-2) !important; }}
section[data-testid="stSidebar"] .stButton > button:hover {{ background-color: rgba(32, 39, 32, 0.045) !important; }}
section[data-testid="stSidebar"] .stButton > button[kind="primary"],
section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] {{
    background-color: var(--ki-accent-soft) !important; border-color: transparent !important; color: var(--ki-forest) !important;
}}
section[data-testid="stSidebar"] .stButton > button[kind="primary"] p,
section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] p {{ font-weight: 550 !important; }}
section[data-testid="stSidebar"] .stButton > button[kind="primary"]::before,
section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"]::before {{ background-color: var(--ki-accent) !important; }}

.ki-brand {{ display: flex; align-items: center; gap: 10px; padding: 2px 4px 22px 4px; }}
.ki-brand-mark {{ width: 32px; height: 32px; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: #FFFFFF; background: var(--ki-forest); }}
.ki-brand-name {{ color: var(--ki-text); font-size: 1rem; font-weight: 600; letter-spacing: -0.01em; }}
.ki-brand-tag {{ color: var(--ki-text-2); font-size: 0.75rem; margin-top: 1px; }}
.ki-nav-section {{ color: var(--ki-text-3); font-size: 0.6875rem; font-weight: 500; letter-spacing: 0.04em; text-transform: uppercase; padding: 16px 10px 6px 10px; }}
.ki-profile {{ display: flex; gap: 10px; align-items: center; padding: 10px; border-radius: var(--ki-radius-sm); background: var(--ki-surface); border: 1px solid var(--ki-border); margin-top: 8px; }}
.ki-avatar {{
    width: 32px; height: 32px; flex: 0 0 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
    background: var(--ki-forest); color: #FFFFFF; font-weight: 500; font-size: 0.75rem; letter-spacing: 0.02em;
}}
.ki-profile-name {{ color: var(--ki-text); font-size: 0.8125rem; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.ki-profile-farm {{ color: var(--ki-text-2); font-size: 0.75rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.ki-sidebar-divider {{ border-top: 1px solid var(--ki-border); margin: 14px 4px 6px 4px; }}

/* ---------- Page header & greeting ---------- */
.ki-page-header {{ display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; margin: 0 0 28px 0; flex-wrap: wrap; }}
.ki-page-eyebrow {{ display: flex; align-items: center; gap: 6px; color: var(--ki-accent); font-size: 0.8125rem; font-weight: 500; margin-bottom: 6px; }}
.ki-page-title {{ color: var(--ki-text) !important; font-size: 2rem !important; font-weight: 600 !important; letter-spacing: -0.025em !important; line-height: 1.15 !important; margin: 0 !important; padding: 0 !important; }}
.ki-page-sub {{ color: var(--ki-text-2) !important; font-size: 0.9375rem; margin: 8px 0 0 0 !important; line-height: 1.55; max-width: 680px; }}
.ki-greeting-meta {{ display: flex; flex-wrap: wrap; gap: 6px 18px; margin-top: 10px; color: var(--ki-text-2); font-size: 0.875rem; }}
.ki-greeting-meta span {{ display: inline-flex; align-items: center; gap: 6px; }}
.ki-topline {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 28px; color: var(--ki-text-2); font-size: 0.8125rem; }}
.ki-topline-right {{ display: flex; align-items: center; gap: 14px; }}
.ki-topline-date {{ display: inline-flex; align-items: center; gap: 6px; }}
.ki-breadcrumb {{ display: flex; align-items: center; gap: 8px; font-weight: 500; }}
.ki-crumb-sep {{ color: var(--ki-border-strong); }}
.ki-crumb-current {{ color: var(--ki-text); }}
.ki-section-title {{ display: flex; align-items: baseline; gap: 10px; color: var(--ki-text); font-size: 1.125rem; font-weight: 550; letter-spacing: -0.015em; margin: 4px 0 2px 0; }}
.ki-section-title span {{ color: var(--ki-text-2); font-size: 0.8125rem; font-weight: 450; letter-spacing: 0; }}

/* ---------- Card internals ---------- */
.ki-card-head {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 18px; }}
.ki-card-head__lead {{ display: flex; align-items: flex-start; gap: 10px; }}
.ki-card-icon {{ color: var(--ki-accent); display: inline-flex; padding-top: 1px; }}
.ki-card-title {{ color: var(--ki-text); font-size: 1rem; font-weight: 550; letter-spacing: -0.01em; line-height: 1.35; }}
.ki-card-sub {{ color: var(--ki-text-2); font-size: 0.8125rem; margin-top: 2px; line-height: 1.45; }}
.ki-eyebrow {{ color: var(--ki-text-2); font-size: 0.75rem; font-weight: 500; }}
.ki-text {{ color: var(--ki-text-2); font-size: 0.875rem; line-height: 1.6; }}
.ki-text strong {{ color: var(--ki-text); }}
.ki-unit {{ color: var(--ki-text-2); font-size: 0.5em; font-weight: 450; margin-left: 3px; letter-spacing: 0; }}
.ki-hint {{ color: var(--ki-text-2); font-size: 0.8125rem; line-height: 1.5; padding-top: 4px; }}
.ki-badge {{
    display: inline-flex; align-items: center; gap: 5px; padding: 3px 9px; border-radius: 999px; border: 1px solid;
    font-size: 0.75rem; font-weight: 500; line-height: 1.4; white-space: nowrap; font-variant-numeric: tabular-nums;
}}

/* ---------- KPI / highlight tiles ---------- */
.ki-kpi {{
    position: relative; background: var(--ki-surface); border: 1px solid var(--ki-border); border-radius: var(--ki-radius);
    padding: 20px; box-shadow: var(--ki-shadow); height: 100%; min-height: 124px; min-width: 0;
    transition: box-shadow .25s var(--ki-ease), transform .25s var(--ki-ease), border-color .25s var(--ki-ease);
}}
.ki-kpi:hover {{ box-shadow: var(--ki-shadow-hover); transform: translateY(-1px); border-color: var(--ki-border-strong); }}
.ki-kpi--highlight {{ border-color: {hex_alpha(c['accent'], 0.35)}; }}
.ki-kpi-label {{ display: flex; align-items: center; gap: 7px; color: var(--ki-text-2); font-size: 0.8125rem; font-weight: 500; }}
.ki-kpi-label > span:not(.ki-kpi-icon):not(.ki-badge) {{ white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; }}
.ki-kpi-icon {{ display: inline-flex; }}
.ki-kpi-dot {{ position: absolute; top: 16px; right: 16px; width: 7px; height: 7px; border-radius: 50%; background: var(--ki-accent); box-shadow: 0 0 0 3px {hex_alpha(c['accent'], 0.15)}; }}
.ki-kpi-row {{ display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 8px 10px; margin-top: 12px; }}
.ki-kpi-value {{ color: var(--ki-text); font-size: 1.75rem; font-weight: 600; letter-spacing: -0.025em; line-height: 1.1; white-space: nowrap; }}
.ki-kpi-sub {{ font-size: 0.8125rem; font-weight: 500; margin-top: 8px; line-height: 1.4; }}
.ki-kpi-base {{ color: var(--ki-text-2); font-weight: 400; margin-top: 2px; }}
.ki-spark {{ width: 96px; height: 32px; flex: 0 0 96px; background-repeat: no-repeat; background-size: 100% 100%; }}

/* ---------- Weather ---------- */
.ki-wx-now {{ display: flex; align-items: center; justify-content: space-between; gap: 16px; }}
.ki-wx-temp {{ color: var(--ki-text); font-size: 3.25rem; font-weight: 300; letter-spacing: -0.04em; line-height: 1; }}
.ki-wx-cond {{ color: var(--ki-text); font-size: 0.9375rem; font-weight: 500; margin-top: 6px; }}
.ki-wx-hl {{ color: var(--ki-text-2); font-size: 0.8125rem; margin-top: 2px; }}
.ki-wx-icon {{ color: var(--ki-forest); }}
.ki-wx-metrics {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: 20px 0 6px 0; padding: 14px 0; border-top: 1px solid var(--ki-border); border-bottom: 1px solid var(--ki-border); }}
.ki-wx-metric-label {{ display: flex; align-items: center; gap: 5px; color: var(--ki-text-2); font-size: 0.75rem; }}
.ki-wx-metric-value {{ color: var(--ki-text); font-size: 1rem; font-weight: 500; margin-top: 3px; }}
.ki-wx-day {{ display: grid; grid-template-columns: 44px 22px 40px 38px 1fr 38px; align-items: center; gap: 10px; padding: 9px 0; border-bottom: 1px solid var(--ki-border); font-size: 0.8125rem; }}
.ki-wx-day:last-child {{ border-bottom: none; }}
.ki-wx-day-name {{ color: var(--ki-text); font-weight: 500; }}
.ki-wx-day-rain {{ color: var(--ki-accent); font-size: 0.75rem; }}
.ki-wx-day-lo {{ color: var(--ki-text-2); text-align: right; }}
.ki-wx-day-hi {{ color: var(--ki-text); text-align: right; font-weight: 500; }}
.ki-wx-range {{ position: relative; height: 4px; border-radius: 999px; background: var(--ki-grid, {c['grid']}); }}
.ki-wx-range-fill {{ position: absolute; top: 0; bottom: 0; border-radius: 999px; background: linear-gradient(90deg, {c['sage']}, {c['warning']}); }}
.ki-attribution {{ color: var(--ki-text-3); font-size: 0.6875rem; margin-top: 10px; }}

/* ---------- Lists, rows, stats ---------- */
.ki-row {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 12px 0; border-bottom: 1px solid var(--ki-border); }}
.ki-row:last-child {{ border-bottom: none; }}
.ki-row-title {{ color: var(--ki-text); font-size: 0.875rem; font-weight: 500; }}
.ki-row-meta {{ color: var(--ki-text-2); font-size: 0.75rem; margin-top: 2px; }}
.ki-row-body {{ color: var(--ki-text-2); font-size: 0.8125rem; margin-top: 3px; line-height: 1.5; }}
.ki-row-icon {{ width: 32px; height: 32px; flex: 0 0 32px; border-radius: 8px; display: flex; align-items: center; justify-content: center; background: var(--ki-accent-soft); color: var(--ki-accent); }}
.ki-stats {{ display: flex; flex-direction: column; margin: 4px 0 16px 0; }}
.ki-stat {{ display: flex; justify-content: space-between; align-items: baseline; gap: 12px; padding: 9px 0; border-bottom: 1px solid var(--ki-border); }}
.ki-stat:last-child {{ border-bottom: none; }}
.ki-stat-label {{ color: var(--ki-text-2); font-size: 0.8125rem; }}
.ki-stat-value {{ color: var(--ki-text); font-size: 0.8125rem; font-weight: 500; white-space: nowrap; }}
.ki-stats--compact {{ margin: 12px 0 0 0; }}
.ki-stats--compact .ki-stat {{ padding: 5px 0; border-bottom: none; }}

/* ---------- Result blocks ---------- */
.ki-hero {{ background: var(--ki-bg-raised); border: 1px solid var(--ki-border); border-radius: var(--ki-radius-sm); padding: 20px 22px; }}
.ki-hero-top {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; }}
.ki-hero-value {{ color: var(--ki-text); font-size: 2.25rem; font-weight: 600; letter-spacing: -0.03em; line-height: 1.15; margin: 8px 0 12px 0; }}
.ki-hero-sub {{ color: var(--ki-text-2); font-size: 0.8125rem; font-weight: 500; margin-top: 8px; }}
.ki-meter {{ height: 6px; border-radius: 999px; background: var(--ki-border); overflow: hidden; }}
.ki-meter-fill {{ height: 100%; border-radius: 999px; transition: width .6s var(--ki-ease); }}
.ki-callout {{ display: flex; gap: 12px; align-items: flex-start; border: 1px solid; border-radius: var(--ki-radius-sm); padding: 14px 16px; }}
.ki-callout-icon {{ display: inline-flex; padding-top: 1px; }}
.ki-callout-title {{ color: var(--ki-text); font-weight: 550; font-size: 0.875rem; }}
.ki-callout-body {{ color: var(--ki-text-2); font-size: 0.8125rem; margin-top: 3px; line-height: 1.55; }}
.ki-quote {{ margin-top: 16px; padding: 14px 16px; border-radius: var(--ki-radius-sm); background: var(--ki-bg-raised); border: 1px solid var(--ki-border); color: var(--ki-text-2); font-size: 0.8125rem; line-height: 1.65; }}
.ki-flag {{ display: flex; gap: 8px; align-items: flex-start; color: var(--ki-text-2); font-size: 0.8125rem; line-height: 1.5; padding: 6px 0; }}
.ki-flag .ki-icon {{ color: var(--ki-warning); margin-top: 2px; }}
.ki-decision {{ background: var(--ki-bg-raised); border: 1px solid var(--ki-border); border-radius: var(--ki-radius); padding: 24px; height: 100%; }}
.ki-decision-title {{ font-size: 1.625rem; font-weight: 600; letter-spacing: -0.02em; margin: 6px 0 10px 0; }}
.ki-decision-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; margin: 18px 0; padding: 16px 0; border-top: 1px solid var(--ki-border); border-bottom: 1px solid var(--ki-border); }}
.ki-decision-num {{ color: var(--ki-text); font-size: 1.125rem; font-weight: 600; margin-top: 4px; letter-spacing: -0.01em; }}
.ki-decision-action {{ display: flex; gap: 10px; align-items: flex-start; color: var(--ki-text-2); font-size: 0.8125rem; line-height: 1.55; }}
.ki-decision-action .ki-icon {{ color: var(--ki-accent); margin-top: 2px; }}
.ki-empty {{ text-align: center; padding: 40px 24px; border: 1px dashed var(--ki-border-strong); border-radius: var(--ki-radius); background: var(--ki-surface); }}
.ki-empty-icon {{ width: 40px; height: 40px; margin: 0 auto 12px auto; border-radius: 10px; display: flex; align-items: center; justify-content: center; color: var(--ki-text-2); background: var(--ki-bg); }}
.ki-empty-title {{ color: var(--ki-text); font-weight: 550; font-size: 0.9375rem; }}
.ki-empty-body {{ color: var(--ki-text-2); font-size: 0.8125rem; margin: 4px auto 0 auto; max-width: 460px; line-height: 1.55; }}
.ki-empty-body code {{ font-size: 0.75rem; background: var(--ki-bg); padding: 1px 5px; border-radius: 4px; }}

/* ---------- Buyer network ---------- */
.ki-buyer {{ padding: 4px 0; }}
.ki-buyer--muted {{ opacity: 0.62; }}
.ki-buyer-head {{ display: flex; flex-wrap: wrap; align-items: center; gap: 6px 8px; margin-bottom: 4px; }}
.ki-buyer-name {{ color: var(--ki-text); font-size: 0.9375rem; font-weight: 550; letter-spacing: -0.01em; margin-right: 2px; }}
.ki-buyer-stats {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: 12px 0 10px 0; }}
.ki-buyer-num {{ color: var(--ki-text); font-size: 1.0625rem; font-weight: 600; letter-spacing: -0.01em; margin-top: 2px; }}
.ki-buyer-foot {{ display: flex; flex-wrap: wrap; gap: 6px; }}
.ki-sep-line {{ border-top: 1px solid var(--ki-border); margin: 4px 0; }}
[data-testid="stPopoverButton"] {{ border-radius: var(--ki-radius-sm) !important; }}

/* ---------- Trend-shift calibration ---------- */
.ki-banner {{ display: flex; align-items: center; gap: 12px; padding: 12px 16px; margin: 4px 0 20px 0; background: var(--tone-soft); border: 1px solid var(--tone-border); border-radius: var(--ki-radius-sm); }}
.ki-banner-icon {{ color: var(--tone); display: inline-flex; }}
.ki-banner-text {{ display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px; flex: 1; min-width: 0; }}
.ki-banner-title {{ color: var(--ki-text); font-size: 0.875rem; font-weight: 550; }}
.ki-banner-meta {{ color: var(--ki-text-2); font-size: 0.8125rem; }}
.ki-scale-labels {{ display: flex; justify-content: space-between; gap: 8px; margin: -6px 0 16px 0; color: var(--ki-text-2); font-size: 0.6875rem; line-height: 1.35; }}
.ki-scale-labels em {{ font-style: normal; color: var(--ki-text-3); }}
.ki-readout {{ margin-top: 8px; padding-top: 16px; border-top: 1px solid var(--ki-border); }}
.ki-readout-value {{ font-size: 1.5rem; font-weight: 600; letter-spacing: -0.02em; margin-top: 6px; }}
.ki-readout-sub {{ color: var(--ki-text-2); font-size: 0.8125rem; margin-top: 2px; }}

/* ---------- Auth ---------- */
.ki-auth-hero {{ text-align: center; padding: 28px 0 24px 0; }}
.ki-auth-mark {{ width: 44px; height: 44px; margin: 0 auto 18px auto; border-radius: 11px; display: flex; align-items: center; justify-content: center; background: var(--ki-forest); color: #FFFFFF; }}
.ki-auth-title {{ color: var(--ki-text) !important; font-size: 2.25rem !important; font-weight: 600 !important; letter-spacing: -0.03em !important; margin: 0 0 10px 0 !important; padding: 0 !important; line-height: 1.12 !important; }}
.ki-auth-sub {{ color: var(--ki-text-2) !important; font-size: 1rem; max-width: 560px; margin: 0 auto !important; line-height: 1.55; }}
.ki-divider-label {{ display: flex; align-items: center; gap: 12px; margin: 20px 0 12px 0; color: var(--ki-text-2); font-size: 0.75rem; font-weight: 500; }}
.ki-divider-label::before, .ki-divider-label::after {{ content: ""; flex: 1; border-top: 1px solid var(--ki-border); }}
.ki-feature-wrap {{ max-width: 1040px; margin: 36px auto 16px auto; }}
.ki-feature-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }}
.ki-feature {{ display: flex; gap: 12px; align-items: flex-start; padding: 18px; background: var(--ki-surface); border: 1px solid var(--ki-border); border-radius: var(--ki-radius); }}
.ki-feature-icon {{ color: var(--ki-accent); display: inline-flex; padding-top: 1px; }}
.ki-feature-title {{ color: var(--ki-text); font-weight: 550; font-size: 0.875rem; }}
.ki-feature-body {{ color: var(--ki-text-2); font-size: 0.8125rem; margin-top: 3px; line-height: 1.5; }}
.ki-security-note {{ display: flex; align-items: center; justify-content: center; gap: 8px; margin-top: 24px; color: var(--ki-text-2); font-size: 0.8125rem; text-align: center; }}

/* ---------- Voice assistant host (the button itself lives in a Shadow DOM attached to the page body) ---------- */
/* Never put an HTML tag inside this stylesheet: st.html's sanitizer drops a style block that contains one. */
.st-key-voice_widget_host {{ display: none !important; }}
[data-testid="stToastContainer"] {{ bottom: 96px !important; }}

/* ---------- Native components ---------- */
[data-testid="stDataFrame"] {{ border: 1px solid var(--ki-border); border-radius: var(--ki-radius-sm); overflow: hidden; }}
[data-testid="stAlert"] {{ border-radius: var(--ki-radius-sm) !important; }}
.modebar {{ display: none !important; }}

/* ---------- Responsive ---------- */
@media (max-width: 900px) {{
    .block-container {{ padding-top: 1.75rem !important; padding-left: 1rem !important; padding-right: 1rem !important; }}
    .ki-page-title {{ font-size: 1.625rem !important; }}
    .ki-topline {{ margin-bottom: 20px; }}
    .ki-decision-grid {{ grid-template-columns: 1fr 1fr; }}
}}
@media (max-width: 640px) {{
    .block-container {{ padding-top: 3.5rem !important; }}
    .ki-topline-date {{ display: none; }}
    [class*="st-key-tiles_"] [data-testid="stHorizontalBlock"] {{ flex-wrap: wrap !important; gap: 12px !important; }}
    [class*="st-key-tiles_"] [data-testid="stColumn"] {{ flex: 1 1 calc(50% - 6px) !important; min-width: calc(50% - 6px) !important; width: calc(50% - 6px) !important; }}
    .ki-kpi {{ padding: 16px; min-height: 0; }}
    .ki-spark {{ display: none; }}
    .ki-wx-temp {{ font-size: 2.75rem; }}
    .ki-decision-grid {{ grid-template-columns: 1fr; }}
    .ki-kpi-value {{ font-size: 1.5rem; }}
    [class*="st-key-card_"] {{ padding: 18px !important; }}
}}
/* Keep the sign-in tabs on one row on phones */
.st-key-auth_tabs [data-testid="stHorizontalBlock"] {{ flex-wrap: nowrap !important; gap: 8px !important; }}
.st-key-auth_tabs [data-testid="stColumn"] {{ min-width: 0 !important; width: auto !important; flex: 1 1 0 !important; }}
@media (max-width: 1100px) {{
    .st-key-auth_tabs button {{ padding: 8px 6px !important; }}
    .st-key-auth_tabs button::before {{ display: none !important; }}
}}
@media (prefers-reduced-motion: reduce) {{
    *, *::before, *::after {{ animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }}
}}
</style>
"""
