/**
 * 行情监控视图
 */

import * as vscode from 'vscode';
import { ApiClient } from '../services/apiClient';
import { WebSocketClient } from '../services/websocketClient';
import { StorageService } from '../services/storage';
import { Stock, KLineData } from '../types/market';

export class MarketDataView {
    private context: vscode.ExtensionContext;
    private apiClient: ApiClient;
    private wsClient: WebSocketClient;
    private storageService: StorageService;
    private view: StockTreeDataProvider;
    private refreshTimer: NodeJS.Timeout | null = null;

    constructor(
        context: vscode.ExtensionContext,
        apiClient: ApiClient,
        wsClient: WebSocketClient,
        storageService: StorageService
    ) {
        this.context = context;
        this.apiClient = apiClient;
        this.wsClient = wsClient;
        this.storageService = storageService;
        this.view = new StockTreeDataProvider(apiClient, storageService);

        // 注册视图
        const treeView = vscode.window.createTreeView('quantFree.marketData', {
            treeDataProvider: this.view,
            showCollapseAll: true
        });

        context.subscriptions.push(treeView);

        // 订阅WebSocket实时数据
        this.wsClient.subscribe('market_data', (data: Stock) => {
            this.view.updateStock(data);
        });

        // 启动定时刷新
        this.startRefresh();
    }

    async addStock(code: string): Promise<void> {
        const trimmedCode = code.trim();
        if (!trimmedCode) {
            vscode.window.showWarningMessage('股票代码不能为空');
            return;
        }

        const stocks = await this.storageService.getStocks();
        if (stocks.includes(trimmedCode)) {
            vscode.window.showInformationMessage(`${trimmedCode} 已在自选股列表中`);
            return;
        }

        stocks.push(trimmedCode);
        await this.storageService.saveStocks(stocks);
        vscode.window.showInformationMessage(`已添加自选股: ${trimmedCode}`);
        this.view.refresh();
        this.wsClient.subscribeMarketData([trimmedCode]);
    }

    async removeSelectedStock(): Promise<void> {
        const stocks = await this.storageService.getStocks();
        if (stocks.length === 0) {
            vscode.window.showInformationMessage('自选股列表为空');
            return;
        }

        const selected = await vscode.window.showQuickPick(stocks, {
            placeHolder: '选择要删除的股票代码',
            canPickMany: false,
        });

        if (selected) {
            const idx = stocks.indexOf(selected);
            if (idx !== -1) {
                stocks.splice(idx, 1);
                await this.storageService.saveStocks(stocks);
                this.view.refresh();
                vscode.window.showInformationMessage(`已删除 ${selected}`);
            }
        }
    }

    async openChart(code: string): Promise<void> {
        try {
            vscode.window.withProgress(
                { location: vscode.ProgressLocation.Notification, title: `正在加载 ${code} K线数据...` },
                async () => {
                    const klineData = await this.apiClient.getKLineData(code);
                    if (!klineData || klineData.length === 0) {
                        vscode.window.showWarningMessage(`暂无 ${code} 的K线数据`);
                        return;
                    }
                    this.showKLineWebView(code, klineData);
                }
            );
        } catch (error) {
            vscode.window.showErrorMessage(`获取K线数据失败: ${error}`);
        }
    }

    private showKLineWebView(code: string, data: KLineData[]): void {
        const panel = vscode.window.createWebviewPanel(
            'quantFreeKLine',
            `K线图 - ${code}`,
            vscode.ViewColumn.One,
            { enableScripts: true }
        );
        panel.webview.html = this.getKLineHtml(code, data);
    }

