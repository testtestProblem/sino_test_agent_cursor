"""Tkinter debug GUI for Shioaji API functions."""

from __future__ import annotations

import json
import queue
import threading
import tkinter as tk
from tkinter import scrolledtext, ttk
from typing import Any, Callable

from sino_account.core import session
from sino_account.core.serialize import account_label
from sino_account.functions.get_account_balance import get_account_balance
from sino_account.functions.get_account_info import get_account_info
from sino_account.functions.get_margin import get_margin
from sino_account.functions.get_positions import get_positions
from sino_account.functions.get_profit_loss import default_date_range, get_profit_loss
from sino_account.functions.get_settlements import get_settlements
from sino_account.functions.login import login, logout


class ApiWorker:
    """Run all Shioaji API calls on one background thread."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self._queue: queue.Queue[tuple[Callable[[], Any], Callable[[Any], None], Callable[[Exception], None]] | None] = (
            queue.Queue()
        )
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


class ShioajiDebugApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Shioaji Debug GUI")
        self.root.geometry("980x640")

        session.load_env()
        self._api_worker = ApiWorker(root)
        self._accounts: dict[str, Any] = {}
        self._busy = False

        self._build_layout()
        self._update_status()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_layout(self) -> None:
        top_frame = ttk.Frame(self.root, padding=8)
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="Account").grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        self.account_var = tk.StringVar()
        self.account_combo = ttk.Combobox(
            top_frame,
            textvariable=self.account_var,
            state="readonly",
            width=40,
        )
        self.account_combo.grid(row=0, column=1, sticky=tk.W)

        default_begin, default_end = default_date_range()
        ttk.Label(top_frame, text="Begin").grid(row=0, column=2, sticky=tk.W, padx=(16, 8))
        self.begin_var = tk.StringVar(value=default_begin)
        ttk.Entry(top_frame, textvariable=self.begin_var, width=12).grid(row=0, column=3, sticky=tk.W)

        ttk.Label(top_frame, text="End").grid(row=0, column=4, sticky=tk.W, padx=(16, 8))
        self.end_var = tk.StringVar(value=default_end)
        ttk.Entry(top_frame, textvariable=self.end_var, width=12).grid(row=0, column=5, sticky=tk.W)

        body_frame = ttk.Frame(self.root, padding=8)
        body_frame.pack(fill=tk.BOTH, expand=True)

        button_frame = ttk.Frame(body_frame)
        button_frame.pack(side=tk.LEFT, fill=tk.Y)

        buttons = [
            ("Login", self._on_login),
            ("Logout", self._on_logout),
            ("Get Account Info", self._on_get_account_info),
            ("Get Account Balance", self._on_get_account_balance),
            ("Get Positions", self._on_get_positions),
            ("Get Margin", self._on_get_margin),
            ("Get Profit/Loss", self._on_get_profit_loss),
            ("Get Settlements", self._on_get_settlements),
        ]
        for index, (label, handler) in enumerate(buttons):
            ttk.Button(button_frame, text=label, command=handler, width=22).grid(
                row=index,
                column=0,
                pady=4,
                sticky=tk.EW,
            )

        output_frame = ttk.Frame(body_frame)
        output_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0))

        ttk.Label(output_frame, text="Result").pack(anchor=tk.W)
        self.output_text = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, font=("Consolas", 10))
        self.output_text.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

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

    def _apply_account_list(self, accounts: list[Any]) -> None:
        self._accounts = {account_label(account): account for account in accounts}
        labels = list(self._accounts.keys())
        self.account_combo["values"] = labels
        if labels:
            self.account_var.set(labels[0])

    def _clear_accounts(self) -> None:
        self._accounts = {}
        self.account_combo["values"] = []
        self.account_var.set("")

    def _update_status(self) -> None:
        if session.is_logged_in():
            self.status_var.set(f"Status: logged in ({session.get_environment()})")
        else:
            self.status_var.set("Status: not logged in")

    def _set_output(self, payload: Any) -> None:
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert(tk.END, json.dumps(payload, ensure_ascii=False, indent=2, default=str))

    def _set_error(self, exc: Exception) -> None:
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert(tk.END, f"Error: {type(exc).__name__}: {exc}")

    def _finish_success(self, payload: Any, refresh_accounts: bool = False) -> None:
        self._busy = False
        if refresh_accounts and session.is_logged_in():
            accounts = payload.get("accounts", []) if isinstance(payload, dict) else []
            self._apply_account_list(accounts)
            if isinstance(payload, dict) and "result" in payload:
                self._set_output(payload["result"])
            else:
                self._set_output(payload)
        else:
            self._set_output(payload)
        self._update_status()

    def _finish_error(self, exc: Exception) -> None:
        self._busy = False
        self._set_error(exc)
        self._update_status()

    def _run_api(
        self,
        action_name: str,
        func: Callable[[], Any],
        refresh_accounts: bool = False,
    ) -> None:
        if self._busy:
            self._set_error(RuntimeError("Another request is still running."))
            return

        self._busy = True
        self.status_var.set(f"Status: running {action_name}...")

        def on_success(payload: Any) -> None:
            self._finish_success(payload, refresh_accounts=refresh_accounts)

        self._api_worker.submit(func, on_success, self._finish_error)

    def _on_login(self) -> None:
        def action() -> dict[str, Any]:
            result = login()
            accounts = session.get_api().list_accounts() if session.is_logged_in() else []
            return {"result": result, "accounts": accounts}

        self._run_api("login", action, refresh_accounts=True)

    def _on_logout(self) -> None:
        def action() -> dict[str, Any]:
            return logout()

        def on_success(payload: Any) -> None:
            self._busy = False
            self._clear_accounts()
            self._set_output(payload)
            self._update_status()

        if self._busy:
            self._set_error(RuntimeError("Another request is still running."))
            return

        self._busy = True
        self.status_var.set("Status: running logout...")
        self._api_worker.submit(action, on_success, self._finish_error)

    def _on_get_account_info(self) -> None:
        def action() -> dict[str, Any]:
            result = get_account_info()
            accounts = session.get_api().list_accounts()
            return {"result": result, "accounts": accounts}

        self._run_api("get_account_info", action, refresh_accounts=True)

    def _on_get_account_balance(self) -> None:
        account = self._selected_account()
        self._run_api(
            "get_account_balance",
            lambda selected=account: get_account_balance(selected),
        )

    def _on_get_positions(self) -> None:
        account = self._selected_account()
        self._run_api(
            "get_positions",
            lambda selected=account: get_positions(selected),
        )

    def _on_get_margin(self) -> None:
        account = self._selected_account()
        self._run_api(
            "get_margin",
            lambda selected=account: get_margin(selected),
        )

    def _on_get_profit_loss(self) -> None:
        account = self._selected_account()
        begin = self.begin_var.get().strip()
        end = self.end_var.get().strip()
        self._run_api(
            "get_profit_loss",
            lambda selected=account, begin_date=begin, end_date=end: get_profit_loss(
                selected,
                begin_date,
                end_date,
            ),
        )

    def _on_get_settlements(self) -> None:
        account = self._selected_account()
        self._run_api(
            "get_settlements",
            lambda selected=account: get_settlements(selected),
        )


def main() -> None:
    root = tk.Tk()
    ShioajiDebugApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
