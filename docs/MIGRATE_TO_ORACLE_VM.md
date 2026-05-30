# crypto-ai-agent 遷移到 Oracle Cloud VM(Tokyo)

> 上一個 session 沒講完的事:GHA runner 跑在美國,Binance 封美國 IP,所以 `exec_tick` 撞 `APIError: Service unavailable from a restricted location`。本機台灣可以打,所以本機跑 OK。
>
> **解法**:把執行層從 GHA 搬到 Oracle Cloud 永久免費 VM(東京 region)。Code 完全不動,只是換主機。
>
> 預計 90-120 分鐘。

---

## 0. 這份文件給下個 Claude session 用

如果你是接手的 Claude:

- 專案在 `C:\Projects\crypto-ai-agent`,branch 是 `master`。
- 已經跑通的:P0 + P1 + P1.5 + tech debt cleanup(116 tests passing)。
- Turso DB 已建好、有 schema、有 3 筆 signals(2 triggered + 1 expired)。
- Binance testnet API key + Discord webhook 都設好,本機 `.env` 內有。
- GHA workflows 存在但因 IP 地理限制無法跑(`exec_tick` 100% 失敗)。
- 目標:**讓 Oracle VM 取代 GHA cron** 做 tick 執行;GHA workflow 留著,但拿掉 cron schedule(保留 workflow_dispatch 給 debug/seed 用)。
- VM 規格:Oracle Always Free,Tokyo region(`ap-tokyo-1`),Ubuntu 22.04 LTS,A1.Flex(ARM)或 E2.1.Micro(x86)都行。
- 使用者沒玩過 VM/Linux,需要手把手。

---

## 1. 事前準備

需要:
- 一張信用卡(Oracle 會驗證但**不會扣款**,Always Free 真的不收錢)
- 一支手機(收驗證簡訊)
- 一個非拋棄式 email
- 約 30-60 分鐘等 Oracle 審核帳號(他們慢)

**重要陷阱**:
- 「Free Tier」 ≠ 「Always Free」。Free Tier 是 30 天免費,Always Free 是永久免費。我們只用 Always Free shapes(`VM.Standard.A1.Flex` 或 `VM.Standard.E2.1.Micro`)。
- Always Free 在 Tokyo 經常缺貨,尤其 A1.Flex(ARM)。如果建 VM 跳「Out of capacity」,**換時間**(凌晨/週末)或**換 shape**(從 A1 換 E2.1.Micro)。

---

## 2. 申請 Oracle Cloud

1. 開 https://signup.oracle.com/
2. 填 email、姓名、國家(Taiwan)、密碼
3. 收 email 驗證信,點連結
4. 填地址、電話(會收簡訊驗證碼)
5. **Home Region 選 Japan East (Tokyo)** — 這是最重要的一步。Home Region 之後不能改。
   - 為什麼 Tokyo:離台灣近、能打 Binance、Always Free 額度也在這 region
6. 加信用卡(驗證用,Always Free 不會扣)
7. 帳號審核(15-60 分鐘),完成會收 email
8. 登入 https://cloud.oracle.com/

---

## 3. 建立 Always Free VM

### 3.1 進入 Console

登入後左上漢堡 → Compute → Instances → **Create Instance**。

### 3.2 設定欄位

| 欄位 | 填什麼 |
|---|---|
| Name | `crypto-agent`(隨便取) |
| Compartment | 預設那個就好 |
| Image | **Ubuntu 22.04(Minimal)** — 點 Change Image → Canonical Ubuntu 22.04 |
| Shape | 點 Change Shape → 進階展開 → **VM.Standard.A1.Flex**(ARM,推薦)或 **VM.Standard.E2.1.Micro**(x86,小但穩) |
| ARM (A1.Flex) 配置 | 1 OCPU + 6 GB RAM(都在 Always Free 額度內) |
| Networking | 預設新建 VCN 就好,記得勾「Assign a public IPv4 address」 |
| SSH keys | **Generate SSH key pair for me** → 點 Download private key + Download public key,**兩個都存起來,private 是 .key 副檔名,千萬不要遺失** |
| Boot volume | 預設 47-50GB,在 Always Free 範圍內 |

