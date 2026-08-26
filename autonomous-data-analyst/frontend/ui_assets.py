"""Load optional presentation assets separately from the Streamlit app flow."""

from pathlib import Path

import streamlit as st


FRONTEND_DIR = Path(__file__).resolve().parent
STYLES_DIR = FRONTEND_DIR / "styles"
SCRIPTS_DIR = FRONTEND_DIR / "scripts"


def _read_asset(asset_path: Path) -> str:
    """Read one CSS or JavaScript asset from the frontend folder."""
    return asset_path.read_text(encoding="utf-8")


def load_presentation_assets() -> None:
    """Inject optional CSS and browser behavior without mixing it into app.py."""
    st.markdown(
        _read_asset(STYLES_DIR / "app.css"),
        unsafe_allow_html=True,
    )

    for script_name in ("sidebar_state.js", "sidebar_theme.js"):
        st.html(f"<script>{_read_asset(SCRIPTS_DIR / script_name)}</script>")
