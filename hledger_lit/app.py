"""Streamlit UI for hledger-lit."""

from __future__ import annotations

import dataclasses
import html
import json
import subprocess
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

import plotly.graph_objects as go
import streamlit as st

from hledger_lit.charts import ChartBuilder
from hledger_lit.config import ConfigManager
from hledger_lit.hledger import HledgerError, HledgerRunner
from hledger_lit.models import AppConfig
from hledger_lit.sidebar import render_core_filters
from hledger_lit.transforms import DataTransformer


def display_chart(
    label: str,
    session_key: str,
    *,
    tip: str | None = None,
) -> None:
    """Display a previously-generated chart from session state."""
    st.header(label)
    if tip:
        st.caption(tip)

    result = st.session_state.get(session_key)
    if isinstance(result, Exception):
        st.error(f"Error generating {label}: {result}")
    elif result is not None:
        st.plotly_chart(result, key=session_key, width="stretch")

    st.divider()


# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------
st.set_page_config(page_title="'HLedger is Lit!' Visualizer", layout="wide")
st.title("'HLedger is Lit!' Visualizer")
st.markdown("Generate graphs from hledger balance reports")

# Instantiate service objects
config_manager = ConfigManager()
hledger = HledgerRunner()
charts = ChartBuilder()
transformer = DataTransformer()

# Load persisted config (merged with defaults)
cfg = config_manager.load()
dev_mode = config_manager.dev_mode

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Configuration")

    if dev_mode:
        st.info(
            "🧪 Dev mode active — using example.journal, config not persisted"
        )

    core = render_core_filters(cfg, hledger, dev_mode)
    filename, commodity, start_date, end_date, depth = (
        core.filename,
        core.commodity,
        core.start_date,
        core.end_date,
        core.depth,
    )

    period = st.selectbox(
        "Report Period",
        options=ConfigManager.PERIOD_CHOICES,
        index=ConfigManager.PERIOD_CHOICES.index(ConfigManager.DEFAULT_PERIOD),
        help="Report interval for the historical balances and expenses charts (hledger --period flag)",
    )

    exclude_filter_catalog = [
        f.strip() for f in cfg.exclude_filter_options.split(",") if f.strip()
    ]
    excluded_filters = st.multiselect(
        "Excluded Query Filters",
        options=exclude_filter_catalog,
        default=exclude_filter_catalog,
        accept_new_options=True,
        help=(
            "Selected filters are excluded from all reports for the current session. "
            "Click 'Save Excluded Filters' to keep the current selection permanently."
        ),
    )
    save_excluded_filters_btn = st.button(
        "Save Excluded Filters", width="stretch", disabled=dev_mode
    )

    col_save, col_reset = st.columns(2)
    with col_save:
        save_btn = st.button(
            "Save Config", width="stretch", disabled=dev_mode
        )
    with col_reset:
        reset_btn = st.button(
            "Reset to Defaults", width="stretch", disabled=dev_mode
        )

    # ---- Account Regex Patterns ----
    st.subheader("Account Regex Patterns")
    st.caption("Regular expressions for matching account categories")

    income_regex = st.text_input(
        "Income Regex",
        value=cfg.income_regex,
        help="Regex to match income accounts. Multiple patterns separated by space or '|'",
    )
    expense_regex = st.text_input(
        "Expense Regex",
        value=cfg.expense_regex,
        help="Regex to match expense accounts. Multiple patterns separated by space or '|'",
    )
    asset_regex = st.text_input(
        "Asset Regex",
        value=cfg.asset_regex,
        help="Regex to match asset accounts. Multiple patterns separated by space or '|'",
    )
    liability_regex = st.text_input(
        "Liability Regex",
        value=cfg.liability_regex,
        help="Regex to match liability accounts. Multiple patterns separated by space or '|'",
    )

    # ---- Command Templates ----
    st.subheader("Command Templates")
    st.caption(
        "Available variables: {filename}, {commodity}, {start_date}, {end_date}, "
        "{income_regex}, {expense_regex}, {asset_regex}, {liability_regex}, "
        "{all_accounts}, {depth}, {period}, {exclude_filters}"
    )

    with st.expander("Historical Balances Command", expanded=False):
        historical_cmd = st.text_area(
            "HLedger Command",
            value=cfg.historical_cmd,
            height=100,
            key="historical_cmd_sidebar",
        )

    with st.expander("Expenses Treemap Command", expanded=False):
        expenses_cmd = st.text_area(
            "HLedger Command",
            value=cfg.expenses_cmd,
            height=100,
            key="expenses_cmd_sidebar",
        )

    with st.expander("Income & Expenses Command", expanded=False):
        income_expenses_cmd = st.text_area(
            "HLedger Command",
            value=cfg.income_expenses_cmd,
            height=100,
            key="income_expenses_cmd_sidebar",
        )

    with st.expander("All Flows Command", expanded=False):
        all_flows_cmd = st.text_area(
            "HLedger Command",
            value=cfg.all_flows_cmd,
            height=100,
            key="all_flows_cmd_sidebar",
        )

    with st.expander("Daily Expenses Command", expanded=False):
        daily_expenses_cmd = st.text_area(
            "HLedger Command",
            value=cfg.daily_expenses_cmd,
            height=100,
            key="daily_expenses_cmd_sidebar",
        )