### 3.3 Create

按右下「Create」。

如果跳「Out of capacity」:換時間重試、或改 E2.1.Micro。

VM 建好後狀態變綠「Running」,記下右側 **Public IPv4 address**(例如 `140.238.x.x`)。

---

## 4. SSH 連到 VM

### 4.1 把 private key 放好

下載的 private key 假設叫 `ssh-key-2026-05-31.key`,放到 `C:\Users\riverkid\.ssh\oracle_crypto.key`(自己取個好記的名)。

設權限(Windows PowerShell):

```powershell
icacls "$env:USERPROFILE\.ssh\oracle_crypto.key" /inheritance:r
icacls "$env:USERPROFILE\.ssh\oracle_crypto.key" /grant:r "$env:USERNAME:R"
```

### 4.2 連線

PowerShell 或 Git Bash:

```bash
ssh -i ~/.ssh/oracle_crypto.key ubuntu@<your-public-ip>
```

第一次會問「Are you sure you want to continue?」打 `yes`。

連進去之後 prompt 應該變 `ubuntu@<hostname>:~$`,代表你在 VM 裡面了。

> 如果連不上:Oracle 預設 SSH port 22 是開的,但有時 ingress rule 沒設好。Console → 你的 VM → Subnet → Security List → 確認 0.0.0.0/0:22 TCP 是 Allow。

---

## 5. VM 初始化

在 VM 裡面(SSH session 內)跑:

```bash
sudo apt update && sudo apt upgrade -y

# 裝 Python 3.11
sudo apt install -y python3.11 python3.11-venv python3-pip git

python3.11 --version   # Should print Python 3.11.x
git --version
```

如果 `apt install python3.11` 找不到套件,加 deadsnakes PPA:

```bash
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv
```

### 設防火牆(只開 SSH)

```bash
sudo apt install -y ufw
sudo ufw allow OpenSSH
sudo ufw --force enable
sudo ufw status
```

### 設時區(讓 log 時間好看)

```bash
sudo timedatectl set-timezone Asia/Taipei
date
```

---

## 6. Clone repo + 設 .env

### 6.1 GitHub PAT(因為 repo 是 private)

1. https://github.com/settings/personal-access-tokens/new
2. Fine-grained personal access token
3. Name: `crypto-vm-readonly`
4. Resource owner: 你自己
5. Repository access: Only select repositories → 選 `crypto-ai-agent`
6. Permissions → Repository permissions → **Contents: Read** 就夠了
7. Generate → 複製 token(`github_pat_xxx`)

### 6.2 Clone

回 VM:

```bash
cd ~
git clone https://<your-pat>@github.com/riverkid12/crypto-ai-agent.git
cd crypto-ai-agent
```

### 6.3 建 venv + 裝套件

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

python -c "import binance, requests, responses; print('OK')"
pytest tests/ --tb=short -q
```

預期 116 passed。

### 6.4 設 .env

```bash
cp .env.example .env
nano .env
```

填入跟你本機 `.env` 一樣的值(URL、tokens、API keys)。Ctrl+O, Enter, Ctrl+X 存檔離開。

```bash
chmod 600 .env
```

### 6.5 第一次跑驗證

```bash
set -a; source .env; set +a
python -m executor.tick
```

預期 output:`[live tick] summary: {'triggered': 0, 'blocked': 0, 'api_errors': 0}`(因為目前沒 active signal)。

**如果這步成功 → 代表 Binance 從 Tokyo VM 打得到,問題解決。**

可以跑更完整測試:

```bash
python -m scripts.seed_signal --symbol SOLUSDT --size 30
python -m executor.tick
python -m scripts.status --no-exchange
```

Discord 也會收到 fill 卡片。

---

## 7. 設 systemd timer 每 5 分鐘跑一次

VM 上的 cron 用 systemd timer(比 crontab 現代、log 好看)。

### 7.1 建 service unit

```bash
sudo tee /etc/systemd/system/crypto-tick.service > /dev/null << 'UNITEOF'
[Unit]
Description=crypto-ai-agent tick
After=network.target

