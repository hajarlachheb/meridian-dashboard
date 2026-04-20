import streamlit as st
import pandas as pd
from utils.data_loader import generate_sample_data, load_meridian_excel
from utils.charts import GLOBAL_CSS, sidebar_logo, get_logo_base64

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


@st.dialog("Load Data", width="large")
def upload_dialog():
    st.markdown(
        "<p style='color:#64748B; font-size:0.95rem; margin-bottom:1.25rem;'>"
        "Upload your Google Meridian Excel output to get started.</p>",
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
            with st.spinner("Processing..."):
                st.session_state.data = load_meridian_excel(uploaded_file)
                st.session_state.data_source = f"📄 {uploaded_file.name}"
            st.rerun()
        except Exception as e:
            st.error(f"Error loading file: {str(e)}")

    st.markdown(
        "<div style='text-align:center; margin:0.75rem 0;'>"
        "<span style='color:#94A3B8; font-size:0.85rem;'>— or —</span></div>",
        unsafe_allow_html=True,
    )

    if st.button("Load Sample Data", use_container_width=True):
        st.session_state.data = generate_sample_data()
        st.session_state.data_source = "🔬 Sample Data (Simulated)"
        st.rerun()

    with st.expander("Supported formats"):
        st.markdown(
            "**Meridian Looker Studio export** — sheets: `MediaROI`, `ModelDiagnostics`, "
            "`ModelFit`, `MediaOutcome`, `MediaSpend`, `response_curves`, `budget_opt_results`\n\n"
            "**Simple format** — sheets: `media_summary`, `model_fit`, `weekly_decomposition`, `response_curves`"
        )


if st.session_state.data is None:
    logo_b64 = get_logo_base64()
    if logo_b64:
        st.markdown(
            f'<div style="text-align:center; padding:3rem 0 1rem;">'
            f'<img src="data:image/png;base64,{logo_b64}" style="height:56px;" />'
            f'</div>',
            unsafe_allow_html=True,
        )
    st.markdown(
        "<h2 style='text-align:center; color:#1E293B; font-weight:700; margin-bottom:0.25rem;'>"
        "Meridian MMM Dashboard</h2>"
        "<p style='text-align:center; color:#94A3B8; font-size:0.95rem;'>"
        "Marketing Mix Model Analytics & Budget Optimization</p>",
        unsafe_allow_html=True,
    )
    upload_dialog()
else:
    st.switch_page("pages/1_🏠_Home.py")
