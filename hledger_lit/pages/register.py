"""Register page: spot-check hledger transactions via ad-hoc queries."""

from __future__ import annotations

import dataclasses
import subprocess

import streamlit as st

from hledger_lit.config import ConfigManager
from hledger_lit.hledger import HledgerError, HledgerRunner
from hledger_lit.sidebar import render_core_filters

st.set_page_config(page_title="Register — HLedger is Lit!", layout="wide")
st.title("Register")
st.markdown("Spot-check transactions and postings via hledger's register command")

config_manager = ConfigManager()
hledger = HledgerRunner()

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

if st.button("Run Register", type="primary"):
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
    except (HledgerError, subprocess.CalledProcessError) as exc:
        st.error(f"Error running register: {exc}")
    except Exception as exc:
        st.error(f"Unexpected error: {exc}")
    else:
        if not postings:
            st.info("No matching postings.")
        else:
            st.dataframe(
                [dataclasses.asdict(p) for p in postings], width="stretch"
            )