[Service]
Type=oneshot
User=ubuntu
WorkingDirectory=/home/ubuntu/crypto-ai-agent
EnvironmentFile=/home/ubuntu/crypto-ai-agent/.env
ExecStart=/home/ubuntu/crypto-ai-agent/venv/bin/python -m executor.tick
StandardOutput=journal
StandardError=journal
UNITEOF
```

### 7.2 建 timer unit

```bash
sudo tee /etc/systemd/system/crypto-tick.timer > /dev/null << 'UNITEOF'
[Unit]
Description=Run crypto-ai-agent tick every 5 minutes
Requires=crypto-tick.service

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
AccuracySec=10s
Persistent=true

[Install]
WantedBy=timers.target
UNITEOF
```

### 7.3 啟動

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now crypto-tick.timer

sudo systemctl status crypto-tick.timer
sudo systemctl list-timers | grep crypto-tick
```

`list-timers` 應該顯示下次觸發時間(2 分鐘後)。

### 7.4 看 log

```bash
# 即時看(類似 tail -f)
sudo journalctl -u crypto-tick.service -f

# 看最近 50 行
sudo journalctl -u crypto-tick.service -n 50

# 看今天的
sudo journalctl -u crypto-tick.service --since today
```

等個 5-10 分鐘,應該會看到一兩次 tick 跑過的 log,每次都印 `[live tick] summary: {...}`。

---

## 8. 關 GHA exec_tick cron

VM 跑 tick 之後 GHA 的 cron 就不需要了(留著兩邊都跑會打架)。但保留 `workflow_dispatch` 給之後 debug / manual seed 用。

### 8.1 改 exec_tick.yml(本機改完 push)

回**本機**(不是 VM):

```bash
cd C:\Projects\crypto-ai-agent
```

編輯 `.github/workflows/exec_tick.yml`,把 `schedule:` 那兩行刪掉,只留 `workflow_dispatch:`:

```yaml
on:
  workflow_dispatch:
    inputs:
      strategy:
        description: 'Strategy name (default: trend_majors)'
        required: false
        default: 'trend_majors'
```

### 8.2 Commit + push

```bash
git add .github/workflows/exec_tick.yml
git -c user.email=yihuang0903@gmail.com -c user.name=riverkid commit -m "chore(p1.6): disable exec_tick cron (Oracle VM took over)"
git push origin master
```

### 8.3 等 GHA UI 反映

5-10 分鐘後 Actions 頁面就不會再出現自動排程的 `exec_tick` runs。手動觸發還是能用。

---

## 9. 驗證遷移完成

### 9.1 從本機看 status

```bash
cd C:\Projects\crypto-ai-agent
source venv/Scripts/activate
set -a; source .env; set +a
python -m scripts.status
```

確認 positions / events 都正常,events log 裡能看到 VM 上跑的 tick 留下的紀錄。

### 9.2 從 VM 看 systemd log

```bash
sudo journalctl -u crypto-tick.service -n 20
```

應該看到每 5 分鐘一次的 tick run,沒有 error。

### 9.3 Discord 通知

如果 VM 有跑出新 signal 觸發,Discord 應該會收到對應卡片。

---

## 10. 維運紀律

### 10.1 系統更新(每月一次)

```bash
ssh -i ~/.ssh/oracle_crypto.key ubuntu@<your-public-ip>
sudo apt update && sudo apt upgrade -y
sudo reboot
```