    private getKLineHtml(code: string, data: KLineData[]): string {
        const chartData = JSON.stringify(data);
        return /*html*/`<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>K线图 - ${code}</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: var(--vscode-editor-background, #1e1e1e);
    color: var(--vscode-editor-foreground, #d4d4d4);
    font-family: var(--vscode-font-family, 'Segoe UI', sans-serif);
    overflow: hidden;
  }
  .header {
    padding: 12px 20px;
    display: flex;
    align-items: center;
    gap: 16px;
    border-bottom: 1px solid var(--vscode-panel-border, #333);
  }
  .header h2 { font-size: 16px; font-weight: 600; }
  .header .info {
    font-size: 12px;
    opacity: 0.7;
  }
  .tabs {
    display: flex;
    gap: 2px;
    padding: 8px 20px 0;
  }
  .tab {
    padding: 6px 16px;
    font-size: 12px;
    cursor: pointer;
    border: 1px solid transparent;
    border-bottom: none;
    border-radius: 4px 4px 0 0;
    background: transparent;
    color: var(--vscode-editor-foreground, #d4d4d4);
    opacity: 0.6;
  }
  .tab:hover { opacity: 0.8; }
  .tab.active {
    opacity: 1;
    background: var(--vscode-editor-background, #1e1e1e);
    border-color: var(--vscode-panel-border, #333);
  }
  .chart-container {
    padding: 12px 20px;
    position: relative;
    width: 100%;
  }
  canvas { display: block; }
  .tooltip {
    position: absolute;
    display: none;
    background: var(--vscode-editorWidget-background, #252526);
    border: 1px solid var(--vscode-editorWidget-border, #454545);
    border-radius: 4px;
    padding: 8px 12px;
    font-size: 12px;
    pointer-events: none;
    z-index: 100;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    line-height: 1.6;
    white-space: nowrap;
  }
  .tooltip .up { color: #ef5350; }
  .tooltip .down { color: #26a69a; }
</style>
</head>
<body>
<div class="header">
  <h2>${code} K线图</h2>
  <span class="info" id="dataInfo"></span>
</div>
<div class="tabs">
  <div class="tab active" data-type="close">收盘价</div>
  <div class="tab" data-type="candlestick">K线</div>
  <div class="tab" data-type="volume">成交量</div>
</div>
<div class="chart-container">
  <canvas id="chart"></canvas>
  <div class="tooltip" id="tooltip"></div>
</div>
<script>
const rawData = ${chartData};
const data = rawData.map(d => ({
  date: d.date,
  open: +d.open,
  high: +d.high,
  low: +d.low,
  close: +d.close,
  volume: +d.volume
}));

const canvas = document.getElementById('chart');
const ctx = canvas.getContext('2d');
const tooltip = document.getElementById('tooltip');
const info = document.getElementById('dataInfo');

info.textContent = data.length + ' 条数据 | ' + data[0].date + ' ~ ' + data[data.length - 1].date;

let currentType = 'close';
const dpr = window.devicePixelRatio || 1;
const PADDING = { top: 30, right: 60, bottom: 50, left: 20 };

function resize() {
  const w = window.innerWidth - 40;
  const h = window.innerHeight - 130;
  canvas.width = w * dpr;
  canvas.height = h * dpr;
  canvas.style.width = w + 'px';
  canvas.style.height = h + 'px';
  ctx.scale(dpr, dpr);
  draw();
}

function getColor(val) {
  return val >= 0 ? '#ef5350' : '#26a69a';
}

function formatNum(n) {
  if (n >= 1e8) return (n / 1e8).toFixed(2) + '亿';
  if (n >= 1e4) return (n / 1e4).toFixed(1) + '万';
  return n.toFixed(2);
}

function drawGrid(w, h, minY, maxY, steps) {
  ctx.strokeStyle = 'rgba(128,128,128,0.15)';
  ctx.lineWidth = 1;
  ctx.setLineDash([4, 4]);
  ctx.fillStyle = 'rgba(128,128,128,0.6)';
  ctx.font = '11px monospace';
  ctx.textAlign = 'right';
  for (let i = 0; i <= steps; i++) {
    const y = PADDING.top + (h - PADDING.top - PADDING.bottom) * i / steps;
    const val = maxY - (maxY - minY) * i / steps;
    ctx.beginPath();
    ctx.moveTo(PADDING.left, y);
    ctx.lineTo(w - PADDING.right, y);
    ctx.stroke();
    ctx.fillText(formatNum(val), w - 8, y + 4);
  }
  ctx.setLineDash([]);
}

function drawXLabels(w, h) {
  ctx.fillStyle = 'rgba(128,128,128,0.6)';
  ctx.font = '10px monospace';
  ctx.textAlign = 'center';
  const step = Math.max(1, Math.floor(data.length / 8));
  for (let i = 0; i < data.length; i += step) {
    const x = PADDING.left + (w - PADDING.left - PADDING.right) * i / (data.length - 1);
    const label = data[i].date.slice(5);
    ctx.fillText(label, x, h - PADDING.bottom + 16);
  }
}

function drawCloseChart(w, h) {
  const closes = data.map(d => d.close);
  const minP = Math.min(...closes) * 0.998;
  const maxP = Math.max(...closes) * 1.002;
  const chartW = w - PADDING.left - PADDING.right;
  const chartH = h - PADDING.top - PADDING.bottom;

  drawGrid(w, h, minP, maxP, 6);
  drawXLabels(w, h);

  // 渐变填充
  const grad = ctx.createLinearGradient(0, PADDING.top, 0, PADDING.top + chartH);
  grad.addColorStop(0, 'rgba(66,165,245,0.3)');
  grad.addColorStop(1, 'rgba(66,165,245,0.02)');

  ctx.beginPath();
  for (let i = 0; i < data.length; i++) {
    const x = PADDING.left + chartW * i / (data.length - 1);
    const y = PADDING.top + chartH * (1 - (closes[i] - minP) / (maxP - minP));
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  // 填充
  ctx.lineTo(PADDING.left + chartW, PADDING.top + chartH);
  ctx.lineTo(PADDING.left, PADDING.top + chartH);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  // 折线
  ctx.beginPath();
  for (let i = 0; i < data.length; i++) {
    const x = PADDING.left + chartW * i / (data.length - 1);
    const y = PADDING.top + chartH * (1 - (closes[i] - minP) / (maxP - minP));
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.strokeStyle = '#42a5f5';
  ctx.lineWidth = 2;
  ctx.stroke();
}

function drawCandlestick(w, h) {
  const allPrices = data.flatMap(d => [d.high, d.low]);
  const minP = Math.min(...allPrices) * 0.998;
  const maxP = Math.max(...allPrices) * 1.002;
  const chartW = w - PADDING.left - PADDING.right;
  const chartH = h - PADDING.top - PADDING.bottom;
  const barW = Math.max(1, chartW / data.length * 0.7);

  drawGrid(w, h, minP, maxP, 6);
  drawXLabels(w, h);

  for (let i = 0; i < data.length; i++) {
    const d = data[i];
    const x = PADDING.left + chartW * i / (data.length - 1);
    const yOpen = PADDING.top + chartH * (1 - (d.open - minP) / (maxP - minP));
    const yClose = PADDING.top + chartH * (1 - (d.close - minP) / (maxP - minP));
    const yHigh = PADDING.top + chartH * (1 - (d.high - minP) / (maxP - minP));
    const yLow = PADDING.top + chartH * (1 - (d.low - minP) / (maxP - minP));
    const isUp = d.close >= d.open;
    const color = isUp ? '#ef5350' : '#26a69a';

    // 上下影线
    ctx.strokeStyle = color;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, yHigh);
    ctx.lineTo(x, yLow);
    ctx.stroke();

    // 实体
    const bodyTop = Math.min(yOpen, yClose);
    const bodyH = Math.max(Math.abs(yOpen - yClose), 1);
    ctx.fillStyle = isUp ? color : color;
    if (isUp) {
      ctx.fillRect(x - barW / 2, bodyTop, barW, bodyH);
    } else {
      ctx.fillRect(x - barW / 2, bodyTop, barW, bodyH);
    }
  }
}

function drawVolumeChart(w, h) {
  const vols = data.map(d => d.volume);
  const maxV = Math.max(...vols) * 1.1;
  const chartW = w - PADDING.left - PADDING.right;
  const chartH = h - PADDING.top - PADDING.bottom;
  const barW = Math.max(1, chartW / data.length * 0.7);

  drawGrid(w, h, 0, maxV, 5);
  drawXLabels(w, h);

  for (let i = 0; i < data.length; i++) {
    const d = data[i];
    const x = PADDING.left + chartW * i / (data.length - 1);
    const barH = chartH * (d.volume / maxV);
    const isUp = d.close >= d.open;
    ctx.fillStyle = isUp ? 'rgba(239,83,80,0.7)' : 'rgba(38,166,154,0.7)';
    ctx.fillRect(x - barW / 2, PADDING.top + chartH - barH, barW, barH);
  }
}

function draw() {
  const w = canvas.width / dpr;
  const h = canvas.height / dpr;
  ctx.clearRect(0, 0, w, h);
  if (currentType === 'close') drawCloseChart(w, h);
  else if (currentType === 'candlestick') drawCandlestick(w, h);
  else if (currentType === 'volume') drawVolumeChart(w, h);
}

// Tab 切换
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    currentType = tab.dataset.type;
    draw();
  });
});

// Tooltip
canvas.addEventListener('mousemove', (e) => {
  const rect = canvas.getBoundingClientRect();
  const mx = e.clientX - rect.left;
  const w = rect.width;
  const chartW = w - PADDING.left - PADDING.right;
  const idx = Math.round((mx - PADDING.left) / chartW * (data.length - 1));
  if (idx < 0 || idx >= data.length) { tooltip.style.display = 'none'; return; }
  const d = data[idx];
  const change = d.close - d.open;
  const changePct = ((change / d.open) * 100).toFixed(2);
  const cls = change >= 0 ? 'up' : 'down';
  tooltip.innerHTML =
    '<b>' + d.date + '</b><br>' +
    '开盘: ' + d.open.toFixed(2) + '<br>' +
    '最高: ' + d.high.toFixed(2) + '<br>' +
    '最低: ' + d.low.toFixed(2) + '<br>' +
    '收盘: <span class="' + cls + '">' + d.close.toFixed(2) + '</span><br>' +
    '涨跌: <span class="' + cls + '">' + (change >= 0 ? '+' : '') + change.toFixed(2) + ' (' + (change >= 0 ? '+' : '') + changePct + '%)</span><br>' +
    '成交量: ' + formatNum(d.volume);
  tooltip.style.display = 'block';
  const tx = e.clientX - rect.left + 20;
  const ty = e.clientY - rect.top - 10;
  tooltip.style.left = (tx + tooltip.offsetWidth > w ? tx - tooltip.offsetWidth - 30 : tx) + 'px';
  tooltip.style.top = Math.max(0, ty) + 'px';
});

canvas.addEventListener('mouseleave', () => { tooltip.style.display = 'none'; });

window.addEventListener('resize', () => { ctx.setTransform(1, 0, 0, 1, 0, 0); resize(); });
resize();
</script>
</body>
</html>`;
    }

