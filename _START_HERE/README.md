# _START_HERE 控制台

雙擊任何一個 `.bat` 來操作系統。所有 `.bat` 都會:
1. 自動 cd 到專案根目錄
2. 自動 activate venv
3. 自動讀取 `.env`(透過 Python script)

---

## 檔案說明

| 檔案 | 動作 | 用途 |
|---|---|---|
| `1_status.bat` | 一次性印出系統狀態 | 想看現在持倉、最近 events、Binance 餘額 |
| `2_status_watch.bat` | 即時 dashboard,每 10 秒 refresh | 想盯著系統運轉(Ctrl+C 離開)|
| `3_tick.bat` | 跑一次 tick(讀 active signals → 嘗試下單)| 想手動觸發一次決策執行 |
| `4_seed_signal.bat` | 互動式注入測試 signal | 想餵一筆假 signal 看系統行為(會問 symbol + size)|
| `5_kill_switch_on.bat` | **緊急停止** | 系統行為怪、或想暫停。擋所有新開倉,但允許平倉/停損 |
| `6_kill_switch_off.bat` | 解除緊急停止 | 系統 OK 了想恢復自動執行 |

---

## 典型工作流

**早上開機看看昨天怎樣**:
- 雙擊 `1_status.bat`

**想手動跑一次驗證系統**:
- 雙擊 `4_seed_signal.bat`,輸入 SOLUSDT, 30(假設你沒 SOL 持倉)
- 雙擊 `3_tick.bat`,看 summary
- 雙擊 `1_status.bat`,確認部位入帳

**發現異常想立刻停**:
- 雙擊 `5_kill_switch_on.bat`
- 之後就算 cron 跑也不會開新倉
- 處理完問題後 → 雙擊 `6_kill_switch_off.bat`

**長時間觀察**:
- 雙擊 `2_status_watch.bat`,放著看
- Ctrl+C 結束

---

## 注意

- 這些 `.bat` 只跑「本機操作」,不會啟動排程
- 你要的 24/7 自動執行靠 Oracle Cloud VM(`docs/MIGRATE_TO_ORACLE_VM.md`)
- 改 `.env` 之後不用做什麼,下次 `.bat` 跑會自己讀新值
- 緊急停止寫到 Turso `control` 表,所以雲端 VM 也會即時讀到
