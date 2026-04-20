import streamlit as st
import pandas as pd
from utils.data_loader import generate_sample_data, load_meridian_excel

st.set_page_config(
    page_title="Meridian MMM Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Hide the default "app" entry in sidebar nav */
[data-testid="stSidebarNav"] li:first-child { display: none; }

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0F172A 0%, #1E293B 100%);
    border-right: 1px solid rgba(100,116,139,0.2);
}

[data-testid="stSidebar"] [data-testid="stMarkdown"] h1 {
    background: linear-gradient(135deg, #6366F1, #EC4899);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-weight: 700;
    font-size: 1.5rem;
    letter-spacing: -0.02em;
}

div[data-testid="stMetric"] {
    background: linear-gradient(135deg, rgba(99,102,241,0.1), rgba(236,72,153,0.05));
    border: 1px solid rgba(99,102,241,0.2);
    border-radius: 12px;
    padding: 1rem 1.2rem;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}

div[data-testid="stMetric"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(99,102,241,0.15);
}

div[data-testid="stMetric"] label {
    color: #94A3B8 !important;
    font-size: 0.8rem !important;
    font-weight: 500 !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: #F1F5F9 !important;
    font-weight: 700 !important;
    font-size: 1.8rem !important;
}

.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    background: rgba(15,23,42,0.5);
    border-radius: 12px;
    padding: 4px;
}

.stTabs [data-baseweb="tab"] {
    border-radius: 8px;
    padding: 8px 20px;
    font-weight: 500;
    color: #94A3B8;
}

.stTabs [aria-selected="true"] {
    background: rgba(99,102,241,0.2) !important;
    color: #E2E8F0 !important;
}

[data-testid="stFileUploader"] {
    border: 2px dashed rgba(99,102,241,0.3);
    border-radius: 12px;
    padding: 1rem;
    transition: border-color 0.3s;
}

[data-testid="stFileUploader"]:hover {
    border-color: rgba(99,102,241,0.6);
}

div.stButton > button {
    background: linear-gradient(135deg, #6366F1, #8B5CF6);
    color: white;
    border: none;
    border-radius: 8px;
    padding: 0.5rem 2rem;
    font-weight: 600;
    transition: all 0.3s ease;
}

div.stButton > button:hover {
    background: linear-gradient(135deg, #4F46E5, #7C3AED);
    box-shadow: 0 4px 15px rgba(99,102,241,0.4);
    transform: translateY(-1px);
}

[data-testid="stDataFrame"] {
    border-radius: 12px;
    overflow: hidden;
}

h1, h2, h3 {
    letter-spacing: -0.02em;
}

hr {
    border: none;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(99,102,241,0.3), transparent);
}
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def init_session_state():
    if "data" not in st.session_state:
        st.session_state.data = None
    if "data_source" not in st.session_state:
        st.session_state.data_source = None


init_session_state()

with st.sidebar:
    st.markdown("# Meridian MMM")
    st.markdown("*Marketing Mix Modelling Dashboard*")
    st.markdown("---")

    if st.session_state.data_source:
        st.caption(f"Source: {st.session_state.data_source}")
        st.markdown("---")

    st.markdown(
        "<div style='text-align:center; color:#64748B; font-size:0.75rem; padding-top:1rem;'>"
        "Powered by Google Meridian<br>"
        "Marketing Mix Model"
        "</div>",
        unsafe_allow_html=True,
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MAIN CONTENT — Upload-first landing
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if st.session_state.data is None:
    st.markdown(
        """
        <div style="display:flex; flex-direction:column; align-items:center;
                    justify-content:center; min-height:70vh; text-align:center;">
            <div style="font-size:3.5rem; margin-bottom:1rem;">📊</div>
            <h1 style="font-size:2.6rem; background:linear-gradient(135deg,#6366F1,#EC4899);
                -webkit-background-clip:text; -webkit-text-fill-color:transparent;
                font-weight:800; margin-bottom:0.5rem; line-height:1.2;">
                Meridian MMM Dashboard
            </h1>
            <p style="color:#94A3B8; font-size:1.1rem; max-width:500px; margin:0 auto 2.5rem;">
                Upload your Google Meridian Marketing Mix Model output
                to unlock interactive insights and budget optimization.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.markdown(
            """<div style="background: linear-gradient(135deg, rgba(99,102,241,0.08), rgba(236,72,153,0.04));
                border:1px solid rgba(99,102,241,0.25); border-radius:16px; padding:2rem; text-align:center;">
                <p style="color:#CBD5E1; font-size:0.95rem; margin-bottom:1rem; font-weight:500;">
                    Upload your Excel file to get started
                </p>
            </div>""",
            unsafe_allow_html=True,
        )

        uploaded_file = st.file_uploader(
            "Upload Meridian Excel Output",
            type=["xlsx", "xls"],
            help="Upload the Excel file exported from your Google Meridian MMM run",
            label_visibility="collapsed",
        )

        if uploaded_file is not None:
            try:
                st.session_state.data = load_meridian_excel(uploaded_file)
                st.session_state.data_source = f"📄 {uploaded_file.name}"
                st.rerun()
            except Exception as e:
                st.error(f"Error loading file: {str(e)}")

        st.markdown("<div style='text-align:center; margin:1rem 0;'>"
                    "<span style='color:#475569; font-size:0.85rem;'>— or —</span></div>",
                    unsafe_allow_html=True)

        if st.button("Load Sample Data", use_container_width=True):
            st.session_state.data = generate_sample_data()
            st.session_state.data_source = "🔬 Sample Data (Simulated)"
            st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("Supported Excel formats"):
            st.markdown(
                """
**Google Meridian Looker Studio export** (auto-detected):

| Sheet | Contents |
|---|---|
| `MediaROI` | Channel ROI, spend, confidence intervals |
| `ModelDiagnostics` | R², MAPE, wMAPE |
| `ModelFit` | Weekly predicted vs. actual |
| `MediaOutcome` | Incremental outcome per channel |
| `MediaSpend` | Spend share per channel |
| `response_curves` | Spend vs. incremental outcome |
| `budget_opt_results` | Optimized allocation |

**Simple format** also supported — sheets: `media_summary`, `model_fit`, `weekly_decomposition`, `response_curves`
                """
            )

else:
    st.switch_page("pages/1_🏠_Home.py")
