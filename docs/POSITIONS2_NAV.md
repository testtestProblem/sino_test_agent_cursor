# Get Positions 2 — 股價值與總資產 (NAV) 計算

## 1. 文件目的

本文件記錄 **sino-gui → Get Positions 2** 如何計算：

- **單檔／合計股價值（持倉市值）**
- **總資產 (NAV)** 及其各項加總

Canonical 實作：

- [`get_positions2.py`](../src/sino_account/functions/get_positions2.py) — 查詢、加總、報表
- [`quantity_units.py`](../src/sino_account/performance/analytics/quantity_units.py) — 股數合併、單檔市值

持倉股數合併的反模式與通用規則另見 [SINO_POSITION_ALGORITHMS.md](./SINO_POSITION_ALGORITHMS.md)。  
GUI 操作說明見 [SINO_GUI.md](./SINO_GUI.md)。

**範圍**：僅 **即時快照**（API 當下查詢）。**Get Daily NAV** 使用 Excel 回放歷史，公式不同，見 [SINO_GUI.md §6.8](./SINO_GUI.md#68-get-daily-nav歷史每日總資產)。

---

## 2. 資料來源（API 呼叫順序）

Get Positions 2 依序呼叫（各步之間 `throttle()` 約 0.25 秒）：

| 順序 | API | 用途 |
|------|-----|------|
| 1 | `account_balance(account=)` | 現金餘額 `acc_balance` |
| 2 | `list_positions(account=, unit=Unit.Share)` | 持倉（股數單位） |
| 3 | `trading_limits(account=)` | 融資／融券額度（報表附加資訊） |
| 4 | `settlements(account=)` | T+1、T+2 交割款（NAV 用） |

帳戶限定 **證券帳戶 (S)**，由 `resolve_stock_account()` 解析。

---

## 3. 持倉前置處理

### 3.1 股數單位

目前 Positions 2 **僅**使用 `Unit.Share`：

- `quantity` 單位為 **股**（× 1）
- Share API 回傳的股數已含整股＋零股，無需再查 Common

### 3.2 依 `(code, cond)` 合併

同一商品、同一交易條件可能有多列 raw 資料。以 `(code, cond)` 分組後合併為一列：

| 欄位 | 合併規則 |
|------|----------|
| `shares` | `combine_unit_shares()`（避免 Common/Share 重複加總） |
| `price` | 加權平均成本 |
| `last_price` | 取有值的現價 |
| `pnl` | **只取一次**（勿對 raw 多列各加一次） |
| `margin_purchase_amount` 等 | 取各列最大值（避免重複列 double count） |

`cond` 常見值：

| cond | 說明 |
|------|------|
| `Cash` | 現股 |
| `MarginTrading` | 融資 |
| `ShortSelling` | 融券 |
| `Netting` | 餘額交割 |
| `Emerging` | 興櫃 |

---

## 4. 單檔股價值（持倉市值）

函式：`merged_position_market_value(position)`

對每一筆合併後持倉，**優先使用現價 mark-to-market**：

```
若 last_price > 0：
    單檔市值 = last_price × shares

否則若 price > 0：
    單檔市值 = price × shares + pnl

否則若 pnl ≠ 0：
    單檔市值 = pnl          （fallback，報表會顯示 warning）

否則：
    單檔市值 = 0            （無法估算，報表 warning）
```

### 4.1 與券商「現值」的對齊

正常情況下使用 **`last_price × 合併後股數`**，對齊永豐庫存表的「現值」欄。

`price × shares + pnl` 僅在缺少 `last_price` 時使用；數學上等同成本＋未實現損益。

### 4.2 損益%（報表附加）

```
損益% = pnl ÷ (price × shares) × 100
```

若成本為 0 且有 `last_price`、`price`，改以 `(last_price - price) / price × 100` 估算。

---

## 5. 合計股價值

程式內有多種加總，用途不同：

| 名稱 | 公式 | 用途 |
|------|------|------|
| **持倉市值** `total_market_value` | 全部 `(code, cond)` 的單檔市值加總 | 合計區塊參考 |
| **股價值（現股等）** `cash_stock_market_value` | 僅 **非** `MarginTrading`、**非** `ShortSelling` 的單檔市值加總 | **NAV 公式用** |
| 融資持倉市值 | `cond == MarginTrading` 的市值加總 | 融資區塊顯示 |
| 融券持倉市值 | `cond == ShortSelling` 的市值加總 | 融券區塊顯示 |

```
股價值（現股等）= Σ 單檔市值
    where cond ∉ { MarginTrading, ShortSelling }
```

亦即 **Cash、Netting、Emerging 等現股類持倉** 的市值總和，**不含**融資／融券部位的完整市值。

---

## 6. 總資產 (NAV) 公式

### 6.1 主公式

```
總資產 (NAV) = 現金
            + 股價值（現股等）
            + 融資 (MarginTrading) 盈虧
            + 融券 (ShortSelling) 盈虧
            + T+1 交割款
            + T+2 交割款
```

對應程式（`_compute_nav_breakdown`）：

```python
total_nav = (
    acc_balance
    + cash_stock_market_value
    + margin_pnl
    + short_pnl
    + settlement_t1
    + settlement_t2
)
```

### 6.2 各項定義

| 項目 | 欄位 | 來源 |
|------|------|------|
| 現金 | `acc_balance` | `account_balance()` |
| 股價值（現股等） | `cash_stock_market_value` | 見 §5 |
| 融資盈虧 | `margin_pnl` | 所有 `MarginTrading` 持倉的 `pnl` 加總 |
| 融券盈虧 | `short_pnl` | 所有 `ShortSelling` 持倉的 `pnl` 加總 |
| T+1 交割款 | `settlement_t1` | `settlements()` 中 `T == 1` 的 `amount` |
| T+2 交割款 | `settlement_t2` | `settlements()` 中 `T == 2` 的 `amount` |

### 6.3 交割款 (`settlements`)

`api.settlements()` 回傳 `SettlementV1` 列表：

| 欄位 | 說明 |
|------|------|
| `date` | 交割日期 |
| `amount` | 交割金額（正＝應收，負＝應付） |
| `T` | T 日：`0`＝當日，`1`＝T+1，`2`＝T+2 |

NAV **只納入 T+1、T+2**；T+0 不列入此公式（通常已反映在 `acc_balance` 或當日帳務）。

### 6.4 為何融資／融券用「盈虧」而非「市值」

- **現股等**：以完整市值計入股價值（你持有標的的現值）。
- **融資／融券**：部位市值含借貸／保證金結構，若再全額加總市值會與現金、融資金額重複計算。
- 因此 NAV 對融資／融券只加 **`pnl`（未實現損益）**，反映該類部位的損益貢獻。

報表仍會在「融資／融券持倉合計」區塊另外列出 **總金額(市值)**、**融資金額**／**保證金**，供對照，但不直接全額代入 NAV。

---

## 7. 報表輸出範例

Get Positions 2 報表**最後**會列出完整計算過程：

```
=== 總資產 (NAV) 計算 ===
公式: 現金 + 股價值 + 融資盈虧 + 融券盈虧 + T+1 交割款 + T+2 交割款
  現金 (acc_balance)                    +     229,955.00
  股價值（現股等）                       +   1,500,000.00
  融資 (MarginTrading) 盈虧             +      12,345.67
  融券 (ShortSelling) 盈虧              +      -1,234.56
  T+1 交割款 (2026-06-17)               +     -50,000.00
  T+2 交割款 (2026-06-18)               +     100,000.00
  ----------------------------------------------------
  總資產 (NAV)                          1,791,066.11
```

「合計」區塊另顯示：

- 現金餘額
- **現股市值**（＝股價值）
- **持倉市值**（全部 cond 加總，含融資／融券）
- 未實現損益、未實現損益%

---

## 8. 程式回傳結構

`get_positions2()` 的 `summary` 主要欄位：

```json
{
  "acc_balance": 229955.0,
  "cash_stock_market_value": 1500000.0,
  "total_market_value": 1650000.0,
  "total_unrealized_pnl": 11111.11,
  "total_nav": 1791066.11,
  "nav_breakdown": {
    "acc_balance": 229955.0,
    "cash_stock_market_value": 1500000.0,
    "margin_pnl": 12345.67,
    "short_pnl": -1234.56,
    "settlement_t1": -50000.0,
    "settlement_t2": 100000.0,
    "settlement_t1_date": "2026-06-17",
    "settlement_t2_date": "2026-06-18",
    "total_nav": 1791066.11
  },
  "margin_trading": { "count": 2, "market_value": ..., "pnl": ..., "margin_purchase_amount": ... },
  "short_selling": { "count": 1, "market_value": ..., "pnl": ..., "short_sale_margin": ... }
}
```

文字報表：`format_positions2_report(data)`。

---

## 9. 與其他功能的差異

| 項目 | Get Positions 2 | Get Daily NAV |
|------|-----------------|---------------|
| 時間 | 即時快照 | 歷史每日 |
| 持倉來源 | `list_positions(Share)` | `庫存.xlsx` + `對帳單.xlsx` 回放 |
| 股價 | API `last_price` | kbars 收盤價 |
| 現金 | `acc_balance` | 期末 balance + 對帳單 T+2 回放 |
| NAV | 本文件公式 | `現金(D) + 持倉市值(D)`（無融資／融券分拆、無 settlements） |

---

## 10. 限制與注意事項

1. **估算值**：NAV 為 API 資料估算，未必與永豐 APP 完全一致。
2. **settlements 時效**：交割款為「未來交割」快照；成交後、交割前，持倉與現金時間點可能不一致。
3. **T+0 未列入**：若需納入當日交割，需另行擴充公式。
4. **缺少現價**：無 `last_price` 時市值為 fallback，可能與 APP 現值有差。
5. **速率限制**：連續呼叫 `account_balance`、`list_positions`、`trading_limits`、`settlements` 受 Shioaji 帳務 API 速率限制（約 5 秒 25 次）。

---

## 11. 快速對照（給 AI / 開發者）

### 單檔市值

```
merged_market_value = last_price × shares   （優先）
```

### 股價值（NAV 用）

```
cash_stock_market_value = Σ merged_market_value
    where cond not in (MarginTrading, ShortSelling)
```

### NAV

```
NAV = acc_balance
    + cash_stock_market_value
    + Σ pnl (MarginTrading)
    + Σ pnl (ShortSelling)
    + settlements[T=1].amount
    + settlements[T=2].amount
```

### 禁止

- 勿對 raw `list_positions` 多列重複加總 `pnl`
- 勿用 `total_market_value`（含融資／融券市值）直接當 NAV 的股價值
- 勿將 `acc_balance + total_market_value` 當成目前 Positions 2 的 NAV（舊公式，已廢除）
