# sino-gui 使用指南

## 1. 概述

`sino-gui` 是永豐金 Shioaji API 的 **Debug GUI**（Tkinter），用於手動測試帳務查詢、行情查詢與連線狀態：登入、API 流量／連線數、餘額、持倉、損益、交割、股票 K 線等。適合開發階段驗證 API 回傳與帳戶資料。

- **CLI 入口**：[`pyproject.toml`](../pyproject.toml) → `sino-gui = sino_account.gui.app:main`
- **主程式**：[`src/sino_account/gui/app.py`](../src/sino_account/gui/app.py)
- **技術架構**（模組依賴、執行緒、Get API Usage、Positions 2、K 線）：見 [SINO_GUI_ARCHITECTURE.md](./SINO_GUI_ARCHITECTURE.md)

`sino_gui` branch 僅保留 `sino-gui` 入口，不含 `performance-3m`、`nav-chart-gui` 等 CLI。

---

## 2. 環境需求

| 項目 | 說明 |
|------|------|
| Python | 3.8+（見 `pyproject.toml`） |
| 套件 | `shioaji`、`python-dotenv`（`pip install -e .` 會一併安裝） |
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
| **Begin / End** | 日期區間 `YYYY-MM-DD`；**Get Profit/Loss**、**Get Stock Kbars**、**Get Stock Kbars 2** 使用；預設為當月 1 日～今天 |
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
| **Get Positions** | 已登入 + 選帳戶 | JSON | 原始 `list_positions()`（預設整股） |
| **Get Positions 2** | 已登入 + 選帳戶 | 純文字 | 合併整股/零股、名稱、市值、損益%、NAV 合計 |
| **Get Margin** | 已登入 + 選帳戶 | JSON | 期貨保證金（主要供期貨帳戶） |
| **Get Profit/Loss** | 已登入 + 選帳戶 + Begin/End | JSON | 區間內已實現損益明細 |
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
4. K 線查詢：輸入 **Code** 與 **Begin / End**，按 **Get Stock Kbars** 或 **Get Stock Kbars 2**
5. 結束後按 **Logout**

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

合併與市值公式見 [SINO_GUI_ARCHITECTURE.md §10](./SINO_GUI_ARCHITECTURE.md#10-get-positions-2-演算法)、[INVENTORY_MARKET_VALUE.md](./INVENTORY_MARKET_VALUE.md)。

### 6.7 Get Stock Kbars vs Get Stock Kbars 2

| | Get Stock Kbars | Get Stock Kbars 2 |
|--|-----------------|-------------------|
| API | `api.kbars()` 分 K | 同上，再依日彙總 |
| 粒度 | 每分鐘一根 K | 每個交易日一行 |
| 欄位 | 時間、開、高、低、收、量、額 | 日期、開盤、收盤 |
| 開盤 | 每根 K 的 Open | 當日第一根 K 的 Open |
| 收盤 | 每根 K 的 Close | 當日最後一根 K 的 Close |

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

### 7.8 Windows 中文或路徑問題

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
