import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from utils.charts import model_fit_chart, CHART_LAYOUT, COLORS, page_header, setup_page, sidebar_logo

st.set_page_config(page_title="Data & Model | s360 MMM", page_icon="🔍", layout="wide")
setup_page()
sidebar_logo()

data = st.session_state.data

page_header("Data & Model", "Transparency into the MMM engine — model diagnostics, data overview, and methodology")

tab1, tab2, tab3 = st.tabs([
    "Model Diagnostics",
    "Data Overview",
    "Methodology",
])

with tab1:
    fit_data = data.get("model_fit")
    decomp = data.get("weekly_decomposition")

    if fit_data is not None:
        st.markdown("#### Model Fit Statistics")
        cols = st.columns(len(fit_data))
        for i, (_, row) in enumerate(fit_data.iterrows()):
            metric_name = row["metric"]
            val = row["value"]

            if "MAPE" in metric_name.upper() or "NRMSE" in metric_name.upper():
                display = f"{val:.1%}" if val < 1 else f"{val:.1f}%"
                if val < 0.1:
                    quality = "Excellent"
                    color = "#276749"
                elif val < 0.2:
                    quality = "Good"
                    color = "#975A16"
                else:
                    quality = "Fair"
                    color = "#9B2C2C"
            elif "R-squared" in metric_name or "R2" in metric_name.upper():
                display = f"{val:.4f}"
                if val > 0.9:
                    quality = "Excellent"
                    color = "#276749"
                elif val > 0.8:
                    quality = "Good"
                    color = "#975A16"
                else:
                    quality = "Fair"
                    color = "#9B2C2C"
            elif "DW" in metric_name.upper():
                display = f"{val:.3f}"
                if 1.5 < val < 2.5:
                    quality = "Good"
                    color = "#276749"
                else:
                    quality = "Review"
                    color = "#975A16"
            else:
                display = f"{val:.4f}"
                quality = ""
                color = "#64748B"

            with cols[i]:
                st.metric(metric_name, display)
                if quality:
                    st.markdown(
                        f"<span style='color:{color}; font-size:0.85rem; font-weight:600;'>{quality}</span>",
                        unsafe_allow_html=True,
                    )

        st.markdown("---")

    if decomp is not None:
        st.markdown("#### Predicted vs. Actual Revenue")
        fig = model_fit_chart(decomp)
        st.plotly_chart(fig, use_container_width=True)

        if "total_actual" in decomp.columns and "total_predicted" in decomp.columns:
            residuals = decomp["total_actual"] - decomp["total_predicted"]

            st.markdown("#### Residuals Analysis")

            res_cols = st.columns(2)
            with res_cols[0]:
                fig_res = go.Figure()
                fig_res.add_trace(go.Scatter(
                    x=decomp["date"],
                    y=residuals,
                    mode="lines+markers",
                    marker=dict(size=4, color="#4A6CF7"),
                    line=dict(color="#4A6CF7", width=1),
                    hovertemplate="%{x|%b %d, %Y}<br>Residual: $%{y:,.0f}<extra></extra>",
                ))
                fig_res.add_hline(y=0, line=dict(color="rgba(245,101,101,0.5)", dash="dash"))
                fig_res.update_layout(
                    **CHART_LAYOUT,
                    title="Residuals Over Time",
                    xaxis_title="",
                    yaxis_title="Residual ($)",
                    height=350,
                )
                st.plotly_chart(fig_res, use_container_width=True)

            with res_cols[1]:
                fig_hist = go.Figure()
                fig_hist.add_trace(go.Histogram(
                    x=residuals,
                    nbinsx=30,
                    marker=dict(color="#4A6CF7", opacity=0.75,
                                line=dict(width=0.5, color="white")),
                    hovertemplate="Range: $%{x:,.0f}<br>Count: %{y}<extra></extra>",
                ))
                fig_hist.update_layout(
                    **CHART_LAYOUT,
                    title="Residual Distribution",
                    xaxis_title="Residual ($)",
                    yaxis_title="Frequency",
                    height=350,
                )
                st.plotly_chart(fig_hist, use_container_width=True)

            st.markdown("#### Fit Statistics")
            actual = decomp["total_actual"]
            predicted = decomp["total_predicted"]

            r2 = 1 - (residuals ** 2).sum() / ((actual - actual.mean()) ** 2).sum()
            mape = (abs(residuals) / actual).mean()
            wmape = abs(residuals).sum() / actual.sum()

            stat_cols = st.columns(4)
            with stat_cols[0]:
                st.metric("R²", f"{r2:.4f}")
            with stat_cols[1]:
                st.metric("MAPE", f"{mape:.1%}")
            with stat_cols[2]:
                st.metric("wMAPE", f"{wmape:.1%}")
            with stat_cols[3]:
                st.metric("Mean Residual", f"${residuals.mean():,.0f}")

