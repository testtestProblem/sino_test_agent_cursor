# sino-gui 使用指南

## 1. 概述

`sino-gui` 是永豐金 Shioaji API 的 **Debug GUI**（Tkinter），用於手動測試帳務查詢、行情查詢與連線狀態：登入、API 流量／連線數、餘額、持倉、損益、交割、**歷史每日總資產（Daily NAV）**、股票 K 線等。適合開發階段驗證 API 回傳與帳戶資料。

- **CLI 入口**：[`pyproject.toml`](../pyproject.toml) → `sino-gui = sino_account.gui.app:main`
- **主程式**：[`src/sino_account/gui/app.py`](../src/sino_account/gui/app.py)
- **技術架構**（模組依賴、執行緒、Get API Usage、Positions 2、Daily NAV、K 線）：見 [SINO_GUI_ARCHITECTURE.md](./SINO_GUI_ARCHITECTURE.md)

`sino_gui` branch 僅保留 `sino-gui` 入口，不含 `performance-3m`、`nav-chart-gui` 等 CLI。

---

## 2. 環境需求

| 項目 | 說明 |
|------|------|
| Python | 3.8+（見 `pyproject.toml`） |
| 套件 | `shioaji`、`python-dotenv`、`openpyxl`（`pip install -e .` 會一併安裝） |
| GUI | Tkinter（Windows / macOS 通常隨 Python 內建） |
| 憑證 | 永豐 Shioaji API Key（`.env` 設定） |

---

## 3. 安裝

在**專案根目錄**（含 `pyproject.toml` 的目錄）執行：

```bash
pip install -e .
```

請勿在 `src/` 或 `gui/` 子目錄執行，否則找不到套件。

### 3.1 環境變數

複製 [`.env.example`](../.env.example) 為 `.env`：

```env
SJ_API_KEY=YOUR_API_KEY
SJ_SEC_KEY=YOUR_SECRET_KEY
SJ_PRODUCTION=true
```

| 變數 | 必填 | 說明 |
|------|------|------|
| `SJ_API_KEY` | 是 | API Key |
| `SJ_SEC_KEY` | 是 | Secret Key |
| `SJ_PRODUCTION` | 建議 | `true` 正式環境，`false` 模擬 |
| `SJ_CA_PATH` | 否 | 憑證路徑（下單用；查帳務通常不需要） |
| `SJ_CA_PASSWD` | 否 | 憑證密碼 |

`.env` 由 [`core/session.py`](../src/sino_account/core/session.py) 從專案根目錄載入。

---

## 4. 啟動

```bash
sino-gui
```

或：

```bash
python -m sino_account.gui.app
```

若 `sino-gui` 找不到，確認 `pip install -e .` 在專案根目錄執行，且 Python Scripts 目錄在 PATH 中。

---

## 5. 介面說明

```
┌─────────────────────────────────────────────────────────────┐
│ Account [下拉]   Begin [日期]   End [日期]                  │
│ Code [2330]      （K 線查詢用，如 2330、0050）              │
├──────────────┬──────────────────────────────────────────────┤
│ Login        │ Result                                       │
│ Logout       │ ┌──────────────────────────────────────────┐ │
│ Get API Usage│ │ JSON 或純文字表格                         │ │
│ Get Account… │ └──────────────────────────────────────────┘ │
│ …            │                                              │
├──────────────┴──────────────────────────────────────────────┤
│ Status: logged in (production)                              │
└─────────────────────────────────────────────────────────────┘
```

| 區域 | 說明 |
|------|------|
| **Account** | 登入後顯示帳戶列表，格式 `S \| BROKER_ID-ACCOUNT_ID` |
| **Begin / End** | 日期區間 `YYYY-MM-DD`；**Get Profit/Loss**、**Get Daily NAV**、**Get Stock Kbars**、**Get Stock Kbars 2** 使用；預設為當月 1 日～今天 |
| **Code** | 股票代號；**Get Stock Kbars** / **Get Stock Kbars 2** 使用；預設 `2330` |
| **左側按鈕** | 觸發 API 查詢 |
| **Result** | 查詢結果（多數為 JSON；Get API Usage / Positions 2 / Kbars 為表格文字） |
| **Status** | 登入狀態或目前執行的動作 |

---

## 6. 按鈕操作

### 6.1 連線與帳戶

