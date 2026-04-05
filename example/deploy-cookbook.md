# QuantFree Deployment Cookbook

This cookbook provides copy-paste deployment recipes for running QuantFree on cloud servers.

It covers two production patterns:

1. **Research/Simulation only (recommended first step)**  
   - Linux cloud VM
   - `TRADING_MODE=sim`
   - Full backtest/screening/auto-trade simulation

2. **Live-trading architecture (recommended for real money)**  
   - Linux cloud VM for QuantFree backend
   - Separate macOS node for `broker_gateway` (evolving + Tonghuashun)
   - Backend calls macOS gateway via private network/VPN

---

## 0) Prerequisites

- A Linux VM (Ubuntu 22.04/24.04 recommended)
- A domain name (optional but recommended)
- Python 3.10+
- Git
- (Optional) Nginx + TLS certificates
- (Live mode only) a macOS machine with Tonghuashun + evolving stack

---

## 1) Quick Start: Linux Simulation Deployment

### 1.1 Install base packages

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git nginx
```

### 1.2 Clone and install backend

```bash
cd /opt
sudo git clone https://github.com/ZhengWG/quant_free.git
sudo chown -R "$USER":"$USER" /opt/quant_free
cd /opt/quant_free/server

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 1.3 Configure environment

```bash
cd /opt/quant_free/server
cp .env.example .env
```

Suggested simulation defaults in `.env`:

```env
DEBUG=False
HOST=0.0.0.0
PORT=3000
TRADING_MODE=sim
AUTO_START_BROKER_GATEWAY=0
```

Optional notifications:

```env
# Email report
EMAIL_ENABLED=1
EMAIL_SMTP_HOST=smtp.qq.com
EMAIL_SMTP_PORT=465
EMAIL_SENDER=your_email@example.com
EMAIL_AUTH_CODE=your_smtp_auth_code
EMAIL_RECEIVER=a@example.com,b@example.com

# SMS reminder (optional)
SMS_ENABLED=1
SMS_PROVIDER=webhook
SMS_RECEIVERS=13800138000,13900139000
SMS_WEBHOOK_URL=https://your-sms-gateway/send
SMS_WEBHOOK_TOKEN=your_token
```

### 1.4 Smoke test

```bash
cd /opt/quant_free/server
source .venv/bin/activate
python main.py
```

Check:

- `http://<SERVER_IP>:3000/health`
- `http://<SERVER_IP>:3000/docs`

Stop with `Ctrl+C` after verification.

---

## 2) Run as a systemd Service

Create service file:

```bash
sudo tee /etc/systemd/system/quantfree-server.service >/dev/null <<'EOF'
[Unit]
Description=QuantFree FastAPI Backend
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/quant_free/server
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/quant_free/server/.venv/bin/python main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable quantfree-server
sudo systemctl restart quantfree-server
sudo systemctl status quantfree-server --no-pager
```

Logs:

```bash
journalctl -u quantfree-server -f
```

---

## 3) Nginx Reverse Proxy (Recommended)

Create Nginx site config:

```bash
sudo tee /etc/nginx/sites-available/quantfree >/dev/null <<'EOF'
server {
    listen 80;
    server_name your.domain.com;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
```

Enable site:

```bash
sudo ln -sf /etc/nginx/sites-available/quantfree /etc/nginx/sites-enabled/quantfree
sudo nginx -t
sudo systemctl restart nginx
```

TLS (optional but strongly recommended):

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your.domain.com
```

---

## 4) Live Trading Architecture (Cloud + macOS)

> Important: `broker_gateway` requires **macOS** (Tonghuashun + evolving).  
> Do **not** expect full live trading to run on Linux-only cloud.

### 4.1 macOS node setup (gateway host)

On macOS:

```bash
git clone https://github.com/ZhengWG/quant_free.git
cd quant_free
git submodule update --init --recursive

cd broker_gateway
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Run gateway:

```bash
cd broker_gateway
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 7070
```

Health check:

```bash
curl http://127.0.0.1:7070/health
```

### 4.2 Cloud backend points to macOS gateway

On cloud backend `.env`:

```env
TRADING_MODE=live
BROKER_API_URL=http://<PRIVATE_MAC_IP>:7070
AUTO_START_BROKER_GATEWAY=0
```

Use private networking (WireGuard/Tailscale/VPN) instead of open internet exposure.

### 4.3 Validate live connectivity from cloud

```bash
curl http://<PRIVATE_MAC_IP>:7070/health
```

If healthy, restart backend:

```bash
sudo systemctl restart quantfree-server
```

---

## 5) Security Checklist (Must-do for production)

- Keep backend and gateway behind private network if possible.
- Restrict inbound ports with security groups/firewall.
- Use HTTPS if exposed publicly.
- Keep `DEBUG=False`.
- Rotate all secret values (`API keys`, `SMTP`, `SMS tokens`).
- Use reminder mode first (`SMS/Email`) before enabling full live automation.

---

## 6) Upgrade Procedure

```bash
cd /opt/quant_free
git pull

cd /opt/quant_free/server
source .venv/bin/activate
pip install -r requirements.txt

sudo systemctl restart quantfree-server
sudo systemctl status quantfree-server --no-pager
```

---

## 7) Troubleshooting

### Backend not starting

```bash
journalctl -u quantfree-server -n 200 --no-pager
```

### API unreachable

```bash
curl http://127.0.0.1:3000/health
sudo systemctl status nginx --no-pager
```

### Live order path failing

1. Check cloud backend can reach macOS gateway:
   ```bash
   curl http://<PRIVATE_MAC_IP>:7070/health
   ```
2. Check macOS Tonghuashun/evolving runtime status.
3. Check gateway logs for order errors.

---

## 8) Recommended Rollout Strategy

1. Deploy simulation-only backend first (`TRADING_MODE=sim`).
2. Verify backtest/screening/auto scheduler and reminders.
3. Add macOS gateway and test `BROKER_API_URL` connectivity.
4. Switch selected sessions to `execution_mode=live` gradually.

