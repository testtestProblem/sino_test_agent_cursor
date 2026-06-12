"""One-off verification for FetchStatus / AccountType serialization."""

import json

import shioaji as sj

from sino_account.core.serialize import account_info, serialize


class MockBalance:
    def dict(self) -> dict:
        return {
            "status": sj.FetchStatus.Fetched,
            "acc_balance": 100.0,
            "date": "2026-01-01",
            "errmsg": "",
        }


def main() -> None:
    print("FetchStatus", serialize(sj.FetchStatus.Fetched))
    print("AccountType", serialize(sj.AccountType.Stock))
    account = sj.Account(
        account_type=sj.AccountType.Stock,
        person_id="P",
        broker_id="B",
        account_id="A",
        signed=True,
        username="U",
    )
    print("account_info", json.dumps(account_info(account), ensure_ascii=False))
    print("balance", json.dumps(serialize(MockBalance()), ensure_ascii=False))


if __name__ == "__main__":
    main()