| 按鈕 | 前置條件 | 輸出 | 說明 |
|------|----------|------|------|
| **Login** | `.env` 已設定 | JSON | 登入並下載商品檔（`fetch_contract=True`），更新 Account 下拉 |
| **Logout** | — | JSON | 登出並清空帳戶列表 |
| **Get API Usage** | 已登入 | 純文字 | 連線數、已用／上限／剩餘流量（`api.usage()`）；**不需**選 Account |
| **Get Account Info** | 已登入 | JSON | 所有帳戶的 `account_type`、`broker_id`、`account_id` 等 |

### 6.2 帳務查詢

| 按鈕 | 前置條件 | 輸出 | 說明 |
|------|----------|------|------|
| **Get Account Balance** | 已登入 + 選帳戶 | JSON | 現金餘額 `acc_balance` |
| **Get Positions** | 已登入 + 選帳戶 | JSON | `list_positions(unit=Unit.Share)`（股數，已含整股） |
| **Get Positions 2** | 已登入 + 選帳戶 | 純文字 | 合併整股/零股、名稱、市值、損益%、NAV 合計 |
| **Get Margin** | 已登入 + 選帳戶 | JSON | 期貨保證金（主要供期貨帳戶） |
| **Get Profit/Loss** | 已登入 + 選帳戶 + Begin/End | JSON | 區間內已實現損益明細 |
| **Get Daily NAV** | 已登入 + 選帳戶 + Begin/End + Excel | 純文字 | 歷史每日總資產（現金 + 持倉收盤市值）；見 §6.8 |
| **Get Settlements** | 已登入 + 選帳戶 | JSON | 未來交割排程（T+0～T+2） |

### 6.3 行情查詢（K 線）

| 按鈕 | 前置條件 | 輸出 | 說明 |
|------|----------|------|------|
| **Get Stock Kbars** | 已登入 + Code + Begin/End | 純文字 | 分 K 歷史行情（開高低收、量、額）；超過 80 筆省略中間 |
| **Get Stock Kbars 2** | 已登入 + Code + Begin/End | 純文字 | 依交易日彙總，只顯示每日**開盤**與**收盤** |

行情查詢需 Login 時已載入商品檔（`fetch_contract=True`）。實作見 [`get_stock_kbars.py`](../src/sino_account/functions/get_stock_kbars.py)。

### 6.4 建議操作流程

1. 按 **Login**（首次可能較慢，正在下載商品檔）
2. 可選：按 **Get API Usage** 確認連線數與剩餘流量
3. 帳務查詢：在 **Account** 選擇證券帳戶（`S | …`），按所需按鈕
4. **Get Daily NAV**：確認專案根目錄（或 `data/`）有 **`庫存.xlsx`**、**`對帳單.xlsx`**（永豐券商匯出），設定 **Begin / End** 後查詢
5. K 線查詢：輸入 **Code** 與 **Begin / End**，按 **Get Stock Kbars** 或 **Get Stock Kbars 2**
6. 結束後按 **Logout**

### 6.5 Get API Usage

| 項目 | 說明 |
|------|------|
| API | `api.usage()` |
| 輸出欄位 | 連線數、已用 MB、上限 GB、剩餘 GB、使用率% |
| 重置 | 每日流量於開盤日 **08:00** 重置 |
| 用途 | 開發時監控 kbars 等行情查詢消耗的流量 |

輸出範例：

```
=== API 流量及連線數 ===
連線數:     2
已用流量:   41.85 MB / 2.00 GB
剩餘流量:   1.96 GB
使用率:     2.00%
```

