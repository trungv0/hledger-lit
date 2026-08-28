"""Tests for DataTransformer (transforms.py)."""

from __future__ import annotations

import pytest

from hledger_lit.models import AccountBalance
from hledger_lit.transforms import DataTransformer, MissingParentAccountError

# ---------------------------------------------------------------------------
# parent()
# ---------------------------------------------------------------------------


class TestParent:
    def test_hierarchical_name(self):
        assert DataTransformer.parent("a:b:c") == "a:b"

    def test_two_levels(self):
        assert DataTransformer.parent("assets:checking") == "assets"

    def test_top_level_returns_empty(self):
        assert DataTransformer.parent("assets") == ""

    def test_single_component(self):
        assert DataTransformer.parent("expenses") == ""


# ---------------------------------------------------------------------------
# compile_account_pattern()
# ---------------------------------------------------------------------------


class TestCompileAccountPattern:
    def test_space_separated(self):
        pat = DataTransformer.compile_account_pattern("income revenues")
        assert pat.search("income:salary")
        assert pat.search("revenues:other")
        assert not pat.search("expenses:food")

    def test_pipe_separated(self):
        pat = DataTransformer.compile_account_pattern("income|revenues")
        assert pat.search("income:salary")
        assert pat.search("revenues:other")

    def test_single_pattern(self):
        pat = DataTransformer.compile_account_pattern("assets")
        assert pat.search("assets:checking")
        assert not pat.search("liabilities")

    def test_invalid_regex_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid regex pattern"):
            DataTransformer.compile_account_pattern("[invalid")


# ---------------------------------------------------------------------------
# extract_period_balances()
# ---------------------------------------------------------------------------


class TestExtractPeriodBalances:
    def test_matching_commodity(self):
        amounts = [
            [{"acommodity": "£", "aquantity": {"floatingPoint": 100.0}}],
            [{"acommodity": "£", "aquantity": {"floatingPoint": 200.0}}],
        ]
        result = DataTransformer.extract_period_balances(amounts, "£")
        assert result == [100.0, 200.0]

    def test_missing_commodity_returns_zero(self):
        amounts = [
            [{"acommodity": "$", "aquantity": {"floatingPoint": 100.0}}],
        ]
        result = DataTransformer.extract_period_balances(amounts, "£")
        assert result == [0.0]

    def test_empty_amount_list(self):
        amounts: list[list] = [[]]
        result = DataTransformer.extract_period_balances(amounts, "£")
        assert result == [0.0]

    def test_negative_value_returns_absolute(self):
        amounts = [
            [{"acommodity": "£", "aquantity": {"floatingPoint": -500.0}}],
        ]
        result = DataTransformer.extract_period_balances(amounts, "£")
        assert result == [500.0]


# ---------------------------------------------------------------------------
# extract_amount()
# ---------------------------------------------------------------------------


class TestExtractAmount:
    def test_matching_commodity(self):
        amounts = [{"acommodity": "£", "aquantity": {"floatingPoint": 100.0}}]
        assert DataTransformer.extract_amount(amounts, "£") == 100.0

    def test_missing_commodity_returns_zero(self):
        amounts = [{"acommodity": "$", "aquantity": {"floatingPoint": 100.0}}]
        assert DataTransformer.extract_amount(amounts, "£") == 0.0

    def test_sign_is_preserved(self):
        amounts = [{"acommodity": "£", "aquantity": {"floatingPoint": -500.0}}]
        assert DataTransformer.extract_amount(amounts, "£") == -500.0

    def test_empty_list_returns_zero(self):
        assert DataTransformer.extract_amount([], "£") == 0.0


# ---------------------------------------------------------------------------
# to_sankey_data()
# ---------------------------------------------------------------------------


class TestToSankeyData:
    def test_income_flows_to_pot(self, account_balances: list[AccountBalance]):
        links = DataTransformer.to_sankey_data(account_balances)
        # Top-level income (negative balance) should flow: income → pot
        income_links = [
            lk for lk in links if lk.source == "income" and lk.target == "pot"
        ]
        assert len(income_links) == 1
        assert income_links[0].value == 2000.0

    def test_expense_flows_from_pot(self, account_balances: list[AccountBalance]):
        links = DataTransformer.to_sankey_data(account_balances)
        expense_links = [
            lk for lk in links if lk.source == "pot" and lk.target == "expenses"
        ]
        assert len(expense_links) == 1
        assert expense_links[0].value == 800.0

    def test_child_income_links_to_parent(self, account_balances: list[AccountBalance]):
        links = DataTransformer.to_sankey_data(account_balances)
        salary_links = [lk for lk in links if lk.source == "income:salary"]
        assert len(salary_links) == 1
        assert salary_links[0].target == "income"

    def test_missing_parent_raises_error(self):
        balances = [
            AccountBalance(name="expenses:food:groceries", amount=200.0),
        ]
        with pytest.raises(MissingParentAccountError, match="--no-elide"):
            DataTransformer.to_sankey_data(balances)

    def test_sign_reversal_expense(self):
        """A negative expense balance reverses the link direction."""
        balances = [
            AccountBalance(name="expenses", amount=-50.0),
        ]
        links = DataTransformer.to_sankey_data(balances)
        assert links[0].source == "expenses"
        assert links[0].target == "pot"
        assert links[0].value == 50.0

    def test_all_links_have_positive_values(
        self, account_balances: list[AccountBalance]
    ):
        links = DataTransformer.to_sankey_data(account_balances)
        for lk in links:
            assert lk.value >= 0


