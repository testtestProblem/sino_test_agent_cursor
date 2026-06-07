"""Data models for performance reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Period:
    start: str
    end: str


@dataclass
class AccountRef:
    broker_id: str
    account_id: str
    account_type: str = "S"


@dataclass
class PerformanceSummary:
    realized_pnl_total: float = 0.0
    unrealized_pnl_total: float = 0.0
    cash_balance: float = 0.0
    position_market_value: float = 0.0
    ending_nav: float = 0.0
    net_cash_flow: float = 0.0
    estimated_beginning_nav: float | None = None
    portfolio_return_pct: float | None = None
    benchmark_return_pct: float | None = None
    excess_return_pct: float | None = None


@dataclass
class StockContribution:
    code: str
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    total_pnl: float = 0.0
    trade_count: int = 0
    pr_ratio: float | None = None


@dataclass
class PerformanceMeta:
    generated_at: str
    method_note: str = "組合報酬率為估算值，非券商官方績效"
    account: AccountRef | None = None


@dataclass
class PerformanceReport:
    meta: PerformanceMeta
    period: Period
    summary: PerformanceSummary
    by_stock: list[StockContribution] = field(default_factory=list)
    trades: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
