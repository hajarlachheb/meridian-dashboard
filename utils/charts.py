import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import base64
import os
from typing import List, Optional

HIDE_APP_NAV = '<style>[data-testid="stSidebarNav"] li:first-child { display: none; }</style>'

COLORS = [
    "#4A6CF7", "#F56565", "#48BB78", "#ED8936", "#9F7AEA",
    "#38B2AC", "#E53E8E", "#DD6B20", "#3182CE", "#D69E2E",
    "#805AD5", "#319795",
]

CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#334155", family="Inter, sans-serif", size=12),
    margin=dict(l=40, r=40, t=50, b=40),
    legend=dict(
        bgcolor="rgba(255,255,255,0.9)",
        bordercolor="#E2E8F0",
        borderwidth=1,
        font=dict(size=11, color="#475569"),
    ),
    xaxis=dict(gridcolor="#F1F5F9", zerolinecolor="#E2E8F0"),
    yaxis=dict(gridcolor="#F1F5F9", zerolinecolor="#E2E8F0"),
)

_LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "s360-logo-blue.png")


def get_logo_base64() -> str:
    if os.path.exists(_LOGO_PATH):
        with open(_LOGO_PATH, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""


GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

[data-testid="stSidebarNav"] li:first-child { display: none; }

[data-testid="stSidebar"] {
    background: #FFFFFF;
    border-right: 1px solid #E2E8F0;
}

[data-testid="stSidebar"] [data-testid="stMarkdown"] p,
[data-testid="stSidebar"] [data-testid="stMarkdown"] span {
    color: #475569;
}

div[data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 1rem 1.2rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    transition: box-shadow 0.2s ease;
}

div[data-testid="stMetric"]:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}

div[data-testid="stMetric"] label {
    color: #64748B !important;
    font-size: 0.78rem !important;
    font-weight: 500 !important;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}

div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: #1E293B !important;
    font-weight: 700 !important;
    font-size: 1.6rem !important;
}

.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: #F8F9FC;
    border-radius: 10px;
    padding: 3px;
    border: 1px solid #E2E8F0;
}

.stTabs [data-baseweb="tab"] {
    border-radius: 8px;
    padding: 8px 20px;
    font-weight: 500;
    color: #64748B;
    font-size: 0.9rem;
}

.stTabs [aria-selected="true"] {
    background: #FFFFFF !important;
    color: #1E293B !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08) !important;
}

div.stButton > button {
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 0.45rem 1.5rem;
    font-weight: 500;
    color: #334155;
    background: #FFFFFF;
    transition: all 0.2s ease;
}

