import streamlit as st
import plotly.graph_objects as go
from utils.charts import (
    format_currency, format_number, model_fit_chart, contribution_pie_chart,
    CHART_LAYOUT, COLORS, page_header, setup_page, sidebar_logo,
)

st.set_page_config(page_title="Home | s360 MMM", page_icon="🏠", layout="wide")
setup_page()
sidebar_logo()

data = st.session_state.data

page_header("Executive Overview", "High-level summary of your marketing mix model results")

media = data.get("media_summary")
fit_data = data.get("model_fit")
decomp = data.get("weekly_decomposition")

if media is not None:
    total_spend = media["spend"].sum()
    total_revenue = media["incremental_revenue"].sum()
    avg_roi = total_revenue / total_spend if total_spend > 0 else 0
    top_channel = media.loc[media["roi"].idxmax(), "channel"]
    top_roi = media["roi"].max()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Revenue", format_currency(total_spend + total_revenue))
    with col2:
        st.metric("Media Contribution", format_currency(total_revenue))
    with col3:
        st.metric("Blended ROAS", f"{avg_roi:.2f}x")
    with col4:
        r2_val = 0
        if fit_data is not None:
            r2_row = fit_data[fit_data["metric"].str.contains("R-squared|R2", case=False, na=False)]
            if len(r2_row) > 0:
                r2_val = r2_row["value"].iloc[0]
        st.metric("Model R²", f"{r2_val:.3f}")

    st.markdown("")

if fit_data is not None:
    st.markdown("#### Model Fit Statistics")
    cols = st.columns(len(fit_data))
    for i, (_, row) in enumerate(fit_data.iterrows()):
        metric_name = row["metric"]
        val = row["value"]
        if "%" in metric_name or "MAPE" in metric_name.upper() or "NRMSE" in metric_name.upper():
            display_val = f"{val:.1%}" if val < 1 else f"{val:.1f}%"
        elif "R-squared" in metric_name or "R2" in metric_name.upper():
            display_val = f"{val:.3f}"
        else:
            display_val = f"{val:.3f}"
        with cols[i]:
            st.metric(metric_name, display_val)

    st.markdown("---")

if decomp is not None:
    st.markdown("#### Model Fit: Predicted vs. Actual")
    fig = model_fit_chart(decomp)
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("---")

if media is not None and decomp is not None:
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### Revenue Contribution")
        fig = contribution_pie_chart(media, decomp)
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.markdown("#### Channel ROI Ranking")
        sorted_media = media.sort_values("roi", ascending=False)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=sorted_media["channel"],
            x=sorted_media["roi"],
            orientation="h",
            marker=dict(
                color=[COLORS[i % len(COLORS)] for i in range(len(sorted_media))],
                opacity=0.85,
            ),
            text=[f"{v:.1f}x" for v in sorted_media["roi"]],
            textposition="outside",
            textfont=dict(color="#334155", size=11),
            hovertemplate="<b>%{y}</b><br>ROI: %{x:.2f}x<extra></extra>",
        ))

        fig.update_layout(
            **CHART_LAYOUT,
            height=500,
            showlegend=False,
            xaxis_title="ROI",
        )
        st.plotly_chart(fig, use_container_width=True)

if media is not None:
    st.markdown("---")
    st.markdown("#### Key Recommendations")

    high_roi_low_spend = media[
        (media["roi"] > media["roi"].median()) &
        (media["pct_spend"] < media["pct_spend"].median())
    ]
    low_roi_high_spend = media[
        (media["roi"] < media["roi"].median()) &
        (media["pct_spend"] > media["pct_spend"].median())
    ]

    rec_cols = st.columns(2)

    with rec_cols[0]:
        st.markdown(
            """<div style="background:#F0FFF4; border:1px solid #C6F6D5;
                border-radius:10px; padding:1.2rem;">
                <h4 style="color:#276749; margin-top:0;">🔼 Consider Increasing</h4>""",
            unsafe_allow_html=True,
        )
        if len(high_roi_low_spend) > 0:
            for _, row in high_roi_low_spend.iterrows():
                st.markdown(
                    f"**{row['channel']}** — ROI: {row['roi']:.1f}x | "
                    f"Only {row['pct_spend']:.1f}% of budget"
                )
        else:
            st.markdown("*No clear scale-up candidates identified*")
        st.markdown("</div>", unsafe_allow_html=True)

    with rec_cols[1]:
        st.markdown(
            """<div style="background:#FFF5F5; border:1px solid #FED7D7;
                border-radius:10px; padding:1.2rem;">
                <h4 style="color:#9B2C2C; margin-top:0;">🔽 Consider Reducing</h4>""",
            unsafe_allow_html=True,
        )
        if len(low_roi_high_spend) > 0:
            for _, row in low_roi_high_spend.iterrows():
                st.markdown(
                    f"**{row['channel']}** — ROI: {row['roi']:.1f}x | "
                    f"Uses {row['pct_spend']:.1f}% of budget"
                )
        else:
            st.markdown("*No clear reduction candidates identified*")
        st.markdown("</div>", unsafe_allow_html=True)
