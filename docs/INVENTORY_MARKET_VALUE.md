# 庫存市值演算法

本文件以純文字記錄「持倉市值」的完整計算步驟，對齊券商庫存表「今日餘額 / 現值」。全文不含超連結，可直接閱讀。

---

## 一、使用 Shioaji API 計算庫存市值

### 1.1 環境準備

在專案根目錄建立 `.env`（可參考 `.env.example`）：

```
SJ_API_KEY=你的_API_KEY
SJ_SEC_KEY=你的_SECRET_KEY
SJ_PRODUCTION=true
```

查帳務通常不需要憑證（SJ_CA_PATH）。安裝專案：`pip install -e .`

### 1.2 登入（必須先完成）

```python
import os
import shioaji as sj
from dotenv import load_dotenv

load_dotenv()
production = os.getenv("SJ_PRODUCTION", "true").lower() == "true"

api = sj.Shioaji(simulation=not production)
accounts = api.login(
    api_key=os.environ["SJ_API_KEY"],
    secret_key=os.environ["SJ_SEC_KEY"],
    fetch_contract=True,   # 若要顯示股票名稱，必須 True
)
```

注意事項：

- 同一時間只允許一個 process 持有 Shioaji 連線
- 查詢進行中勿呼叫 api.fetch_contracts()，否則會 exclusive access lost
- 帳務 API 約 5 秒內 25 次，連續查詢間隔建議 0.25 秒

### 1.3 帳戶物件

```python
from shioaji.constant import Unit

# 預設股票帳戶
account = api.stock_account

# 或從 list_accounts() 選擇
# account = api.list_accounts()[0]
```

### 1.4 API 呼叫順序（標準流程）

計算庫存市值**至少**需要以下三次帳務 API 呼叫，順序不可省略 Share 查詢：

```
步驟 1  api.account_balance(account=account)
        → 取得 acc_balance（現金，算 NAV 用）

步驟 2  api.list_positions(account=account)
        → 整股列 Common，quantity 單位為「張」

        （throttle 0.25 秒）

步驟 3  api.list_positions(account=account, unit=Unit.Share)
        → 零股列 Share，quantity 單位為「股」
```

每筆持倉（StockPosition）與市值相關的欄位：

| 欄位 | 用途 |
|------|------|
| code | 商品代號 |
| quantity | 數量（Common=張，Share=股） |
| price | 成本均價 |
| last_price | 現價（算「現值」優先用此欄） |
| pnl | 未實現損益（合併後只取一次） |
| cond | 現股 / 融資 / 融券等（合併分組鍵） |

**禁止**：只執行步驟 2 就計算總市值或 NAV。

### 1.5 序列化 raw 列

Shioaji 回傳物件需轉成 dict 才能合併計算。專案使用 serialize()：

```python
from sino_account.core.serialize import serialize

raw = []
for item in common_positions:
    row = serialize(item)
    row.setdefault("unit", "Common")
    raw.append(row)
for item in share_positions:
    row = serialize(item)
    row["unit"] = "Share"
    raw.append(row)
```

### 1.6 合併股數並計算市值

```python
import time
from sino_account.performance.analytics.quantity_units import (
    build_code_multipliers,
    merge_position_rows,
    merged_position_market_value,
)
from sino_account.performance.data.throttle import throttle

balance = serialize(api.account_balance(account=account))
throttle()
common_positions = api.list_positions(account=account)
throttle()
share_positions = api.list_positions(account=account, unit=Unit.Share)

# ... 組 raw 列（見 1.5）...

multipliers = build_code_multipliers(raw, [])
merged = merge_position_rows(raw, multipliers)

total_market_value = 0.0
for position in merged:
    market_value, warning = merged_position_market_value(position)
    total_market_value += market_value
    # position["shares"] = 合併後股數
    # position["last_price"] = 現價
    # market_value = last_price × shares（優先）

acc_balance = float(balance.get("acc_balance") or 0)
total_nav = acc_balance + total_market_value
```

合併與市值公式詳見本文件第三～五節。

### 1.7 專案內建一鍵查詢（建議）

已登入 session 後，直接呼叫 get_positions2()，內部會完成 1.4～1.6 全流程：

```python
from sino_account.functions.login import login   # 或 GUI Login
from sino_account.functions.get_positions2 import get_positions2, format_positions2_report

login(fetch_contract=True)   # 若要股票名稱
data = get_positions2()
print(format_positions2_report(data))

summary = data["summary"]
print("持倉市值:", summary["total_market_value"])
print("總資產 NAV:", summary["total_nav"])
```

回傳結構：

```
data["positions"][i]["code"]          代號
data["positions"][i]["name"]          名稱（需 fetch_contract=True）
data["positions"][i]["shares"]      合併後股數
data["positions"][i]["last_price"]  現價
data["positions"][i]["market_value"]  單檔市值
data["summary"]["total_market_value"] 持倉總市值
data["summary"]["total_nav"]          現金 + 持倉市值
```

