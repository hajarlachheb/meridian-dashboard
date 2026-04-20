import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from typing import List, Optional

HIDE_APP_NAV = '<style>[data-testid="stSidebarNav"] li:first-child { display: none; }</style>'

COLORS = [
    "#6366F1", "#EC4899", "#14B8A6", "#F59E0B", "#8B5CF6",
    "#EF4444", "#06B6D4", "#84CC16", "#F97316", "#3B82F6",
    "#D946EF", "#10B981",
]

CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#E2E8F0", family="Inter, sans-serif"),
    margin=dict(l=40, r=40, t=50, b=40),
    legend=dict(
        bgcolor="rgba(30,41,59,0.8)",
        bordercolor="rgba(100,116,139,0.3)",
        borderwidth=1,
        font=dict(size=11),
    ),
    xaxis=dict(gridcolor="rgba(100,116,139,0.2)", zerolinecolor="rgba(100,116,139,0.3)"),
    yaxis=dict(gridcolor="rgba(100,116,139,0.2)", zerolinecolor="rgba(100,116,139,0.3)"),
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
            colorscale=[[0, "#EF4444"], [0.5, "#F59E0B"], [1, "#10B981"]],
            line=dict(width=0),
        ),
        text=[f"{v:.1f}x" for v in sorted_df["roi"]],
        textposition="outside",
        textfont=dict(color="#E2E8F0", size=12),
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
                color="rgba(226,232,240,0.4)",
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
            opacity=0.8,
            line=dict(width=1, color="rgba(255,255,255,0.3)"),
        ),
        text=df["channel"],
        textposition="top center",
        textfont=dict(size=10, color="#E2E8F0"),
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
        fillcolor="rgba(100,116,139,0.4)",
        line=dict(color="rgba(100,116,139,0.6)", width=0.5),
        hovertemplate="%{x|%b %d, %Y}<br>Baseline: $%{y:,.0f}<extra></extra>",
    ))

    cumulative = df["baseline"].copy()
    for i, ch in enumerate(channels):
        if ch in df.columns:
            prev_cumulative = cumulative.copy()
            cumulative = cumulative + df[ch]
            color = COLORS[i % len(COLORS)]
            fig.add_trace(go.Scatter(
                x=df["date"], y=cumulative,
                fill="tonexty",
                name=ch,
                fillcolor=f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.6)",
                line=dict(color=color, width=0.5),
                hovertemplate=f"%{{x|%b %d, %Y}}<br>{ch}: $%{{y:,.0f}}<extra></extra>",
            ))

    if "total_actual" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["total_actual"],
            mode="lines",
            name="Actual Revenue",
            line=dict(color="#FFFFFF", width=2, dash="dot"),
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
            marker=dict(size=12, color=color, symbol="diamond", line=dict(width=2, color="white")),
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
            colorscale=[[0, "#EF4444"], [0.5, "#F59E0B"], [1, "#10B981"]],
        ),
        text=[f"{v:.2f}x" for v in sorted_df["marginal_roi"]],
        textposition="outside",
        textfont=dict(color="#E2E8F0", size=12),
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
                color="rgba(226,232,240,0.4)",
                thickness=1.5,
            ),
            mode="markers",
            marker=dict(size=0, color="rgba(0,0,0,0)"),
            showlegend=False,
            hoverinfo="skip",
        ))

    fig.add_vline(x=1.0, line=dict(color="rgba(239,68,68,0.5)", width=1.5, dash="dash"))

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
        marker=dict(color="#6366F1", opacity=0.8),
        hovertemplate="<b>%{x}</b><br>% Spend: %{y:.1f}%<extra></extra>",
    ))

    fig.add_trace(go.Bar(
        x=sorted_df["channel"],
        y=sorted_df["pct_incremental_revenue"],
        name="% of Incr. Revenue",
        marker=dict(color="#14B8A6", opacity=0.8),
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

    colors = ["#10B981" if v > 0 else "#EF4444" for v in sorted_df["spend_change"]]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=sorted_df["channel"],
        y=sorted_df["spend_change"],
        marker=dict(color=colors, opacity=0.85),
        text=[f"{v:+,.0f}" for v in sorted_df["spend_change"]],
        textposition="outside",
        textfont=dict(size=10, color="#E2E8F0"),
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Change: $%{y:,.0f}<br>"
            "<extra></extra>"
        ),
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
        marker=dict(color="rgba(99,102,241,0.6)", line=dict(color="#6366F1", width=1)),
        hovertemplate="<b>%{x}</b><br>Current: $%{y:,.0f}<extra></extra>",
    ))

    fig.add_trace(go.Bar(
        x=sorted_df["channel"],
        y=sorted_df["optimized_spend"],
        name="Optimized Spend",
        marker=dict(color="rgba(20,184,166,0.6)", line=dict(color="#14B8A6", width=1)),
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
    """Predicted vs Actual over time, with optional confidence interval band."""
    fig = go.Figure()

    has_ci = "expected_ci_low" in df.columns and "expected_ci_high" in df.columns

    if has_ci:
        fig.add_trace(go.Scatter(
            x=df["date"],
            y=df["expected_ci_high"],
            mode="lines",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=df["date"],
            y=df["expected_ci_low"],
            mode="lines",
            line=dict(width=0),
            fill="tonexty",
            fillcolor="rgba(99,102,241,0.15)",
            name="Prediction CI",
            hoverinfo="skip",
        ))

    fig.add_trace(go.Scatter(
        x=df["date"],
        y=df["total_actual"],
        mode="lines",
        name="Actual Revenue",
        line=dict(color="#E2E8F0", width=2),
    ))

    fig.add_trace(go.Scatter(
        x=df["date"],
        y=df["total_predicted"],
        mode="lines",
        name="Predicted Revenue",
        line=dict(color="#6366F1", width=2, dash="dash"),
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

    all_colors = ["#475569", "#64748B", "#94A3B8"] + COLORS

    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.45,
        marker=dict(colors=all_colors[:len(labels)]),
        textinfo="label+percent",
        textfont=dict(size=11),
        hovertemplate="<b>%{label}</b><br>Value: $%{value:,.0f}<br>Share: %{percent}<extra></extra>",
    )])

    fig.update_layout(
        **CHART_LAYOUT,
        title="Revenue Contribution Breakdown",
        height=500,
    )
    return fig
