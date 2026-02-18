/**
 * 策略推荐视图
 */

import * as vscode from 'vscode';
import { ApiClient } from '../services/apiClient';
import { Strategy, BacktestResult } from '../types/strategy';

class StrategyItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly description: string,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState = vscode.TreeItemCollapsibleState.None,
        public readonly iconPath?: vscode.ThemeIcon
    ) {
        super(label, collapsibleState);
        this.tooltip = `${label}: ${description}`;
        if (iconPath) {
            this.iconPath = iconPath;
        }
    }
}

class StrategyTreeDataProvider implements vscode.TreeDataProvider<StrategyItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<StrategyItem | undefined | null | void>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

    private currentStrategy: Strategy | null = null;

    getTreeItem(element: StrategyItem): vscode.TreeItem {
        return element;
    }

    async getChildren(element?: StrategyItem): Promise<StrategyItem[]> {
        if (!this.currentStrategy) {
            return [];
        }

        const s = this.currentStrategy;
        const actionIcon = s.action === 'BUY'
            ? new vscode.ThemeIcon('arrow-up', new vscode.ThemeColor('charts.green'))
            : s.action === 'SELL'
                ? new vscode.ThemeIcon('arrow-down', new vscode.ThemeColor('charts.red'))
                : new vscode.ThemeIcon('dash', new vscode.ThemeColor('charts.yellow'));

        const items: StrategyItem[] = [
            new StrategyItem(`${s.stockName}`, `${s.stockCode}`, vscode.TreeItemCollapsibleState.None, new vscode.ThemeIcon('graph')),
            new StrategyItem('建议', s.action, vscode.TreeItemCollapsibleState.None, actionIcon),
            new StrategyItem('置信度', `${(s.confidence * 100).toFixed(1)}%`, vscode.TreeItemCollapsibleState.None, new vscode.ThemeIcon('dashboard')),
            new StrategyItem('风险等级', s.riskLevel, vscode.TreeItemCollapsibleState.None, new vscode.ThemeIcon('warning')),
        ];

        if (s.targetPrice) {
            items.push(new StrategyItem('目标价', `¥${s.targetPrice.toFixed(2)}`, vscode.TreeItemCollapsibleState.None, new vscode.ThemeIcon('target')));
        }
        if (s.stopLoss) {
            items.push(new StrategyItem('止损价', `¥${s.stopLoss.toFixed(2)}`, vscode.TreeItemCollapsibleState.None, new vscode.ThemeIcon('shield')));
        }
        items.push(new StrategyItem('持仓周期', s.timeHorizon, vscode.TreeItemCollapsibleState.None, new vscode.ThemeIcon('clock')));
        items.push(new StrategyItem('AI模型', s.aiModel || 'deepseek', vscode.TreeItemCollapsibleState.None, new vscode.ThemeIcon('hubot')));

        return items;
    }

    updateStrategy(strategy: Strategy): void {
        this.currentStrategy = strategy;
        this._onDidChangeTreeData.fire();
    }

    clear(): void {
        this.currentStrategy = null;
        this._onDidChangeTreeData.fire();
    }
}

export class StrategyView {
    private context: vscode.ExtensionContext;
    private apiClient: ApiClient;
    private outputChannel: vscode.OutputChannel;
    private treeProvider: StrategyTreeDataProvider;

    constructor(context: vscode.ExtensionContext, apiClient: ApiClient) {
        this.context = context;
        this.apiClient = apiClient;
        this.outputChannel = vscode.window.createOutputChannel('QuantFree Strategy');
        context.subscriptions.push(this.outputChannel);

        this.treeProvider = new StrategyTreeDataProvider();
        const treeView = vscode.window.createTreeView('quantFree.strategy', {
            treeDataProvider: this.treeProvider,
            showCollapseAll: false
        });
        context.subscriptions.push(treeView);
    }

