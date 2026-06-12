"""Unit tests for daily NAV analytics (no API required)."""



from sino_account.performance.analytics.daily_closes import (

    build_daily_close_map,

    forward_fill_daily_closes,

    kbars_to_daily_closes,

)

from sino_account.performance.analytics.daily_nav import (

    build_daily_nav_series_from_data,

    calc_daily_cash,

    calc_daily_market_value,

)

from sino_account.performance.analytics.holdings_timeline import build_holdings_timeline

from sino_account.performance.analytics.quantity_units import (

    calc_positions_market_value,

    infer_trade_undo_shares,

    position_market_value,

    quantity_to_shares,

)





def test_kbars_to_daily_closes_uses_last_bar_of_day() -> None:

    kbars = {

        "datetime": [

            "2026-03-07 09:00",

            "2026-03-07 13:00",

            "2026-03-08 09:00",

        ],

        "Close": [100.0, 105.0, 110.0],

    }

    daily = kbars_to_daily_closes(kbars)

    assert daily["2026-03-07"] == 105.0

    assert daily["2026-03-08"] == 110.0





def test_forward_fill_daily_closes() -> None:

    filled = forward_fill_daily_closes(

        {"2026-03-07": 100.0, "2026-03-09": 110.0},

        "2026-03-07",

        "2026-03-09",

    )

    assert filled["2026-03-07"] == 100.0

    assert filled["2026-03-08"] == 100.0

    assert filled["2026-03-09"] == 110.0





def test_holdings_timeline_backward_replay() -> None:

    positions = [{"code": "2330", "quantity": 1}]

    trades = [

        {"code": "2330", "quantity": 1, "date": "2026-05-01"},

        {"code": "2330", "quantity": 1, "date": "2026-04-01"},

    ]

    timeline, _ = build_holdings_timeline(trades, positions, "2026-03-01", "2026-06-01")



    assert timeline["2026-03-15"]["2330"] == 3000

    assert timeline["2026-04-01"]["2330"] == 2000

    assert timeline["2026-04-15"]["2330"] == 2000

    assert timeline["2026-05-01"]["2330"] == 1000

    assert timeline["2026-06-01"]["2330"] == 1000





def test_calc_daily_cash_is_flat_by_default() -> None:

    settlements = [

        {"date": "2026-05-10", "amount": -10_000},

        {"date": "2026-05-20", "amount": 5_000},

    ]

    assert calc_daily_cash(100_000, settlements, "2026-05-09", end="2026-06-01") == 100_000

    assert calc_daily_cash(100_000, settlements, "2026-05-25", end="2026-06-01") == 100_000





def test_calc_daily_market_value_whole_lot() -> None:

    holdings = {"2330": 2000}

    close_map = {

        "2330": {

            "2026-03-07": 100.0,

            "2026-03-08": 110.0,

        }

    }

    assert calc_daily_market_value(holdings, close_map, "2026-03-07") == 200_000

    assert calc_daily_market_value(holdings, close_map, "2026-03-08") == 220_000





def test_calc_daily_market_value_odd_lot() -> None:

    holdings = {"2890": 500}

    close_map = {"2890": {"2026-03-07": 31.0}}

    assert calc_daily_market_value(holdings, close_map, "2026-03-07") == 15_500





def test_position_market_value_uses_cost_plus_pnl() -> None:

    multipliers = {"2330": 1000.0}

    value, warning = position_market_value(

        {"code": "2330", "quantity": 1, "price": 800.0, "last_price": 0, "pnl": 50_000},

        multipliers,

    )

    assert value == 850_000

    assert warning is None





def test_position_market_value_pnl_only_fallback() -> None:

    multipliers = {"2330": 1000.0}

    value, warning = position_market_value(

        {"code": "2330", "quantity": 1, "price": 0, "last_price": 0, "pnl": 112_707},

        multipliers,

    )

    assert value == 112_707

    assert warning is not None





def test_quantity_to_shares_supports_share_mode() -> None:

    multipliers = {"2890": 1.0}

    position = {"code": "2890", "quantity": 500, "unit": "Share"}

    assert quantity_to_shares(position, multipliers) == 500





def test_infer_trade_undo_shares_for_zero_quantity() -> None:

    trade = {

        "code": "2317",

        "quantity": 0,

        "pnl": -5575.0,

        "price": 192.0,

        "pr_ratio": -0.1628,

    }

    shares = infer_trade_undo_shares(trade)

    assert 140 < shares < 160





def test_build_daily_nav_series_anchors_end_day() -> None:

    positions = [{"code": "2330", "quantity": 1, "price": 100.0, "last_price": 110.0, "pnl": 10_000}]

    balance = {"acc_balance": 50_000}

    settlements: list[dict] = []

    trades: list[dict] = []

    kbars_by_code = {

        "2330": {

            "datetime": ["2026-03-07", "2026-03-08"],

            "Close": [100.0, 50.0],

        }

    }



    series = build_daily_nav_series_from_data(

        trades=trades,

        positions=positions,

        balance=balance,

        settlements=settlements,

        kbars_by_code=kbars_by_code,

        start="2026-03-07",

        end="2026-03-08",

    )



    assert series.snapshot_nav == 160_000

    assert series.points[-1].nav == 160_000

    assert series.points[-1].market_value == 110_000

    assert series.points[-1].cash == 50_000





def test_calc_positions_market_value_merges_share_lot() -> None:

    positions = [

        {"code": "2890", "quantity": 1, "price": 30.0, "pnl": 1000},

        {"code": "2890", "quantity": 500, "unit": "Share", "price": 30.0, "pnl": 500},

    ]

    total, _ = calc_positions_market_value(positions)

    assert total == 31_000 + 15_500





def test_build_daily_close_map() -> None:

    close_map, warnings = build_daily_close_map(

        {

            "2330": {

                "datetime": ["2026-03-07", "2026-03-08"],

                "Close": [100.0, 110.0],

            }

        },

        "2026-03-07",

        "2026-03-08",

    )

    assert not warnings

    assert close_map["2330"]["2026-03-07"] == 100.0

    assert close_map["2330"]["2026-03-08"] == 110.0





if __name__ == "__main__":

    test_kbars_to_daily_closes_uses_last_bar_of_day()

    test_forward_fill_daily_closes()

    test_holdings_timeline_backward_replay()

    test_calc_daily_cash_is_flat_by_default()

    test_calc_daily_market_value_whole_lot()

    test_calc_daily_market_value_odd_lot()

    test_position_market_value_uses_cost_plus_pnl()

    test_position_market_value_pnl_only_fallback()

    test_quantity_to_shares_supports_share_mode()

    test_infer_trade_undo_shares_for_zero_quantity()

    test_build_daily_nav_series_anchors_end_day()

    test_calc_positions_market_value_merges_share_lot()

    test_build_daily_close_map()

    print("daily nav tests passed")


