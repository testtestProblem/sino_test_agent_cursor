"""Standalone GUI for 3-month daily capital level (NAV) chart."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import scrolledtext, ttk
from typing import Any, Callable

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from sino_account.core import session
from sino_account.core.serialize import account_info, account_label
from sino_account.performance.analytics.daily_nav import build_daily_nav_series
from sino_account.performance.date_range import three_month_range
from sino_account.performance.models import DailyNavSeries
from sino_account.performance.session import ensure_performance_session, logout_performance


class ApiWorker:
    """Run all Shioaji API calls on one background thread."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self._queue: queue.Queue[
            tuple[Callable[[], Any], Callable[[Any], None], Callable[[Exception], None]] | None
        ] = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                return

            func, on_success, on_error = item
            try:
                result = func()
            except Exception as exc:
                self.root.after(0, lambda error=exc: on_error(error))
            else:
                self.root.after(0, lambda payload=result: on_success(payload))
            finally:
                self._queue.task_done()

    def submit(
        self,
        func: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[Exception], None],
    ) -> None:
        self._queue.put((func, on_success, on_error))

    def stop(self) -> None:
        self._queue.put(None)


def _configure_matplotlib_font() -> None:
    for font_name in ("Microsoft JhengHei", "Microsoft YaHei", "SimHei", "Arial Unicode MS"):
        try:
            plt.rcParams["font.sans-serif"] = [font_name]
            plt.rcParams["axes.unicode_minus"] = False
            return
        except Exception:
            continue


class NavChartApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("資金水位圖")
        self.root.geometry("1100x720")

        session.load_env()
        _configure_matplotlib_font()
        self._api_worker = ApiWorker(root)
        self._accounts: dict[str, Any] = {}
        self._busy = False
        self._canvas: FigureCanvasTkAgg | None = None

        self._build_layout()
        self._update_status()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_layout(self) -> None:
        top_frame = ttk.Frame(self.root, padding=8)
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="帳戶").grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        self.account_var = tk.StringVar()
        self.account_combo = ttk.Combobox(
            top_frame,
            textvariable=self.account_var,
            state="readonly",
            width=36,
        )
        self.account_combo.grid(row=0, column=1, sticky=tk.W)

        default_start, default_end = three_month_range()
        ttk.Label(top_frame, text="Begin").grid(row=0, column=2, sticky=tk.W, padx=(16, 8))
        self.begin_var = tk.StringVar(value=default_start)
        ttk.Entry(top_frame, textvariable=self.begin_var, width=12).grid(row=0, column=3, sticky=tk.W)

        ttk.Label(top_frame, text="End").grid(row=0, column=4, sticky=tk.W, padx=(16, 8))
        self.end_var = tk.StringVar(value=default_end)
        ttk.Entry(top_frame, textvariable=self.end_var, width=12).grid(row=0, column=5, sticky=tk.W)

        ttk.Button(top_frame, text="Login", command=self._on_login).grid(row=0, column=6, padx=(16, 4))
        ttk.Button(top_frame, text="Logout", command=self._on_logout).grid(row=0, column=7, padx=4)
        ttk.Button(top_frame, text="載入水位圖", command=self._on_load_chart).grid(
            row=0,
            column=8,
            padx=(16, 0),
        )

        self.note_var = tk.StringVar(value="每日資金水位為估算值，非券商官方 NAV")
        ttk.Label(self.root, textvariable=self.note_var, padding=(8, 0)).pack(anchor=tk.W)

        self.chart_frame = ttk.Frame(self.root, padding=8)
        self.chart_frame.pack(fill=tk.BOTH, expand=True)

        bottom_frame = ttk.Frame(self.root, padding=8)
        bottom_frame.pack(fill=tk.BOTH)

        ttk.Label(bottom_frame, text="Warnings").pack(anchor=tk.W)
        self.warning_text = scrolledtext.ScrolledText(
            bottom_frame,
            height=5,
            wrap=tk.WORD,
            font=("Consolas", 9),
        )
        self.warning_text.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        self.status_var = tk.StringVar(value="Status: not logged in")
        ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding=6).pack(
            fill=tk.X
        )

    def _on_close(self) -> None:
        self._api_worker.stop()
        self.root.destroy()

    def _selected_account(self) -> Any | None:
        label = self.account_var.get()
        if not label:
            return None
        return self._accounts.get(label)

    def _stock_accounts(self, accounts: list[Any]) -> list[Any]:
        stock_accounts = []
        for account in accounts:
            info = account_info(account)
            if str(info.get("account_type") or "") == "S":
                stock_accounts.append(account)
        return stock_accounts

    def _apply_account_list(self, accounts: list[Any]) -> None:
        stock_accounts = self._stock_accounts(accounts)
        self._accounts = {account_label(account): account for account in stock_accounts}
        labels = list(self._accounts.keys())
        self.account_combo["values"] = labels
        if labels:
            self.account_var.set(labels[0])
        else:
            self.account_var.set("")

    def _clear_accounts(self) -> None:
        self._accounts = {}
        self.account_combo["values"] = []
        self.account_var.set("")

    def _update_status(self) -> None:
        if session.is_logged_in():
            self.status_var.set(f"Status: logged in ({session.get_environment()})")
        else:
            self.status_var.set("Status: not logged in")

    def _set_warnings(self, warnings: list[str]) -> None:
        self.warning_text.delete("1.0", tk.END)
        if warnings:
            self.warning_text.insert(tk.END, "\n".join(f"- {item}" for item in warnings))
        else:
            self.warning_text.insert(tk.END, "(none)")

    def _finish_error(self, exc: Exception) -> None:
        self._busy = False
        self._set_warnings([f"{type(exc).__name__}: {exc}"])
        self.status_var.set(f"Status: error — {exc}")
        self._update_status()

    def _run_api(
        self,
        action_name: str,
        func: Callable[[], Any],
        on_success: Callable[[Any], None],
    ) -> None:
        if self._busy:
            self._set_warnings(["Another request is still running."])
            return

        self._busy = True
        self.status_var.set(f"Status: running {action_name}...")

        def success_wrapper(payload: Any) -> None:
            self._busy = False
            on_success(payload)
            self._update_status()

        def error_wrapper(exc: Exception) -> None:
            self._finish_error(exc)

        self._api_worker.submit(func, success_wrapper, error_wrapper)

    def _on_login(self) -> None:
        def action() -> list[Any]:
            ensure_performance_session()
            return session.get_api().list_accounts()

        def on_success(accounts: list[Any]) -> None:
            self._apply_account_list(accounts)
            self._set_warnings([])

        self._run_api("login", action, on_success)

    def _on_logout(self) -> None:
        def action() -> dict[str, Any]:
            return logout_performance()

        def on_success(_payload: Any) -> None:
            self._clear_accounts()
            self._set_warnings([])

        self._run_api("logout", action, on_success)

    def _on_load_chart(self) -> None:
        account = self._selected_account()
        start = self.begin_var.get().strip()
        end = self.end_var.get().strip()

        if account is None:
            self._set_warnings(["請先 Login 並選擇證券帳戶。"])
            return

        def action() -> DailyNavSeries:
            self.root.after(0, lambda: self.status_var.set("Status: 收集交易與快照..."))
            series = build_daily_nav_series(account, start, end)
            self.root.after(0, lambda: self.status_var.set("Status: 繪製圖表..."))
            return series

        def on_success(series: DailyNavSeries) -> None:
            self._render_chart(series)
            display_warnings = list(series.warnings)
            if series.snapshot_nav is not None:
                display_warnings.insert(
                    0,
                    f"快照 NAV：{series.snapshot_nav:,.0f} "
                    f"（現金 {series.snapshot_cash:,.0f} + "
                    f"持倉 {series.snapshot_market_value:,.0f}）",
                )
            if any("偏差超過 5%" in item for item in display_warnings):
                display_warnings.append(
                    "期末 kbars 與快照偏差較大，請執行 nav-diagnose 查看逐檔市值明細。"
                )
            self._set_warnings(display_warnings)
            account_ref = self._selected_account()
            if account_ref is not None:
                info = account_info(account_ref)
                title_account = f"{info.get('broker_id')}-{info.get('account_id')}"
                self.root.title(f"資金水位圖 — {title_account}")

        self._run_api("load chart", action, on_success)

    def _render_chart(self, series: DailyNavSeries) -> None:
        for child in self.chart_frame.winfo_children():
            child.destroy()

        if not series.points:
            ttk.Label(self.chart_frame, text="區間內無資料可繪製。").pack()
            return

        dates = [point.date for point in series.points]
        nav_values = [point.nav for point in series.points]
        cash_values = [point.cash for point in series.points]
        market_values = [point.market_value for point in series.points]

        fig = Figure(figsize=(10, 4.8), dpi=100)
        ax = fig.add_subplot(111)
        ax.plot(dates, nav_values, label="總資金水位 (NAV)", linewidth=2)
        ax.plot(dates, cash_values, label="現金餘額", linewidth=1.5)
        ax.plot(dates, market_values, label="持倉市值", linewidth=1.5)
        ax.set_title(f"資金水位圖 {series.start} ~ {series.end}")
        ax.set_xlabel("日期")
        ax.set_ylabel("金額 (TWD)")
        ax.grid(True, linestyle="--", alpha=0.35)
        ax.legend(loc="best")

        tick_count = min(8, len(dates))
        if tick_count > 0:
            step = max(len(dates) // tick_count, 1)
            ax.set_xticks(dates[::step])
            fig.autofmt_xdate(rotation=30)

        fig.tight_layout()
        self._canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        self._canvas.draw()
        self._canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)


def main() -> None:
    root = tk.Tk()
    NavChartApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
