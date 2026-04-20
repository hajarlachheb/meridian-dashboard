# Meridian MMM Dashboard

A Sellforte-style interactive dashboard for visualizing Google Meridian Marketing Mix Model results.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the dashboard
streamlit run app.py
```

## Features

| Page | Description |
|------|-------------|
| **Home** | KPI summary, model fit overview, key recommendations |
| **Dashboard** | Sales decomposition, ROI analysis (bar, bubble, table), contribution breakdown |
| **Performance** | Channel ROI with confidence intervals, marginal ROI, response curves, saturation analysis |
| **Optimizer** | Budget optimization with scenario planning, weekly pacing, allocation comparison |
| **Data & Model** | Model diagnostics, residual analysis, data quality, methodology reference |

## Data Format

Upload an Excel file (`.xlsx`) with one or more of these sheets:

| Sheet | Required Columns |
|-------|-----------------|
| `media_summary` | `channel`, `spend`, `roi`, `incremental_revenue`, `marginal_roi`, `pct_spend`, `pct_incremental_revenue` |
| `model_fit` | `metric`, `value` |
| `weekly_decomposition` | `date`, `baseline`, `total_predicted`, `total_actual`, plus one column per channel |
| `response_curves` | `channel`, `spend_level`, `incremental_revenue`, `current_spend`, `current_revenue` |
| `roi_summary` | `channel`, `roi`, `roi_lower_ci`, `roi_upper_ci`, `marginal_roi`, `mroi_lower_ci`, `mroi_upper_ci` |
| `optimal_frequency` | `channel`, `current_frequency`, `optimal_frequency`, `current_reach`, `saturation_point` |

### Generate Sample Data

```bash
python generate_sample_excel.py
```

This creates `sample_meridian_output.xlsx` which you can use as a template.

## Powered By

- [Google Meridian](https://developers.google.com/meridian) — Open-source Bayesian MMM
- [Streamlit](https://streamlit.io/) — Python web framework
- [Plotly](https://plotly.com/) — Interactive charts
