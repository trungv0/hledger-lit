"""Shared sidebar widgets reused across Streamlit pages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import streamlit as st

from hledger_lit.config import ConfigManager
from hledger_lit.hledger import HledgerRunner
from hledger_lit.models import AppConfig


@dataclass
class CoreFilters:
    """The filters shared by every page: file, commodity, date range, depth."""

    filename: str
    commodity: str
    start_date: date
    end_date: date
    depth: int


def render_core_filters(
    cfg: AppConfig, hledger: HledgerRunner, dev_mode: bool
) -> CoreFilters:
    """Render the filename/commodity/date-range/depth widgets.

    Must be called inside a ``with st.sidebar:`` block by the caller.
    """
    filename = st.text_input(
        "HLedger Journal File Path",
        value=cfg.filename,
        help="Path to your hledger journal file, defaults to $LEDGER_FILE",
    )

    try:
        commodities = hledger.get_commodities(filename)
    except Exception:
        commodities = []
    if cfg.commodity and cfg.commodity not in commodities:
        commodities.insert(0, cfg.commodity)
    if commodities:
        default_index = (
            commodities.index(cfg.commodity) if cfg.commodity in commodities else 0
        )
        commodity = st.selectbox(
            "Commodity",
            options=commodities,
            index=default_index,
            help="Commodity to convert all values to (via -value=then,{commodity})",
        )
    else:
        commodity = st.text_input(
            "Commodity",
            value=cfg.commodity,
            help="Commodity to convert all values to (via -value=then,{commodity})",
        )

    current_year = date.today().year
    default_start = date(2021, 1, 1) if dev_mode else date(current_year, 1, 1)
    default_end = date(2021, 12, 31) if dev_mode else date.today()
    start_date = st.date_input(
        "Start Date",
        value=default_start,
        help="Beginning date for the report (hledger -b flag)",
    )
    end_date = st.date_input(
        "End Date",
        value=default_end,
        help="End date for the report (hledger -e flag)",
    )

    depth = st.number_input(
        "Account Depth",
        min_value=1,
        value=ConfigManager.DEFAULT_DEPTH,
        help="Account depth for the treemap, sankey, and expenses charts (hledger --depth flag)",
    )

    return CoreFilters(
        filename=filename,
        commodity=commodity,
        start_date=start_date,
        end_date=end_date,
        depth=depth,
    )
