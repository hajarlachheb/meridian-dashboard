import streamlit as st
import pandas as pd
from utils.data_loader import generate_sample_data, load_meridian_excel
from utils.charts import GLOBAL_CSS, sidebar_logo

st.set_page_config(
    page_title="s360 — Meridian MMM Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def init_session_state():
    if "data" not in st.session_state:
        st.session_state.data = None
    if "data_source" not in st.session_state:
        st.session_state.data_source = None


init_session_state()

with st.sidebar:
    sidebar_logo()
    st.markdown("---")
    if st.session_state.data_source:
        st.caption(f"Source: {st.session_state.data_source}")
        st.markdown("---")
    st.markdown(
        "<div style='text-align:center; color:#94A3B8; font-size:0.72rem; padding-top:0.5rem;'>"
        "Powered by Google Meridian<br>Marketing Mix Model"
        "</div>",
        unsafe_allow_html=True,
    )

if st.session_state.data is None:
    st.markdown(
        """
        <div style="display:flex; flex-direction:column; align-items:center;
                    justify-content:center; min-height:65vh; text-align:center;">
            <h1 style="font-size:2.4rem; color:#1E293B;
                font-weight:800; margin-bottom:0.4rem; line-height:1.2;">
                Meridian MMM Dashboard
            </h1>
            <p style="color:#64748B; font-size:1.05rem; max-width:480px; margin:0 auto 2rem;">
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
            """<div style="background:#F8F9FC; border:1px solid #E2E8F0;
                border-radius:14px; padding:1.8rem; text-align:center;">
                <p style="color:#64748B; font-size:0.92rem; margin-bottom:0.75rem; font-weight:500;">
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

        st.markdown(
            "<div style='text-align:center; margin:1rem 0;'>"
            "<span style='color:#94A3B8; font-size:0.85rem;'>— or —</span></div>",
            unsafe_allow_html=True,
        )

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