    private startRefresh(): void {
        const config = vscode.workspace.getConfiguration('quantFree');
        const interval = config.get<number>('refreshInterval', 5000);

        this.refreshTimer = setInterval(async () => {
            await this.view.refresh();
        }, interval);
    }

    dispose(): void {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
        }
    }
}

class StockItem extends vscode.TreeItem {
    constructor(
        label: string,
        description: string,
        tooltip: string,
        collapsibleState: vscode.TreeItemCollapsibleState = vscode.TreeItemCollapsibleState.None,
        iconPath?: vscode.ThemeIcon
    ) {
        super(label, collapsibleState);
        this.description = description;
        this.tooltip = tooltip;
        if (iconPath) {
            this.iconPath = iconPath;
        }
    }

    static fromStock(stock: Stock): StockItem {
        const priceStr = `¥${stock.price.toFixed(2)}`;
        const changeStr = `${stock.changePercent >= 0 ? '+' : ''}${stock.changePercent.toFixed(2)}%`;
        const icon = stock.changePercent > 0
            ? new vscode.ThemeIcon('arrow-up', new vscode.ThemeColor('charts.red'))
            : stock.changePercent < 0
                ? new vscode.ThemeIcon('arrow-down', new vscode.ThemeColor('charts.green'))
                : new vscode.ThemeIcon('dash');
        return new StockItem(
            `${stock.name} (${stock.code})`,
            `${priceStr}  ${changeStr}`,
            `${stock.code} ${stock.name}\n价格: ${priceStr}\n涨跌: ${changeStr}\n最高: ¥${stock.high?.toFixed(2) ?? '-'}\n最低: ¥${stock.low?.toFixed(2) ?? '-'}\n成交量: ${stock.volume ?? '-'}`,
            vscode.TreeItemCollapsibleState.None,
            icon
        );
    }