div.stButton > button:hover {
    background: #F8F9FC;
    border-color: #CBD5E1;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}

div.stButton > button[kind="primary"],
div.stButton > button.st-emotion-cache-primary {
    background: #4A6CF7 !important;
    color: white !important;
    border: none !important;
}

div.stButton > button[kind="primary"]:hover {
    background: #3B5DE7 !important;
}

[data-testid="stDataFrame"] {
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid #E2E8F0;
}

h1, h2, h3 { letter-spacing: -0.02em; color: #1E293B; }
h4, h5 { color: #334155; }

hr {
    border: none;
    height: 1px;
    background: #E2E8F0;
    margin: 1.5rem 0;
}

[data-testid="stFileUploader"] {
    border: 2px dashed #CBD5E1;
    border-radius: 12px;
    padding: 1rem;
}

[data-testid="stFileUploader"]:hover {
    border-color: #4A6CF7;
}

[data-testid="stExpander"] {
    border: 1px solid #E2E8F0;
    border-radius: 10px;
}

@media print {
    [data-testid="stSidebar"], [data-testid="stHeader"],
    .stButton, [data-testid="stFileUploader"],
    [data-testid="stDeployButton"] { display: none !important; }
    [data-testid="stAppViewContainer"] { padding: 0 !important; }
}
</style>
"""


def page_header(title: str, subtitle: str = ""):
    """Render a consistent page header with Export button."""
    logo_b64 = get_logo_base64()
    logo_html = (
        f'<img src="data:image/png;base64,{logo_b64}" '
        f'style="height:28px; margin-right:0.75rem;" />'
        if logo_b64 else ""
    )

    right_btns = ""
    st.markdown(
        f"""<div style="display:flex; align-items:center; justify-content:space-between;
                margin-bottom:0.25rem;">
            <div style="display:flex; align-items:center;">
                {logo_html}
                <div>
                    <h1 style="font-size:1.75rem; font-weight:700; color:#1E293B;
                        margin:0; line-height:1.2;">{title}</h1>
                    {'<p style="color:#64748B; font-size:0.9rem; margin:0.15rem 0 0;">' + subtitle + '</p>' if subtitle else ''}
                </div>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    _, rc = st.columns([5, 1])
    with rc:
        if st.button("Export PDF", key=f"_pdf_{title}", use_container_width=True):
            st.markdown(
                "<script>window.print();</script>",
                unsafe_allow_html=True,
            )

    st.markdown("---")


def setup_page():
    """Inject global CSS and check data."""
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
    if "data" not in st.session_state or st.session_state.data is None:
        st.switch_page("app.py")


def sidebar_logo():
    """Render the s360 logo in the sidebar."""
    logo_b64 = get_logo_base64()
    if logo_b64:
        st.sidebar.markdown(
            f'<div style="text-align:center; padding: 1rem 0 0.5rem;">'
            f'<img src="data:image/png;base64,{logo_b64}" style="height:40px;" />'
            f'</div>',
            unsafe_allow_html=True,
        )


def format_currency(val: float) -> str:
    if abs(val) >= 1_000_000:
        return f"${val/1_000_000:.1f}M"
    if abs(val) >= 1_000:
        return f"${val/1_000:.0f}K"
    return f"${val:.0f}"


def format_number(val: float) -> str:
    if abs(val) >= 1_000_000:
        return f"{val/1_000_000:.1f}M"
    if abs(val) >= 1_000:
        return f"{val/1_000:.0f}K"
    return f"{val:.0f}"


def roi_bar_chart(df: pd.DataFrame) -> go.Figure:
    sorted_df = df.sort_values("roi", ascending=True)
    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=sorted_df["channel"],
        x=sorted_df["roi"],
        orientation="h",
        marker=dict(
            color=sorted_df["roi"],
            colorscale=[[0, "#F56565"], [0.5, "#ED8936"], [1, "#48BB78"]],
            line=dict(width=0),
        ),
        text=[f"{v:.1f}x" for v in sorted_df["roi"]],
        textposition="outside",
        textfont=dict(color="#334155", size=12),
        hovertemplate="<b>%{y}</b><br>ROI: %{x:.2f}x<extra></extra>",
    ))

    if "roi_lower_ci" in sorted_df.columns:
        fig.add_trace(go.Scatter(
            y=sorted_df["channel"],
            x=sorted_df["roi"],
            error_x=dict(
                type="data",
                symmetric=False,
                array=sorted_df["roi_upper_ci"].values - sorted_df["roi"].values,
                arrayminus=sorted_df["roi"].values - sorted_df["roi_lower_ci"].values,
                color="rgba(100,116,139,0.4)",
                thickness=1.5,
            ),
            mode="markers",
            marker=dict(size=0, color="rgba(0,0,0,0)"),
            showlegend=False,
            hoverinfo="skip",
        ))

    fig.update_layout(
        **CHART_LAYOUT,
        title="Return on Investment by Channel",
        xaxis_title="ROI (Revenue / Spend)",
        yaxis_title="",
        height=max(400, len(df) * 45),
        showlegend=False,
    )
    return fig


def roi_bubble_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()

    max_spend = df["spend"].max()
    sizes = (df["spend"] / max_spend * 60) + 10

    fig.add_trace(go.Scatter(
        x=df["pct_spend"],
        y=df["roi"],
        mode="markers+text",
        marker=dict(
            size=sizes,
            color=[COLORS[i % len(COLORS)] for i in range(len(df))],
            opacity=0.75,
            line=dict(width=1, color="white"),
        ),
        text=df["channel"],
        textposition="top center",
        textfont=dict(size=10, color="#334155"),
        hovertemplate=(
            "<b>%{text}</b><br>"
            "ROI: %{y:.2f}x<br>"
            "% of Spend: %{x:.1f}%<br>"
            "<extra></extra>"
        ),
    ))

    fig.update_layout(
        **CHART_LAYOUT,
        title="ROI vs. Share of Spend",
        xaxis_title="% of Total Spend",
        yaxis_title="ROI",
        height=500,
        showlegend=False,
    )
    return fig


def sales_decomposition_chart(df: pd.DataFrame, channels: List[str]) -> go.Figure:
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df["date"], y=df["baseline"],
        fill="tozeroy",
        name="Baseline",
        fillcolor="rgba(203,213,225,0.5)",
        line=dict(color="rgba(148,163,184,0.7)", width=0.5),
        hovertemplate="%{x|%b %d, %Y}<br>Baseline: $%{y:,.0f}<extra></extra>",
    ))

    cumulative = df["baseline"].copy()
    for i, ch in enumerate(channels):
        if ch in df.columns:
            cumulative = cumulative + df[ch]
            color = COLORS[i % len(COLORS)]
            fig.add_trace(go.Scatter(
                x=df["date"], y=cumulative,
                fill="tonexty",
                name=ch,
                fillcolor=f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.5)",
                line=dict(color=color, width=0.5),
                hovertemplate=f"%{{x|%b %d, %Y}}<br>{ch}: $%{{y:,.0f}}<extra></extra>",
            ))

    if "total_actual" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["total_actual"],
            mode="lines",
            name="Actual Revenue",
            line=dict(color="#1E293B", width=2, dash="dot"),
            hovertemplate="%{x|%b %d, %Y}<br>Actual: $%{y:,.0f}<extra></extra>",
        ))

    fig.update_layout(
        **CHART_LAYOUT,
        title="Revenue Decomposition Over Time",
        xaxis_title="",
        yaxis_title="Revenue ($)",
        height=500,
        hovermode="x unified",
    )
    return fig