### 1.8 GUI 操作

```
sino-gui → Login → Get Positions 2
```

輸出表格「市值」欄即 merged_position_market_value；底部「持倉市值」「總資產 (NAV)」為合計。

### 1.9 API 流程總覽

```
Login(fetch_contract=True)
    ↓
account_balance → acc_balance
    ↓
list_positions(Common) → raw 整股列
    ↓ throttle
list_positions(Share)  → raw 零股列
    ↓
merge_position_rows(by code+cond)
    ↓
merged_position_market_value(each row)
    ↓
total_market_value = Σ market_value
total_nav = acc_balance + total_market_value
```

---

## 二、輸入資料摘要

1. account_balance → acc_balance
2. list_positions(account) → Common 列
3. list_positions(account, unit=Unit.Share) → Share 列
4. 每列欄位：code, quantity, price, last_price, pnl, cond

兩次 list_positions 之間 throttle 約 0.25 秒。

---

## 三、股數換算

```
Common 列股數 = quantity × 1000
Share  列股數 = quantity × 1
```

（個股 contract.unit 若不同，以商品檔為準；台股預設 1 張 = 1000 股。）

---

## 四、依 (code, cond) 合併兩種 API 列

同一商品、同一交易條件（現股 / 融資等）可能同時有 Common 列與 Share 列。不可把兩列股數無條件相加。

```
若只有 Common 列：total_shares = common_shares
若只有 Share  列：total_shares = share_shares
若兩列都有：
    若 share_shares >= common_shares：
        total_shares = share_shares    # Share 列代表「總股數」，不是額外零股
    否則：
        total_shares = common_shares + share_shares
```

### 0050 範例

- Common：3 張 → 3,000 股
- Share：3,300 股（總量）
- 錯誤：3,000 + 3,300 = 6,300
- 正確：3,300（因 3300 >= 3000）

### pnl 合併規則

同一 (code, cond) 的 Common / Share 兩列，pnl 數值相同且只代表整筆持倉損益 → 合併後只保留一筆 pnl，不可兩列各加一次。

---

## 五、單檔市值（對齊券商庫存「現值」）

合併後每檔持倉 (code, cond) 計算 market_value：

```
若 last_price > 0：
    market_value = last_price × total_shares        ← 優先，對齊「現值 = 現價 × 今日餘額」

否則若 price > 0：
    market_value = price × total_shares + pnl       ← pnl 只加一次

否則若 pnl != 0：
    market_value = pnl                              ← fallback，應記 warning

否則：
    market_value = 0                                ← 無法估算
```

### 0050 市值範例

```
total_shares = 3300
last_price   = 101.95
market_value = 101.95 × 3300 = 336,435
```

---

## 六、持倉總市值

```
total_market_value = Σ 各合併列的 market_value
```

禁止：對未合併的 raw 列逐列用 price×shares+pnl 加總（Common + Share 並存時 pnl 會算兩次、股數也可能錯）。

---

## 七、總資產 NAV（延伸）

```
total_nav = acc_balance + total_market_value
```

未實現損益合計（與市值分開）：

```
total_unrealized_pnl = Σ 各合併列的 pnl    # 每 (code, cond) 一筆，不可 raw 雙列相加
```

---

## 八、常見錯誤

| 錯誤做法 | 後果 |
|---------|------|
| 只查整股 list_positions() | 漏零股或股數錯 |
| Common 股數 + Share 股數無條件相加 | 0050 變 6300 股 |
| raw 兩列各加一次 pnl | 未實現損益 ×2 |
| raw 兩列各算市值再加總 | 市值與 pnl 雙重計算 |
| 有 last_price 仍用 price×shares+pnl | 與券商「現值」不一致 |
| 未 Login 或 session 未建立就查詢 | API 錯誤 |
| 查詢中途 fetch_contracts() | exclusive access lost |

---

## 九、程式對照

| 步驟 | 模組路徑 | 函式 |
|------|----------|------|
| 登入 | src/sino_account/functions/login.py | login |
| Session | src/sino_account/core/session.py | get_api |
| 序列化 | src/sino_account/core/serialize.py | serialize, resolve_account |
| throttle | src/sino_account/performance/data/throttle.py | throttle |
| 合併股數 | src/sino_account/performance/analytics/quantity_units.py | combine_unit_shares, merge_position_rows |
| 單檔市值 | src/sino_account/performance/analytics/quantity_units.py | merged_position_market_value |
| 完整查詢流程 | src/sino_account/functions/get_positions2.py | get_positions2, format_positions2_report |

---

## 十、驗證方式

1. 執行 sino-gui → Login → Get Positions 2
2. 與券商 APP 比對：
   - 今日餘額 ↔ 合併後 total_shares
   - 現值 ↔ market_value
   - 現金 + 持倉現值 ↔ total_nav
