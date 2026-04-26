"""Light medical theme — design token definitions and ttk Style setup."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# ── Design Tokens ────────────────────────────────────────────────────────────
BG_CANVAS  = "#F7FAFC"
BG_SURFACE = "#FFFFFF"
BG_SUBTLE  = "#EEF3F7"

TEXT_PRIMARY   = "#1F2D3D"
TEXT_SECONDARY = "#5A6B7B"
TEXT_MUTED     = "#8FA0B0"

ACCENT_PRIMARY = "#2E7DD7"
ACCENT_SOFT    = "#E6F0FB"

STATE_HEALTHY  = "#2BB673"
STATE_WARNING  = "#F5A623"
STATE_CRITICAL = "#E5484D"
STATE_UNKNOWN  = "#8FA0B0"

DIVIDER = "#E3EAF1"

FONT_FAMILY = "Segoe UI"
FONT_SM   = (FONT_FAMILY, 11)
FONT_BASE = (FONT_FAMILY, 13)
FONT_LG   = (FONT_FAMILY, 16, "bold")
FONT_XL   = (FONT_FAMILY, 22, "bold")
FONT_SCORE = (FONT_FAMILY, 52, "bold")

CARD_RADIUS = 12
PAD = 12


def severity_color(severity_value: str) -> str:
    return {
        "healthy": STATE_HEALTHY,
        "warning": STATE_WARNING,
        "critical": STATE_CRITICAL,
    }.get(severity_value, STATE_UNKNOWN)


def score_color(score: int) -> str:
    if score >= 90:
        return STATE_HEALTHY
    if score >= 70:
        return STATE_WARNING
    return STATE_CRITICAL


def apply(root: tk.Tk) -> None:
    """Apply the light medical theme to the root Tk instance."""
    root.configure(bg=BG_CANVAS)
    style = ttk.Style(root)

    # Try modern themes
    for candidate in ("clam", "alt", "default"):
        try:
            style.theme_use(candidate)
            break
        except tk.TclError:
            pass

    # ── Frame variants ──────────────────────────────────────────────────────
    style.configure("TFrame", background=BG_CANVAS)
    style.configure("Surface.TFrame", background=BG_SURFACE)
    style.configure("Subtle.TFrame", background=BG_SUBTLE)
    style.configure("Accent.TFrame", background=ACCENT_SOFT)

    # ── Label variants ──────────────────────────────────────────────────────
    _label_base = dict(background=BG_CANVAS, foreground=TEXT_PRIMARY, font=FONT_BASE)
    style.configure("TLabel", **_label_base)
    style.configure("Secondary.TLabel", **{**_label_base, "foreground": TEXT_SECONDARY, "font": FONT_SM})
    style.configure("Muted.TLabel", **{**_label_base, "foreground": TEXT_MUTED, "font": FONT_SM})
    style.configure("Title.TLabel", **{**_label_base, "font": FONT_XL})
    style.configure("Heading.TLabel", **{**_label_base, "font": FONT_LG})
    style.configure("Score.TLabel", **{**_label_base, "font": FONT_SCORE, "foreground": ACCENT_PRIMARY})

    style.configure("Healthy.TLabel",  **{**_label_base, "foreground": STATE_HEALTHY, "font": FONT_BASE})
    style.configure("Warning.TLabel",  **{**_label_base, "foreground": STATE_WARNING, "font": FONT_BASE})
    style.configure("Critical.TLabel", **{**_label_base, "foreground": STATE_CRITICAL, "font": FONT_BASE})

    style.configure("Card.TLabel",  **{**_label_base, "background": BG_SURFACE})
    style.configure("CardSm.TLabel",  **{**_label_base, "background": BG_SURFACE, "foreground": TEXT_SECONDARY, "font": FONT_SM})

    # ── Button ──────────────────────────────────────────────────────────────
    style.configure(
        "Accent.TButton",
        background=ACCENT_PRIMARY,
        foreground="#FFFFFF",
        font=(FONT_FAMILY, 12, "bold"),
        padding=(16, 8),
        relief="flat",
        borderwidth=0,
    )
    style.map(
        "Accent.TButton",
        background=[("active", "#1D6BBF"), ("disabled", "#B0C4DE")],
    )
    style.configure(
        "Ghost.TButton",
        background=BG_CANVAS,
        foreground=ACCENT_PRIMARY,
        font=(FONT_FAMILY, 11),
        padding=(8, 4),
        relief="flat",
        borderwidth=0,
    )
    style.map(
        "Ghost.TButton",
        background=[("active", ACCENT_SOFT)],
    )

    # ── Separator ───────────────────────────────────────────────────────────
    style.configure("TSeparator", background=DIVIDER)

    # ── Progressbar ─────────────────────────────────────────────────────────
    style.configure(
        "Scan.Horizontal.TProgressbar",
        troughcolor=BG_SUBTLE,
        background=ACCENT_PRIMARY,
        thickness=4,
        borderwidth=0,
    )

    # ── Scrollbar ───────────────────────────────────────────────────────────
    style.configure(
        "TScrollbar",
        troughcolor=BG_SUBTLE,
        background=TEXT_MUTED,
        arrowcolor=TEXT_MUTED,
        borderwidth=0,
        relief="flat",
    )
