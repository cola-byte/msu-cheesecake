# 技術筆記

資料來源是 [Eat at State](https://eatatstate.msu.edu/) 連結到的 Nutrislice 公開菜單。2026-09-22 的初次測試確認，菜單 JSON 可以不帶登入 Cookie 或 API key 讀取。這是網站前端使用的介面；網站改版時可能需要調整程式。

## 資料入口

```
GET https://msu.api.nutrislice.com/menu/api/schools/
```

程式使用每個地點 `active_menu_types[].urls.full_menu_by_date_api_url_template` 提供的網址模板取得週菜單，不自行猜測餐廳 ID。

- `days[].date`：菜單日期。
- `days[].menu_items[].food`：品名、描述、成分及食物分類。
- `menu_id`、`station_id`：對應餐台及分區。
- `days[].menu_info[menu_id].section_options.display_name`：餐台顯示名稱。
- `last_updated`：來源更新時間，與本機報表產生時間不同。

## 日期與抓取

API 以星期日至星期六回傳一週。查詢星期一至星期日需要取得兩份週資料，再依實際日期篩選，避免漏掉最後的星期日。

程式最多同時使用兩個連線，每次下載後稍作間隔。部分 HTTP 暫時性錯誤會重試；失敗會記錄並回傳非零結束碼。不能將抓取失敗或空白資料當成沒有起司蛋糕。

`--refresh` 強制下載；預設可重用已存來源；`--offline` 不連線。預設快取沒有過期時間，要查最新菜單必須使用 `--refresh`。

## 保存與分類

採集時保存完整 API 回應。在目標日期內，所有非空 `food` 紀錄都會進入完整品項檔案，不依關鍵字丟棄，也不在採集階段去重。非食物列仍保留於原始 JSON。

分類只使用文字規則，不使用 AI。規則位於 `filter_menus.py`，會記錄命中欄位及詞語；未知品項仍保留，可離線重新篩選。完整原始 JSON 和產生的報表不隨原始碼發佈。

## 瀏覽器核對

網站餐台預設折疊，部分食物要捲動才會載入；切換餐廳也會重設日期和餐別。API 可直接取得週資料，避免只讀到畫面初始內容。

初次測試曾以網頁核對 Landon 2026-09-26 午餐的 `Cheesecake with Fruit`、`Sour Cream Cheesecake`，以及 Case 2026-09-24 晚餐的 `Cheesecake`。這是歷史驗證，不是持續有效的供應保證。