    async generateStrategy(code: string): Promise<void> {
        this.outputChannel.show();
        this.outputChannel.appendLine(`正在为 ${code} 生成策略推荐...`);

        try {
            const strategy = await this.apiClient.generateStrategy({
                stockCode: code
            });

            // 更新侧边栏视图
            this.treeProvider.updateStrategy(strategy);

            this.outputChannel.appendLine('\n=== 策略推荐 ===');
            this.outputChannel.appendLine(`股票：${strategy.stockName} (${strategy.stockCode})`);
            this.outputChannel.appendLine(`建议：${strategy.action}`);
            if (strategy.targetPrice) {
                this.outputChannel.appendLine(`目标价：¥${strategy.targetPrice.toFixed(2)}`);
            }
            if (strategy.stopLoss) {
                this.outputChannel.appendLine(`止损价：¥${strategy.stopLoss.toFixed(2)}`);
            }
            this.outputChannel.appendLine(`置信度：${(strategy.confidence * 100).toFixed(1)}%`);
            this.outputChannel.appendLine(`风险等级：${strategy.riskLevel}`);
            this.outputChannel.appendLine(`持仓周期：${strategy.timeHorizon}`);
            this.outputChannel.appendLine(`\n策略理由：\n${strategy.reasoning}`);

            vscode.window.showInformationMessage(`策略生成成功！建议：${strategy.action}`);
        } catch (error: any) {
            const message = error.response?.data?.detail || error.message || '生成策略失败';
            this.outputChannel.appendLine(`\n错误：${message}`);
            vscode.window.showErrorMessage(`生成策略失败：${message}`);
        }
    }

    async runBacktest(code: string): Promise<void> {
        // 选择策略
        const strategyPick = await vscode.window.showQuickPick(
            [
                { label: 'MA均线交叉', value: 'ma_cross', description: '双均线金叉死叉策略' },
                { label: 'MACD', value: 'macd', description: 'MACD指标策略' },
                { label: 'KDJ', value: 'kdj', description: 'KDJ随机指标策略' }
            ],
            { placeHolder: '请选择回测策略' }
        );
        if (!strategyPick) { return; }

        // 输入日期范围
        const startDate = await vscode.window.showInputBox({
            prompt: '请输入回测开始日期',
            placeHolder: 'YYYY-MM-DD',
            value: '2024-01-01',
            validateInput: (v) => /^\d{4}-\d{2}-\d{2}$/.test(v) ? null : '请输入正确的日期格式 YYYY-MM-DD'
        });
        if (!startDate) { return; }

        const endDate = await vscode.window.showInputBox({
            prompt: '请输入回测结束日期',
            placeHolder: 'YYYY-MM-DD',
            value: '2024-12-31',
            validateInput: (v) => /^\d{4}-\d{2}-\d{2}$/.test(v) ? null : '请输入正确的日期格式 YYYY-MM-DD'
        });
        if (!endDate) { return; }

        this.outputChannel.show();
        this.outputChannel.appendLine(`\n正在回测 ${code} [${strategyPick.value}] ${startDate} ~ ${endDate} ...`);

        try {
            const result = await this.apiClient.runBacktest({
                stockCode: code,
                strategy: strategyPick.value,
                startDate,
                endDate
            });

            if (!result) {
                this.outputChannel.appendLine(`⚠ ${code} 暂无可用的K线数据，跳过回测`);
                vscode.window.showWarningMessage(`${code} 暂无可用的K线数据，无法回测`);
                return;
            }

            this.outputChannel.appendLine('\n========== 回测结果 ==========');
            this.outputChannel.appendLine(`股票代码：${result.stockCode}`);
            this.outputChannel.appendLine(`策略：${result.strategy}`);
            this.outputChannel.appendLine(`回测区间：${result.startDate} ~ ${result.endDate}`);
            this.outputChannel.appendLine('------------------------------');
            this.outputChannel.appendLine(`初始资金：¥${result.initialCapital.toFixed(2)}`);
            this.outputChannel.appendLine(`最终资金：¥${result.finalCapital.toFixed(2)}`);
            this.outputChannel.appendLine(`总收益：¥${result.totalReturn.toFixed(2)}`);
            this.outputChannel.appendLine(`收益率：${result.totalReturnPercent.toFixed(2)}%`);
            this.outputChannel.appendLine(`最大回撤：${result.maxDrawdown.toFixed(2)}%`);
            this.outputChannel.appendLine(`夏普比率：${result.sharpeRatio.toFixed(4)}`);
            this.outputChannel.appendLine(`胜率：${result.winRate.toFixed(2)}%`);
            this.outputChannel.appendLine(`交易次数：${result.totalTrades}`);

            if (result.trades.length > 0) {
                this.outputChannel.appendLine('\n---------- 交易明细 ----------');
                this.outputChannel.appendLine(
                    '日期'.padEnd(14) + '操作'.padEnd(6) + '价格'.padEnd(12) + '数量'.padEnd(10) + '盈亏'
                );
                for (const t of result.trades) {
                    const profitStr = t.profit != null ? `¥${t.profit.toFixed(2)}` : '-';
                    this.outputChannel.appendLine(
                        t.date.padEnd(14) + t.action.padEnd(6) + `¥${t.price.toFixed(2)}`.padEnd(12) + String(t.quantity).padEnd(10) + profitStr
                    );
                }
            }
            this.outputChannel.appendLine('==============================\n');

            vscode.window.showInformationMessage(`回测完成！收益率：${result.totalReturnPercent.toFixed(2)}%`);
            this.showBacktestWebView(result);
        } catch (error: any) {
            const message = error.response?.data?.detail || error.message || '回测失败';
            this.outputChannel.appendLine(`\n错误：${message}`);
            vscode.window.showErrorMessage(`回测失败：${message}`);
        }
    }

