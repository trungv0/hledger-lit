"""Tests for HledgerRunner (hledger.py)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from hledger_lit.hledger import HledgerError, HledgerRunner
from hledger_lit.models import AccountBalance, HistoricalData, Posting


@pytest.fixture()
def runner() -> HledgerRunner:
    return HledgerRunner()


# ---------------------------------------------------------------------------
# run_command()
# ---------------------------------------------------------------------------


class TestRunCommand:
    def test_returns_parsed_json(self, runner: HledgerRunner):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"key": "value"})

        with patch(
            "hledger_lit.hledger.subprocess.run", return_value=mock_result
        ) as mock_run:
            result = runner.run_command("hledger balance -O json")
            assert result == {"key": "value"}
            # Verify shlex.split is used (args should be a list, not a string)
            args_passed = mock_run.call_args[0][0]
            assert isinstance(args_passed, list)
            assert args_passed == ["hledger", "balance", "-O", "json"]

    def test_raises_hledger_error_on_nonzero_exit(self, runner: HledgerRunner):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "hledger: file not found"

        with patch("hledger_lit.hledger.subprocess.run", return_value=mock_result):
            with pytest.raises(HledgerError, match="file not found"):
                runner.run_command("hledger balance -O json")


# ---------------------------------------------------------------------------
# run_historical_command()
# ---------------------------------------------------------------------------


class TestRunHistoricalCommand:
    def test_returns_historical_data(
        self, runner: HledgerRunner, historical_balance_json: dict
    ):
        with patch.object(runner, "run_command", return_value=historical_balance_json):
            result = runner.run_historical_command(
                command="hledger balance --historical -O json",
                commodity="£",
                asset_regex="assets",
                liability_regex="liabilities",
            )

        assert isinstance(result, HistoricalData)
        assert result.dates == ["2024-01-01", "2024-02-01", "2024-03-01"]
        assert "assets:checking" in result.balances
        assert "assets:savings" in result.balances
        assert "liabilities:credit_card" in result.balances
        assert "net_worth" in result.balances

    def test_net_worth_calculation(
        self, runner: HledgerRunner, historical_balance_json: dict
    ):
        with patch.object(runner, "run_command", return_value=historical_balance_json):
            result = runner.run_historical_command(
                command="hledger balance --historical -O json",
                commodity="£",
                asset_regex="assets",
                liability_regex="liabilities",
            )

        # net_worth = assets:checking + assets:savings - liabilities:credit_card
        assert result.balances["net_worth"] == [5800.0, 6050.0, 6600.0]


# ---------------------------------------------------------------------------
# read_current_balances()
# ---------------------------------------------------------------------------


class TestReadCurrentBalances:
    def test_returns_account_balance_list(
        self, runner: HledgerRunner, current_balance_json: list
    ):
        with patch.object(runner, "run_command", return_value=current_balance_json):
            result = runner.read_current_balances("hledger balance -O json")

        assert all(isinstance(ab, AccountBalance) for ab in result)
        assert len(result) == 8

    def test_balance_values_match(
        self, runner: HledgerRunner, current_balance_json: list
    ):
        with patch.object(runner, "run_command", return_value=current_balance_json):
            result = runner.read_current_balances("hledger balance -O json")

        by_name = {ab.name: ab.amount for ab in result}
        assert by_name["expenses"] == 800.0
        assert by_name["expenses:food"] == 300.0
        assert by_name["income"] == -2000.0


# ---------------------------------------------------------------------------
# read_register()
# ---------------------------------------------------------------------------


class TestReadRegister:
    def test_returns_posting_list(self, runner: HledgerRunner, register_json: list):
        with patch.object(runner, "run_command", return_value=register_json):
            result = runner.read_register("hledger register -O json", "£")

        assert all(isinstance(p, Posting) for p in result)
        assert len(result) == 3

    def test_forward_fills_date_and_description(
        self, runner: HledgerRunner, register_json: list
    ):
        with patch.object(runner, "run_command", return_value=register_json):
            result = runner.read_register("hledger register -O json", "£")

        # Second posting has null date/description in the JSON, forward-filled here
        assert result[1].date == "2024-01-01"
        assert result[1].description == "Opening Balances"

    def test_amount_and_running_total_are_signed(
        self, runner: HledgerRunner, register_json: list
    ):
        with patch.object(runner, "run_command", return_value=register_json):
            result = runner.read_register("hledger register -O json", "£")

        assert result[1].amount == -1200.0
        assert result[1].running_total == 0.0

    def test_missing_commodity_defaults_to_zero(
        self, runner: HledgerRunner, register_json: list
    ):
        with patch.object(runner, "run_command", return_value=register_json):
            result = runner.read_register("hledger register -O json", "$")

        assert all(p.amount == 0.0 for p in result)
        assert all(p.running_total == 0.0 for p in result)

    def test_tags_are_tuples(self, runner: HledgerRunner, register_json: list):
        with patch.object(runner, "run_command", return_value=register_json):
            result = runner.read_register("hledger register -O json", "£")

        assert result[0].tags == [("type", "A")]
        assert result[1].tags == []
