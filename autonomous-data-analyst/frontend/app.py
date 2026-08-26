"""
Autonomous Data Analyst - Modern Slate Dark UI
Sophisticated Tailwind-inspired Slate/Charcoal palette with interactive
dataset cards, visual chart gallery, and live HTML report previews.
"""

from pathlib import Path
import json
from html import escape
import requests
import streamlit as st
import streamlit.components.v1 as components

from ui_assets import load_presentation_assets

# -----------------------------------------------------------------------------
# Configuration & Paths
# -----------------------------------------------------------------------------
API = "http://127.0.0.1:8000"
WORKSPACE_DIR = Path(__file__).resolve().parent.parent / "workspace"
CHARTS_DIR = Path(__file__).resolve().parent.parent / "backend" / "charts"
REPORTS_DIR = WORKSPACE_DIR / "reports"

st.set_page_config(
    page_title="Autonomous Data Analyst",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------
def format_count(val) -> str:
    """Safely format numbers with commas without raising ValueError."""
    if val is None:
        return "N/A"
    if isinstance(val, (int, float)):
        return f"{int(val):,}"
    if isinstance(val, str):
        val_clean = val.replace(",", "").strip()
        if val_clean.isdigit():
            return f"{int(val_clean):,}"
        return val
    return str(val)


# Presentation assets are optional to the application flow. Keeping this call
# separate makes it easy to study the Streamlit/FastAPI code without reading CSS.
load_presentation_assets()

# -----------------------------------------------------------------------------
# API Helper Functions
# -----------------------------------------------------------------------------
def check_backend_health() -> bool:
    """Return whether the FastAPI service is reachable before sending chat requests."""
    try:
        res = requests.get(f"{API}/", timeout=1.5)
        return res.status_code == 200
    except Exception:
        return False


def create_session(title: str = "New Chat") -> str | None:
    """Ask FastAPI to create a conversation and return its ID."""
    try:
        response = requests.post(f"{API}/sessions", json={"title": title}, timeout=5)
        if response.status_code == 200:
            return response.json()["session_id"]
    except Exception:
        pass
    return None


def load_sessions() -> list:
    """Load the conversations shown in the sidebar."""
    try:
        response = requests.get(f"{API}/sessions", timeout=5)
        if response.status_code == 200:
            return response.json().get("sessions", [])
    except Exception:
        pass
    return []


def load_session_details(session_id: str) -> dict | None:
    """Load messages and the active dataset for one conversation."""
    try:
        response = requests.get(f"{API}/sessions/{session_id}", timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None


def chart_url(chart: str) -> str:
    """Convert a backend chart path into a URL the browser can display."""
    chart_clean = chart.lstrip("/")
    if not chart_clean.startswith("charts/"):
        chart_clean = f"charts/{chart_clean}"
    return f"{API}/{chart_clean}"


# -----------------------------------------------------------------------------
# State Management
# -----------------------------------------------------------------------------
def init_app_state():
    if "session_id" not in st.session_state:
        sessions = load_sessions()
        if sessions:
            st.session_state.session_id = sessions[0]["session_id"]
        else:
            new_id = create_session()
            st.session_state.session_id = new_id

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "current_dataset" not in st.session_state:
        st.session_state.current_dataset = None

    if "current_title" not in st.session_state:
        st.session_state.current_title = "New Chat"

    if "uploaded_file_key" not in st.session_state:
        st.session_state.uploaded_file_key = None

    if "session_loaded" not in st.session_state:
        st.session_state.session_loaded = False


def restore_active_session(session_id: str) -> bool:
    """Copy one session's saved API data into Streamlit session state."""
    data = load_session_details(session_id)
    if not data:
        return False

    st.session_state.session_id = session_id
    st.session_state.messages = []

    for message in data.get("messages", []):
        role = message.get("role")
        if role in {"user", "assistant"}:
            st.session_state.messages.append({
                "role": role,
                "content": message.get("content", ""),
                "charts": message.get("charts", []),
                "report_path": message.get("report_path")
            })

    session_info = data.get("session", {})
    st.session_state.current_title = session_info.get("title", "New Chat")
    st.session_state.current_dataset = data.get("current_dataset")

    if st.session_state.current_dataset:
        dataset = st.session_state.current_dataset
        st.session_state.uploaded_file_key = f"{dataset.get('filename')}_{dataset.get('version')}"
    else:
        st.session_state.uploaded_file_key = None

    st.session_state.session_loaded = True
    return True


init_app_state()

if not st.session_state.session_loaded and st.session_state.session_id:
    restore_active_session(st.session_state.session_id)


# -----------------------------------------------------------------------------
# Clean Top Navigation Header
# -----------------------------------------------------------------------------
backend_online = check_backend_health()
status_indicator = (
    '<span class="status-badge online"><span class="status-dot"></span> Backend Active</span>'
    if backend_online
    else '<span class="status-badge offline"><span class="status-dot"></span> Backend Offline</span>'
)

st.markdown(
    f"""
    <div class="app-header-clean">
        <div class="header-content">
            <div class="header-brand">
                <div class="brand-logo">⚡</div>
                <div>
                    <h1 class="header-title">Autonomous Data Analyst</h1>
                    <p class="header-subtitle">Multi-Agent Data Intelligence &bull; Gemini 2.5 &bull; Automated Reports</p>
                </div>
            </div>
            <div>
                {status_indicator}
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# -----------------------------------------------------------------------------
# Sidebar: Clean Session Navigation & Upload Manager
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-brand-card">
            <div class="sidebar-brand-icon">⚡</div>
            <div>
                <div class="sidebar-brand-text">Analyst Workspace</div>
                <div class="sidebar-brand-subtitle">Autonomous AI Agent</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("✨  **New Conversation**", width='stretch', type="primary"):
        new_sid = create_session()
        if new_sid:
            st.session_state.session_id = new_sid
            st.session_state.messages = []
            st.session_state.current_dataset = None
            st.session_state.current_title = "New Chat"
            st.session_state.uploaded_file_key = None
            st.session_state.session_loaded = True
            st.rerun()

    sessions = load_sessions()
    session_count = len(sessions)

    st.markdown(
        f"""
        <div class="sidebar-section-header">
            <span class="sidebar-section-title">Chat History</span>
            <span class="sidebar-count-badge">{session_count}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if sessions:
        with st.container(height=230):
            for s in sessions:
                sid = s["session_id"]
                stitle = s.get("title", "New Chat")
                is_active = sid == st.session_state.session_id
                btn_icon = "📍" if is_active else "💬"
                label = f"{btn_icon} {stitle}"

                if st.button(
                    label,
                    key=f"session_btn_{sid}",
                    width='stretch',
                    type="primary" if is_active else "secondary",
                ):
                    if sid != st.session_state.session_id:
                        restore_active_session(sid)
                        st.rerun()

    if st.button("🗑️ Delete Conversation", width='stretch', help="Delete active conversation"):
        if st.session_state.session_id:
            requests.delete(f"{API}/sessions/{st.session_state.session_id}", timeout=5)
            remaining = load_sessions()
            if remaining:
                restore_active_session(remaining[0]["session_id"])
            else:
                new_sid = create_session()
                st.session_state.session_id = new_sid
                st.session_state.messages = []
                st.session_state.current_dataset = None
                st.session_state.current_title = "New Chat"
                st.session_state.uploaded_file_key = None
                st.session_state.session_loaded = True
            st.rerun()

    st.markdown(
        """
        <div class="sidebar-section-header dataset-section-header">
            <span class="sidebar-section-title">Dataset Manager</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Dataset Upload Section
    uploader_key = f"uploader_{st.session_state.session_id}"
    uploaded_file = st.file_uploader(
        "Upload CSV or Excel (.xlsx)",
        type=["csv", "xlsx"],
        key=uploader_key,
        help="Upload tabular data to analyze with pandas & matplotlib.",
        label_visibility="collapsed",
    )

    if uploaded_file is not None:
        file_key = f"{uploaded_file.name}_{uploaded_file.size}"
        current_dataset = st.session_state.current_dataset
        current_filename = current_dataset.get("filename") if current_dataset else None

        already_uploaded = file_key == st.session_state.uploaded_file_key
        same_name = current_filename == uploaded_file.name

        if not already_uploaded and not same_name:
            with st.spinner("Indexing dataset..."):
                try:
                    upload_res = requests.post(
                        f"{API}/upload",
                        params={"session_id": st.session_state.session_id},
                        files={"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)},
                        timeout=15,
                    )
                    if upload_res.status_code == 200:
                        info = upload_res.json()
                        st.session_state.current_dataset = {
                            "dataset_id": info["dataset_id"],
                            "filename": info["filename"],
                            "version": info["version"],
                            "rows": info.get("rows"),
                            "columns": info.get("columns", []),
                            "metadata": info.get("metadata", ""),
                        }
                        st.session_state.uploaded_file_key = file_key
                        st.success(f"✅ Loaded {info['filename']}")
                        st.rerun()
                    else:
                        st.error(f"Upload failed: {upload_res.text}")
                except Exception as exc:
                    st.error(f"Upload error: {exc}")
        elif same_name:
            st.session_state.uploaded_file_key = file_key

    if st.session_state.current_dataset:
        active_filename = escape(st.session_state.current_dataset.get("filename", "Dataset"))
        st.markdown(
            f"""
            <div class="uploaded-file-card">
                <span aria-hidden="true">📄</span>
                <div>
                    <div class="file-name">{active_filename}</div>
                    <div class="file-status">Uploaded and ready for analysis</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Capability tags card
    st.markdown(
        """
        <div class="capability-footer-card">
            <div class="capability-heading">
                <span>⚡</span> Agent Engines
            </div>
            <div class="capability-chip-grid">
                <span class="cap-chip"><span class="chip-icon">📊</span> Pandas</span>
                <span class="cap-chip"><span class="chip-icon">📈</span> Matplotlib</span>
                <span class="cap-chip"><span class="chip-icon">🌐</span> Serper AI</span>
                <span class="cap-chip"><span class="chip-icon">🛡️</span> Validator</span>
                <span class="cap-chip"><span class="chip-icon">📑</span> Reports</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# -----------------------------------------------------------------------------
# Active Dataset Stats Floating Bar (if dataset uploaded)
# -----------------------------------------------------------------------------
if st.session_state.current_dataset:
    ds = st.session_state.current_dataset
    filename = ds.get("filename", "Dataset")
    version = ds.get("version", 1)
    rows_val = ds.get("rows", "Active")
    cols = ds.get("columns", [])
    col_count = len(cols) if cols else "N/A"

    st.markdown(
        f"""
        <div class="dataset-banner">
            <div class="dataset-info-left">
                <div class="dataset-icon-wrap">📊</div>
                <div>
                    <h3 class="dataset-name-text">{filename}</h3>
                    <p class="dataset-sub-text">Active Session Dataset &bull; Version {version}</p>
                </div>
            </div>
            <div class="dataset-metrics-row">
                <div class="mini-stat">
                    <div class="mini-stat-label">Total Rows</div>
                    <div class="mini-stat-val">{format_count(rows_val)}</div>
                </div>
                <div class="mini-stat">
                    <div class="mini-stat-label">Columns</div>
                    <div class="mini-stat-val">{col_count}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("🔍 **View Dataset Schema & Metadata**", expanded=False):
        metadata_text = ds.get("metadata", "")
        if metadata_text:
            st.code(metadata_text, language="yaml")
        elif cols:
            st.write(f"**Columns:** {', '.join(str(c) for c in cols)}")
        else:
            st.caption("Schema metadata loaded.")


# -----------------------------------------------------------------------------
# Hero / Empty State View (When conversation is fresh)
# -----------------------------------------------------------------------------
if not st.session_state.messages:
    st.markdown(
        """
        <div class="bento-hero">
            <div class="hero-heading">What would you like to discover today?</div>
            <div class="hero-subheading">Upload a dataset or choose an analysis template below to trigger automated statistical modeling, visualizations, and validated reports.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📊 **Full Exploratory Data Analysis**\n\nGenerate comprehensive summary statistics, missing value profiles, and distributions.", width='stretch'):
            st.session_state["preset_prompt"] = "Perform a thorough exploratory data analysis on this dataset. Summarize distributions, check missing values, and highlight key statistical patterns."
            st.rerun()

        if st.button("📈 **Correlation Matrix & Visualizations**\n\nIdentify top numerical relationships and plot high-impact charts.", width='stretch'):
            st.session_state["preset_prompt"] = "Analyze the correlation between numerical variables, identify the strongest relationships, and create a visual chart."
            st.rerun()

    with col2:
        if st.button("📑 **Generate Validated HTML Report**\n\nProduce an executive HTML report with embedded charts and research.", width='stretch'):
            st.session_state["preset_prompt"] = "Create a comprehensive HTML report named executive_data_analysis with statistical breakdowns and visualizations."
            st.rerun()

        if st.button("🌐 **Contextual Web Research Comparison**\n\nCompare dataset trends against recent external public statistics.", width='stretch'):
            st.session_state["preset_prompt"] = "Analyze the primary variables in this dataset and compare the findings with recent external real-world statistics from the web."
            st.rerun()


# -----------------------------------------------------------------------------
# Report Artifact Component (Download + Embedded Preview)
# -----------------------------------------------------------------------------
def render_report_artifact(report_path: str):
    rep_file = Path(__file__).resolve().parent.parent / report_path
    if not rep_file.exists():
        safe_name = Path(report_path).name
        rep_file = REPORTS_DIR / safe_name

    if not rep_file.exists():
        st.info(f"📄 **Report published at:** `{report_path}`")
        return

    content_bytes = rep_file.read_bytes()
    suffix = rep_file.suffix.lower()
    filename = rep_file.name

    st.markdown(
        f"""
        <div class="report-showcase">
            <div class="report-header">
                <div class="report-title-wrap">
                    <span class="report-icon">📑</span>
                    <span class="report-filename">{filename}</span>
                </div>
                <span class="report-badge">{suffix.upper().replace('.', '')} Document</span>
            </div>
            <p class="report-description">
                Validated analysis report generated with embedded charts and epidemiological context.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c_dl, c_prev = st.columns([1, 3])
    with c_dl:
        st.download_button(
            label=f"⬇️ Download {suffix.upper().replace('.', '')}",
            data=content_bytes,
            file_name=filename,
            mime="text/html" if suffix == ".html" else "text/markdown",
            width='stretch',
            key=f"dl_btn_{filename}_{len(content_bytes)}",
        )

    with st.expander(f"👁️ **Interactive Live Preview: {filename}**", expanded=False):
        if suffix == ".html":
            html_content = content_bytes.decode(encoding="utf-8", errors="ignore")
            st.html(html_content)
        else:
            text_content = content_bytes.decode(encoding="utf-8", errors="ignore")
            st.markdown(text_content)


# -----------------------------------------------------------------------------
# Chat Feed Rendering
# -----------------------------------------------------------------------------
for msg_idx, msg in enumerate(st.session_state.messages):
    role = msg.get("role", "assistant")
    avatar = "👤" if role == "user" else "⚡"

    with st.chat_message(role, avatar=avatar):
        if role == "user":
            st.markdown('<div class="chat-bubble-marker-user chat-bubble-marker"></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="chat-bubble-marker-assistant chat-bubble-marker"></div>', unsafe_allow_html=True)
        st.markdown(msg.get("content", ""))

        # Charts Display
        charts = msg.get("charts", [])
        if charts:
            st.markdown("##### 📊 Visual Artifacts")
            chart_columns = st.columns(min(len(charts), 2))
            for c_idx, chart in enumerate(charts):
                with chart_columns[c_idx % len(chart_columns)]:
                    img_url = chart_url(chart)
                    st.image(img_url, width='stretch')

                    c_name = Path(chart).name
                    local_chart_file = CHARTS_DIR / c_name
                    if local_chart_file.exists():
                        st.download_button(
                            label=f"⬇️ Download {c_name}",
                            data=local_chart_file.read_bytes(),
                            file_name=c_name,
                            mime="image/png",
                            key=f"chart_btn_{msg_idx}_{c_idx}",
                            width='stretch',
                        )

        # Reports Display
        report_path = msg.get("report_path")
        if report_path:
            render_report_artifact(report_path)


# -----------------------------------------------------------------------------
# Chat Input & Agent Invocation
# -----------------------------------------------------------------------------
preset_query = st.session_state.pop("preset_prompt", None)
chat_query = st.chat_input("Ask a question, generate visualizations, or export reports...") or preset_query

if chat_query:
    if not backend_online:
        st.error("❌ Backend server is offline. Please start FastAPI with `uvicorn main:app --reload`.")
        st.stop()

    st.session_state.messages.append({
        "role": "user",
        "content": chat_query,
        "charts": [],
        "report_path": None,
    })

    with st.chat_message("user", avatar="👤"):
        st.markdown('<div class="chat-bubble-marker-user chat-bubble-marker"></div>', unsafe_allow_html=True)
        st.markdown(chat_query)

    with st.chat_message("assistant", avatar="⚡"):
        st.markdown('<div class="chat-bubble-marker-assistant chat-bubble-marker"></div>', unsafe_allow_html=True)
        with st.status("🧠 **Agent analyzing data & verifying claims...**", expanded=True) as status_box:
            st.write("• 🧭 **Coordinator**: Structuring execution plan & required capabilities...")
            st.write("• 🔬 **Analyst**: Executing pandas operations & charting tools...")
            st.write("• 🛡️ **Validator**: Reviewing output against evidence and publishing report...")

            try:
                res = requests.post(
                    f"{API}/chat",
                    json={
                        "session_id": st.session_state.session_id,
                        "message": chat_query,
                    },
                    timeout=180,
                )

                if res.status_code == 200:
                    data = res.json()
                    ans = data.get("response", "")
                    charts_res = data.get("charts", [])
                    rep_path = data.get("report_path")
                    updated_title = data.get("title")

                    if updated_title:
                        st.session_state.current_title = updated_title

                    status_box.update(label="✅ **Analysis verified & completed!**", state="complete", expanded=False)

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": ans,
                        "charts": charts_res,
                        "report_path": rep_path,
                    })

                    st.markdown(ans)

                    if charts_res:
                        st.markdown("##### 📊 Visual Artifacts")
                        c_cols = st.columns(min(len(charts_res), 2))
                        for i, ch in enumerate(charts_res):
                            with c_cols[i % len(c_cols)]:
                                st.image(chart_url(ch), width='stretch')

                    if rep_path:
                        render_report_artifact(rep_path)

                    st.rerun()

                else:
                    err_text = f"Backend Error ({res.status_code}): {res.text}"
                    status_box.update(label="❌ **Execution Failed**", state="error")
                    st.error(err_text)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": err_text,
                        "charts": [],
                        "report_path": None,
                    })

            except requests.exceptions.Timeout:
                status_box.update(label="⏱️ **Execution Timeout**", state="error")
                st.error("Request timed out waiting for backend agent.")
            except Exception as e:
                status_box.update(label="❌ **Connection Error**", state="error")
                st.error(f"Failed to communicate with agent backend: {e}")