### 10.2 程式碼更新

每次本機 push 新版到 master 後,SSH 進 VM:

```bash
cd ~/crypto-ai-agent
git pull
source venv/bin/activate
pip install -r requirements.txt
pytest tests/ --tb=short -q
# systemd 下一次 tick 自動跑新版,不用手動 restart
```

### 10.3 VM 自動關機防範

Oracle Always Free **不會**自動關機。但連續 7 天 CPU < 20% 也沒手動 reboot,Oracle 會發 email 警告。讓 tick 每 5 分鐘跑一次 Python 應該夠用,不會被回收。

### 10.4 緊急停止

從 VM:

```bash
sudo systemctl stop crypto-tick.timer
sudo systemctl disable crypto-tick.timer
```

或從本機改 Turso kill_switch:

```bash
python -c "
from db.client import Database
import os; from pathlib import Path
for line in Path('.env').read_text(encoding='utf-8').splitlines():
    if '=' in line and not line.startswith('#'):
        k, _, v = line.partition('='); os.environ.setdefault(k.strip(), v.strip())
db = Database(os.environ['DB_URL'], auth_token=os.environ['DB_AUTH_TOKEN'])
db.execute(\"UPDATE control SET value='true' WHERE key='kill_switch'\")
db.close()
print('kill_switch=true')
"
```

### 10.5 重啟服務(改 .env 之後要做)

```bash
sudo systemctl restart crypto-tick.timer
```

---

## 11. 疑難排解

| 症狀 | 原因 | 解 |
|---|---|---|
| `apt: command not found` | 不是 Ubuntu(可能挑到 Oracle Linux) | 重建 VM,Image 選 Ubuntu 22.04 |
| `python3.11: command not found` | PPA 沒裝 | 跑第 5 節 deadsnakes 那段 |
| `git clone` 跳 `Authentication failed` | PAT 過期或權限不對 | 重建 PAT,Contents: Read 權限 |
| `pip install` 卡很久 | VM 出口慢或套件源遠 | 等,或換 pip mirror |
| `python -m executor.tick` 還是 geo error | VM 不在 Tokyo region | console 看 VM 的 Availability Domain,應該是 `NRT-AD-1`;不是的話 VM 建錯區了,刪掉重建 |
| systemd timer 沒觸發 | timer 沒 enable 或 service 有 syntax error | `sudo systemctl status crypto-tick.timer` + `journalctl -u crypto-tick.service` |
| `journalctl` 看到 Permission denied | 沒 sudo 跑 | 加 `sudo` |
| Oracle Console 顯示「Reclaiming instance」 | VM 太閒被 Oracle 標記要回收 | 立刻 SSH 進去跑點東西、Console 重啟一次 |

---

## 12. 收工檢查清單

- [ ] Oracle VM 建好、Public IP 記下
- [ ] SSH 從本機連得進去
- [ ] VM 上裝好 Python 3.11、git、ufw
- [ ] Repo cloned 到 `~/crypto-ai-agent`
- [ ] `pytest tests/` 在 VM 上 116 passed
- [ ] `.env` 已填、權限 600
- [ ] `python -m executor.tick` 手動跑 OK,沒 geo error
- [ ] systemd timer enabled + active,`list-timers` 看到下次觸發
- [ ] `journalctl -u crypto-tick.service -n 20` 看到至少一次成功的 tick
- [ ] GHA exec_tick.yml 已移除 schedule(本機 push 完成)
- [ ] 本機跑 `python -m scripts.status` 看得到 VM 上的 events
- [ ] Discord 收得到 VM 觸發的通知卡片(如果有 fill/blocked 事件)

全部打勾 → 遷移完成,P1.6 結束。原本 P1 的 3 天觀察期計時器從這天開始重算(因為架構變了)。

接著:**continue observation period** 或 **直接開 P2 plan**(讓 Cowork-side Claude 真的出 signal)。
