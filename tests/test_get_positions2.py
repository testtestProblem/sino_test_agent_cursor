"""Unit tests for Get Positions 2 merge logic."""

from sino_account.performance.analytics.quantity_units import (
    build_code_multipliers,
    combine_unit_shares,
    format_shares_lots,
    merge_position_rows,
    merged_position_market_value,
)


def test_combine_unit_shares_share_row_is_total_when_larger() -> None:
    assert combine_unit_shares(3000, 3300) == 3300
    assert combine_unit_shares(1000, 1000) == 1000


def test_combine_unit_shares_adds_small_odd_lot_slice() -> None:
    assert combine_unit_shares(3000, 300) == 3300


def test_merge_position_rows_combines_common_and_share() -> None:
    raw = [
        {
            "code": "0050",
            "cond": "Cash",
            "unit": "Common",
            "quantity": 3,
            "price": 85.05,
            "last_price": 104.15,
            "pnl": 62191,
        },
        {
            "code": "0050",
            "cond": "Cash",
            "unit": "Share",
            "quantity": 3300,
            "price": 85.05,
            "last_price": 104.15,
            "pnl": 62191,
        },
    ]
    multipliers = build_code_multipliers(raw, [])
    merged = merge_position_rows(raw, multipliers)

    assert len(merged) == 1
    row = merged[0]
    assert row["code"] == "0050"
    assert row["shares"] == 3300
    assert row["pnl"] == 62191
    assert abs(row["price"] - 85.05) < 0.01


def test_merge_matches_inventory_market_value_formula() -> None:
    """庫存.xlsx uses 現值 = 現價 × 今日餘額 (share count)."""
    raw = [
        {
            "code": "0050",
            "cond": "Cash",
            "unit": "Common",
            "quantity": 3,
            "price": 85.05,
            "last_price": 101.95,
            "pnl": 54951,
        },
        {
            "code": "0050",
            "cond": "Cash",
            "unit": "Share",
            "quantity": 3300,
            "price": 85.05,
            "last_price": 101.95,
            "pnl": 54951,
        },
    ]
    multipliers = build_code_multipliers(raw, [])
    merged = merge_position_rows(raw, multipliers)
    market_value, warning = merged_position_market_value(merged[0])

    assert warning is None
    assert merged[0]["shares"] == 3300
    assert abs(market_value - 101.95 * 3300) < 1.0
    assert abs(market_value - 335624) < 1000


def test_merged_market_value_uses_last_price_not_double_pnl() -> None:
    row = {
        "code": "0050",
        "shares": 3300,
        "price": 85.05,
        "last_price": 104.15,
        "pnl": 62191,
    }
    market_value, warning = merged_position_market_value(row)

    assert warning is None
    assert market_value == 104.15 * 3300
    assert market_value != 85.05 * 3000 + 62191 + 85.05 * 3300 + 62191


def test_merge_keeps_different_cond_separate() -> None:
    raw = [
        {
            "code": "2330",
            "cond": "Cash",
            "unit": "Common",
            "quantity": 1,
            "price": 800,
            "last_price": 900,
            "pnl": 100000,
        },
        {
            "code": "2330",
            "cond": "MarginTrading",
            "unit": "Common",
            "quantity": 1,
            "price": 700,
            "last_price": 900,
            "pnl": 200000,
        },
    ]
    multipliers = build_code_multipliers(raw, [])
    merged = merge_position_rows(raw, multipliers)

    assert len(merged) == 2
    by_cond = {row["cond"]: row for row in merged}
    assert by_cond["Cash"]["shares"] == 1000
    assert by_cond["MarginTrading"]["shares"] == 1000


def test_merge_common_zero_quantity_with_share_row() -> None:
    raw = [
        {
            "code": "2330",
            "cond": "Cash",
            "unit": "Common",
            "quantity": 0,
            "price": 1937.15,
            "last_price": 2365.0,
            "pnl": 112707,
        },
        {
            "code": "2330",
            "cond": "Cash",
            "unit": "Share",
            "quantity": 270,
            "price": 1937.15,
            "last_price": 2365.0,
            "pnl": 112707,
        },
    ]
    multipliers = build_code_multipliers(raw, [])
    merged = merge_position_rows(raw, multipliers)

    assert len(merged) == 1
    assert merged[0]["shares"] == 270
    market_value, _ = merged_position_market_value(merged[0])
    assert market_value == 2365.0 * 270


def test_format_shares_lots() -> None:
    assert format_shares_lots(3300) == "3張300股"
    assert format_shares_lots(3000) == "3張"
    assert format_shares_lots(270) == "270股"


if __name__ == "__main__":
    test_combine_unit_shares_share_row_is_total_when_larger()
    test_combine_unit_shares_adds_small_odd_lot_slice()
    test_merge_position_rows_combines_common_and_share()
    test_merge_matches_inventory_market_value_formula()
    test_merged_market_value_uses_last_price_not_double_pnl()
    test_merge_keeps_different_cond_separate()
    test_merge_common_zero_quantity_with_share_row()
    test_format_shares_lots()
    print("get_positions2 tests passed")
