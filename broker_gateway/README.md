# 券商网关（macOS + evolving）

实现 QuantFree 约定的 HTTP 接口（`/order`、`/orders`、`/positions`、`/account`、`/health`），内部通过 [evolving](https://github.com/zetatez/evolving) 控制同花顺 Mac 版。**仅支持 macOS**。

## 依赖

- macOS，同花顺 Mac 版 2.3.1
- `cliclick`（[安装说明](scripts/install_cliclick_macos15.sh) 含 macOS 15 从源码安装）
- Python 3.8+，`pip install -r requirements.txt`
- 配置 `~/.config/evolving/config.xml`（同花顺账号、券商代码、资金账号等）

evolving 通过 **Git Submodule** 集成在 `evolving_repo/`，克隆主仓库时请执行 `git submodule update --init --recursive`。财通等券商通过 `ascmds_adapter` 在运行时注入，无需改子模块。

## 配置

```bash
cp .env.example .env
# 可选：修改 GATEWAY_PORT；不设 EVOLVING_PATH 时使用 submodule
```

## 运行

**默认**：在 `server/.env` 中配置 `TRADING_MODE=live`、`BROKER_API_URL=http://127.0.0.1:7070`、`AUTO_START_BROKER_GATEWAY=1` 后，启动后端（`python server/main.py`）时会**自动拉起本网关**，无需手动运行。

**手动启动**（调试或未开自动启动时）：
```bash
cd broker_gateway
uvicorn main:app --host 0.0.0.0 --port 7070
```
健康检查：`curl http://127.0.0.1:7070/health`。
