# QuantFree 部署 Cookbook（中文）

本 Cookbook 提供可直接复制执行的 QuantFree 云端部署方案。

覆盖两种生产模式：

1. **仅研究/模拟（建议先上这个）**  
   - Linux 云主机
   - `TRADING_MODE=sim`
   - 支持回测、选股、自动交易模拟全流程

2. **实盘架构（真实资金建议）**  
   - Linux 云主机运行 QuantFree 后端
   - 独立 macOS 节点运行 `broker_gateway`（evolving + 同花顺）
   - 后端通过内网/VPN 调用 macOS 网关

---

## 0) 前置条件

- 一台 Linux 云主机（建议 Ubuntu 22.04/24.04）
- 域名（可选但推荐）
- Python 3.10+
- Git
- （可选）Nginx + TLS 证书
- （仅实盘）一台可用的 macOS 机器（同花顺 + evolving 环境）

---

## 1) 快速开始：Linux 模拟部署

### 1.1 安装基础依赖

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git nginx
```

### 1.2 拉代码并安装后端依赖

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

### 1.3 配置环境变量

```bash
cd /opt/quant_free/server
cp .env.example .env
```

`.env` 推荐模拟默认值：

```env
DEBUG=False
HOST=0.0.0.0
PORT=3000
TRADING_MODE=sim
AUTO_START_BROKER_GATEWAY=0
```

可选提醒配置：

```env
# 邮件日报
EMAIL_ENABLED=1
EMAIL_SMTP_HOST=smtp.qq.com
EMAIL_SMTP_PORT=465
EMAIL_SENDER=your_email@example.com
EMAIL_AUTH_CODE=your_smtp_auth_code
EMAIL_RECEIVER=a@example.com,b@example.com

# 短信提醒（可选）
SMS_ENABLED=1
SMS_PROVIDER=webhook
SMS_RECEIVERS=13800138000,13900139000
SMS_WEBHOOK_URL=https://your-sms-gateway/send
SMS_WEBHOOK_TOKEN=your_token
```

### 1.4 烟雾测试

```bash
cd /opt/quant_free/server
source .venv/bin/activate
python main.py
```

检查：

- `http://<服务器IP>:3000/health`
- `http://<服务器IP>:3000/docs`

验证后 `Ctrl+C` 停止。

---

## 2) 以 systemd 服务方式运行

创建服务文件：

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

启用并启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable quantfree-server
sudo systemctl restart quantfree-server
sudo systemctl status quantfree-server --no-pager
```

查看日志：

```bash
journalctl -u quantfree-server -f
```

---

## 3) Nginx 反向代理（推荐）

创建站点配置：

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

启用配置：

```bash
sudo ln -sf /etc/nginx/sites-available/quantfree /etc/nginx/sites-enabled/quantfree
sudo nginx -t
sudo systemctl restart nginx
```

HTTPS（可选但强烈建议）：

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your.domain.com
```

---

## 4) 实盘架构（云主机 + macOS）

> 重要：`broker_gateway` 依赖 **macOS**（同花顺 + evolving）。  
> 仅 Linux 云主机无法完整跑通同花顺实盘链路。

### 4.1 macOS 节点部署（网关机）

在 macOS 上执行：

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

启动网关：

```bash
cd broker_gateway
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 7070
```

健康检查：

```bash
curl http://127.0.0.1:7070/health
```

### 4.2 云端后端指向 macOS 网关

云端后端 `.env`：

```env
TRADING_MODE=live
BROKER_API_URL=http://<MAC内网IP>:7070
AUTO_START_BROKER_GATEWAY=0
```

建议用 WireGuard/Tailscale/VPN 内网，不要公网裸露网关端口。

### 4.3 云端验证网关连通

```bash
curl http://<MAC内网IP>:7070/health
```

若通过，重启后端：

```bash
sudo systemctl restart quantfree-server
```

---

## 5) 生产安全清单（必做）

- 后端与网关优先放在私网，避免公网直连
- 用安全组/防火墙限制入站端口
- 公网暴露时务必启用 HTTPS
- `DEBUG=False`
- 所有密钥定期轮换（AI、SMTP、SMS、券商网关鉴权）
- 建议先启用提醒模式（短信/邮件），再逐步打开实盘自动执行

---

## 6) 升级流程

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

## 7) 故障排查

### 后端启动失败

```bash
journalctl -u quantfree-server -n 200 --no-pager
```

### API 不可达

```bash
curl http://127.0.0.1:3000/health
sudo systemctl status nginx --no-pager
```

### 实盘下单链路异常

1. 云端检查是否能访问 macOS 网关：
   ```bash
   curl http://<MAC内网IP>:7070/health
   ```
2. 检查 macOS 同花顺/evolving 运行状态与权限（辅助功能、窗口焦点等）。
3. 查看网关日志定位具体委托失败原因。

---

## 8) 推荐上线顺序

1. 先上线模拟环境（`TRADING_MODE=sim`）
2. 验证回测、选股、调度、短信/邮件提醒
3. 接入 macOS 网关并验证 `BROKER_API_URL` 连通
4. 先小范围会话切换 `execution_mode=live`，逐步放量

