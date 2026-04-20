import streamlit as st
import pandas as pd
import numpy as np
from utils.charts import (
    sales_decomposition_chart, roi_bar_chart, roi_bubble_chart,
    spend_vs_revenue_chart, contribution_pie_chart, format_currency,
    CHART_LAYOUT, COLORS, page_header, setup_page, sidebar_logo,
)

st.set_page_config(page_title="Dashboard | s360 MMM", page_icon="📊", layout="wide")
setup_page()
sidebar_logo()

data = st.session_state.data

page_header("Marketing Dashboard", "Analyze how each marketing activity contributes to your revenue")

media = data.get("media_summary")
decomp = data.get("weekly_decomposition")

if media is not None:
    channels = media["channel"].tolist()

    with st.expander("Filters", expanded=False):
        filter_cols = st.columns(2)
        with filter_cols[0]:
            selected_channels = st.multiselect(
                "Select Channels",
                options=channels,
                default=channels,
            )
        with filter_cols[1]:
            if decomp is not None and "date" in decomp.columns:
                min_date = decomp["date"].min().date()
                max_date = decomp["date"].max().date()
                date_range = st.date_input(
                    "Date Range",
                    value=(min_date, max_date),
                    min_value=min_date,
                    max_value=max_date,
                )
            else:
                date_range = None

    filtered_media = media[media["channel"].isin(selected_channels)]
    if decomp is not None and date_range and len(date_range) == 2:
        filtered_decomp = decomp[
            (decomp["date"].dt.date >= date_range[0]) &
            (decomp["date"].dt.date <= date_range[1])
        ]
    else:
        filtered_decomp = decomp

    tab1, tab2, tab3, tab4 = st.tabs([
        "Sales Decomposition",
        "ROI Analysis",
        "Contribution",
        "Data Table",
    ])

    with tab1:
        if filtered_decomp is not None:
            st.markdown("#### Revenue Decomposition Over Time")
            st.markdown(
                "<p style='color:#64748B;'>How much of your revenue is driven by "
                "baseline, seasonality, promotions, and each marketing channel.</p>",
                unsafe_allow_html=True,
            )
            fig = sales_decomposition_chart(filtered_decomp, selected_channels)
            st.plotly_chart(fig, use_container_width=True)

            if "baseline" in filtered_decomp.columns:
                total_rev = filtered_decomp["total_actual"].sum() if "total_actual" in filtered_decomp.columns else filtered_decomp["total_predicted"].sum()
                baseline_pct = filtered_decomp["baseline"].sum() / total_rev * 100
                media_pct = sum(
                    filtered_decomp[ch].sum() for ch in selected_channels if ch in filtered_decomp.columns
                ) / total_rev * 100

                info_cols = st.columns(3)
                with info_cols[0]:
                    st.metric("Baseline Share", f"{baseline_pct:.1f}%")
                with info_cols[1]:
                    st.metric("Media-Driven Share", f"{media_pct:.1f}%")
                with info_cols[2]:
                    other_pct = 100 - baseline_pct - media_pct
                    st.metric("Other Factors", f"{max(other_pct, 0):.1f}%")
        else:
            st.info("Weekly decomposition data not available.")

    with tab2:
        st.markdown("#### Return on Investment Analysis")

        view_mode = st.radio(
            "View",
            ["Bar Chart", "Bubble Chart", "Spend vs Revenue"],
            horizontal=True,
        )

        if view_mode == "Bar Chart":
            fig = roi_bar_chart(filtered_media)
            st.plotly_chart(fig, use_container_width=True)
        elif view_mode == "Bubble Chart":
            fig = roi_bubble_chart(filtered_media)
            st.plotly_chart(fig, use_container_width=True)
        else:
            fig = spend_vs_revenue_chart(filtered_media)
            st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.markdown("#### Revenue Contribution Breakdown")
        if filtered_decomp is not None:
            fig = contribution_pie_chart(filtered_media, filtered_decomp)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Decomposition data needed for contribution analysis.")

        st.markdown("#### Channel Efficiency Matrix")
        if "marginal_roi" in filtered_media.columns:
            import plotly.graph_objects as go

            fig = go.Figure()
            for i, (_, row) in enumerate(filtered_media.iterrows()):
                color = COLORS[i % len(COLORS)]
                fig.add_trace(go.Scatter(
                    x=[row["roi"]],
                    y=[row["marginal_roi"]],
                    mode="markers+text",
                    marker=dict(
                        size=row["pct_spend"] * 3 + 10,
                        color=color,
                        opacity=0.75,
                        line=dict(width=1, color="white"),
                    ),
                    text=[row["channel"]],
                    textposition="top center",
                    textfont=dict(size=9, color="#334155"),
                    name=row["channel"],
                    hovertemplate=(
                        f"<b>{row['channel']}</b><br>"
                        f"ROI: {row['roi']:.2f}x<br>"
                        f"mROI: {row['marginal_roi']:.2f}x<br>"
                        f"Spend share: {row['pct_spend']:.1f}%<extra></extra>"
                    ),
                ))

            fig.add_hline(y=1, line=dict(color="rgba(245,101,101,0.4)", dash="dash"))
            fig.add_vline(x=1, line=dict(color="rgba(245,101,101,0.4)", dash="dash"))

            fig.update_layout(
                **CHART_LAYOUT,
                title="Average ROI vs. Marginal ROI",
                xaxis_title="Average ROI",
                yaxis_title="Marginal ROI",
                height=500,
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)

    with tab4:
        st.markdown("#### Channel Performance Data")
        display_df = filtered_media.copy()

        rename_map = {
            "channel": "Channel",
            "spend": "Spend",
            "roi": "ROI",
            "marginal_roi": "Marginal ROI",
            "incremental_revenue": "Incr. Revenue",
            "pct_spend": "% Spend",
            "pct_incremental_revenue": "% Incr. Revenue",
            "effectiveness": "Effectiveness",
            "cpa": "CPA",
        }

        display_cols = [c for c in rename_map.keys() if c in display_df.columns]
        display_df = display_df[display_cols].rename(columns=rename_map)

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
        )

        csv = display_df.to_csv(index=False)
        st.download_button(
            "Download as CSV",
            csv,
            "channel_performance.csv",
            "text/csv",
        )

else:
    st.info("No media summary data available. Please upload an Excel file with a 'media_summary' sheet.")
