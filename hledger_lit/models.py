"""Typed data structures for hledger-lit."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class HistoricalData:
    """Time-series balances keyed by account name, with a shared date axis."""

    dates: list[str]
    balances: dict[str, list[float]]


@dataclass
class SankeyLink:
    """A single directed flow between two accounts."""

    source: str
    target: str
    value: float


@dataclass
class AccountBalance:
    """An account name paired with its balance."""

    name: str
    amount: float


@dataclass
class Posting:
    """A single posting line from ``hledger register``, with running total."""

    date: str
    description: str
    account: str
    amount: float
    running_total: float
    status: str
    comment: str
    tags: list[tuple[str, str]]


@dataclass
class AppConfig:
    """All user-configurable settings, persisted to the INI file."""

    filename: str
    commodity: str
    income_regex: str
    expense_regex: str
    asset_regex: str
    liability_regex: str
    historical_cmd: str
    expenses_cmd: str
    income_expenses_cmd: str
    all_flows_cmd: str
    daily_expenses_cmd: str
    exclude_filter_options: str