with tab2:
    st.markdown("#### Available Data Sheets")

    for key, df in data.items():
        with st.expander(f"**{key}** — {len(df)} rows × {len(df.columns)} columns"):
            st.markdown(f"**Columns:** {', '.join(df.columns.tolist())}")
            st.dataframe(df.head(20), use_container_width=True, hide_index=True)

            csv = df.to_csv(index=False)
            st.download_button(
                f"Download {key}.csv",
                csv,
                f"{key}.csv",
                "text/csv",
                key=f"download_{key}",
            )

    st.markdown("---")
    st.markdown("#### Data Quality Summary")

    quality_data = []
    for key, df in data.items():
        nulls = df.isnull().sum().sum()
        total = df.shape[0] * df.shape[1]
        quality_data.append({
            "Sheet": key,
            "Rows": df.shape[0],
            "Columns": df.shape[1],
            "Missing Values": nulls,
            "Completeness": f"{(1 - nulls / total) * 100:.1f}%" if total > 0 else "N/A",
        })

    st.dataframe(pd.DataFrame(quality_data), use_container_width=True, hide_index=True)

with tab3:
    st.markdown("#### Google Meridian MMM Methodology")

    st.markdown(
        """
        <div style="background:#F8F9FC; border:1px solid #E2E8F0;
            border-radius:10px; padding:1.5rem; margin-bottom:1rem;">

        **Google Meridian** is an open-source Bayesian Marketing Mix Model (MMM) framework
        designed for modern marketers. Key methodological features:

        - **Bayesian Causal Inference**: Uses Bayesian regression to estimate the causal impact
          of marketing activities on business outcomes, providing credible intervals for all estimates.

        - **Geo-Level Hierarchical Modeling**: Leverages geographic variation in marketing spend
          and outcomes to improve model identification and causal inference.

        - **Adstock & Saturation**: Models advertising carryover effects (adstock) and diminishing
          returns (saturation) using flexible functional forms.

        - **Google Query Volume (GQV)**: Incorporates Google search data as a proxy for consumer
          interest and brand awareness, improving model accuracy.

        - **Prior Elicitation**: Allows incorporation of domain expertise and experimental results
          (e.g., geo lift tests) as Bayesian priors, calibrating the model to known truths.

        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("#### Key Metrics Explained")

    metrics_info = {
        "ROI (Return on Investment)": "Total incremental revenue generated per dollar spent on a channel. ROI = Incremental Revenue / Spend.",
        "Marginal ROI (mROI)": "The incremental revenue from the *next* dollar spent. Unlike average ROI, mROI accounts for diminishing returns and indicates whether additional investment is worthwhile.",
        "R-squared (R²)": "Proportion of variance in the target KPI explained by the model. Values above 0.90 indicate strong model fit.",
        "MAPE": "Mean Absolute Percentage Error — average prediction error as a percentage. Values below 10% indicate good predictive accuracy.",
        "wMAPE": "Weighted MAPE — MAPE weighted by actual values, reducing the influence of small-value periods.",
        "Response Curve": "Shows the relationship between spend and incremental revenue for a channel, capturing diminishing returns at higher spend levels.",
        "Saturation": "How close a channel is to its maximum achievable incremental impact. High saturation means additional spend yields minimal extra returns.",
    }

    for metric, description in metrics_info.items():
        with st.expander(f"**{metric}**"):
            st.markdown(description)

    st.markdown("---")
    st.markdown(
        "<p style='color:#94A3B8; font-size:0.85rem; text-align:center;'>"
        "Learn more at "
        "<a href='https://developers.google.com/meridian' style='color:#4A6CF7;'>"
        "developers.google.com/meridian</a>"
        "</p>",
        unsafe_allow_html=True,
    )
