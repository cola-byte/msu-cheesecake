# MSU 起司蛋糕菜單查詢

抓取 Michigan State University 的公開餐廳菜單，完整保存後，再找出起司蛋糕及相關甜點候選。可以在本機手動查詢，也可以使用 GitHub Actions 每天自動查詢並寄信。

**第一次使用：**請看 [一步一步操作指南（含 git clone 和啟用寄信）](docs/quick-start.md)。設定完成並啟用後，電腦不用保持開機。進階設定見 [自動寄信設定](docs/email-setup.md)。

## 第一次使用

需要 **Python 3.10 以上**和 **Git**。只使用 Python 標準函式庫，**不用執行 pip install，也不用 API key**。

開啟終端機：Windows 使用 PowerShell；macOS 使用 Terminal。

### 1. 下載程式

在終端機貼上以下指令。這是私有倉庫，需要使用已獲邀請的 GitHub 帳號登入，才能下載：

```sh
git clone https://github.com/cola-byte/msu-cheesecake.git
cd msu-cheesecake
```

### 2. 查詢菜單

Windows：

```powershell
python probe_menus.py --start 2026-09-21 --refresh
```

macOS / Linux：

```sh
python3 probe_menus.py --start 2026-09-21 --refresh
```

**請把 `2026-09-21` 換成你要查詢那一週的星期一。** 也可以省略 `--start`，程式會依 MSU 時區自動計算當週星期一。若 Windows 顯示缺少時區資料，可繼續明確指定日期，或執行 `python -m pip install tzdata`。

這行指令會重新抓取全部公開餐廳，從指定日期開始查詢 7 天，保存全部品項並分類候選。

執行時會顯示 `10/108 ... ok` 等進度。分母會依網站當時的餐廳和餐別而變動。等程式結束，確認最後的 `errors` 是 `0`。

### 3. 看結果

打開程式資料夾內的 **`probe-output/results.md`**。這是 Markdown 文字表格，會列出日期、餐廳、餐別、品名與原菜單連結。

Windows 可以直接執行：

```powershell
notepad .\probe-output\results.md
```

macOS 可用文字編輯器開啟，或執行：

```sh
open -a TextEdit probe-output/results.md
```

摘要只列出明確含起司蛋糕名稱的候選及相關甜點；其他寬鬆候選保存在 JSON 檔案中。

## 結果怎麼看

| Classification | 意思 |
|---|---|
| `cheesecake_candidate` | 品名明確包含起司蛋糕，仍是待核實候選 |
| `related_dessert_review` | 起司蛋糕相關甜點，例如起司蛋糕口味冰淇淋 |
| `broad_review` | 名稱、描述、成分或餐台等含有起司、蛋糕、甜點線索，可能包含起司披薩 |
| `not_selected` | 目前規則未命中，但資料仍然保留 |

數量按日期、餐廳、餐別的品項紀錄計算，不是獨立菜色數。分類是程式規則初篩，沒有使用 AI，也不代表人工確認。校方菜單是預定供應，不能保證現場沒有換菜或售完。

## 常用操作

以下以 Windows 的 `python` 示範；macOS / Linux 通常改用 `python3`。

**重新抓取最新資料**，包含已抓過的日期：

```powershell
python probe_menus.py --start 2026-09-21 --refresh
```

**只用已保存資料重新分析**，不連線網站：

```powershell
python probe_menus.py --start 2026-09-21 --offline
```

剛 clone 的版本不包含任何菜單資料，第一次請用 `--refresh`。未加 `--refresh` 或 `--offline` 時，有快取就使用快取，缺少的資料才連線下載。

**只查某間餐廳**，並另存結果：

```powershell
python probe_menus.py --start 2026-09-21 --locations south-pointe-at-case --refresh --output case-output
```

**查看所有參數**：

```powershell
python probe_menus.py --help
```

調整 `filter_menus.py` 的規則後，可用 `--offline` 重新產生所有摘要；也能單獨執行 `python filter_menus.py`，只更新分類 JSON，這個單獨指令不會更新 `results.md` 或 `results.json`。

## 資料檔案

| 檔案 | 用途 |
|---|---|
| `probe-output/results.md` | 優先閱讀的候選摘要 |
| `probe-output/results.json` | 候選、來源、查詢覆蓋及錯誤狀態 |
| `probe-output/all_menu_items.json` | 全部目標日期的食物紀錄 |
| `probe-output/classified_menu_items.json` | 全部品項、分類及命中原因 |
| `probe-output/review_candidates.json` | 所有候選，包括寬鬆候選 |
| `probe-output/raw/` | 原始 API 回應 |

執行會更新同一輸出資料夾內的檔案。要保留不同次查詢，使用不同的 `--output` 路徑，例如 `--output september-21-output`。

`.gitignore` 已排除 `probe-output/`、根目錄下的 `*-output/`、Python 快取、虛擬環境及 `.env`。自訂其他名稱的輸出資料夾時，請也加入 `.gitignore`。抓下來的資料留在自己電腦，不需要上傳 GitHub。

## 遇到問題

- **找不到 python**：先安裝 Python；Windows 也可試 `py -3`，macOS 可試 `python3`。
- **找不到 probe_menus.py**：先 `cd msu-cheesecake`，確認終端機位於程式資料夾。
- **Offline mode: missing cached source**：尚未抓過這份資料，改用 `--refresh`。
- **`errors` 大於 0**：查詢不完整，查看 `results.json` 的 `coverage` 錯誤訊息；不要解讀成沒有起司蛋糕。
- **空白菜單**：可能休息或尚未提供資料，不等於已確認沒有蛋糕。

目前已在 Windows / Python 3.13 實測。macOS / Linux 指令是對應的使用方式，尚未在這兩個平台實跑驗證。

網站 API 與日期邊界說明見 [技術筆記](docs/technical-notes.md)。

## 預覽郵件與執行測試

抓完菜單後，先產生信件預覽，不會寄信：

```powershell
python notify_menus.py --mode preview
```

用瀏覽器開啟 `probe-output/email-preview.html`。預覽顯示本週今天起的候選，不會寫入已寄送紀錄。

執行測試（不會寄信）：

```powershell
python -m unittest discover -s tests -v
```