實作見 [`get_usage.py`](../src/sino_account/functions/get_usage.py)；技術細節見 [SINO_GUI_ARCHITECTURE.md §9](./SINO_GUI_ARCHITECTURE.md#9-get-api-usage-演算法)。

### 6.6 Get Positions vs Get Positions 2

| | Get Positions | Get Positions 2 |
|--|---------------|-----------------|
| 格式 | JSON | 固定寬度表格 |
| 資料來源 | 僅整股 API | 整股 + 零股 API，再合併 |
| 股票名稱 | 無 | 有（需 Login 下載商品檔） |
| 損益% | 無 | 有（`pnl ÷ 成本 × 100`） |
| 合計 | 無 | 現金、持倉市值、未實現損益、未實現損益%、NAV |

Positions 2 表格欄位：代號、名稱、張/股、股數、成本價、現價、損益、**損益%**、市值。

合併與市值公式見 [SINO_GUI_ARCHITECTURE.md §10](./SINO_GUI_ARCHITECTURE.md#10-get-positions-2-演算法)、[INVENTORY_MARKET_VALUE.md](./INVENTORY_MARKET_VALUE.md)。**股價值與 NAV 計算**（含 T+1／T+2 交割款、融資／融券盈虧）見 [POSITIONS2_NAV.md](./POSITIONS2_NAV.md)。

### 6.7 Get Stock Kbars vs Get Stock Kbars 2

| | Get Stock Kbars | Get Stock Kbars 2 |
|--|-----------------|-------------------|
| API | `api.kbars()` 分 K | 同上，再依日彙總 |
| 粒度 | 每分鐘一根 K | 每個交易日一行 |
| 欄位 | 時間、開、高、低、收、量、額 | 日期、開盤、收盤 |
| 開盤 | 每根 K 的 Open | 當日第一根 K 的 Open |
| 收盤 | 每根 K 的 Close | 當日最後一根 K 的 Close |

### 6.8 Get Daily NAV（歷史每日總資產）

依**對帳單**完整買賣紀錄 + **庫存**目前持股，往回重建區間內**每個交易日**的持倉；再以 **kbars 收盤價**計算持倉市值，加上推估現金，得到每日總資產（NAV）。

| 項目 | 說明 |
|------|------|
| 目的 | 了解過去每日「現金 + 股票市值」變化 |
| 前置 | 已 Login（`fetch_contract=True`）、選證券帳戶、Begin/End |
| **必要檔案** | 專案根目錄或 `data/` 下的 **`庫存.xlsx`**、**`對帳單.xlsx`**（永豐券商匯出） |
| 持倉來源 | `庫存.xlsx` 的「今日餘額」＝目前股數；`對帳單.xlsx` 每筆成交往回扣 |
| 股價來源 | Shioaji `api.kbars()` → 每日**收盤價**（當日最後一根分 K 的 Close） |
| 交易日 | 以 **2330** 有 kbars 的日期為準；**休市日不輸出** |
| 現金 | 目前 `account_balance`，依 **T+2 交割日**往回扣對帳單應付/應收（**非成交日**；不含股息、入金、出金） |
| 輸出 | 純文字表格：日期、現金、持倉市值、總資產、持倉檔數 |

**Excel 檔案說明**

| 檔案 | 主要欄位 | 用途 |
|------|----------|------|
| `庫存.xlsx` | 商品、今日餘額、現值 | 目前持倉快照（股數與庫存現值合計） |
| `對帳單.xlsx` | 成交日、商品、買賣、數量、應付/應收金額 | 區間內每筆買賣（現買/現賣/券買/券賣）；數量單位為**股** |

**持倉重建公式**（某日收盤後）：

```
持倉(D) = 庫存今日餘額 − Σ(對帳單中 成交日 > D 的淨股數變動)
現金(D) = 期末 acc_balance − Σ(對帳單中 交割日 > D 的淨現金流)   ← 交割日 = 成交日 + 2 個交易日 (T+2)
持倉市值(D) = Σ 持倉股數 × 該日收盤價
總資產(D) = 現金(D) + 持倉市值(D)
```

對帳單最早一筆之前的持股，視為**區間外底倉**（由庫存往回推自然保留，報表會提示若 Begin 早於對帳單起日）。

**輸出範例**（節錄）：

```
=== 歷史每日總資產（收盤價結算） ===
區間: 2026-06-01 ~ 2026-06-15
交易日數: 11
資料來源: 庫存.xlsx（26 檔） + 對帳單.xlsx（561 筆交易）
期末現金: 775,750.00（account_balance）
庫存現值快照: 2,006,828.00；快照 NAV: 2,782,578.00
交易日曆: 2330 有 kbars 之日期（休市日不列入）

日期                       現金           持倉市值            總資產     持倉檔數
------------------------------------------------------------------
2026-06-01       637,923.00   1,950,000.00   2,587,923.00       24
...
```

**與 Get Positions 2 的關係**

| | Get Positions 2 | Get Daily NAV |
|--|-----------------|---------------|
| 時間 | 僅**目前**快照 | **歷史**每個交易日 |
| 持倉 | API `list_positions` | Excel 庫存 + 對帳單回放 |
| 股價 | API `last_price` | kbars **收盤價** |
| 現金 | API `acc_balance` | API 期末現金 + 對帳單回放 |

實作見 [`get_daily_nav.py`](../src/sino_account/functions/get_daily_nav.py)、[`statements.py`](../src/sino_account/performance/data/statements.py)；演算法見 [SINO_GUI_ARCHITECTURE.md §12](./SINO_GUI_ARCHITECTURE.md#12-get-daily-nav-演算法)。

**注意**

- 查詢前請更新 **庫存.xlsx**、**對帳單.xlsx**，與券商 APP 一致
- 區間內持倉檔數會隨買賣變動（非固定為目前 26 檔）
- 持倉多、區間長時會對每檔呼叫 kbars，請留意 **Get API Usage** 流量
- 若某日任一持股缺收盤價，該**交易日整列略過**（報表提示）

---

## 7. 常見問題

### 7.1 `尚未登入，請先按 Login`

尚未按 Login 或登入失敗。檢查 `.env` 的 API Key 是否正確。

### 7.2 `Another request is still running`

上一個 API 請求尚未完成。Shioaji 不支援並行呼叫，請等待完成後再按。

### 7.3 `fetch_contracts: exclusive access lost`

在 API 連線使用中又觸發商品檔下載。請 **Logout → Login** 重試；勿在查詢進行中重複 Login。

### 7.4 股票名稱顯示 `(未知)`

商品檔未載入。GUI Login 已設 `fetch_contract=True`；若仍未知，請 Logout 後重新 Login。

### 7.5 Positions 2 市值與券商庫存表不一致

可能原因：

- **時間差**：API 快照與庫存表匯出時間不同
- **報價差**：`last_price` 與庫存表「現價」略有延遲
- **持倉範圍**：API 可能含庫存表未列出的標的（或已賣出）

Positions 2 市值公式為 `現價 × 合併後股數`，與券商庫存「現值」欄對齊。合併邏輯見架構文件。

### 7.6 K 線查詢無資料

- 確認已 **Login** 且商品檔已載入
- **Code** 是否正確（如 `2330`、`0050`）
- **Begin / End** 是否為有交易的日期（格式 `YYYY-MM-DD`）
- 行情 API 有流量限制，避免短時間大量查詢；可先按 **Get API Usage** 查看剩餘流量

### 7.7 Get API Usage 全為 0

- 確認已 **Login**（未登入無法查詢）
- 若仍全 0 且含 `warning`，可能是 `UsageOut` 解析問題；見 [SINO_API_GUIDE.md §6](./SINO_API_GUIDE.md#6-序列化與帳戶)
- 模擬環境（`SJ_PRODUCTION=false`）行為可能與正式環境不同

### 7.8 Get Daily NAV 找不到 Excel 或結果為空

- 確認 **`庫存.xlsx`**、**`對帳單.xlsx`** 在專案根目錄或 `data/`（檔名需完全一致）
- 確認已 **Login** 且 `fetch_contract=True`（kbars 需商品檔）
- **Begin / End** 是否在對帳單涵蓋範圍內；休市日不會出現在表格中
- 若提示缺收盤價，該日會略過；可縮短區間或確認該股票在該日有交易

### 7.9 Get Daily NAV 最後一日與庫存現值差異

- 持倉市值用 **kbars 收盤價 × 股數**；庫存表「現值」用券商 **現價**，來源與時間可能不同
- 除權息、報價延遲會造成數％偏差；報表偏差 >5% 會提示
- **現金**依 T+2 **交割日**回放（非成交日）；未含股息、入金、出金
- 成交日～交割日前：持倉已變、現金尚未扣/入帳，總資產在這段可能略有不準

### 7.10 Windows 中文或路徑問題

專案路徑含中文時，請在專案根目錄執行 `pip install -e .` 與 `sino-gui`。

---

## 8. 連線注意事項

- 共用 `core/session.py`，**同一時間只應有一個程式**持有 Shioaji 連線
- 帳務 API 約 5 秒內 25 次；Positions 2 連續查詢間有 `throttle()`
- 行情 `kbars` 消耗**每日流量**（bytes），與帳務次數限制不同；可用 **Get API Usage** 監控（見 `sino_API_full.md` §流量及連線數查詢）

---

## 9. 相關文件

- [SINO_GUI_ARCHITECTURE.md](./SINO_GUI_ARCHITECTURE.md) — 完整技術架構
- [SINO_API_GUIDE.md](./SINO_API_GUIDE.md) — Shioaji 帳務 API 使用指南
- [SINO_POSITION_ALGORITHMS.md](./SINO_POSITION_ALGORITHMS.md) — 持倉股數、市值、NAV 演算法
- [INVENTORY_MARKET_VALUE.md](./INVENTORY_MARKET_VALUE.md) — 庫存市值演算法與 API 用法
- [sino_API_full.md](../sino_API_full.md) — Shioaji API 參考（含 Kbars）