# ---------------------------------------------------------------------------
# Button handlers
# ---------------------------------------------------------------------------
if save_btn:
    new_cfg = AppConfig(
        filename=filename,
        commodity=commodity,
        income_regex=income_regex,
        expense_regex=expense_regex,
        asset_regex=asset_regex,
        liability_regex=liability_regex,
        historical_cmd=historical_cmd,
        expenses_cmd=expenses_cmd,
        income_expenses_cmd=income_expenses_cmd,
        all_flows_cmd=all_flows_cmd,
        daily_expenses_cmd=daily_expenses_cmd,
        exclude_filter_options=cfg.exclude_filter_options,
    )
    path = config_manager.save(new_cfg)
    st.success(f"Configuration saved to {path}")

if save_excluded_filters_btn:
    new_cfg = dataclasses.replace(cfg, exclude_filter_options=",".join(excluded_filters))
    path = config_manager.save(new_cfg)
    st.success(f"Excluded filters saved to {path}")

if reset_btn:
    config_manager.reset()
    st.success(
        "Configuration reset to defaults. Please refresh the page to see the changes."
    )

# Guard: require a journal file
if not filename:
    st.warning("👈 Please provide a path to your hledger journal file in the sidebar")
    st.stop()

# ---------------------------------------------------------------------------
# Template variables shared by all commands
# ---------------------------------------------------------------------------
all_accounts = f"{income_regex} {expense_regex} {asset_regex} {liability_regex}"
exclude_filters = " ".join(f"not:{f}" for f in excluded_filters)
cmd_vars: dict[str, object] = {
    "filename": filename,
    "commodity": commodity,
    "start_date": start_date,
    "end_date": end_date,
    "income_regex": income_regex,
    "expense_regex": expense_regex,
    "asset_regex": asset_regex,
    "liability_regex": liability_regex,
    "all_accounts": all_accounts,
    "depth": depth,
    "period": period,
    "exclude_filters": exclude_filters,
}

# ---------------------------------------------------------------------------
# Charts — generate all concurrently, re-run when config changes
# ---------------------------------------------------------------------------

ChartSpec = tuple[str, str, Callable[[], go.Figure], str | None]

