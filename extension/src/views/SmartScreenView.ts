/**
 * 批量智能选股视图
 */

import * as vscode from 'vscode';
import { ApiClient } from '../services/apiClient';
import { SmartScreenParams, SmartScreenResult, RankedResult, BacktestResult } from '../types/strategy';

export class SmartScreenView {
    private context: vscode.ExtensionContext;
    private apiClient: ApiClient;

    constructor(context: vscode.ExtensionContext, apiClient: ApiClient) {
        this.context = context;
        this.apiClient = apiClient;
    }

    async run(): Promise<void> {
        // 0. 选择模式
        const modePick = await vscode.window.showQuickPick(
            [
                { label: '经典模式', value: 'classic', description: '技术面筛选 + 策略回测 + 综合评分' },
                { label: '综合智选', value: 'smart_v2', description: '估值筛选 + 策略测试(置信度) + 预测收益 + 复合排名' },
            ],
            { placeHolder: '请选择选股模式' }
        );
        if (!modePick) { return; }
        const mode = modePick.value;

        // 1. 选择股票池
        const poolPick = await vscode.window.showQuickPick(
            [
                { label: '沪深热门', value: 'hot_hs', description: '80只沪深热门股票（蓝筹+科技+消费+医药+新能源）' },
                { label: '行业龙头', value: 'industry_leaders', description: '60只各行业龙头股票' },
                { label: '港股热门', value: 'hot_hk', description: '30只港股热门股票（互联网+金融+消费）' },
                { label: 'A股+港股', value: 'hs_and_hk', description: '沪深热门 + 港股热门合并筛选' },
                { label: '自定义', value: 'custom', description: '手动输入股票代码（港股用HK前缀，如HK00700）' },
            ],
            { placeHolder: '请选择股票池' }
        );
        if (!poolPick) { return; }

        // 2. 自定义时输入代码
        let customCodes: string | undefined;
        if (poolPick.value === 'custom') {
            customCodes = await vscode.window.showInputBox({
                prompt: '请输入股票代码（逗号分隔）',
                placeHolder: '例如：600519,000858,601318',
                validateInput: (v) => v.trim() ? null : '请输入至少一个股票代码',
            });
            if (!customCodes) { return; }
        }

        // 3. 选股策略 (classic) 或 预测月数 (smart_v2)
        let screeningStrategy = 'all';
        let predictionMonths: number | undefined;

        if (mode === 'classic') {
            const strategyPick = await vscode.window.showQuickPick(
                [
                    { label: '全部通过', value: 'all', description: '不筛选，所有股票均参与回测' },
                    { label: '趋势向上', value: 'uptrend', description: 'MA5>MA20 且 价格>MA60' },
                    { label: '动量最强', value: 'momentum', description: '按20日涨幅排序取前半' },
                    { label: '放量突破', value: 'volume_breakout', description: '近5日均量 > 1.5倍60日均量' },
                    { label: 'RSI超卖', value: 'rsi_oversold', description: 'RSI14 < 35 超卖反弹机会' },
                    { label: 'MACD金叉', value: 'macd_golden', description: '近5日内出现MACD金叉' },
                ],
                { placeHolder: '请选择选股策略' }
            );
            if (!strategyPick) { return; }
            screeningStrategy = strategyPick.value;
        } else {
            const monthPick = await vscode.window.showQuickPick(
                [
                    { label: '3个月', value: '3' },
                    { label: '6个月', value: '6' },
                    { label: '12个月', value: '12' },
                ],
                { placeHolder: '预测未来收益的时间跨度' }
            );
            if (!monthPick) { return; }
            predictionMonths = Number(monthPick.value);
        }

        // 4. 输入日期
        const startDate = await vscode.window.showInputBox({
            prompt: '请输入回测开始日期',
            placeHolder: 'YYYY-MM-DD',
            value: '2024-01-01',
            validateInput: (v) => /^\d{4}-\d{2}-\d{2}$/.test(v) ? null : '请输入正确的日期格式 YYYY-MM-DD',
        });
        if (!startDate) { return; }

        const endDate = await vscode.window.showInputBox({
            prompt: '请输入回测结束日期',
            placeHolder: 'YYYY-MM-DD',
            value: '2024-12-31',
            validateInput: (v) => /^\d{4}-\d{2}-\d{2}$/.test(v) ? null : '请输入正确的日期格式 YYYY-MM-DD',
        });
        if (!endDate) { return; }

        // 5. 风控参数 (classic mode only)
        let advParams: Partial<SmartScreenParams> = {};
        if (mode === 'classic') {
            const advPick = await vscode.window.showQuickPick(
                [
                    { label: '使用默认参数', value: 'default', description: '止损8% / 移动止盈12% / 单笔风险2%' },
                    { label: '自定义风控参数', value: 'custom', description: '自行设置止损、仓位、趋势过滤等' },
                ],
                { placeHolder: '风控参数设置' }
            );
            if (!advPick) { return; }

            if (advPick.value === 'custom') {
                const sl = await vscode.window.showInputBox({ prompt: '止损比例（%）', value: '8', validateInput: v => isNaN(Number(v)) ? '请输入数字' : null });
                if (!sl) { return; }
                const ts = await vscode.window.showInputBox({ prompt: '移动止盈回撤（%）', value: '12', validateInput: v => isNaN(Number(v)) ? '请输入数字' : null });
                if (!ts) { return; }
                const rpt = await vscode.window.showInputBox({ prompt: '单笔风险占资金比例（%）', value: '2', validateInput: v => isNaN(Number(v)) ? '请输入数字' : null });
                if (!rpt) { return; }
                const mpp = await vscode.window.showInputBox({ prompt: '最大仓位比例（%）', value: '95', validateInput: v => isNaN(Number(v)) ? '请输入数字' : null });
                if (!mpp) { return; }
                const tma = await vscode.window.showInputBox({ prompt: '趋势均线天数', value: '60', validateInput: v => isNaN(Number(v)) ? '请输入数字' : null });
                if (!tma) { return; }
                const cd = await vscode.window.showInputBox({ prompt: '止损后冷却天数', value: '3', validateInput: v => isNaN(Number(v)) ? '请输入数字' : null });
                if (!cd) { return; }
                advParams = {
                    stopLossPct: Number(sl) / 100,
                    trailingStopPct: Number(ts) / 100,
                    riskPerTrade: Number(rpt) / 100,
                    maxPositionPct: Number(mpp) / 100,
                    trendMaLen: Number(tma),
                    cooldownBars: Number(cd),
                };
            }
        }

        // 6. 执行
        const params: SmartScreenParams = {
            stockPool: poolPick.value,
            customCodes,
            screeningStrategy,
            startDate,
            endDate,
            mode,
            predictionMonths,
            ...advParams,
        };

        const progressTitle = mode === 'smart_v2'
            ? '综合智选分析中（估值+策略测试+预测）...'
            : '批量智能选股中...';

        await vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: progressTitle,
                cancellable: false,
            },
            async (progress) => {
                progress.report({ message: '正在获取数据并回测，请耐心等待...' });
                try {
                    const result = await this.apiClient.runSmartScreen(params);
                    this.showResultWebView(result);
                } catch (error: any) {
                    const message = error.response?.data?.detail || error.message || '批量智能选股失败';
                    vscode.window.showErrorMessage(`批量智能选股失败：${message}`);
                }
            }
        );
    }

    private showResultWebView(result: SmartScreenResult): void {
        const panel = vscode.window.createWebviewPanel(
            'quantFreeSmartScreen',
            `批量智能选股结果 - ${result.poolName}`,
            vscode.ViewColumn.One,
            { enableScripts: true }
        );
        panel.webview.html = this.getResultsHtml(result);
    }

    private getResultsHtml(result: SmartScreenResult): string {
        const r = result;
        const isV2 = r.mode === 'smart_v2';

        // Overview cards
        const overviewCards: Array<{ label: string; value: string; color?: string }> = [
            { label: '股票池总数', value: `${r.totalStocks}` },
            { label: isV2 ? '估值通过' : '通过筛选', value: `${r.screenedStocks}` },
            { label: '回测总次数', value: `${r.totalBacktests}` },
            { label: '耗时', value: `${r.timeTakenSeconds}s` },
        ];
        if (isV2) {
            overviewCards.push(
                { label: '平均置信度', value: `${r.avgConfidence ?? 0}`, color: '#ffd54f' },
                { label: '平均预测收益', value: `${(r.avgPredictedReturn ?? 0) >= 0 ? '+' : ''}${(r.avgPredictedReturn ?? 0).toFixed(2)}%`, color: (r.avgPredictedReturn ?? 0) >= 0 ? '#ef5350' : '#26a69a' },
                { label: '买入持有基准', value: `${(r.testBnhPct ?? 0) >= 0 ? '+' : ''}${(r.testBnhPct ?? 0).toFixed(2)}%` },
            );
        }
        const overviewHtml = overviewCards.map(c => {
            const vs = c.color ? ` style="color:${c.color}"` : '';
            return `<div class="card"><div class="card-label">${c.label}</div><div class="card-value"${vs}>${c.value}</div></div>`;
        }).join('\n');

        const valColor = (v: number) => v >= 0 ? '#ef5350' : '#26a69a';

        // Table rows
        let rankHeaderHtml: string;
        let rankRowsHtml: string;

        if (isV2) {
            rankHeaderHtml = `<th>排名</th><th>代码</th><th>名称</th><th>行业</th><th>PE</th><th>PB</th><th>ROE%</th><th>估值分</th><th>AI评分</th>
                <th>策略</th><th>置信度</th><th>预测收益</th><th>Alpha</th><th>信号</th><th>综合分</th>`;
            rankRowsHtml = r.rankings.map((item, idx) => {
                const predColor = valColor(item.predictedReturnPct ?? 0);
                const alphaColor = valColor(item.alphaPct ?? 0);
                const confColor = (item.confidenceScore ?? 0) >= 60 ? '#ffd54f' : (item.confidenceScore ?? 0) >= 35 ? '#81c784' : '#90a4ae';
                const scoreColor = item.score >= 70 ? '#ffd54f' : item.score >= 40 ? '#81c784' : '#90a4ae';
                const sigColor = item.signal === '看涨' ? '#ef5350' : item.signal === '看跌' ? '#26a69a' : '#90a4ae';
                const aiColor = (item.aiScore ?? 50) >= 70 ? '#ffd54f' : (item.aiScore ?? 50) >= 50 ? '#81c784' : '#90a4ae';
                const roeColor = (item.roe ?? 0) >= 15 ? '#ffd54f' : (item.roe ?? 0) >= 8 ? '#81c784' : '#90a4ae';
                const bgOpacity = Math.max(0.02, (r.rankings.length - idx) / r.rankings.length * 0.08);
                return `<tr style="background:rgba(66,165,245,${bgOpacity})" data-idx="${idx}">
                    <td style="font-weight:700;text-align:center">${item.rank}</td>
                    <td>${item.stockCode}</td>
                    <td>${item.stockName}</td>
                    <td style="font-size:11px;opacity:0.8">${item.industry ?? '-'}</td>
                    <td>${item.pe != null ? (item.pe as number).toFixed(1) : '-'}</td>
                    <td>${item.pb != null ? (item.pb as number).toFixed(2) : '-'}</td>
                    <td style="color:${roeColor}">${item.roe != null ? (item.roe as number).toFixed(1) : '-'}</td>
                    <td>${(item.valuationScore ?? 0).toFixed(0)}</td>
                    <td style="color:${aiColor};font-weight:600">${(item.aiScore ?? 50).toFixed(0)}</td>
                    <td>${item.strategyLabel}</td>
                    <td style="color:${confColor};font-weight:600">${(item.confidenceScore ?? 0).toFixed(1)}</td>
                    <td style="color:${predColor};font-weight:600">${(item.predictedReturnPct ?? 0) >= 0 ? '+' : ''}${(item.predictedReturnPct ?? 0).toFixed(2)}%</td>
                    <td style="color:${alphaColor}">${(item.alphaPct ?? 0) >= 0 ? '+' : ''}${(item.alphaPct ?? 0).toFixed(2)}%</td>
                    <td style="color:${sigColor};font-weight:600">${item.signal ?? '-'}</td>
                    <td style="color:${scoreColor};font-weight:700">${item.score.toFixed(1)}</td>
                </tr>`;
            }).join('\n');
        } else {
            rankHeaderHtml = `<th>排名</th><th>代码</th><th>名称</th><th>策略</th>
                <th>收益率</th><th>夏普</th><th>最大回撤</th><th>胜率</th><th>评分</th>`;
            rankRowsHtml = r.rankings.map((item, idx) => {
                const retColor = valColor(item.totalReturnPercent);
                const scoreColor = item.score >= 70 ? '#ffd54f' : item.score >= 40 ? '#81c784' : '#90a4ae';
                const bgOpacity = Math.max(0.02, (r.rankings.length - idx) / r.rankings.length * 0.08);
                return `<tr style="background:rgba(66,165,245,${bgOpacity})" data-idx="${idx}">
                    <td style="font-weight:700;text-align:center">${item.rank}</td>
                    <td>${item.stockCode}</td>
                    <td>${item.stockName}</td>
                    <td>${item.strategyLabel}</td>
                    <td style="color:${retColor};font-weight:600">${item.totalReturnPercent >= 0 ? '+' : ''}${item.totalReturnPercent.toFixed(2)}%</td>
                    <td>${item.sharpeRatio.toFixed(2)}</td>
                    <td>-${item.maxDrawdown.toFixed(2)}%</td>
                    <td>${item.winRate.toFixed(1)}%</td>
                    <td style="color:${scoreColor};font-weight:700">${item.score.toFixed(1)}</td>
                </tr>`;
            }).join('\n');
        }

        const screenedRowsHtml = r.allScreened.map(s => {
            const statusColor = s.passed ? '#26a69a' : '#ef5350';
            const statusText = s.passed ? '通过' : '未通过';
            return `<tr>
                <td>${s.code}</td>
                <td>${s.name}</td>
                <td style="color:${statusColor};font-weight:600">${statusText}</td>
                <td>${s.reason}</td>
            </tr>`;
        }).join('\n');

        const rankingsJson = JSON.stringify(r.rankings.map(item => {
            const bt = item.backtestResult;
            const equityPoints: Array<{ date: string; value: number }> = [];
            if (bt) {
                let equity = bt.initialCapital;
                equityPoints.push({ date: bt.startDate, value: bt.initialCapital });
                for (const t of bt.trades) {
                    if (t.action === 'SELL' && t.profit != null) {
                        equity += t.profit;
                    }
                    equityPoints.push({ date: t.date, value: equity });
                }
                if (equityPoints[equityPoints.length - 1].date !== bt.endDate) {
                    equityPoints.push({ date: bt.endDate, value: bt.finalCapital });
                }
            }
            return {
                label: `${item.stockCode} ${item.stockName} [${item.strategyLabel}]`,
                stockCode: item.stockCode,
                stockName: item.stockName,
                strategyLabel: item.strategyLabel,
                totalReturnPercent: item.totalReturnPercent,
                sharpeRatio: item.sharpeRatio,
                maxDrawdown: item.maxDrawdown,
                winRate: item.winRate,
                totalTrades: item.totalTrades,
                equityPoints,
                initialCapital: bt?.initialCapital ?? 100000,
                finalCapital: bt?.finalCapital ?? 100000,
                trades: bt?.trades ?? [],
                priceSeries: bt?.priceSeries ?? [],
                // smart_v2 extras
                valuationScore: item.valuationScore,
                confidenceScore: item.confidenceScore,
                predictedReturnPct: item.predictedReturnPct,
                alphaPct: item.alphaPct,
                pe: item.pe,
                pb: item.pb,
                roe: item.roe,
                industry: item.industry ?? '',
                revenueGrowth: item.revenueGrowth,
                profitGrowth: item.profitGrowth,
                grossMargin: item.grossMargin,
                signal: item.signal,
                aiScore: item.aiScore ?? 50,
                aiAnalysis: item.aiAnalysis ?? '',
                // smart_v2 chart data
                equityCurve: item.equityCurve ?? [],
                projectedEquity: item.projectedEquity ?? [],
                fullPriceSeries: item.fullPriceSeries ?? [],
                allTrades: item.allTrades ?? [],
                splitDate: item.splitDate ?? '',
            };
        }));

        const modeLabel = isV2 ? '综合智选' : '经典模式';
        const headerInfo = isV2
            ? `模式: ${modeLabel} | 股票池: ${r.poolName}`
            : `股票池: ${r.poolName} | 选股策略: ${r.screeningStrategy}`;
        const overviewCols = isV2 ? 7 : 4;

        return /*html*/`<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>批量智能选股结果</title>
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
    display: flex; align-items: center; gap: 16px;
    border-bottom: 1px solid var(--vscode-panel-border, #333);
  }
  .header h2 { font-size: 16px; font-weight: 600; }
  .header .info { font-size: 12px; opacity: 0.7; }
  .overview {
    display: grid;
    grid-template-columns: repeat(${overviewCols}, 1fr);
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
    display: flex; gap: 2px;
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
  .section { padding: 0 20px 20px; display: none; }
  .section.active { display: block; }
  .table-container { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td {
    padding: 8px 12px;
    text-align: left;
    border-bottom: 1px solid var(--vscode-panel-border, #333);
    white-space: nowrap;
  }
  th {
    font-weight: 600; opacity: 0.7; font-size: 11px;
    text-transform: uppercase;
    position: sticky; top: 0;
    background: var(--vscode-editor-background, #1e1e1e);
  }
  td { font-family: monospace; }
  #rankBody tr:hover { background: rgba(128,128,128,0.1); cursor: pointer; }

  #detailPanel {
    display: none;
    border-top: 2px solid var(--vscode-panel-border, #333);
    padding: 16px 0;
    margin-top: 12px;
  }
  .detail-header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 12px;
  }
  .detail-header h3 { font-size: 15px; }
  .detail-close {
    cursor: pointer; font-size: 12px; padding: 4px 12px;
    border: 1px solid var(--vscode-panel-border, #555);
    border-radius: 4px; background: transparent;
    color: var(--vscode-editor-foreground, #d4d4d4);
  }
  .detail-close:hover { background: rgba(128,128,128,0.2); }
  .detail-stats {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
    gap: 8px; margin-bottom: 16px;
  }
  .stat-chip {
    background: var(--vscode-editorWidget-background, #252526);
    border: 1px solid var(--vscode-panel-border, #333);
    border-radius: 4px; padding: 6px 10px; text-align: center;
  }
  .stat-chip .sl { font-size: 10px; opacity: 0.5; }
  .stat-chip .sv { font-size: 14px; font-weight: 600; font-family: monospace; }
  .chart-section-title {
    font-size: 12px; font-weight: 600; opacity: 0.7;
    margin: 12px 0 6px; padding-left: 2px;
  }
  canvas { display: block; margin-bottom: 8px; }
  .trade-table-wrap {
    max-height: 280px; overflow-y: auto;
    margin-top: 8px;
  }
  .trade-table-wrap table { font-size: 12px; }
  .trade-table-wrap th { font-size: 10px; }
  .buy-tag { color: #ef5350; font-weight: 700; }
  .sell-tag { color: #26a69a; font-weight: 700; }
</style>
</head>
<body>
<div class="header">
  <h2>${isV2 ? '综合智选结果' : '批量智能选股结果'}</h2>
  <span class="info">${headerInfo}</span>
</div>
<div class="overview">
  ${overviewHtml}
</div>
<div class="tabs">
  <div class="tab active" data-tab="rankings">排行榜</div>
  <div class="tab" data-tab="screened">筛选明细</div>
</div>
<div class="section active" id="sec-rankings">
  <div class="table-container">
    <table>
      <thead><tr>${rankHeaderHtml}</tr></thead>
      <tbody id="rankBody">${rankRowsHtml}</tbody>
    </table>
  </div>

  <div id="detailPanel">
    <div class="detail-header">
      <h3 id="detailTitle"></h3>
      <button class="detail-close" id="detailClose">收起</button>
    </div>
    <div class="detail-stats" id="detailStats"></div>

    <div id="aiAnalysisBlock" style="display:none;margin-bottom:14px;">
      <div class="chart-section-title">AI 基本面分析</div>
      <div style="background:var(--vscode-editorWidget-background,#252526);border:1px solid var(--vscode-panel-border,#333);border-left:3px solid #ffd54f;border-radius:4px;padding:10px 14px;font-size:13px;line-height:1.6;" class="ai-text"></div>
    </div>

    <div class="chart-section-title">股价走势 &amp; 买卖信号</div>
    <canvas id="priceCanvas"></canvas>

    <div id="projectionSection" style="display:none">
      <div class="chart-section-title">收益预测曲线（历史 + 未来预估）</div>
      <canvas id="projectionCanvas"></canvas>
      <div style="font-size:11px;opacity:0.5;padding:2px 0 8px;display:flex;gap:16px">
        <span>&#9632; <span style="color:#42a5f5">训练期权益</span></span>
        <span>&#9632; <span style="color:#ff9800">测试期权益</span></span>
        <span>&#9632; <span style="color:#ffd54f">未来预估</span></span>
      </div>
    </div>

    <div class="chart-section-title">资金曲线</div>
    <canvas id="equityCanvas"></canvas>

    <div class="chart-section-title">交易明细</div>
    <div class="trade-table-wrap">
      <table>
        <thead><tr><th>日期</th><th>操作</th><th>价格</th><th>数量</th><th>盈亏</th></tr></thead>
        <tbody id="tradeBody"></tbody>
      </table>
    </div>
  </div>
</div>

<div class="section" id="sec-screened">
  <div class="table-container">
    <table>
      <thead><tr><th>代码</th><th>名称</th><th>状态</th><th>原因</th></tr></thead>
      <tbody>${screenedRowsHtml}</tbody>
    </table>
  </div>
</div>

<script>
var RD = ${rankingsJson};
var IS_V2 = ${isV2 ? 'true' : 'false'};
var dpr = window.devicePixelRatio || 1;
var PAD = { top: 24, right: 64, bottom: 36, left: 24 };

document.querySelectorAll('.tab').forEach(function(tab) {
  tab.addEventListener('click', function() {
    document.querySelectorAll('.tab').forEach(function(t) { t.classList.remove('active'); });
    tab.classList.add('active');
    document.querySelectorAll('.section').forEach(function(s) { s.classList.remove('active'); });
    document.getElementById('sec-' + tab.dataset.tab).classList.add('active');
  });
});

document.getElementById('rankBody').addEventListener('click', function(e) {
  var tr = e.target.closest('tr');
  if (!tr) return;
  var idx = parseInt(tr.dataset.idx, 10);
  if (isNaN(idx) || idx >= RD.length) return;
  showDetail(idx);
});

document.getElementById('detailClose').addEventListener('click', function() {
  document.getElementById('detailPanel').style.display = 'none';
});

function showDetail(idx) {
  var d = RD[idx];
  var panel = document.getElementById('detailPanel');
  panel.style.display = 'block';

  document.getElementById('detailTitle').textContent =
    d.stockCode + ' ' + d.stockName + '  [' + d.strategyLabel + ']';

  var retColor = d.totalReturnPercent >= 0 ? '#ef5350' : '#26a69a';
  var statsHtml =
    chip('训练收益', (d.totalReturnPercent >= 0 ? '+' : '') + d.totalReturnPercent.toFixed(2) + '%', retColor) +
    chip('夏普比率', d.sharpeRatio.toFixed(2)) +
    chip('最大回撤', '-' + d.maxDrawdown.toFixed(2) + '%') +
    chip('胜率', d.winRate.toFixed(1) + '%') +
    chip('交易次数', d.totalTrades);

  if (IS_V2) {
    var confColor = (d.confidenceScore || 0) >= 60 ? '#ffd54f' : (d.confidenceScore || 0) >= 35 ? '#81c784' : '#90a4ae';
    var predColor = (d.predictedReturnPct || 0) >= 0 ? '#ef5350' : '#26a69a';
    var alphaColor = (d.alphaPct || 0) >= 0 ? '#ef5350' : '#26a69a';
    statsHtml +=
      chip('置信度', (d.confidenceScore || 0).toFixed(1), confColor) +
      chip('预测收益', ((d.predictedReturnPct || 0) >= 0 ? '+' : '') + (d.predictedReturnPct || 0).toFixed(2) + '%', predColor) +
      chip('Alpha', ((d.alphaPct || 0) >= 0 ? '+' : '') + (d.alphaPct || 0).toFixed(2) + '%', alphaColor) +
      chip('行业', d.industry || '-') +
      chip('PE', d.pe != null ? d.pe.toFixed(1) : '-') +
      chip('PB', d.pb != null ? d.pb.toFixed(2) : '-') +
      chip('ROE', d.roe != null ? d.roe.toFixed(1) + '%' : '-', d.roe != null && d.roe >= 15 ? '#ffd54f' : undefined) +
      chip('营收增长', d.revenueGrowth != null ? (d.revenueGrowth >= 0 ? '+' : '') + d.revenueGrowth.toFixed(1) + '%' : '-', d.revenueGrowth != null ? (d.revenueGrowth >= 0 ? '#ef5350' : '#26a69a') : undefined) +
      chip('净利润增长', d.profitGrowth != null ? (d.profitGrowth >= 0 ? '+' : '') + d.profitGrowth.toFixed(1) + '%' : '-', d.profitGrowth != null ? (d.profitGrowth >= 0 ? '#ef5350' : '#26a69a') : undefined) +
      chip('毛利率', d.grossMargin != null ? d.grossMargin.toFixed(1) + '%' : '-') +
      chip('估值分', (d.valuationScore || 0).toFixed(0)) +
      chip('AI评分', (d.aiScore || 50).toFixed(0), (d.aiScore || 50) >= 70 ? '#ffd54f' : (d.aiScore || 50) >= 50 ? '#81c784' : '#90a4ae') +
      chip('信号', d.signal || '-', d.signal === '看涨' ? '#ef5350' : d.signal === '看跌' ? '#26a69a' : '#90a4ae');
  }

  document.getElementById('detailStats').innerHTML = statsHtml;

  // AI analysis block
  var aiBlock = document.getElementById('aiAnalysisBlock');
  if (IS_V2 && d.aiAnalysis) {
    aiBlock.style.display = 'block';
    aiBlock.querySelector('.ai-text').textContent = d.aiAnalysis;
  } else {
    aiBlock.style.display = 'none';
  }

  // For smart_v2, prefer fullPriceSeries + allTrades over backtest-only data
  var chartData = d;
  if (IS_V2 && d.fullPriceSeries && d.fullPriceSeries.length >= 2) {
    chartData = Object.assign({}, d, {
      priceSeries: d.fullPriceSeries,
      trades: d.allTrades || [],
    });
  }

  if (chartData.priceSeries && chartData.priceSeries.length >= 2) {
    document.getElementById('priceCanvas').style.display = 'block';
    drawPriceChart(chartData);
  } else {
    document.getElementById('priceCanvas').style.display = 'none';
  }

  // Projection chart for smart_v2
  var projSec = document.getElementById('projectionSection');
  if (IS_V2 && d.equityCurve && d.equityCurve.length >= 2) {
    projSec.style.display = 'block';
    drawProjectionChart(d);
  } else {
    projSec.style.display = 'none';
  }

  if (d.equityPoints && d.equityPoints.length >= 2) {
    document.getElementById('equityCanvas').style.display = 'block';
    drawEquityCurve(d);
  } else {
    document.getElementById('equityCanvas').style.display = 'none';
  }

  // For smart_v2, show combined trades
  if (IS_V2 && d.allTrades && d.allTrades.length > 0) {
    fillTradeTable(Object.assign({}, d, { trades: d.allTrades }));
  } else {
    fillTradeTable(d);
  }

  panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function chip(label, value, color) {
  var c = color ? ' style="color:' + color + '"' : '';
  return '<div class="stat-chip"><div class="sl">' + label + '</div><div class="sv"' + c + '>' + value + '</div></div>';
}

/* ======= Price Chart with Buy/Sell Markers ======= */
function drawPriceChart(d) {
  var canvas = document.getElementById('priceCanvas');
  var ctx = canvas.getContext('2d');
  var w = window.innerWidth - 60;
  var h = 300;
  canvas.width = w * dpr; canvas.height = h * dpr;
  canvas.style.width = w + 'px'; canvas.style.height = h + 'px';
  ctx.setTransform(1,0,0,1,0,0); ctx.scale(dpr, dpr);
  ctx.clearRect(0,0,w,h);

  var ps = d.priceSeries;
  if (!ps || ps.length < 2) {
    ctx.fillStyle = 'rgba(128,128,128,0.5)'; ctx.font = '13px sans-serif';
    ctx.fillText('暂无价格数据', w/2 - 40, h/2);
    return;
  }

  var closes = ps.map(function(p){ return p.close; });
  var dates  = ps.map(function(p){ return p.date; });
  var minC = Math.min.apply(null, closes);
  var maxC = Math.max.apply(null, closes);
  var pad = (maxC - minC) * 0.08 || maxC * 0.02;
  minC -= pad; maxC += pad;
  var cW = w - PAD.left - PAD.right;
  var cH = h - PAD.top - PAD.bottom;
  var range = maxC - minC || 1;

  function xOf(i) { return PAD.left + cW * i / Math.max(1, ps.length - 1); }
  function yOf(v) { return PAD.top + cH * (1 - (v - minC) / range); }

  var dateIdx = {};
  for (var i = 0; i < dates.length; i++) dateIdx[dates[i]] = i;

  ctx.strokeStyle = 'rgba(128,128,128,0.12)'; ctx.lineWidth = 1; ctx.setLineDash([4,4]);
  ctx.fillStyle = 'rgba(128,128,128,0.6)'; ctx.font = '10px monospace'; ctx.textAlign = 'right';
  for (var g = 0; g <= 5; g++) {
    var gy = PAD.top + cH * g / 5;
    var gv = maxC - (maxC - minC) * g / 5;
    ctx.beginPath(); ctx.moveTo(PAD.left, gy); ctx.lineTo(w - PAD.right, gy); ctx.stroke();
    ctx.fillText(gv.toFixed(2), w - 6, gy + 4);
  }
  ctx.setLineDash([]);

  ctx.textAlign = 'center';
  var xStep = Math.max(1, Math.floor(ps.length / 6));
  for (var i = 0; i < ps.length; i += xStep) {
    ctx.fillText(dates[i], xOf(i), h - PAD.bottom + 14);
  }

  var grad = ctx.createLinearGradient(0, PAD.top, 0, PAD.top + cH);
  grad.addColorStop(0, 'rgba(66,165,245,0.18)');
  grad.addColorStop(1, 'rgba(66,165,245,0.01)');
  ctx.beginPath();
  for (var i = 0; i < ps.length; i++) {
    var x = xOf(i), y = yOf(closes[i]);
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  }
  ctx.lineTo(xOf(ps.length - 1), PAD.top + cH);
  ctx.lineTo(xOf(0), PAD.top + cH);
  ctx.closePath(); ctx.fillStyle = grad; ctx.fill();

  ctx.beginPath();
  for (var i = 0; i < ps.length; i++) {
    var x = xOf(i), y = yOf(closes[i]);
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  }
  ctx.strokeStyle = '#42a5f5'; ctx.lineWidth = 1.8; ctx.stroke();

  var trades = d.trades || [];
  for (var ti = 0; ti < trades.length; ti++) {
    var t = trades[ti];
    var di = dateIdx[t.date];
    if (di === undefined) {
      var best = -1, bestDiff = 1e9;
      for (var j = 0; j < dates.length; j++) {
        var diff = Math.abs(new Date(dates[j]) - new Date(t.date));
        if (diff < bestDiff) { bestDiff = diff; best = j; }
      }
      di = best;
    }
    if (di < 0) continue;

    var mx = xOf(di);
    var my = yOf(t.price);

    if (t.action === 'BUY') {
      ctx.beginPath();
      ctx.moveTo(mx, my - 10);
      ctx.lineTo(mx - 6, my + 2);
      ctx.lineTo(mx + 6, my + 2);
      ctx.closePath();
      ctx.fillStyle = '#ef5350'; ctx.fill();
      ctx.fillStyle = '#ef5350'; ctx.font = '9px sans-serif'; ctx.textAlign = 'center';
      ctx.fillText('B', mx, my - 12);
    } else {
      ctx.beginPath();
      ctx.moveTo(mx, my + 10);
      ctx.lineTo(mx - 6, my - 2);
      ctx.lineTo(mx + 6, my - 2);
      ctx.closePath();
      ctx.fillStyle = '#26a69a'; ctx.fill();
      ctx.fillStyle = '#26a69a'; ctx.font = '9px sans-serif'; ctx.textAlign = 'center';
      ctx.fillText('S', mx, my + 20);
    }
  }
}

/* ======= Equity Curve ======= */
function drawEquityCurve(d) {
  var canvas = document.getElementById('equityCanvas');
  var ctx = canvas.getContext('2d');
  var w = window.innerWidth - 60;
  var h = 220;
  canvas.width = w * dpr; canvas.height = h * dpr;
  canvas.style.width = w + 'px'; canvas.style.height = h + 'px';
  ctx.setTransform(1,0,0,1,0,0); ctx.scale(dpr, dpr);
  ctx.clearRect(0,0,w,h);

  var pts = d.equityPoints;
  if (!pts || pts.length < 2) return;
  var values = pts.map(function(p){ return p.value; });
  var minV = Math.min.apply(null, values);
  var maxV = Math.max.apply(null, values);
  var pad = (maxV - minV) * 0.05 || maxV * 0.01;
  minV -= pad; maxV += pad;
  var cW = w - PAD.left - PAD.right;
  var cH = h - PAD.top - PAD.bottom;
  var range = maxV - minV || 1;

  ctx.strokeStyle = 'rgba(128,128,128,0.12)'; ctx.lineWidth = 1; ctx.setLineDash([4,4]);
  ctx.fillStyle = 'rgba(128,128,128,0.6)'; ctx.font = '10px monospace'; ctx.textAlign = 'right';
  for (var g = 0; g <= 4; g++) {
    var gy = PAD.top + cH * g / 4;
    var gv = maxV - (maxV - minV) * g / 4;
    ctx.beginPath(); ctx.moveTo(PAD.left, gy); ctx.lineTo(w - PAD.right, gy); ctx.stroke();
    ctx.fillText(gv.toFixed(0), w - 6, gy + 4);
  }
  ctx.setLineDash([]);

  ctx.textAlign = 'center';
  var step = Math.max(1, Math.floor(pts.length / 6));
  for (var i = 0; i < pts.length; i += step) {
    var x = PAD.left + cW * i / Math.max(1, pts.length - 1);
    ctx.fillText(pts[i].date, x, h - PAD.bottom + 14);
  }

  var baseY = PAD.top + cH * (1 - (d.initialCapital - minV) / range);
  ctx.strokeStyle = 'rgba(255,255,255,0.15)'; ctx.lineWidth = 1; ctx.setLineDash([6,3]);
  ctx.beginPath(); ctx.moveTo(PAD.left, baseY); ctx.lineTo(w - PAD.right, baseY); ctx.stroke();
  ctx.setLineDash([]);

  var above = d.finalCapital >= d.initialCapital;
  var gc = above ? '76,175,80' : '239,83,80';
  var grad = ctx.createLinearGradient(0, PAD.top, 0, PAD.top + cH);
  grad.addColorStop(0, 'rgba(' + gc + ',0.25)');
  grad.addColorStop(1, 'rgba(' + gc + ',0.02)');
  ctx.beginPath();
  for (var i = 0; i < pts.length; i++) {
    var x = PAD.left + cW * i / Math.max(1, pts.length - 1);
    var y = PAD.top + cH * (1 - (values[i] - minV) / range);
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  }
  ctx.lineTo(PAD.left + cW, PAD.top + cH);
  ctx.lineTo(PAD.left, PAD.top + cH);
  ctx.closePath(); ctx.fillStyle = grad; ctx.fill();

  ctx.beginPath();
  for (var i = 0; i < pts.length; i++) {
    var x = PAD.left + cW * i / Math.max(1, pts.length - 1);
    var y = PAD.top + cH * (1 - (values[i] - minV) / range);
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  }
  ctx.strokeStyle = above ? '#4caf50' : '#ef5350'; ctx.lineWidth = 2; ctx.stroke();
}

/* ======= Projection Chart (smart_v2) ======= */
function drawProjectionChart(d) {
  var canvas = document.getElementById('projectionCanvas');
  var ctx = canvas.getContext('2d');
  var w = window.innerWidth - 60;
  var h = 280;
  canvas.width = w * dpr; canvas.height = h * dpr;
  canvas.style.width = w + 'px'; canvas.style.height = h + 'px';
  ctx.setTransform(1,0,0,1,0,0); ctx.scale(dpr, dpr);
  ctx.clearRect(0,0,w,h);

  var histPts = d.equityCurve || [];
  var projPts = d.projectedEquity || [];
  if (histPts.length < 2) return;

  var splitDate = d.splitDate || '';
  var allPts = histPts.concat(projPts.length > 1 ? projPts.slice(1) : []);
  var allValues = allPts.map(function(p){ return p.value; });
  var minV = Math.min.apply(null, allValues);
  var maxV = Math.max.apply(null, allValues);
  var vPad = (maxV - minV) * 0.08 || maxV * 0.02;
  minV -= vPad; maxV += vPad;
  var cW = w - PAD.left - PAD.right;
  var cH = h - PAD.top - PAD.bottom;
  var range = maxV - minV || 1;

  function xOf(i) { return PAD.left + cW * i / Math.max(1, allPts.length - 1); }
  function yOf(v) { return PAD.top + cH * (1 - (v - minV) / range); }

  // Grid
  ctx.strokeStyle = 'rgba(128,128,128,0.12)'; ctx.lineWidth = 1; ctx.setLineDash([4,4]);
  ctx.fillStyle = 'rgba(128,128,128,0.6)'; ctx.font = '10px monospace'; ctx.textAlign = 'right';
  for (var g = 0; g <= 5; g++) {
    var gy = PAD.top + cH * g / 5;
    var gv = maxV - (maxV - minV) * g / 5;
    ctx.beginPath(); ctx.moveTo(PAD.left, gy); ctx.lineTo(w - PAD.right, gy); ctx.stroke();
    ctx.fillText(gv.toFixed(0), w - 6, gy + 4);
  }
  ctx.setLineDash([]);

  // X labels
  ctx.textAlign = 'center';
  var xStep = Math.max(1, Math.floor(allPts.length / 6));
  for (var i = 0; i < allPts.length; i += xStep) {
    ctx.fillText(allPts[i].date, xOf(i), h - PAD.bottom + 14);
  }

  // Find split index (where test period starts) and projection start
  var splitIdx = -1;
  var projStartIdx = histPts.length;
  for (var i = 0; i < histPts.length; i++) {
    if (splitDate && histPts[i].date >= splitDate && splitIdx < 0) {
      splitIdx = i;
    }
  }

  // Baseline (initial capital)
  var initCap = histPts[0].value;
  var baseY = yOf(initCap);
  ctx.strokeStyle = 'rgba(255,255,255,0.12)'; ctx.lineWidth = 1; ctx.setLineDash([6,3]);
  ctx.beginPath(); ctx.moveTo(PAD.left, baseY); ctx.lineTo(w - PAD.right, baseY); ctx.stroke();
  ctx.setLineDash([]);

  // Vertical divider: train/test split
  if (splitIdx > 0) {
    var sx = xOf(splitIdx);
    ctx.strokeStyle = 'rgba(255,152,0,0.3)'; ctx.lineWidth = 1; ctx.setLineDash([4,3]);
    ctx.beginPath(); ctx.moveTo(sx, PAD.top); ctx.lineTo(sx, PAD.top + cH); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = 'rgba(255,152,0,0.5)'; ctx.font = '9px sans-serif'; ctx.textAlign = 'center';
    ctx.fillText('测试起点', sx, PAD.top - 4);
  }

  // Vertical divider: projection start
  if (projPts.length > 0) {
    var px = xOf(projStartIdx - 1);
    ctx.strokeStyle = 'rgba(255,213,79,0.3)'; ctx.lineWidth = 1; ctx.setLineDash([4,3]);
    ctx.beginPath(); ctx.moveTo(px, PAD.top); ctx.lineTo(px, PAD.top + cH); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = 'rgba(255,213,79,0.5)'; ctx.font = '9px sans-serif'; ctx.textAlign = 'center';
    ctx.fillText('预测起点', px, PAD.top - 4);
  }

  // Draw training equity (blue)
  var trainEnd = splitIdx > 0 ? splitIdx : histPts.length;
  ctx.beginPath();
  for (var i = 0; i < trainEnd; i++) {
    var x = xOf(i), y = yOf(histPts[i].value);
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  }
  ctx.strokeStyle = '#42a5f5'; ctx.lineWidth = 2; ctx.stroke();

  // Draw test equity (orange)
  if (splitIdx > 0 && splitIdx < histPts.length) {
    ctx.beginPath();
    for (var i = splitIdx > 0 ? splitIdx - 1 : 0; i < histPts.length; i++) {
      var x = xOf(i), y = yOf(histPts[i].value);
      i === (splitIdx > 0 ? splitIdx - 1 : 0) ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.strokeStyle = '#ff9800'; ctx.lineWidth = 2; ctx.stroke();
  }

  // Draw projected equity (gold, dashed)
  if (projPts.length > 1) {
    ctx.beginPath();
    ctx.setLineDash([6, 4]);
    var projOffset = projStartIdx - 1;
    for (var i = 0; i < projPts.length; i++) {
      var x = xOf(projOffset + i), y = yOf(projPts[i].value);
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.strokeStyle = '#ffd54f'; ctx.lineWidth = 2.5; ctx.stroke();
    ctx.setLineDash([]);

    // End value label
    var lastPt = projPts[projPts.length - 1];
    var endX = xOf(projOffset + projPts.length - 1);
    var endY = yOf(lastPt.value);
    var retPct = ((lastPt.value - initCap) / initCap * 100);
    ctx.fillStyle = '#ffd54f'; ctx.font = 'bold 11px monospace'; ctx.textAlign = 'left';
    ctx.fillText((retPct >= 0 ? '+' : '') + retPct.toFixed(1) + '%', endX + 4, endY + 4);
  }

  // End value of historical
  if (histPts.length > 0) {
    var lastH = histPts[histPts.length - 1];
    var hx = xOf(histPts.length - 1);
    var hy = yOf(lastH.value);
    var hRet = ((lastH.value - initCap) / initCap * 100);
    var hColor = splitIdx > 0 ? '#ff9800' : '#42a5f5';
    ctx.fillStyle = hColor; ctx.font = 'bold 10px monospace'; ctx.textAlign = 'left';
    ctx.fillText((hRet >= 0 ? '+' : '') + hRet.toFixed(1) + '%', hx + 4, hy - 6);
  }
}

/* ======= Trade Table ======= */
function fillTradeTable(d) {
  var tbody = document.getElementById('tradeBody');
  var rows = '';
  var trades = d.trades || [];
  for (var i = 0; i < trades.length; i++) {
    var t = trades[i];
    var cls = t.action === 'BUY' ? 'buy-tag' : 'sell-tag';
    var actionText = t.action === 'BUY' ? '买入' : '卖出';
    var profitCell = '';
    if (t.action === 'SELL' && t.profit != null) {
      var pc = t.profit >= 0 ? '#ef5350' : '#26a69a';
      profitCell = '<span style="color:' + pc + '">' + (t.profit >= 0 ? '+' : '') + t.profit.toFixed(2) + '</span>';
    } else {
      profitCell = '-';
    }
    rows += '<tr>' +
      '<td>' + t.date + '</td>' +
      '<td class="' + cls + '">' + actionText + '</td>' +
      '<td>' + t.price.toFixed(2) + '</td>' +
      '<td>' + t.quantity + '</td>' +
      '<td>' + profitCell + '</td>' +
    '</tr>';
  }
  tbody.innerHTML = rows;
}
</script>
</body>
</html>`;
    }

    dispose(): void {
        // nothing to clean up
    }
}
