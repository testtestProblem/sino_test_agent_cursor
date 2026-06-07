# 3 個月股票帳戶績效 — 需求規劃書

## 1. 專案背景

本專案基於 [Shioaji API](https://sinotrade.github.io/)（永豐金證券），在既有 `sino-account` 模組化架構上，新增**證券帳戶**的 **3 個月投資組合績效回溯**功能。

使用者需要同時掌握：

- **歷史交易數據**（已平倉損益、進出場明細）
- **歷史股價**（個股日 K、大盤指數）
- **完整投資組合績效**（已實現 + 未實現 + 資金變化 + 報酬率%、大盤對比）

本文件為 **Phase 0 規劃文件**，僅定義需求與指標，不含程式實作。架構細節見 [PERFORMANCE_3M_ARCHITECTURE.md](./PERFORMANCE_3M_ARCHITECTURE.md)。

---

## 2. 目標與範圍

### 2.1 目標

| 項目 | 說明 |
|------|------|
| 回溯區間 | 預設為「今日往前 3 個曆月」，支援自訂起訖日 |
| 帳戶類型 | **僅證券帳戶**（`account_type = "S"` / `StockAccount`） |
| 績效範圍 | 完整投資組合：已實現損益、未實現損益、資金變化、組合報酬率、大盤對比 |
| 輸出形式 | JSON 報告 + Markdown 報告 + `sino-gui` 績效頁籤（實作階段） |

### 2.2 不在範圍內

- 期貨／選擇權帳戶
- 複委託帳戶（`account_type = "H"`）
- 當日委託成交查詢（`list_trades` 無法回溯歷史）
- 券商官方績效報告（本系統為 API 資料估算）

---

## 3. 使用者故事

1. 身為股票投資者，我希望能**一鍵產生過去 3 個月的績效報告**，了解總損益與報酬率。
2. 身為開發者，我希望能**逐步 debug 每個資料來源**（交易、股價、快照），與現有 GUI 模組化風格一致。
3. 身為投資者，我希望能**對比同期大盤（加權指數）**，判斷是否跑贏市場。
4. 身為投資者，我希望能看到**各股貢獻明細**，了解哪檔股票賺賠最多。

---

## 4. 資料來源（Shioaji API）

### 4.1 歷史交易數據（帳務 API）

| 資料 | API | 用途 |
|------|-----|------|
| 逐筆已平倉損益 | `api.list_profit_loss(account, begin_date, end_date)` | 區間內每筆 realized P&L |
| 進出場明細 | `api.list_profit_loss_detail(account, detail_id)` | 進倉價／日期、平倉價、數量 |
| 依股票彙總 | `api.list_profit_loss_summary(account, begin_date, end_date)` | 各股 quantity、entry/cover price、pnl |
| 交割款 | `api.settlements(account)` | 近似資金流入流出 |

#### StockProfitLoss 主要欄位

| 欄位 | 說明 |
|------|------|
| `code` | 商品代碼 |
| `quantity` | 數量 |
| `pnl` | 損益 |
| `date` | 交易日期 |
| `price` | 成交價格 |
| `pr_ratio` | 損益比 |
| `cond` | 交易方式（現股、融資、融券等） |

#### StockProfitLossSummary 主要欄位

| 欄位 | 說明 |
|------|------|
| `code` | 商品代碼 |
| `quantity` | 數量 |
| `entry_price` / `cover_price` | 進倉／平倉價格 |
| `pnl` | 損益 |
| `pr_ratio` | 損益比 |

### 4.2 歷史股價（行情 API）

| 資料 | API | 用途 |
|------|-----|------|
| 個股日 K | `api.kbars(contract, start, end)` | 個股 OHLCV，輔助交易分析與市值估算 |
| 加權指數 | `api.kbars(api.Contracts.Indexs["001"], start, end)` | 大盤基準報酬率 |

#### Kbars 主要欄位

| 欄位 | 說明 |
|------|------|
| `Open` / `High` / `Low` / `Close` | 開高低收 |
| `Volume` | 成交量 |
| `ts` / `datetime` | 時間 |

**注意**：`kbars` 需要商品檔存在於 `api.Contracts` 中，登入時需 `fetch_contract=True`（績效查詢專用登入流程）。

### 4.3 期末快照（帳務 API）

| 資料 | API | 用途 |
|------|-----|------|
| 銀行餘額 | `api.account_balance(account)` | 現金部位 |
| 未平倉持倉 | `api.list_positions(account)` | 未實現損益、持倉市值 |

#### StockPosition 主要欄位

| 欄位 | 說明 |
|------|------|
| `code` | 商品代碼 |
| `quantity` | 數量 |
| `price` | 成本價 |
| `last_price` | 最新價 |
| `pnl` | 未實現損益 |

---

## 5. API 使用限制

依 [`sino_API_full.md`](../sino_API_full.md) 官方文件：

| 類別 | 限制 | 因應策略 |
|------|------|----------|
| 帳務查詢 | 5 秒內最多 25 次 | 查詢間隔 ≥ 0.25 秒；按月分批查 `list_profit_loss` |
| 行情 kbars | 單次 session 最多 270 次 | 僅查「有交易或持有」的股票；本地快取 |
| 商品檔 | `code` 須在 `api.Contracts` 中 | 績效查詢登入設 `fetch_contract=True` |

---

## 6. 績效指標定義

### 6.1 重要限制聲明

Shioaji API **不提供 3 個月前的帳戶 NAV（淨資產）歷史快照**。因此：

- 組合報酬率為**估算值**，非券商官方績效
- 報告必須標註計算方法與限制
- 未實現損益僅反映**查詢當下**持倉狀態

### 6.2 區間定義

```
period_end   = 今日（或使用者指定）
period_start = period_end 往前 3 個曆月（同日）
```

範例：若 `period_end = 2026-06-06`，則 `period_start = 2026-03-06`。

### 6.3 核心指標

| 指標 key | 中文名稱 | 計算方式 |
|----------|----------|----------|
| `period_start` | 區間起始日 | 日期字串 YYYY-MM-DD |
| `period_end` | 區間結束日 | 日期字串 YYYY-MM-DD |
| `realized_pnl_total` | 已實現損益合計 | `sum(trade.pnl)` from `list_profit_loss` |
| `unrealized_pnl_total` | 未實現損益合計 | `sum(position.pnl)` from `list_positions` |
| `cash_balance` | 現金餘額 | `account_balance.acc_balance` |
| `position_market_value` | 持倉市值估算 | `sum(position.last_price * position.quantity)` |
| `ending_nav` | 期末淨資產估算 | `cash_balance + position_market_value` |
| `net_cash_flow` | 淨資金流入 | `sum(settlements.amount)` 於區間內（近似） |
| `estimated_beginning_nav` | 期初淨資產估算 | 見下方公式 |
| `portfolio_return_pct` | 組合報酬率 % | 見下方公式 |
| `benchmark_return_pct` | 大盤報酬率 % | 加權指數期初／期末收盤價 |
| `excess_return_pct` | 超額報酬 % | `portfolio_return_pct - benchmark_return_pct` |

### 6.4 估算公式

#### 期初淨資產（反推）

```
estimated_beginning_nav = ending_nav - realized_pnl_total - unrealized_pnl_total + net_cash_flow
```

說明：假設期末 NAV 變動來自（1）已實現損益、（2）未實現損益、（3）淨資金流入，反推期初值。

#### 組合報酬率（簡化式）

```
portfolio_return_pct = (ending_nav - estimated_beginning_nav - net_cash_flow) / estimated_beginning_nav * 100
```

當 `estimated_beginning_nav <= 0` 時，報告標記為 `N/A` 並附警告。

#### 大盤報酬率

```
benchmark_return_pct = (index_close_end - index_close_start) / index_close_start * 100
```

- `index_close_start`：區間起始日（或之後最近交易日）加權指數收盤價
- `index_close_end`：區間結束日加權指數收盤價

### 6.5 個股明細（`by_stock[]`）

每檔股票一筆，欄位建議：

| 欄位 | 來源 |
|------|------|
| `code` | 股票代碼 |
| `realized_pnl` | `profit_loss_summary.pnl` |
| `unrealized_pnl` | 對應 `list_positions.pnl`（若有持倉） |
| `total_pnl` | `realized_pnl + unrealized_pnl` |
| `trade_count` | 區間內交易筆數 |
| `pr_ratio` | `profit_loss_summary.pr_ratio` |

---

## 7. 報告輸出格式

### 7.1 JSON 結構（`report_3m.json`）

```json
{
  "meta": {
    "generated_at": "2026-06-06T10:00:00",
    "account": { "broker_id": "...", "account_id": "...", "account_type": "S" },
    "method_note": "組合報酬率為估算值，非券商官方績效"
  },
  "period": { "start": "2026-03-06", "end": "2026-06-06" },
  "summary": {
    "realized_pnl_total": 0,
    "unrealized_pnl_total": 0,
    "ending_nav": 0,
    "net_cash_flow": 0,
    "estimated_beginning_nav": 0,
    "portfolio_return_pct": 0,
    "benchmark_return_pct": 0,
    "excess_return_pct": 0
  },
  "by_stock": [],
  "trades": [],
  "warnings": []
}
```

### 7.2 Markdown 結構（`report_3m.md`）

1. 標題與產生時間
2. 帳戶資訊與區間
3. 績效摘要表（總損益、報酬率、大盤對比）
4. 個股貢獻表
5. 方法說明與限制聲明
6. 警告訊息（若有）

---

## 8. 風險與限制

| 風險 | 影響 | 緩解 |
|------|------|------|
| 無歷史 NAV | 報酬率為估算 | 報告明確標註；提供組成項目拆解 |
| kbars 次數上限 | 持股種類多時可能超限 | 本地快取；僅查有交易／持有的 code |
| settlements 非完整金流 | `net_cash_flow` 不精確 | 標註為近似值 |
| 零股交易 | 預設 `Unit.Common` 可能漏單 | Phase 2 可選支援 `Unit.Share` |
| 非交易日 | 期初／期末可能無 K 線 | 取最近交易日收盤價 |
| API 簽署未完成 | 帳務查詢失敗 | 沿用既有 signed 檢查與錯誤提示 |

---

## 9. 驗收標準

### 9.1 文件階段（Phase 0，本文件）

- [x] 指標公式與限制已明確定義
- [x] API 對照表完整
- [x] 輸出格式已定義
- [x] 架構文件已撰寫（見 ARCHITECTURE.md）

### 9.2 實作階段（Phase 1–4，後續）

1. CLI `performance-3m` 可產出 `report_3m.json` + `report_3m.md`
2. `sino-gui` 績效頁籤可一鍵產生同內容報告
3. 報告含：總損益、報酬率%、大盤對比、個股明細
4. 僅處理證券帳戶；期貨帳戶跳過並提示
5. `.env` 不上傳 GitHub

---

## 10. 參考文件

- [PERFORMANCE_3M_ARCHITECTURE.md](./PERFORMANCE_3M_ARCHITECTURE.md) — 程式架構
- [sino_API_full.md](../sino_API_full.md) — Shioaji API 完整文件
- [sino_API.md](../sino_API.md) — API 文件索引