chart_specs: list[ChartSpec] = [
    (
        "Historical Account Balances",
        "historical_fig",
        lambda: charts.historical_balances_plot(
            hledger.run_historical_command(
                historical_cmd.format(**cmd_vars),
                commodity,
                asset_regex,
                liability_regex,
            ),
            commodity,
            period,
        ),
        "💡 Tip: Click legend items to show/hide lines, double-click to isolate a single line",
    ),
    (
        "Expenses Treemap",
        "expenses_fig",
        lambda: charts.expenses_treemap_plot(
            hledger.read_current_balances(expenses_cmd.format(**cmd_vars)),
            commodity,
            depth,
        ),
        None,
    ),
    (
        "Income & Expenses Flows",
        "income_expenses_fig",
        lambda: charts.sankey_plot(
            transformer.to_sankey_data(
                hledger.read_current_balances(income_expenses_cmd.format(**cmd_vars)),
                income_regex,
                expense_regex,
                asset_regex,
                liability_regex,
            ),
            commodity,
            depth,
        ),
        None,
    ),
    (
        "All Cash Flows",
        "all_balances_fig",
        lambda: charts.sankey_plot(
            transformer.to_sankey_data(
                hledger.read_current_balances(all_flows_cmd.format(**cmd_vars)),
                income_regex,
                expense_regex,
                asset_regex,
                liability_regex,
            ),
            commodity,
            depth,
        ),
        None,
    ),
    (
        "Daily Expenses",
        "daily_expenses_fig",
        lambda: charts.daily_expenses_plot(
            hledger.run_periodic_command(
                daily_expenses_cmd.format(**cmd_vars),
                commodity,
            ),
            commodity,
            period,
            depth,
        ),
        "💡 Tip: Stacked bar chart of spending by expense category, per period",
    ),
]

# Fingerprint current config so we only regenerate when something changes
_config_fingerprint = (
    filename,
    commodity,
    str(start_date),
    str(end_date),
    income_regex,
    expense_regex,
    asset_regex,
    liability_regex,
    depth,
    period,
    tuple(sorted(excluded_filters)),
    historical_cmd,
    expenses_cmd,
    income_expenses_cmd,
    all_flows_cmd,
    daily_expenses_cmd,
)

_config_changed = st.session_state.get("_config_fingerprint") != _config_fingerprint
render_btn = st.button(
    "Render" if not _config_changed else "Render  :material/autorenew:",
    type="primary",
    width="stretch",
)
_should_render = render_btn or _config_changed


def _generate_all_charts() -> None:
    """Run all chart generators concurrently and stash results in session state."""
    with ThreadPoolExecutor() as executor:
        futures = {
            executor.submit(gen_fn): (label, key)
            for label, key, gen_fn, _tip in chart_specs
        }
        for future in as_completed(futures):
            _label, key = futures[future]
            try:
                st.session_state[key] = future.result()
            except (HledgerError, subprocess.CalledProcessError) as exc:
                st.session_state[key] = exc
            except json.JSONDecodeError as exc:
                st.session_state[key] = exc
            except Exception as exc:
                st.session_state[key] = exc
    st.session_state["_config_fingerprint"] = _config_fingerprint


def _build_html_report(figures: list[tuple[str, go.Figure]]) -> str:
    """Build a single self-contained HTML report from a list of (label, figure) pairs."""
    sections: list[str] = []
    for label, fig in figures:
        export_fig = go.Figure(fig)
        export_fig.update_layout(template="plotly_dark")
        chart_html = export_fig.to_html(full_html=False, include_plotlyjs=False)
        sections.append(
            f"<section><h2>{html.escape(label)}</h2>{chart_html}<hr></section>"
        )
    body = "\n".join(sections)
    title = html.escape(f"HLedger Report — {start_date} to {end_date}")
    return (
        "<!DOCTYPE html>\n"
        f"<html><head><meta charset='utf-8'><title>{title}</title>"
        '<script src="https://cdn.plot.ly/plotly-3.4.0.min.js" charset="utf-8"></script>'
        "<style>"
        "body{font-family:system-ui,sans-serif;max-width:1200px;margin:0 auto;padding:2rem}"
        "h1{color:#333}h2{color:#555}hr{border:none;border-top:1px solid #ddd;margin:2rem 0}"
        "</style>"
        f"</head><body><h1>{title}</h1>{body}</body></html>"
    )


@st.fragment
def _download_report() -> None:
    figures = [
        (label, st.session_state[key])
        for label, key, _, _ in chart_specs
        if isinstance(st.session_state.get(key), go.Figure)
    ]
    st.download_button(
        "Export Report",
        data=_build_html_report(figures) if figures else "",
        file_name="hledger-report.html",
        mime="text/html",
        icon=":material/download:",
        disabled=not figures,
        width="stretch",
    )


if _should_render:
    with st.spinner("Generating all charts...", show_time=True):
        _generate_all_charts()

_download_report()

for label, key, _gen_fn, tip in chart_specs:
    display_chart(label, key, tip=tip)
