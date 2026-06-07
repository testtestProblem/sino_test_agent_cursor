"""Export performance report to Markdown."""

from __future__ import annotations

from pathlib import Path

from sino_account.performance.models import PerformanceReport


def _fmt_money(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:,.2f}"


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2f}%"


def export_markdown(report: PerformanceReport, output_dir: str | Path) -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    file_path = output_path / "report_3m.md"

    account = report.meta.account
    account_text = "N/A"
    if account is not None:
        account_text = f"{account.broker_id}-{account.account_id} ({account.account_type})"

    lines = [
        "# 3 個月股票帳戶績效報告",
        "",
        f"- 產生時間：{report.meta.generated_at}",
        f"- 帳戶：{account_text}",
        f"- 區間：{report.period.start} ~ {report.period.end}",
        f"- 說明：{report.meta.method_note}",
        "",
        "## 績效摘要",
        "",
        "| 指標 | 數值 |",
        "|------|------|",
        f"| 已實現損益 | {_fmt_money(report.summary.realized_pnl_total)} |",
        f"| 未實現損益 | {_fmt_money(report.summary.unrealized_pnl_total)} |",
        f"| 現金餘額 | {_fmt_money(report.summary.cash_balance)} |",
        f"| 持倉市值 | {_fmt_money(report.summary.position_market_value)} |",
        f"| 期末淨資產估算 | {_fmt_money(report.summary.ending_nav)} |",
        f"| 淨資金流入（近似） | {_fmt_money(report.summary.net_cash_flow)} |",
        f"| 期初淨資產估算 | {_fmt_money(report.summary.estimated_beginning_nav)} |",
        f"| 組合報酬率 | {_fmt_pct(report.summary.portfolio_return_pct)} |",
        f"| 大盤報酬率 | {_fmt_pct(report.summary.benchmark_return_pct)} |",
        f"| 超額報酬 | {_fmt_pct(report.summary.excess_return_pct)} |",
        "",
        "## 個股貢獻",
        "",
        "| 代碼 | 已實現 | 未實現 | 合計 | 交易筆數 | 損益比 |",
        "|------|--------|--------|------|----------|--------|",
    ]

    for item in report.by_stock:
        lines.append(
            f"| {item.code} | {_fmt_money(item.realized_pnl)} | {_fmt_money(item.unrealized_pnl)} | "
            f"{_fmt_money(item.total_pnl)} | {item.trade_count} | {_fmt_pct(item.pr_ratio)} |"
        )

    if report.warnings:
        lines.extend(["", "## 警告", ""])
        for warning in report.warnings:
            lines.append(f"- {warning}")

    lines.extend(["", "## 方法限制", "", "- 組合報酬率為估算值，非券商官方績效。", "- 未實現損益為查詢當下快照。"])

    with file_path.open("w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")

    return file_path
