"""Plotly figure builders - one method per chart type."""

from __future__ import annotations

import plotly.graph_objects as go

from hledger_lit.models import AccountBalance, HistoricalData, SankeyLink
from hledger_lit.transforms import DataTransformer


class ChartBuilder:
    """Builds Plotly figures from structured hledger data."""

    @staticmethod
    def historical_balances_plot(
        data: HistoricalData, commodity: str = "", period: str = "daily"
    ) -> go.Figure:
        """Line chart of historical balances per account, with a dashed net-worth line."""
        fig = go.Figure()

        for account_name in sorted(data.balances.keys()):
            if account_name != "net_worth":
                fig.add_trace(
                    go.Scatter(
                        x=data.dates,
                        y=[round(v, 2) for v in data.balances[account_name]],
                        mode="lines",
                        name=account_name,
                        hovertemplate=f"%{{y:,.2f}} {commodity}",
                    )
                )

        if "net_worth" in data.balances:
            fig.add_trace(
                go.Scatter(
                    x=data.dates,
                    y=[round(v, 2) for v in data.balances["net_worth"]],
                    mode="lines",
                    name="net_worth",
                    line={"width": 3, "dash": "dash"},
                    hovertemplate=f"%{{y:,.2f}} {commodity}",
                )
            )

        fig.update_layout(
            title=f"Historical Account Balances ({period})",
            xaxis_title="Date",
            yaxis_title=f"Balance ({commodity})",
            yaxis_type="log",
            yaxis_tickformat=",.2f",
            yaxis_tickprefix=f"{commodity} ",
            hovermode="x unified",
        )
        return fig

    @staticmethod
    def account_treemap_plot(
        balances: list[AccountBalance],
        title: str = "Account Treemap",
        commodity: str = "",
        depth: int | None = None,
    ) -> go.Figure:
        """Treemap for an arbitrary account hierarchy."""
        labels = [ab.name for ab in balances]
        values = [ab.amount for ab in balances]
        parents = [DataTransformer.parent(ab.name) for ab in balances]

        fig = go.Figure(
            go.Treemap(
                labels=labels,
                parents=parents,
                values=values,
                branchvalues="total",
                textinfo="label+value+percent parent+percent entry",
                root_color="lightgrey",
            )
        )
        fig.update_layout(title=title)
        return fig

    @classmethod
    def expenses_treemap_plot(
        cls, balances: list[AccountBalance], commodity: str = "", depth: int | None = None
    ) -> go.Figure:
        """Treemap of expense accounts."""
        title = "Expenses Treemap" if depth is None else f"Expenses Treemap (depth {depth})"
        return cls.account_treemap_plot(
            balances, title=title, commodity=commodity, depth=depth
        )


    @staticmethod
    def daily_expenses_plot(
        data: HistoricalData,
        commodity: str = "",
        period: str = "daily",
        depth: int | None = None,
    ) -> go.Figure:
        """Stacked bar chart of expenses by category, bucketed by period."""
        fig = go.Figure()

        # Compute daily totals for percentage calculation
        num_dates = len(data.dates)
        daily_totals = [0.0] * num_dates
        sorted_accounts = sorted(data.balances.keys())
        for account_name in sorted_accounts:
            for i, v in enumerate(data.balances[account_name]):
                daily_totals[i] += v

        for account_name in sorted_accounts:
            rounded = [round(v, 2) for v in data.balances[account_name]]
            pcts = [
                f"{v / daily_totals[i] * 100:.1f}%" if daily_totals[i] else "0.0%"
                for i, v in enumerate(data.balances[account_name])
            ]
            fig.add_trace(
                go.Bar(
                    x=data.dates,
                    y=rounded,
                    name=account_name,
                    customdata=pcts,
                    hovertemplate=f"%{{y:,.2f}} {commodity} (%{{customdata}})",
                )
            )

        fig.update_layout(
            barmode="stack",
            title=f"Expenses ({period}, depth {depth})" if depth is not None else f"Expenses ({period})",
            xaxis_title="Date",
            yaxis_title=f"Amount ({commodity})",
            yaxis_tickformat=",.2f",
            yaxis_tickprefix=f"{commodity} ",
            hovermode="x unified",
        )
        return fig

    @staticmethod
    def sankey_plot(
        sankey_data: list[SankeyLink],
        commodity: str = "",
        depth: int | None = None,
    ) -> go.Figure:
        """Sankey diagram from a list of directed links."""
        # Sort by (target, source) to keep related accounts together
        sorted_links = sorted(sankey_data, key=lambda lk: (lk.target, lk.source))

        # Unique ordered node list
        nodes: list[str] = list(
            dict.fromkeys(
                [lk.source for lk in sorted_links] + [lk.target for lk in sorted_links]
            )
        )

        # Outflow per source node for percentage calculation
        source_totals: dict[str, float] = {}
        for lk in sorted_links:
            source_totals[lk.source] = source_totals.get(lk.source, 0.0) + lk.value

        fig = go.Figure(
            data=[
                go.Sankey(
                    node={
                        "pad": 25,
                        "thickness": 20,
                        "line": {"color": "black", "width": 0.5},
                        "label": nodes,
                        "color": "blue",
                        "customdata": [commodity] * len(nodes),
                        "hovertemplate": "%{label}<br>%{value:,.2f} %{customdata}<extra></extra>",
                    },
                    link={
                        "source": [nodes.index(lk.source) for lk in sorted_links],
                        "target": [nodes.index(lk.target) for lk in sorted_links],
                        "value": [round(lk.value, 2) for lk in sorted_links],
                        "customdata": [
                            f"{commodity} ({lk.value / source_totals[lk.source] * 100:.1f}%)"
                            if source_totals.get(lk.source)
                            else commodity
                            for lk in sorted_links
                        ],
                        "hovertemplate": (
                            "%{source.label} → %{target.label}<br>"
                            "%{value:,.2f} %{customdata}<extra></extra>"
                        ),
                    },
                )
            ]
        )
        if depth is not None:
            fig.update_layout(title=f"Depth {depth}")
        return fig
