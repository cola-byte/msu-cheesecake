# 第一次使用：下載程式、開啟自動寄信

完成設定後，GitHub 會每天查 MSU 菜單，有新的起司蛋糕候選就寄信。自己的電腦可以關機。

下載程式和自動寄信是兩件事。只想收信，可以跳過第 1、2 步，直接從第 3 步開始。

## 0. 先取得 GitHub 存取權

這個專案是私有的。請先把自己的 **GitHub 帳號名稱**交給倉庫擁有人，請對方在專案的 **Settings → Collaborators → Add people** 邀請你，再登入 GitHub 接受邀請。

確認能開啟 [專案首頁](https://github.com/cola-byte/msu-cheesecake)。如果出現 404，先確認登入帳號及邀請是否已接受。

個人帳號倉庫的協作者可以新增這裡需要的 repository secrets / variables；參見 [GitHub 官方說明](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets)。

## 1. 把程式下載到電腦（git clone）

本機需要 Git；要在本機執行爬蟲，還需要 Python 3.10 以上。只有雲端寄信不需要安裝這些軟體。

Windows 開啟 PowerShell；Mac 開啟 Terminal。到想存放程式的資料夾，一行一行貼上：

```sh
git clone https://github.com/cola-byte/msu-cheesecake.git
cd msu-cheesecake
```

第一行下載程式，第二行進入程式資料夾。如果跳出 GitHub 登入視窗，登入剛剛接受邀請的帳號。

已經下載過就不用再 clone；下次在 `msu-cheesecake` 資料夾執行 `git pull` 更新。

## 2. 本機試跑一次（可跳過）

Windows 貼上：

```powershell
python -m pip install tzdata
python probe_menus.py --refresh
```

Mac 使用：

```sh
python3 -m pip install tzdata
python3 probe_menus.py --refresh
```

`tzdata` 提供時區資料，安裝一次即可。爬蟲會依 MSU 當地時間，自動查詢這週星期一至星期日。

看到 `10/108 ... ok` 代表正在執行，請等它結束。最後確認 `errors` 是 `0`，再打開程式資料夾中的 `probe-output/results.md` 看結果。

這一步只查菜單，不會寄信。

## 3. 確認寄件、收件信箱

打開 [GitHub 的 Variables 設定頁](https://github.com/cola-byte/msu-cheesecake/settings/variables/actions)，確認以下三項：

| 名稱 | 應填內容 |
|---|---|
| `SMTP_USERNAME` | 寄件 Gmail 地址 |
| `EMAIL_TO` | 要收到通知的信箱 |
| `EMAIL_ENABLED` | 先維持 `false`，測試成功後再改 |

維護者已先設定一組寄件、收件地址。如果要沿用，就不必更改地址。寄件和收件可以是同一個信箱。

**接下來建立密碼時，必須登入 `SMTP_USERNAME` 這個 Google 帳號。** 如果要改用自己的 Gmail，先把 `SMTP_USERNAME` 改成自己的地址，並確認 `EMAIL_TO` 是想收到通知的地址。

## 4. 建立 Gmail 應用程式密碼

1. 登入上一步確認的寄件 Google 帳號。
2. 在 Google 帳戶的安全性設定中，啟用「兩步驟驗證」。
3. 打開 [應用程式密碼](https://myaccount.google.com/apppasswords)。
4. 輸入容易辨認的名稱，例如 `MSU cheesecake`，建立密碼。
5. 複製 Google 顯示的應用程式密碼，下一步會用到。

這是另外產生給程式使用的密碼，**不是平常登入 Gmail 的密碼**。不要貼到聊天、程式碼或 README。若找不到這個選項，請看 [Google 官方說明](https://support.google.com/accounts/answer/185833?hl=zh-Hant)；部分帳號設定不支援。

## 5. 把密碼存到 GitHub

打開 [GitHub 的 Secrets 設定頁](https://github.com/cola-byte/msu-cheesecake/settings/secrets/actions)，按 **New repository secret**：

| 欄位 | 填入內容 |
|---|---|
| Name | `SMTP_PASSWORD` |
| Secret | 剛剛產生的 Gmail 應用程式密碼 |

按 **Add secret** 儲存。如果已經有 `SMTP_PASSWORD`，使用該項的編輯按鈕更新即可。密碼要放在 **Secrets**，不要放在 Variables。

## 6. 寄一封測試信

1. 打開 [MSU menu email 執行頁](https://github.com/cola-byte/msu-cheesecake/actions/workflows/menu-email.yml)。
2. 按 **Run workflow**。
3. Branch 保持 **main**，mode 選 **test-email**。
4. 按下選單裡的綠色 **Run workflow** 按鈕。
5. 等新出現的執行紀錄完成，點進去確認是綠色勾勾。
6. 到收件信箱確認收到測試信，也檢查垃圾郵件。

綠色勾勾表示寄信流程成功；仍要實際確認信箱收到了信。收到後再進行下一步。

## 7. 開啟每天自動檢查

回到 [Variables 設定頁](https://github.com/cola-byte/msu-cheesecake/settings/variables/actions)，編輯 `EMAIL_ENABLED`，把值從 `false` 改成小寫的 `true`，再儲存。

完成！之後每天 **MSU 當地時間早上 07:17** 由 GitHub 執行，可能稍有延遲，電腦不用開著。

想現在就查一次，回到 [MSU menu email](https://github.com/cola-byte/msu-cheesecake/actions/workflows/menu-email.yml)，再按 **Run workflow**，這次 mode 選 **send**。

郵件列出本週今天起的起司蛋糕候選，並另外標示起司蛋糕相關甜點，例如冰淇淋。沒有新候選就不寄；同樣的結果不會每天重複寄。菜單是預定供應，仍以餐廳現場為準。

## 卡住時先看這裡

| 情況 | 處理方式 |
|---|---|
| GitHub 頁面 404，或 clone 顯示 Repository not found | 確認已接受邀請，並登入被邀請的帳號 |
| 找不到 `git` 或 `python` 指令 | 本機尚未安裝對應軟體，或安裝後需要重開終端機；只用自動寄信可跳到第 3 步 |
| `test-email` 出現紅色叉叉 | 點開失敗步驟，確認寄件帳號和應用程式密碼屬於同一個 Google 帳號，且 Secret 名稱是 `SMTP_PASSWORD` |
| 排程顯示 Skipped | 確認 `EMAIL_ENABLED` 是小寫 `true` |
| 沒有每天收到信 | 沒有新候選時不寄信；到 Actions 查看最近一次是否成功 |
| 想暫停自動檢查 | 把 `EMAIL_ENABLED` 改回 `false` |

進階模式與寄送狀態處理，請看 [自動寄信設定](email-setup.md)。
