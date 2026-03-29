from __future__ import annotations

import streamlit as st

THEMES = {
    "Dark Pro": {
        "background": "#0E1117",
        "surface": "#1C2230",
        "text": "#EAF0FF",
        "accent": "#4F8CFF",
    },
    "Bright Clean": {
        "background": "#FAFBFF",
        "surface": "#FFFFFF",
        "text": "#0C1B33",
        "accent": "#0F62FE",
    },
    "Emerald": {
        "background": "#081C15",
        "surface": "#1B4332",
        "text": "#D8F3DC",
        "accent": "#52B788",
    },
}


def apply_theme(theme_name: str) -> None:
    selected = THEMES.get(theme_name, THEMES["Dark Pro"])
    st.markdown(
        f"""
        <style>
            .stApp {{background: {selected['background']}; color: {selected['text']};}}
            div[data-testid='stMetric'] {{background: {selected['surface']}; padding: 10px; border-radius: 8px;}}
            .stButton > button {{background: {selected['accent']}; color: white; border: 0;}}
        </style>
        """,
        unsafe_allow_html=True,
    )