    private showBacktestWebView(result: BacktestResult): void {
        const panel = vscode.window.createWebviewPanel(
            'quantFreeBacktest',
            `回测结果 - ${result.stockCode} [${result.strategy}]`,
            vscode.ViewColumn.One,
            { enableScripts: true }
        );
        panel.webview.html = this.getBacktestHtml(result);
    }

    private getBacktestHtml(result: BacktestResult): string {
        const r = result;

        // Compute equity points from trades
        const equityPoints: Array<{date: string; value: number; action: string; profit: number | null}> = [];
        let equity = r.initialCapital;
        equityPoints.push({ date: r.startDate, value: r.initialCapital, action: '', profit: null });
        for (const t of r.trades) {
            if (t.action === 'SELL' && t.profit != null) {
                equity += t.profit;
            }
            equityPoints.push({ date: t.date, value: equity, action: t.action, profit: t.profit ?? null });
        }
        const lastPt = equityPoints[equityPoints.length - 1];
        if (lastPt.date !== r.endDate || Math.abs(lastPt.value - r.finalCapital) > 0.01) {
            equityPoints.push({ date: r.endDate, value: r.finalCapital, action: '', profit: null });
        }
        const pointsJson = JSON.stringify(equityPoints);

        // Color helper (A-share: positive=red, negative=green)
        const valColor = (v: number) => v >= 0 ? '#ef5350' : '#26a69a';

        // Build metrics cards HTML
        const metrics = [
            { label: '收益率', value: `${r.totalReturnPercent >= 0 ? '+' : ''}${r.totalReturnPercent.toFixed(2)}%`, color: valColor(r.totalReturnPercent) },
            { label: '最大回撤', value: `-${r.maxDrawdown.toFixed(2)}%`, color: '#26a69a' },
            { label: '夏普比率', value: r.sharpeRatio.toFixed(2), color: valColor(r.sharpeRatio) },
            { label: '胜率', value: `${r.winRate.toFixed(2)}%`, color: '' },
            { label: '初始资金', value: `¥${r.initialCapital.toFixed(2)}`, color: '' },
            { label: '最终资金', value: `¥${r.finalCapital.toFixed(2)}`, color: valColor(r.finalCapital - r.initialCapital) },
            { label: '总收益', value: `${r.totalReturn >= 0 ? '+' : ''}¥${r.totalReturn.toFixed(2)}`, color: valColor(r.totalReturn) },
            { label: '交易次数', value: `${r.totalTrades}`, color: '' },
        ];
        const cardsHtml = metrics.map(m => {
            const s = m.color ? ` style="color:${m.color}"` : '';
            return `<div class="card"><div class="card-label">${m.label}</div><div class="card-value"${s}>${m.value}</div></div>`;
        }).join('\n          ');

        // Build trade rows HTML
        const tradeRowsHtml = r.trades.map(t => {
            const ac = t.action === 'BUY' ? '#26a69a' : '#ef5350';
            const al = t.action === 'BUY' ? '买入' : '卖出';
            const ps = t.profit != null
                ? `<span style="color:${valColor(t.profit)}">${t.profit >= 0 ? '+' : ''}${t.profit.toFixed(2)}</span>`
                : '-';
            return `<tr><td>${t.date}</td><td style="color:${ac};font-weight:600">${al}</td><td>¥${t.price.toFixed(2)}</td><td>${t.quantity}</td><td>${ps}</td></tr>`;
        }).join('\n');

        return /*html*/`<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>回测结果 - ${r.stockCode}</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: var(--vscode-editor-background, #1e1e1e);
    color: var(--vscode-editor-foreground, #d4d4d4);
    font-family: var(--vscode-font-family, 'Segoe UI', sans-serif);
    overflow-x: hidden;
  }
  .header {
    padding: 12px 20px;
    display: flex;
    align-items: center;
    gap: 16px;
    border-bottom: 1px solid var(--vscode-panel-border, #333);
  }
  .header h2 { font-size: 16px; font-weight: 600; }
  .header .info { font-size: 12px; opacity: 0.7; }
  .metrics {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    padding: 16px 20px;
  }
  .card {
    background: var(--vscode-editorWidget-background, #252526);
    border: 1px solid var(--vscode-panel-border, #333);
    border-radius: 6px;
    padding: 12px 16px;
  }
  .card-label { font-size: 11px; opacity: 0.6; margin-bottom: 4px; }
  .card-value { font-size: 18px; font-weight: 600; font-family: monospace; }
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
  .table-container {
    padding: 0 20px 20px;
    max-height: calc(100vh - 280px);
    overflow-y: auto;
  }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td {
    padding: 8px 12px;
    text-align: left;
    border-bottom: 1px solid var(--vscode-panel-border, #333);
  }
  th {
    font-weight: 600;
    opacity: 0.7;
    font-size: 11px;
    text-transform: uppercase;
    position: sticky;
    top: 0;
    background: var(--vscode-editor-background, #1e1e1e);
  }
  td { font-family: monospace; }
  tr:hover { background: rgba(128,128,128,0.1); }
</style>
</head>
<body>
<div class="header">
  <h2>回测结果 - ${r.stockCode} [${r.strategy}]</h2>
  <span class="info">${r.startDate} ~ ${r.endDate}</span>
</div>
<div class="metrics">
          ${cardsHtml}
</div>
<div class="tabs">
  <div class="tab active" data-type="equity">资金曲线</div>
  <div class="tab" data-type="returns">收益曲线</div>
  <div class="tab" data-type="trades">交易明细</div>
</div>
<div class="chart-container" id="chartSection">
  <canvas id="chart"></canvas>
  <div class="tooltip" id="tooltip"></div>
</div>
<div class="table-container" id="tableSection" style="display:none">
  <table>
    <thead><tr><th>日期</th><th>操作</th><th>价格</th><th>数量</th><th>盈亏</th></tr></thead>
    <tbody>${tradeRowsHtml}</tbody>
  </table>
</div>
<script>
var points = ${pointsJson};
var initialCapital = ${r.initialCapital};
var canvas = document.getElementById('chart');
var ctx = canvas.getContext('2d');
var tooltip = document.getElementById('tooltip');
var chartSection = document.getElementById('chartSection');
var tableSection = document.getElementById('tableSection');
var currentType = 'equity';
var dpr = window.devicePixelRatio || 1;
var PADDING = { top: 30, right: 70, bottom: 50, left: 20 };

function resize() {
  var w = window.innerWidth - 40;
  var h = window.innerHeight - 280;
  if (h < 200) h = 200;
  canvas.width = w * dpr;
  canvas.height = h * dpr;
  canvas.style.width = w + 'px';
  canvas.style.height = h + 'px';
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.scale(dpr, dpr);
  draw();
}

function fmtNum(n) {
  if (Math.abs(n) >= 1e8) return (n / 1e8).toFixed(1) + '亿';
  if (Math.abs(n) >= 1e4) return (n / 1e4).toFixed(1) + '万';
  return n.toFixed(0);
}

function drawGrid(w, h, minY, maxY, steps, suffix) {
  ctx.strokeStyle = 'rgba(128,128,128,0.15)';
  ctx.lineWidth = 1;
  ctx.setLineDash([4, 4]);
  ctx.fillStyle = 'rgba(128,128,128,0.6)';
  ctx.font = '11px monospace';
  ctx.textAlign = 'right';
  var chartH = h - PADDING.top - PADDING.bottom;
  for (var i = 0; i <= steps; i++) {
    var y = PADDING.top + chartH * i / steps;
    var val = maxY - (maxY - minY) * i / steps;
    ctx.beginPath();
    ctx.moveTo(PADDING.left, y);
    ctx.lineTo(w - PADDING.right, y);
    ctx.stroke();
    var label = suffix ? val.toFixed(1) + suffix : fmtNum(val);
    ctx.fillText(label, w - 8, y + 4);
  }
  ctx.setLineDash([]);
}

function drawXLabels(w, h) {
  ctx.fillStyle = 'rgba(128,128,128,0.6)';
  ctx.font = '10px monospace';
  ctx.textAlign = 'center';
  var n = points.length;
  var step = Math.max(1, Math.floor(n / 8));
  for (var i = 0; i < n; i += step) {
    var x = PADDING.left + (w - PADDING.left - PADDING.right) * i / Math.max(1, n - 1);
    ctx.fillText(points[i].date.slice(5), x, h - PADDING.bottom + 16);
  }
}

function drawTriangle(x, y, size, up, color) {
  ctx.fillStyle = color;
  ctx.beginPath();
  if (up) {
    ctx.moveTo(x, y - size);
    ctx.lineTo(x - size * 0.8, y + size * 0.5);
    ctx.lineTo(x + size * 0.8, y + size * 0.5);
  } else {
    ctx.moveTo(x, y + size);
    ctx.lineTo(x - size * 0.8, y - size * 0.5);
    ctx.lineTo(x + size * 0.8, y - size * 0.5);
  }
  ctx.closePath();
  ctx.fill();
}

function drawEquityCurve(w, h) {
  var values = points.map(function(p) { return p.value; });
  var minV = Math.min.apply(null, values);
  var maxV = Math.max.apply(null, values);
  var pad = (maxV - minV) * 0.05 || maxV * 0.01;
  minV -= pad; maxV += pad;
  var chartW = w - PADDING.left - PADDING.right;
  var chartH = h - PADDING.top - PADDING.bottom;
  var range = maxV - minV || 1;

  drawGrid(w, h, minV, maxV, 6);
  drawXLabels(w, h);

  // Gradient fill
  var grad = ctx.createLinearGradient(0, PADDING.top, 0, PADDING.top + chartH);
  grad.addColorStop(0, 'rgba(66,165,245,0.3)');
  grad.addColorStop(1, 'rgba(66,165,245,0.02)');
  ctx.beginPath();
  for (var i = 0; i < points.length; i++) {
    var x = PADDING.left + chartW * i / Math.max(1, points.length - 1);
    var y = PADDING.top + chartH * (1 - (values[i] - minV) / range);
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  }
  ctx.lineTo(PADDING.left + chartW, PADDING.top + chartH);
  ctx.lineTo(PADDING.left, PADDING.top + chartH);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  // Line
  ctx.beginPath();
  for (var i = 0; i < points.length; i++) {
    var x = PADDING.left + chartW * i / Math.max(1, points.length - 1);
    var y = PADDING.top + chartH * (1 - (values[i] - minV) / range);
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  }
  ctx.strokeStyle = '#42a5f5';
  ctx.lineWidth = 2;
  ctx.stroke();

  // Buy/Sell markers
  for (var i = 0; i < points.length; i++) {
    if (!points[i].action) continue;
    var x = PADDING.left + chartW * i / Math.max(1, points.length - 1);
    var y = PADDING.top + chartH * (1 - (values[i] - minV) / range);
    if (points[i].action === 'BUY') {
      drawTriangle(x, y - 10, 6, true, '#26a69a');
    } else if (points[i].action === 'SELL') {
      drawTriangle(x, y + 10, 6, false, '#ef5350');
    }
  }
}

function drawReturnCurve(w, h) {
  var returns = points.map(function(p) { return (p.value / initialCapital - 1) * 100; });
  var minR = Math.min(0, Math.min.apply(null, returns));
  var maxR = Math.max(0, Math.max.apply(null, returns));
  var pad = (maxR - minR) * 0.1 || 1;
  minR -= pad; maxR += pad;
  var range = maxR - minR;
  var chartW = w - PADDING.left - PADDING.right;
  var chartH = h - PADDING.top - PADDING.bottom;

  drawGrid(w, h, minR, maxR, 6, '%');
  drawXLabels(w, h);

  // Zero line
  var zeroY = PADDING.top + chartH * (1 - (0 - minR) / range);
  ctx.strokeStyle = 'rgba(128,128,128,0.5)';
  ctx.lineWidth = 1;
  ctx.setLineDash([6, 4]);
  ctx.beginPath();
  ctx.moveTo(PADDING.left, zeroY);
  ctx.lineTo(PADDING.left + chartW, zeroY);
  ctx.stroke();
  ctx.setLineDash([]);

  function retX(idx) { return PADDING.left + chartW * idx / Math.max(1, points.length - 1); }
  function retY(idx) { return PADDING.top + chartH * (1 - (returns[idx] - minR) / range); }

  // Positive fill (above zero)
  ctx.save();
  ctx.beginPath();
  ctx.rect(PADDING.left, PADDING.top, chartW, zeroY - PADDING.top);
  ctx.clip();
  ctx.beginPath();
  for (var i = 0; i < points.length; i++) {
    i === 0 ? ctx.moveTo(retX(i), retY(i)) : ctx.lineTo(retX(i), retY(i));
  }
  ctx.lineTo(retX(points.length - 1), zeroY);
  ctx.lineTo(retX(0), zeroY);
  ctx.closePath();
  ctx.fillStyle = 'rgba(66,165,245,0.3)';
  ctx.fill();
  ctx.restore();

  // Negative fill (below zero)
  ctx.save();
  ctx.beginPath();
  ctx.rect(PADDING.left, zeroY, chartW, PADDING.top + chartH - zeroY);
  ctx.clip();
  ctx.beginPath();
  for (var i = 0; i < points.length; i++) {
    i === 0 ? ctx.moveTo(retX(i), retY(i)) : ctx.lineTo(retX(i), retY(i));
  }
  ctx.lineTo(retX(points.length - 1), zeroY);
  ctx.lineTo(retX(0), zeroY);
  ctx.closePath();
  ctx.fillStyle = 'rgba(239,83,80,0.3)';
  ctx.fill();
  ctx.restore();

  // Line
  ctx.beginPath();
  for (var i = 0; i < points.length; i++) {
    i === 0 ? ctx.moveTo(retX(i), retY(i)) : ctx.lineTo(retX(i), retY(i));
  }
  ctx.strokeStyle = '#42a5f5';
  ctx.lineWidth = 2;
  ctx.stroke();

  // Buy/Sell markers
  for (var i = 0; i < points.length; i++) {
    if (!points[i].action) continue;
    if (points[i].action === 'BUY') {
      drawTriangle(retX(i), retY(i) - 10, 6, true, '#26a69a');
    } else if (points[i].action === 'SELL') {
      drawTriangle(retX(i), retY(i) + 10, 6, false, '#ef5350');
    }
  }
}

function draw() {
  if (currentType === 'trades') return;
  var w = canvas.width / dpr;
  var h = canvas.height / dpr;
  ctx.clearRect(0, 0, w, h);
  if (currentType === 'equity') drawEquityCurve(w, h);
  else if (currentType === 'returns') drawReturnCurve(w, h);
}

// Tab switching
document.querySelectorAll('.tab').forEach(function(tab) {
  tab.addEventListener('click', function() {
    document.querySelectorAll('.tab').forEach(function(t) { t.classList.remove('active'); });
    tab.classList.add('active');
    currentType = tab.dataset.type;
    if (currentType === 'trades') {
      chartSection.style.display = 'none';
      tableSection.style.display = 'block';
    } else {
      chartSection.style.display = 'block';
      tableSection.style.display = 'none';
      draw();
    }
  });
});

// Tooltip
canvas.addEventListener('mousemove', function(e) {
  var rect = canvas.getBoundingClientRect();
  var mx = e.clientX - rect.left;
  var chartW = rect.width - PADDING.left - PADDING.right;
  var idx = Math.round((mx - PADDING.left) / chartW * (points.length - 1));
  if (idx < 0 || idx >= points.length) { tooltip.style.display = 'none'; return; }
  var p = points[idx];
  var html = '<b>' + p.date + '</b><br>';
  if (currentType === 'equity') {
    html += '资金: ¥' + p.value.toFixed(2) + '<br>';
  } else {
    var ret = ((p.value / initialCapital - 1) * 100).toFixed(2);
    html += '收益率: ' + (Number(ret) >= 0 ? '+' : '') + ret + '%<br>';
  }
  if (p.action === 'BUY') {
    html += '<span style="color:#26a69a">▲ 买入</span>';
  } else if (p.action === 'SELL') {
    html += '<span style="color:#ef5350">▼ 卖出</span>';
    if (p.profit != null) {
      var c = p.profit >= 0 ? '#ef5350' : '#26a69a';
      html += '<br>盈亏: <span style="color:' + c + '">' + (p.profit >= 0 ? '+' : '') + '¥' + p.profit.toFixed(2) + '</span>';
    }
  }
  tooltip.innerHTML = html;
  tooltip.style.display = 'block';
  var tx = e.clientX - rect.left + 16;
  var ty = e.clientY - rect.top - 10;
  if (tx + tooltip.offsetWidth > rect.width) tx = tx - tooltip.offsetWidth - 32;
  tooltip.style.left = tx + 'px';
  tooltip.style.top = Math.max(0, ty) + 'px';
});

canvas.addEventListener('mouseleave', function() { tooltip.style.display = 'none'; });

window.addEventListener('resize', function() { resize(); });
resize();
</script>
</body>
</html>`;
    }

    dispose(): void {
        this.outputChannel.dispose();
    }
}