def response_curve_chart(
    df: pd.DataFrame,
    selected_channels: Optional[List[str]] = None,
) -> go.Figure:
    fig = go.Figure()

    if selected_channels is None:
        selected_channels = df["channel"].unique().tolist()

    for i, ch in enumerate(selected_channels):
        ch_data = df[df["channel"] == ch]
        color = COLORS[i % len(COLORS)]

        fig.add_trace(go.Scatter(
            x=ch_data["spend_level"],
            y=ch_data["incremental_revenue"],
            mode="lines",
            name=ch,
            line=dict(color=color, width=2.5),
            hovertemplate=(
                f"<b>{ch}</b><br>"
                "Spend: $%{x:,.0f}<br>"
                "Incr. Revenue: $%{y:,.0f}<extra></extra>"
            ),
        ))

        current = ch_data[ch_data["spend_level"] == ch_data["current_spend"].iloc[0]]
        if len(current) == 0:
            current_spend = ch_data["current_spend"].iloc[0]
            current_rev = ch_data["current_revenue"].iloc[0]
        else:
            current_spend = current["spend_level"].iloc[0]
            current_rev = current["incremental_revenue"].iloc[0]

        fig.add_trace(go.Scatter(
            x=[current_spend],
            y=[current_rev],
            mode="markers",
            name=f"{ch} (current)",
            marker=dict(size=12, color=color, symbol="diamond",
                        line=dict(width=2, color="white")),
            showlegend=False,
            hovertemplate=(
                f"<b>{ch} - Current</b><br>"
                f"Spend: ${current_spend:,.0f}<br>"
                f"Revenue: ${current_rev:,.0f}<extra></extra>"
            ),
        ))

    fig.update_layout(
        **CHART_LAYOUT,
        title="Response Curves (Diminishing Returns)",
        xaxis_title="Spend ($)",
        yaxis_title="Incremental Revenue ($)",
        height=500,
    )
    return fig


def marginal_roi_chart(df: pd.DataFrame) -> go.Figure:
    sorted_df = df.sort_values("marginal_roi", ascending=True)
    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=sorted_df["channel"],
        x=sorted_df["marginal_roi"],
        orientation="h",
        name="Marginal ROI",
        marker=dict(
            color=sorted_df["marginal_roi"],
            colorscale=[[0, "#F56565"], [0.5, "#ED8936"], [1, "#48BB78"]],
        ),
        text=[f"{v:.2f}x" for v in sorted_df["marginal_roi"]],
        textposition="outside",
        textfont=dict(color="#334155", size=12),
        hovertemplate="<b>%{y}</b><br>mROI: %{x:.2f}x<extra></extra>",
    ))

    if "mroi_lower_ci" in sorted_df.columns:
        fig.add_trace(go.Scatter(
            y=sorted_df["channel"],
            x=sorted_df["marginal_roi"],
            error_x=dict(
                type="data",
                symmetric=False,
                array=sorted_df["mroi_upper_ci"].values - sorted_df["marginal_roi"].values,
                arrayminus=sorted_df["marginal_roi"].values - sorted_df["mroi_lower_ci"].values,
                color="rgba(100,116,139,0.4)",
                thickness=1.5,
            ),
            mode="markers",
            marker=dict(size=0, color="rgba(0,0,0,0)"),
            showlegend=False,
            hoverinfo="skip",
        ))

    fig.add_vline(x=1.0, line=dict(color="rgba(245,101,101,0.5)", width=1.5, dash="dash"))

    fig.update_layout(
        **CHART_LAYOUT,
        title="Marginal ROI by Channel",
        xaxis_title="Marginal ROI",
        yaxis_title="",
        height=max(400, len(df) * 45),
        showlegend=False,
    )
    return fig


def spend_vs_revenue_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    sorted_df = df.sort_values("spend", ascending=False)

    fig.add_trace(go.Bar(
        x=sorted_df["channel"],
        y=sorted_df["pct_spend"],
        name="% of Spend",
        marker=dict(color="#4A6CF7", opacity=0.8),
        hovertemplate="<b>%{x}</b><br>% Spend: %{y:.1f}%<extra></extra>",
    ))

    fig.add_trace(go.Bar(
        x=sorted_df["channel"],
        y=sorted_df["pct_incremental_revenue"],
        name="% of Incr. Revenue",
        marker=dict(color="#48BB78", opacity=0.8),
        hovertemplate="<b>%{x}</b><br>% Revenue: %{y:.1f}%<extra></extra>",
    ))

    fig.update_layout(
        **CHART_LAYOUT,
        title="Spend Share vs Revenue Contribution",
        barmode="group",
        xaxis_title="",
        yaxis_title="Percentage (%)",
        height=450,
    )
    fig.update_xaxes(tickangle=-45)
    return fig