    static placeholder(code: string): StockItem {
        return new StockItem(
            code,
            '等待数据...',
            `${code} - 等待行情数据（请确认后端服务已启动）`,
            vscode.TreeItemCollapsibleState.None,
            new vscode.ThemeIcon('loading~spin')
        );
    }

    static error(message: string): StockItem {
        return new StockItem(
            '数据加载失败',
            message,
            `行情数据加载失败: ${message}\n请检查后端服务是否启动 (python main.py)`,
            vscode.TreeItemCollapsibleState.None,
            new vscode.ThemeIcon('warning', new vscode.ThemeColor('errorForeground'))
        );
    }
}

class StockTreeDataProvider implements vscode.TreeDataProvider<StockItem> {
    private _onDidChangeTreeData: vscode.EventEmitter<StockItem | undefined | null | void> = new vscode.EventEmitter<StockItem | undefined | null | void>();
    readonly onDidChangeTreeData: vscode.Event<StockItem | undefined | null | void> = this._onDidChangeTreeData.event;

    private stocks: Map<string, Stock> = new Map();

    constructor(
        private apiClient: ApiClient,
        private storageService: StorageService
    ) {}

    getTreeItem(element: StockItem): vscode.TreeItem {
        return element;
    }

    async getChildren(element?: StockItem): Promise<StockItem[]> {
        const codes = await this.storageService.getStocks();
        if (codes.length === 0) {
            return [];
        }

        try {
            const stocks = await this.apiClient.getRealTimeData(codes);
            if (stocks.length === 0) {
                return codes.map(code => StockItem.placeholder(code));
            }
            stocks.forEach(stock => {
                this.stocks.set(stock.code, stock);
            });

            return stocks.map(stock => StockItem.fromStock(stock));
        } catch (error: any) {
            console.error('Failed to get market data:', error);
            const errMsg = error.message?.includes('ECONNREFUSED')
                ? '后端服务未启动'
                : (error.message || '未知错误');
            return [
                StockItem.error(errMsg),
                ...codes.map(code => StockItem.placeholder(code))
            ];
        }
    }

    updateStock(stock: Stock): void {
        this.stocks.set(stock.code, stock);
        this._onDidChangeTreeData.fire();
    }

    refresh(): void {
        this._onDidChangeTreeData.fire();
    }
}

