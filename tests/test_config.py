"""Tests for ConfigManager (config.py)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hledger_lit.config import ConfigManager
from hledger_lit.models import AppConfig


@pytest.fixture()
def config_manager(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ConfigManager:
    """A ConfigManager that writes to a temp directory."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return ConfigManager()


# ---------------------------------------------------------------------------
# load() defaults
# ---------------------------------------------------------------------------


class TestLoadDefaults:
    def test_returns_app_config(self, config_manager: ConfigManager):
        cfg = config_manager.load()
        assert isinstance(cfg, AppConfig)

    def test_default_commodity(self, config_manager: ConfigManager):
        cfg = config_manager.load()
        assert cfg.commodity == "£"

    def test_default_regexes(self, config_manager: ConfigManager):
        cfg = config_manager.load()
        assert cfg.income_regex == ConfigManager.INCOME_REGEX
        assert cfg.expense_regex == ConfigManager.EXPENSE_REGEX
        assert cfg.asset_regex == ConfigManager.ASSET_REGEX
        assert cfg.liability_regex == ConfigManager.LIABILITY_REGEX

    def test_default_exclude_filter_options(self, config_manager: ConfigManager):
        cfg = config_manager.load()
        assert cfg.exclude_filter_options == ConfigManager.DEFAULT_EXCLUDE_FILTER_OPTIONS


# ---------------------------------------------------------------------------
# save() / load() round-trip
# ---------------------------------------------------------------------------


class TestSaveLoadRoundTrip:
    def test_round_trip_preserves_all_fields(self, config_manager: ConfigManager):
        original = AppConfig(
            filename="/tmp/test.journal",
            commodity="$",
            income_regex="revenue",
            expense_regex="cost",
            asset_regex="cash",
            liability_regex="debt",
            historical_cmd="hledger bal --historical",
            expenses_cmd="hledger bal expenses",
            income_expenses_cmd="hledger bal inc exp",
            all_flows_cmd="hledger bal all",
            daily_expenses_cmd="hledger bal expenses --period daily",
            exclude_filter_options="tag:clopen,tag:test",
        )

        config_manager.save(original)
        loaded = config_manager.load()

        assert loaded.filename == original.filename
        assert loaded.commodity == original.commodity
        assert loaded.income_regex == original.income_regex
        assert loaded.expense_regex == original.expense_regex
        assert loaded.asset_regex == original.asset_regex
        assert loaded.liability_regex == original.liability_regex
        assert loaded.historical_cmd == original.historical_cmd
        assert loaded.expenses_cmd == original.expenses_cmd
        assert loaded.income_expenses_cmd == original.income_expenses_cmd
        assert loaded.all_flows_cmd == original.all_flows_cmd
        assert loaded.daily_expenses_cmd == original.daily_expenses_cmd
        assert loaded.exclude_filter_options == original.exclude_filter_options

    def test_save_returns_path(self, config_manager: ConfigManager):
        cfg = config_manager.load()
        path = config_manager.save(cfg)
        assert isinstance(path, Path)
        assert path.exists()


# ---------------------------------------------------------------------------
# reset()
# ---------------------------------------------------------------------------


class TestDevMode:
    def test_dev_mode_off_by_default(self, config_manager: ConfigManager):
        assert config_manager.dev_mode is False

    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
    def test_dev_mode_true_variants(
        self,
        config_manager: ConfigManager,
        monkeypatch: pytest.MonkeyPatch,
        value: str,
    ):
        monkeypatch.setenv(ConfigManager.DEV_MODE_ENV_VAR, value)
        assert config_manager.dev_mode is True

    def test_dev_mode_ignores_saved_config(
        self, config_manager: ConfigManager, monkeypatch: pytest.MonkeyPatch
    ):
        custom = AppConfig(
            filename="/tmp/test.journal",
            commodity="$",
            income_regex="revenue",
            expense_regex="cost",
            asset_regex="cash",
            liability_regex="debt",
            historical_cmd="hledger bal --historical",
            expenses_cmd="hledger bal expenses",
            income_expenses_cmd="hledger bal inc exp",
            all_flows_cmd="hledger bal all",
            daily_expenses_cmd="hledger bal expenses --period daily",
            exclude_filter_options="tag:clopen,tag:test",
        )
        config_manager.save(custom)

        monkeypatch.setenv(ConfigManager.DEV_MODE_ENV_VAR, "1")
        cfg = config_manager.load()

        assert cfg.filename.endswith("example.journal")
        assert cfg.commodity == "£"
        assert cfg.income_regex == ConfigManager.INCOME_REGEX
        assert cfg.expense_regex == ConfigManager.EXPENSE_REGEX
        assert cfg.asset_regex == ConfigManager.ASSET_REGEX
        assert cfg.liability_regex == ConfigManager.LIABILITY_REGEX
        assert cfg.exclude_filter_options == ConfigManager.DEFAULT_EXCLUDE_FILTER_OPTIONS

    def test_dev_mode_filename_points_to_existing_file(
        self, config_manager: ConfigManager, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv(ConfigManager.DEV_MODE_ENV_VAR, "1")
        cfg = config_manager.load()
        assert Path(cfg.filename).exists()


class TestExcludeFilters:
    def test_default_exclude_filter_options(self):
        assert ConfigManager.DEFAULT_EXCLUDE_FILTER_OPTIONS == "tag:clopen"

    @pytest.mark.parametrize(
        "template_name",
        [
            "DEFAULT_HISTORICAL_CMD",
            "DEFAULT_EXPENSES_CMD",
            "DEFAULT_INCOME_EXPENSES_CMD",
            "DEFAULT_ALL_FLOWS_CMD",
            "DEFAULT_DAILY_EXPENSES_CMD",
        ],
    )
    def test_templates_use_placeholder_not_literal(self, template_name: str):
        template = getattr(ConfigManager, template_name)
        assert "{exclude_filters}" in template
        assert "not:tag:clopen" not in template


class TestReset:
    def test_reset_removes_config_file(self, config_manager: ConfigManager):
        cfg = config_manager.load()
        config_manager.save(cfg)
        assert config_manager.config_path.exists()

        config_manager.reset()
        assert not config_manager.config_path.exists()

    def test_reset_when_no_file_exists(self, config_manager: ConfigManager):
        # Should not raise
        config_manager.reset()
        assert not config_manager.config_path.exists()
