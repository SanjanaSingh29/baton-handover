"""Shared look and feel: the colourful bento theme, tiles and status badges."""
import html

import streamlit as st

# (fill, border, text) for each tile colour
PALETTE = {
    "mint": ("#E1F5EE", "#9FE1CB", "#085041"),
    "coral": ("#FAECE7", "#F5C4B3", "#712B13"),
    "pink": ("#FBEAF0", "#F4C0D1", "#72243E"),
    "purple": ("#EEEDFE", "#CECBF6", "#3C3489"),
    "amber": ("#FAEEDA", "#FAC775", "#633806"),
    "green": ("#EAF3DE", "#C0DD97", "#27500A"),
}

# (fill, text) for each evidence status badge
STATUS_COLORS = {
    "Verified": ("#C0DD97", "#27500A"),
    "Inferred": ("#CECBF6", "#3C3489"),
    "Conflicting": ("#FAC775", "#633806"),
    "Missing": ("#F5C4B3", "#712B13"),
    "Unverified": ("#EDE8E0", "#5F5E5A"),
}

SENSITIVITY_COLORS = {
    "Open": ("#C0DD97", "#27500A"),
    "Team": ("#CECBF6", "#3C3489"),
    "Restricted": ("#F5C4B3", "#712B13"),
}

CSS = """
<style>
.block-container {padding-top: 2rem; max-width: 1100px;}
.baton-tile {border-radius: 16px; padding: 14px 16px; margin-bottom: 12px; border: 1px solid;}
.baton-title {font-weight: 600; font-size: 15px; margin-bottom: 6px;}
.baton-big {font-size: 30px; font-weight: 600; line-height: 1.2;}
.baton-small {font-size: 13px; opacity: 0.85;}
.baton-badge {display: inline-block; font-size: 12px; font-weight: 600; padding: 2px 10px;
              border-radius: 10px; white-space: nowrap;}
.baton-row {display: flex; justify-content: space-between; align-items: center; gap: 8px;
            padding: 6px 0; font-size: 14px;}
.baton-quote {background: #FAC775; color: #633806; padding: 1px 4px; border-radius: 4px;}
</style>
"""


def apply_theme():
    st.markdown(CSS, unsafe_allow_html=True)


def esc(text):
    """Always escape text that came from files or the AI before putting it in HTML."""
    return html.escape("" if text is None else str(text))


def badge(label, colors=None):
    fill, text = (colors or STATUS_COLORS).get(label, STATUS_COLORS["Unverified"])
    return f'<span class="baton-badge" style="background:{fill};color:{text}">{esc(label)}</span>'


def sensitivity_badge(label):
    return badge(label, SENSITIVITY_COLORS)


def tile(title, body_html, color="mint"):
    """Draw one bento tile. body_html must already be escaped and on one line."""
    fill, border, text = PALETTE[color]
    st.markdown(
        f'<div class="baton-tile" style="background:{fill};border-color:{border};color:{text}">'
        f'<div class="baton-title">{esc(title)}</div>{body_html}</div>',
        unsafe_allow_html=True,
    )


def metric_tile(label, value, color="mint", note=""):
    body = f'<div class="baton-big">{esc(value)}</div>'
    if note:
        body += f'<div class="baton-small">{esc(note)}</div>'
    tile(label, body, color)


def row(left_html, right_html=""):
    return f'<div class="baton-row"><span>{left_html}</span><span>{right_html}</span></div>'