"""Register page: spot-check hledger transactions via ad-hoc queries."""

from __future__ import annotations

import dataclasses
import subprocess

import streamlit as st

from hledger_lit.charts import ChartBuilder
from hledger_lit.config import ConfigManager
from hledger_lit.hledger import HledgerError, HledgerRunner
from hledger_lit.sidebar import render_core_filters
from hledger_lit.transforms import DataTransformer

st.set_page_config(page_title="Register — HLedger is Lit!", layout="wide")
st.title("Register")
st.markdown("Spot-check transactions and postings via hledger's register command")

config_manager = ConfigManager()
hledger = HledgerRunner()
charts = ChartBuilder()

cfg = config_manager.load()
dev_mode = config_manager.dev_mode

with st.sidebar:
    st.header("Configuration")

    if dev_mode:
        st.info(
            "🧪 Dev mode active — using example.journal, config not persisted"
        )

    core = render_core_filters(cfg, hledger, dev_mode)

    query = st.text_input(
        "Query",
        value="",
        help=(
            "Raw hledger query syntax, e.g. `assets:bank tag:type=A`. "
            "Extra flags like -H (historical) or -r (related) also work here."
        ),
    )

if not core.filename:
    st.warning("👈 Please provide a path to your hledger journal file in the sidebar")
    st.stop()

run_register = st.button("Run Register", type="primary")

if run_register:
    cmd_vars = {
        "filename": core.filename,
        "query": query,
        "commodity": core.commodity,
        "depth": core.depth,
        "start_date": core.start_date,
        "end_date": core.end_date,
    }
    command = ConfigManager.DEFAULT_REGISTER_CMD.format(**cmd_vars)

    try:
        postings = hledger.read_register(command, core.commodity)
        st.session_state["register_postings"] = postings
    except (HledgerError, subprocess.CalledProcessError) as exc:
        st.session_state["register_postings"] = None
        st.error(f"Error running register: {exc}")
    except Exception as exc:
        st.session_state["register_postings"] = None
        st.error(f"Unexpected error: {exc}")

if "register_postings" in st.session_state and st.session_state["register_postings"] is not None:
    postings = st.session_state["register_postings"]
    if not postings:
        st.info("No matching postings.")
    else:
        grouped = DataTransformer.group_postings_by_top_level_account(postings)

        tab_viz, tab_table = st.tabs(["📊 Visualizations", "📋 Transactions Table"])

        with tab_viz:
            if not grouped:
                st.info("No account data available for visualization.")
            elif len(grouped) == 1:
                top_acc, balances = next(iter(grouped.items()))
                fig = charts.account_treemap_plot(
                    balances,
                    title=f"{top_acc.capitalize()} Treemap",
                    commodity=core.commodity,
                    depth=core.depth,
                )
                st.plotly_chart(fig, key=f"treemap_{top_acc}", width="stretch")
            else:
                sub_tabs = st.tabs(
                    [f"🌳 {top_acc.capitalize()}" for top_acc in grouped.keys()]
                )
                for (top_acc, balances), sub_tab in zip(
                    grouped.items(), sub_tabs, strict=True
                ):
                    with sub_tab:
                        fig = charts.account_treemap_plot(
                            balances,
                            title=f"{top_acc.capitalize()} Treemap",
                            commodity=core.commodity,
                            depth=core.depth,
                        )
                        st.plotly_chart(
                            fig, key=f"treemap_{top_acc}", width="stretch"
                        )

        with tab_table:
            st.dataframe(
                [dataclasses.asdict(p) for p in postings], width="stretch"
            )