# ---------------------------------------------------------------------------
# sum_positive_contributions()
# ---------------------------------------------------------------------------


class TestSumPositiveContributions:
    def test_no_negatives_is_unchanged(self):
        balances = [
            AccountBalance(name="expenses", amount=800.0),
            AccountBalance(name="expenses:food", amount=300.0),
            AccountBalance(name="expenses:rent", amount=500.0),
        ]
        result = DataTransformer.sum_positive_contributions(balances)
        assert [ab.amount for ab in result] == [800.0, 300.0, 500.0]

    def test_negative_leaf_excluded(self):
        balances = [
            AccountBalance(name="expenses", amount=650.0),
            AccountBalance(name="expenses:food", amount=150.0),
            AccountBalance(name="expenses:food:groceries", amount=200.0),
            AccountBalance(name="expenses:food:dining", amount=-50.0),
            AccountBalance(name="expenses:rent", amount=500.0),
        ]
        result = DataTransformer.sum_positive_contributions(balances)
        by_name = {ab.name: ab.amount for ab in result}
        assert by_name["expenses:food:dining"] == 0.0

    def test_ancestors_rebuilt_from_positive_contributions(self):
        balances = [
            AccountBalance(name="expenses", amount=650.0),
            AccountBalance(name="expenses:food", amount=150.0),
            AccountBalance(name="expenses:food:groceries", amount=200.0),
            AccountBalance(name="expenses:food:dining", amount=-50.0),
            AccountBalance(name="expenses:rent", amount=500.0),
        ]
        result = DataTransformer.sum_positive_contributions(balances)
        by_name = {ab.name: ab.amount for ab in result}
        # food's real net (150) can't be rendered without its negative
        # child, so it's rebuilt from the positive children only (200 + 0)
        assert by_name["expenses:food"] == 200.0
        # expenses in turn matches its children's sum (food + rent)
        assert by_name["expenses"] == 700.0
        assert by_name["expenses:rent"] == 500.0

    def test_entirely_negative_branch_does_not_inflate_ancestors(self):
        """A whole branch net negative (e.g. a refund with no matching spend
        in the reported period) must not cascade extra inflation up the tree
        beyond the positive contributions actually present elsewhere."""
        balances = [
            AccountBalance(name="expenses", amount=670.0),
            AccountBalance(name="expenses:electronics", amount=-30.0),
            AccountBalance(name="expenses:electronics:tv", amount=-50.0),
            AccountBalance(name="expenses:electronics:cable", amount=20.0),
            AccountBalance(name="expenses:groceries", amount=200.0),
            AccountBalance(name="expenses:rent", amount=500.0),
        ]
        result = DataTransformer.sum_positive_contributions(balances)
        by_name = {ab.name: ab.amount for ab in result}
        assert by_name["expenses:electronics:tv"] == 0.0
        # electronics keeps only its positive contribution (cable, 20)
        assert by_name["expenses:electronics"] == 20.0
        # expenses sums the positive contributions actually present: cable
        # (20) + groceries (200) + rent (500) = 720, not more
        assert by_name["expenses"] == 720.0

    def test_no_amounts_are_negative(self):
        balances = [
            AccountBalance(name="expenses", amount=650.0),
            AccountBalance(name="expenses:food", amount=150.0),
            AccountBalance(name="expenses:food:groceries", amount=200.0),
            AccountBalance(name="expenses:food:dining", amount=-50.0),
            AccountBalance(name="expenses:rent", amount=500.0),
        ]
        result = DataTransformer.sum_positive_contributions(balances)
        assert all(ab.amount >= 0 for ab in result)

    def test_preserves_order_and_names(self):
        balances = [
            AccountBalance(name="expenses", amount=650.0),
            AccountBalance(name="expenses:food", amount=150.0),
        ]
        result = DataTransformer.sum_positive_contributions(balances)
        assert [ab.name for ab in result] == ["expenses", "expenses:food"]
