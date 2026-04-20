import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from utils.charts import (
    roi_bar_chart, marginal_roi_chart, response_curve_chart,
    format_currency, CHART_LAYOUT, COLORS, HIDE_APP_NAV
)

st.set_page_config(page_title="Performance | Meridian MMM", page_icon="📈", layout="wide")
st.markdown(HIDE_APP_NAV, unsafe_allow_html=True)

if "data" not in st.session_state or st.session_state.data is None:
    st.switch_page("app.py")

data = st.session_state.data

st.markdown(
    """
    <h1 style="background: linear-gradient(135deg, #6366F1, #EC4899);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        font-weight: 800; font-size: 2.2rem; margin-bottom: 0;">
        Performance
    </h1>
    <p style="color: #94A3B8; margin-top: 0.25rem;">
        Deep-dive into channel-level ROI, marginal returns, and saturation curves
    </p>
    """,
    unsafe_allow_html=True,
)
st.markdown("---")

media = data.get("media_summary")
if media is None:
    media = data.get("roi_summary")
response = data.get("response_curves")
optimal = data.get("optimal_frequency")

if media is not None:
    channels = media["channel"].tolist()

    total_spend = media["spend"].sum()
    total_rev = media["incremental_revenue"].sum()
    weighted_roi = total_rev / total_spend if total_spend > 0 else 0

    if "marginal_roi" in media.columns:
        weighted_mroi = np.average(media["marginal_roi"], weights=media["spend"])
    else:
        weighted_mroi = None

    kpi_cols = st.columns(4)
    with kpi_cols[0]:
        st.metric("Weighted Avg. ROI", f"{weighted_roi:.2f}x")
    with kpi_cols[1]:
        if weighted_mroi is not None:
            st.metric("Weighted Avg. mROI", f"{weighted_mroi:.2f}x")
        else:
            st.metric("Channels Analyzed", str(len(channels)))
    with kpi_cols[2]:
        best_ch = media.loc[media["roi"].idxmax()]
        st.metric("Best ROI Channel", best_ch["channel"], f"{best_ch['roi']:.1f}x")
    with kpi_cols[3]:
        if "marginal_roi" in media.columns:
            best_mroi_ch = media.loc[media["marginal_roi"].idxmax()]
            st.metric("Best mROI Channel", best_mroi_ch["channel"], f"{best_mroi_ch['marginal_roi']:.2f}x")
        else:
            st.metric("Total Channels", str(len(channels)))

    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 ROI Analysis",
        "📉 Marginal ROI",
        "🔄 Response Curves",
        "📡 Saturation Analysis",
    ])

    with tab1:
        st.markdown("#### Return on Investment by Channel")
        st.markdown(
            "<p style='color:#94A3B8;'>Compare ROI across channels with confidence intervals. "
            "Higher ROI means more revenue per dollar spent.</p>",
            unsafe_allow_html=True,
        )

        fig = roi_bar_chart(media)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.markdown("#### ROI with Confidence Intervals")

        fig2 = go.Figure()
        sorted_df = media.sort_values("roi", ascending=False)

        for i, (_, row) in enumerate(sorted_df.iterrows()):
            color = COLORS[i % len(COLORS)]
            ci_lower = row.get("roi_lower_ci", row["roi"] * 0.7)
            ci_upper = row.get("roi_upper_ci", row["roi"] * 1.3)

            fig2.add_trace(go.Scatter(
                x=[ci_lower, row["roi"], ci_upper],
                y=[row["channel"]] * 3,
                mode="lines+markers",
                marker=dict(
                    size=[8, 14, 8],
                    color=color,
                    symbol=["line-ew", "diamond", "line-ew"],
                ),
                line=dict(color=color, width=3),
                name=row["channel"],
                hovertemplate=(
                    f"<b>{row['channel']}</b><br>"
                    f"ROI: {row['roi']:.2f}x<br>"
                    f"CI: [{ci_lower:.2f}x, {ci_upper:.2f}x]<extra></extra>"
                ),
            ))

        fig2.add_vline(x=1, line=dict(color="rgba(239,68,68,0.4)", width=1.5, dash="dash"))

        fig2.update_layout(
            **CHART_LAYOUT,
            title="ROI Credible Intervals (90%)",
            xaxis_title="ROI",
            yaxis_title="",
            height=max(400, len(media) * 50),
            showlegend=False,
        )
        st.plotly_chart(fig2, use_container_width=True)

    with tab2:
        if "marginal_roi" in media.columns:
            st.markdown("#### Marginal Return on Investment")
            st.markdown(
                "<p style='color:#94A3B8;'>Marginal ROI shows the return from the "
                "<em>next dollar</em> spent. Channels with mROI &gt; 1 still have room to grow.</p>",
                unsafe_allow_html=True,
            )

            fig = marginal_roi_chart(media)
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")
            st.markdown("#### Average ROI vs. Marginal ROI Comparison")

            fig3 = go.Figure()
            sorted_m = media.sort_values("roi", ascending=False)

            fig3.add_trace(go.Bar(
                x=sorted_m["channel"],
                y=sorted_m["roi"],
                name="Average ROI",
                marker=dict(color="#6366F1", opacity=0.8),
            ))

            fig3.add_trace(go.Bar(
                x=sorted_m["channel"],
                y=sorted_m["marginal_roi"],
                name="Marginal ROI",
                marker=dict(color="#14B8A6", opacity=0.8),
            ))

            fig3.add_hline(y=1, line=dict(color="rgba(239,68,68,0.5)", dash="dash"),
                           annotation_text="Break-even", annotation_position="top right")

            fig3.update_layout(
                **CHART_LAYOUT,
                title="Average vs. Marginal ROI",
                barmode="group",
                yaxis_title="ROI",
                height=450,
            )
            fig3.update_xaxes(tickangle=-45)
            st.plotly_chart(fig3, use_container_width=True)

            st.markdown("---")

            st.markdown("#### Channel Prioritization Matrix")

            growth = media[media["marginal_roi"] > 1].sort_values("marginal_roi", ascending=False)
            maintain = media[(media["marginal_roi"] <= 1) & (media["roi"] > 1)].sort_values("roi", ascending=False)
            review = media[media["roi"] <= 1].sort_values("roi", ascending=False)

            p_cols = st.columns(3)
            with p_cols[0]:
                st.markdown(
                    '<div style="background:rgba(16,185,129,0.1); border:1px solid rgba(16,185,129,0.3); '
                    'border-radius:12px; padding:1rem;">'
                    '<h4 style="color:#10B981;margin-top:0;">Scale Up</h4>'
                    '<p style="color:#94A3B8;font-size:0.85rem;">mROI &gt; 1 — room to grow</p>',
                    unsafe_allow_html=True,
                )
                for _, r in growth.iterrows():
                    st.markdown(f"**{r['channel']}** — mROI: {r['marginal_roi']:.2f}x")
                st.markdown("</div>", unsafe_allow_html=True)

            with p_cols[1]:
                st.markdown(
                    '<div style="background:rgba(245,158,11,0.1); border:1px solid rgba(245,158,11,0.3); '
                    'border-radius:12px; padding:1rem;">'
                    '<h4 style="color:#F59E0B;margin-top:0;">Maintain</h4>'
                    '<p style="color:#94A3B8;font-size:0.85rem;">ROI &gt; 1, mROI &le; 1 — saturated</p>',
                    unsafe_allow_html=True,
                )
                for _, r in maintain.iterrows():
                    st.markdown(f"**{r['channel']}** — ROI: {r['roi']:.2f}x")
                st.markdown("</div>", unsafe_allow_html=True)

            with p_cols[2]:
                st.markdown(
                    '<div style="background:rgba(239,68,68,0.1); border:1px solid rgba(239,68,68,0.3); '
                    'border-radius:12px; padding:1rem;">'
                    '<h4 style="color:#EF4444;margin-top:0;">Review / Reduce</h4>'
                    '<p style="color:#94A3B8;font-size:0.85rem;">ROI &le; 1 — underperforming</p>',
                    unsafe_allow_html=True,
                )
                for _, r in review.iterrows():
                    st.markdown(f"**{r['channel']}** — ROI: {r['roi']:.2f}x")
                if len(review) == 0:
                    st.markdown("*No underperforming channels*")
                st.markdown("</div>", unsafe_allow_html=True)

        else:
            st.info("Marginal ROI data not available in your dataset.")

    with tab3:
        if response is not None:
            st.markdown("#### Response Curves (Diminishing Returns)")
            st.markdown(
                "<p style='color:#94A3B8;'>Response curves show how incremental revenue changes "
                "as spend increases. The diamond marker shows your current spend level.</p>",
                unsafe_allow_html=True,
            )

            available_channels = response["channel"].unique().tolist()
            selected = st.multiselect(
                "Select channels to compare",
                available_channels,
                default=available_channels[:4],
            )

            if selected:
                fig = response_curve_chart(response, selected)
                st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")
            st.markdown("#### Individual Channel Deep-Dive")

            chosen = st.selectbox("Select a channel", available_channels)
            if chosen:
                ch_data = response[response["channel"] == chosen]

                fig_single = go.Figure()
                fig_single.add_trace(go.Scatter(
                    x=ch_data["spend_level"],
                    y=ch_data["incremental_revenue"],
                    mode="lines",
                    fill="tozeroy",
                    fillcolor="rgba(99,102,241,0.15)",
                    line=dict(color="#6366F1", width=3),
                    hovertemplate="Spend: $%{x:,.0f}<br>Revenue: $%{y:,.0f}<extra></extra>",
                ))

                current_spend = ch_data["current_spend"].iloc[0]
                current_rev = ch_data["current_revenue"].iloc[0]

                fig_single.add_trace(go.Scatter(
                    x=[current_spend],
                    y=[current_rev],
                    mode="markers+text",
                    marker=dict(size=16, color="#EC4899", symbol="diamond",
                                line=dict(width=2, color="white")),
                    text=["Current"],
                    textposition="top center",
                    textfont=dict(color="#EC4899", size=12, family="Inter"),
                    showlegend=False,
                ))

                fig_single.add_vline(x=current_spend, line=dict(color="rgba(236,72,153,0.3)", dash="dot"))

                fig_single.update_layout(
                    **CHART_LAYOUT,
                    title=f"{chosen} — Response Curve",
                    xaxis_title="Spend ($)",
                    yaxis_title="Incremental Revenue ($)",
                    height=400,
                    showlegend=False,
                )
                st.plotly_chart(fig_single, use_container_width=True)

                max_revenue = ch_data["incremental_revenue"].max()
                saturation_pct = current_rev / max_revenue * 100 if max_revenue > 0 else 0

                s_cols = st.columns(3)
                with s_cols[0]:
                    st.metric("Current Spend", format_currency(current_spend))
                with s_cols[1]:
                    st.metric("Current Incr. Revenue", format_currency(current_rev))
                with s_cols[2]:
                    st.metric("Saturation Level", f"{saturation_pct:.0f}%")

        else:
            st.info("Response curve data not available. Upload a sheet named 'response_curves'.")

    with tab4:
        if response is not None:
            st.markdown("#### Saturation Analysis")
            st.markdown(
                "<p style='color:#94A3B8;'>How close each channel is to its saturation point. "
                "Channels near 100% have little room for incremental gains.</p>",
                unsafe_allow_html=True,
            )

            saturation_data = []
            for ch in channels:
                ch_data = response[response["channel"] == ch]
                if len(ch_data) > 0:
                    max_rev = ch_data["incremental_revenue"].max()
                    curr_rev = ch_data["current_revenue"].iloc[0]
                    sat = curr_rev / max_rev * 100 if max_rev > 0 else 0
                    saturation_data.append({
                        "channel": ch,
                        "saturation_pct": sat,
                        "headroom_pct": 100 - sat,
                    })

            if saturation_data:
                sat_df = pd.DataFrame(saturation_data).sort_values("saturation_pct", ascending=True)

                fig_sat = go.Figure()
                bar_colors = []
                for s in sat_df["saturation_pct"]:
                    if s > 80:
                        bar_colors.append("#EF4444")
                    elif s > 60:
                        bar_colors.append("#F59E0B")
                    else:
                        bar_colors.append("#10B981")

                fig_sat.add_trace(go.Bar(
                    y=sat_df["channel"],
                    x=sat_df["saturation_pct"],
                    orientation="h",
                    marker=dict(color=bar_colors, opacity=0.85),
                    text=[f"{v:.0f}%" for v in sat_df["saturation_pct"]],
                    textposition="outside",
                    textfont=dict(color="#E2E8F0", size=11),
                    hovertemplate="<b>%{y}</b><br>Saturation: %{x:.1f}%<extra></extra>",
                ))

                fig_sat.update_layout(
                    **CHART_LAYOUT,
                    title="Channel Saturation Levels",
                    xaxis_title="Saturation (%)",
                    yaxis_title="",
                    height=max(400, len(sat_df) * 40),
                    showlegend=False,
                )
                fig_sat.update_xaxes(range=[0, 110])
                st.plotly_chart(fig_sat, use_container_width=True)

        elif optimal is not None:
            st.markdown("#### Optimal Frequency Analysis")
            st.dataframe(optimal, use_container_width=True, hide_index=True)

        else:
            st.info("No saturation or frequency data available.")

else:
    st.info("No performance data available. Please upload an Excel file with a 'media_summary' or 'roi_summary' sheet.")
