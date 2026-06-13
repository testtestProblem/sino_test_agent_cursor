# sino-gui 使用指南

## 1. 概述

`sino-gui` 是永豐金 Shioaji API 的 **Debug GUI**（Tkinter），用於手動測試帳務查詢：登入、餘額、持倉、損益、交割等。適合開發階段驗證 API 回傳與帳戶資料。

- **CLI 入口**：[`pyproject.toml`](../pyproject.toml) → `sino-gui = sino_account.gui.app:main`
- **主程式**：[`src/sino_account/gui/app.py`](../src/sino_account/gui/app.py)
- **技術架構**（模組依賴、執行緒、Positions 2 演算法）：見 [SINO_GUI_ARCHITECTURE.md](./SINO_GUI_ARCHITECTURE.md)

---

## 2. 環境需求

| 項目 | 說明 |
|------|------|
| Python | 3.8+（見 `pyproject.toml`） |
| 套件 | `shioaji`、`python-dotenv`（`pip install -e .` 會一併安裝） |
| GUI | Tkinter（Windows / macOS 通常隨 Python 內建） |
| 憑證 | 永豐 Shioaji API Key（`.env` 設定） |

> `matplotlib` 為 `nav-chart-gui` 依賴，`sino-gui` 本身不使用。

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
├──────────────┬──────────────────────────────────────────────┤
│ Login        │ Result                                       │
│ Logout       │ ┌──────────────────────────────────────────┐ │
│ Get Account… │ │ JSON 或純文字表格                         │ │
│ …            │ └──────────────────────────────────────────┘ │
├──────────────┴──────────────────────────────────────────────┤
│ Status: logged in (production)                              │
└─────────────────────────────────────────────────────────────┘
```

| 區域 | 說明 |
|------|------|
| **Account** | 登入後顯示帳戶列表，格式 `S \| BROKER_ID-ACCOUNT_ID` |
| **Begin / End** | 僅 **Get Profit/Loss** 使用，預設為當月 1 日～今天 |
| **左側按鈕** | 觸發 API 查詢 |
| **Result** | 查詢結果（多數為 JSON；Get Positions 2 為表格文字） |
| **Status** | 登入狀態或目前執行的動作 |

---

## 6. 按鈕操作

| 按鈕 | 前置條件 | 輸出 | 說明 |
|------|----------|------|------|
| **Login** | `.env` 已設定 | JSON | 登入並下載商品檔（`fetch_contract=True`），更新 Account 下拉 |
| **Logout** | — | JSON | 登出並清空帳戶列表 |
| **Get Account Info** | 已登入 | JSON | 所有帳戶的 `account_type`、`broker_id`、`account_id` 等 |
| **Get Account Balance** | 已登入 + 選帳戶 | JSON | 現金餘額 `acc_balance` |
| **Get Positions** | 已登入 + 選帳戶 | JSON | 原始 `list_positions()`（預設整股） |
| **Get Positions 2** | 已登入 + 選帳戶 | 純文字 | 合併整股/零股、股票名稱、持倉市值與 NAV 合計 |
| **Get Margin** | 已登入 + 選帳戶 | JSON | 期貨保證金（主要供期貨帳戶） |
| **Get Profit/Loss** | 已登入 + 選帳戶 + 日期 | JSON | 區間內已實現損益明細 |
| **Get Settlements** | 已登入 + 選帳戶 | JSON | 未來交割排程（T+0～T+2） |

### 6.1 建議操作流程

1. 按 **Login**（首次可能較慢，正在下載商品檔）
2. 在 **Account** 選擇證券帳戶（`S | …`）
3. 按所需查詢按鈕
4. 結束後按 **Logout**

### 6.2 Get Positions vs Get Positions 2

| | Get Positions | Get Positions 2 |
|--|---------------|-----------------|
| 格式 | JSON | 固定寬度表格 |
| 資料來源 | 僅整股 API | 整股 + 零股 API，再合併 |
| 股票名稱 | 無 | 有（需 Login 下載商品檔） |
| 合計 | 無 | 現金、持倉市值、未實現損益、NAV |

Positions 2 的合併與市值公式見 [SINO_GUI_ARCHITECTURE.md §7](./SINO_GUI_ARCHITECTURE.md#7-get-positions-2-演算法)。

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

### 7.6 Windows 中文或路徑問題

專案路徑含中文時，請在專案根目錄執行 `pip install -e .` 與 `sino-gui`。

---

## 8. 與其他 CLI 的關係

| CLI | 用途 |
|-----|------|
| `sino-gui` | 本 Debug GUI |
| `query-portfolio` | 命令列組合查詢 |
| `performance-3m` | 3 個月績效報告 |
| `nav-chart-gui` | 資金水位圖 |
| `nav-diagnose` | 快照 NAV 診斷 |

共用 [`core/session.py`](../src/sino_account/core/session.py)，但**同一時間只應有一個程式**持有 Shioaji 連線。不可同時開兩個 GUI 程式並各自 Login。

---

## 9. 相關文件

- [SINO_GUI_ARCHITECTURE.md](./SINO_GUI_ARCHITECTURE.md) — 完整技術架構
- [SINO_API_GUIDE.md](./SINO_API_GUIDE.md) — Shioaji 帳務 API 使用指南（登入、查詢流程）
- [SINO_POSITION_ALGORITHMS.md](./SINO_POSITION_ALGORITHMS.md) — 持倉股數、市值、NAV 演算法與 AI 反模式
- [PERFORMANCE_3M_ARCHITECTURE.md](./PERFORMANCE_3M_ARCHITECTURE.md) — 績效模組（Positions 2 部分共用 `quantity_units`）
- [NAV_CHART_ARCHITECTURE.md](./NAV_CHART_ARCHITECTURE.md) — 資金水位圖
- [sino_API_full.md](../sino_API_full.md) — Shioaji API 參考