def optimizer_waterfall(df: pd.DataFrame) -> go.Figure:
    sorted_df = df.sort_values("spend_change", ascending=False)
    colors = ["#48BB78" if v > 0 else "#F56565" for v in sorted_df["spend_change"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=sorted_df["channel"],
        y=sorted_df["spend_change"],
        marker=dict(color=colors, opacity=0.85),
        text=[f"{v:+,.0f}" for v in sorted_df["spend_change"]],
        textposition="outside",
        textfont=dict(size=10, color="#334155"),
        hovertemplate="<b>%{x}</b><br>Change: $%{y:,.0f}<extra></extra>",
    ))

    fig.update_layout(
        **CHART_LAYOUT,
        title="Recommended Budget Changes by Channel",
        xaxis_title="",
        yaxis_title="Spend Change ($)",
        height=450,
    )
    fig.update_xaxes(tickangle=-45)
    return fig


def optimizer_comparison_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    sorted_df = df.sort_values("current_spend", ascending=False)

    fig.add_trace(go.Bar(
        x=sorted_df["channel"],
        y=sorted_df["current_spend"],
        name="Current Spend",
        marker=dict(color="rgba(74,108,247,0.6)", line=dict(color="#4A6CF7", width=1)),
        hovertemplate="<b>%{x}</b><br>Current: $%{y:,.0f}<extra></extra>",
    ))

    fig.add_trace(go.Bar(
        x=sorted_df["channel"],
        y=sorted_df["optimized_spend"],
        name="Optimized Spend",
        marker=dict(color="rgba(72,187,120,0.6)", line=dict(color="#48BB78", width=1)),
        hovertemplate="<b>%{x}</b><br>Optimized: $%{y:,.0f}<extra></extra>",
    ))

    fig.update_layout(
        **CHART_LAYOUT,
        title="Current vs. Optimized Budget Allocation",
        barmode="group",
        xaxis_title="",
        yaxis_title="Spend ($)",
        height=450,
    )
    fig.update_xaxes(tickangle=-45)
    return fig


def model_fit_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()

    has_ci = "expected_ci_low" in df.columns and "expected_ci_high" in df.columns

    if has_ci:
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["expected_ci_high"],
            mode="lines", line=dict(width=0),
            showlegend=False, hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["expected_ci_low"],
            mode="lines", line=dict(width=0),
            fill="tonexty",
            fillcolor="rgba(74,108,247,0.1)",
            name="Prediction CI",
            hoverinfo="skip",
        ))

    fig.add_trace(go.Scatter(
        x=df["date"], y=df["total_actual"],
        mode="lines", name="Actual Revenue",
        line=dict(color="#1E293B", width=2),
    ))

    fig.add_trace(go.Scatter(
        x=df["date"], y=df["total_predicted"],
        mode="lines", name="Predicted Revenue",
        line=dict(color="#4A6CF7", width=2, dash="dash"),
    ))

    fig.update_layout(
        **CHART_LAYOUT,
        title="Model Fit: Predicted vs Actual Revenue",
        xaxis_title="",
        yaxis_title="Revenue ($)",
        height=400,
    )
    return fig


def contribution_pie_chart(media_summary: pd.DataFrame, weekly_decomp: pd.DataFrame) -> go.Figure:
    labels = []
    values = []

    if "baseline" in weekly_decomp.columns:
        labels.append("Baseline")
        values.append(weekly_decomp["baseline"].sum())

    if "seasonality" in weekly_decomp.columns:
        labels.append("Seasonality")
        values.append(weekly_decomp["seasonality"].sum())

    if "promotions" in weekly_decomp.columns:
        labels.append("Promotions")
        values.append(weekly_decomp["promotions"].sum())

    for _, row in media_summary.iterrows():
        labels.append(row["channel"])
        values.append(row["incremental_revenue"])

    all_colors = ["#94A3B8", "#CBD5E1", "#E2E8F0"] + COLORS

    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.45,
        marker=dict(colors=all_colors[:len(labels)]),
        textinfo="label+percent",
        textfont=dict(size=11, color="#334155"),
        hovertemplate="<b>%{label}</b><br>Value: $%{value:,.0f}<br>Share: %{percent}<extra></extra>",
    )])

    fig.update_layout(
        **CHART_LAYOUT,
        title="Revenue Contribution Breakdown",
        height=500,
    )
    return fig
