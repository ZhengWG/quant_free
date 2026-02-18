/**
 * 预测分析视图
 */

import * as vscode from 'vscode';
import { ApiClient } from '../services/apiClient';
import { PredictionParams, PredictionResult, PredictionItem } from '../types/strategy';

export class PredictionView {
    private context: vscode.ExtensionContext;
    private apiClient: ApiClient;

    constructor(context: vscode.ExtensionContext, apiClient: ApiClient) {
        this.context = context;
        this.apiClient = apiClient;
    }

    async run(): Promise<void> {
        const poolPick = await vscode.window.showQuickPick(
            [
                { label: '沪深热门', value: 'hot_hs', description: '80只沪深热门股票' },
                { label: '行业龙头', value: 'industry_leaders', description: '60只各行业龙头' },
                { label: '港股热门', value: 'hot_hk', description: '30只港股热门' },
                { label: 'A股+港股', value: 'hs_and_hk', description: '合并筛选' },
                { label: '自定义', value: 'custom', description: '手动输入股票代码' },
            ],
            { placeHolder: '请选择股票池' }
        );
        if (!poolPick) { return; }

        let customCodes: string | undefined;
        if (poolPick.value === 'custom') {
            customCodes = await vscode.window.showInputBox({
                prompt: '请输入股票代码（逗号分隔，港股加HK前缀）',
                placeHolder: '例如：600519,000858,HK00700',
                validateInput: (v) => v.trim() ? null : '请输入至少一个股票代码',
            });
            if (!customCodes) { return; }
        }

        const monthPick = await vscode.window.showQuickPick(
            [
                { label: '3个月', value: '3', description: '短期预测' },
                { label: '6个月', value: '6', description: '中期预测（推荐）' },
                { label: '12个月', value: '12', description: '长期预测' },
            ],
            { placeHolder: '请选择预测周期' }
        );
        if (!monthPick) { return; }

        const topNStr = await vscode.window.showInputBox({
            prompt: '展示 Top N 只股票',
            value: '10',
            validateInput: v => isNaN(Number(v)) || Number(v) < 1 ? '请输入正整数' : null,
        });
        if (!topNStr) { return; }

        const params: PredictionParams = {
            stockPool: poolPick.value,
            customCodes,
            predictionMonths: Number(monthPick.value),
            topN: Number(topNStr),
        };

        await vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: '预测分析中...',
                cancellable: false,
            },
            async (progress) => {
                progress.report({ message: '正在获取数据、计算因子、回测并生成预测，请耐心等待...' });
                try {
                    const result = await this.apiClient.runPrediction(params);
                    this.showResultWebView(result);
                } catch (error: any) {
                    const message = error.response?.data?.detail || error.message || '预测分析失败';
                    vscode.window.showErrorMessage(`预测分析失败：${message}`);
                }
            }
        );
    }

    private showResultWebView(result: PredictionResult): void {
        const panel = vscode.window.createWebviewPanel(
            'quantFreePrediction',
            `预测分析 - ${result.poolName} (${result.predictionMonths}个月)`,
            vscode.ViewColumn.One,
            { enableScripts: true }
        );
        panel.webview.html = this.getResultsHtml(result);
    }

    private getResultsHtml(result: PredictionResult): string {
        const r = result;

        const overviewCards = [
            { label: '分析股票数', value: `${r.totalAnalyzed}` },
            { label: '预测周期', value: `${r.predictionMonths} 个月` },
            { label: '入选股票', value: `${r.rankings.length}` },
            { label: '耗时', value: `${r.timeTakenSeconds}s` },
        ];
        const overviewHtml = overviewCards.map(c =>
            `<div class="card"><div class="card-label">${c.label}</div><div class="card-value">${c.value}</div></div>`
        ).join('\n');

        const signalIcon = (s: string) => s === '看涨' ? '▲' : s === '看跌' ? '▼' : '◆';
        const signalColor = (s: string) => s === '看涨' ? '#ef5350' : s === '看跌' ? '#26a69a' : '#ffa726';
        const retColor = (v: number) => v >= 0 ? '#ef5350' : '#26a69a';
        const confColor = (c: string) => c === '高' ? '#ffd54f' : c === '中' ? '#81c784' : '#90a4ae';

        const rankRowsHtml = r.rankings.map((item, idx) => {
            return `<tr data-idx="${idx}">
                <td style="font-weight:700;text-align:center">${item.rank}</td>
                <td>${item.stockCode}</td>
                <td>${item.stockName}</td>
                <td style="color:${signalColor(item.signal)};font-weight:700">${signalIcon(item.signal)} ${item.signal}</td>
                <td style="color:${retColor(item.predictedReturnPct)};font-weight:600">${item.predictedReturnPct >= 0 ? '+' : ''}${item.predictedReturnPct.toFixed(2)}%</td>
                <td>${item.fundamental.peDynamic != null ? item.fundamental.peDynamic.toFixed(1) : '-'}</td>
                <td>${item.fundamental.pb != null ? item.fundamental.pb.toFixed(2) : '-'}</td>
                <td>${item.fundamental.marketCapYi != null ? item.fundamental.marketCapYi.toFixed(0) + '亿' : '-'}</td>
                <td>${item.bestStrategyLabel}</td>
                <td style="color:${confColor(item.confidence)};font-weight:600">${item.confidence}</td>
                <td style="font-weight:700">${item.compositeScore.toFixed(1)}</td>
                <td>${item.fitScore.toFixed(1)}</td>
            </tr>`;
        }).join('\n');

        const dataJson = JSON.stringify(r.rankings.map(item => ({
            stockCode: item.stockCode,
            stockName: item.stockName,
            signal: item.signal,
            confidence: item.confidence,
            fundamental: item.fundamental,
            scores: {
                valuation: item.valuationScore,
                trend: item.trendScore,
                momentum: item.momentumScore,
                volatility: item.volatilityScore,
                volume: item.volumeScore,
                composite: item.compositeScore,
            },
            predictedReturnPct: item.predictedReturnPct,
            predictedAnnualReturnPct: item.predictedAnnualReturnPct,
            historicalReturnPct: item.historicalReturnPct,
            bestStrategyLabel: item.bestStrategyLabel,
            fitScore: item.fitScore,
            monthlyReturnMean: item.monthlyReturnMean,
            monthlyReturnStd: item.monthlyReturnStd,
            historicalPrices: item.historicalPrices,
            projectedPrices: item.projectedPrices,
            projectedPricesOpt: item.projectedPricesOptimistic,
            projectedPricesPes: item.projectedPricesPessimistic,
            projectedEquity: item.projectedEquity,
            projectedEquityOpt: item.projectedEquityOptimistic,
            projectedEquityPes: item.projectedEquityPessimistic,
            historicalEquity: item.historicalEquity,
        })));

        return /*html*/`<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>预测分析结果</title>
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
    display: grid; grid-template-columns: repeat(4, 1fr);
    gap: 12px; padding: 16px 20px;
  }
  .card {
    background: var(--vscode-editorWidget-background, #252526);
    border: 1px solid var(--vscode-panel-border, #333);
    border-radius: 6px; padding: 12px 16px;
  }
  .card-label { font-size: 11px; opacity: 0.6; margin-bottom: 4px; }
  .card-value { font-size: 18px; font-weight: 600; font-family: monospace; }
  .table-container { overflow-y: auto; padding: 0 20px; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td {
    padding: 7px 10px; text-align: left;
    border-bottom: 1px solid var(--vscode-panel-border, #333);
  }
  th {
    font-weight: 600; opacity: 0.7; font-size: 10px;
    text-transform: uppercase; position: sticky; top: 0;
    background: var(--vscode-editor-background, #1e1e1e);
  }
  td { font-family: monospace; }
  #rankBody tr:hover { background: rgba(128,128,128,0.1); cursor: pointer; }

  /* Detail panel */
  #detailPanel {
    display: none;
    border-top: 2px solid var(--vscode-panel-border, #333);
    padding: 16px 20px; margin-top: 12px;
  }
  .detail-header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 14px;
  }
  .detail-header h3 { font-size: 15px; }
  .detail-close {
    cursor: pointer; font-size: 12px; padding: 4px 12px;
    border: 1px solid var(--vscode-panel-border, #555);
    border-radius: 4px; background: transparent;
    color: var(--vscode-editor-foreground, #d4d4d4);
  }
  .detail-close:hover { background: rgba(128,128,128,0.2); }

  .detail-metrics {
    display: grid; grid-template-columns: repeat(3, 1fr);
    gap: 8px; margin-bottom: 16px;
  }
  .metric {
    background: var(--vscode-editorWidget-background, #252526);
    border: 1px solid var(--vscode-panel-border, #333);
    border-radius: 4px; padding: 8px 10px; text-align: center;
  }
  .metric .ml { font-size: 10px; opacity: 0.5; }
  .metric .mv { font-size: 14px; font-weight: 600; font-family: monospace; }

  .score-bars {
    display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap;
  }
  .score-bar {
    flex: 1; min-width: 100px;
  }
  .score-bar .sb-label { font-size: 10px; opacity: 0.6; margin-bottom: 3px; }
  .sb-track {
    height: 8px; background: rgba(128,128,128,0.15); border-radius: 4px;
    overflow: hidden; position: relative;
  }
  .sb-fill {
    height: 100%; border-radius: 4px;
    transition: width 0.5s ease;
  }
  .sb-val { font-size: 10px; font-weight: 600; margin-top: 2px; text-align: right; }

  .chart-title {
    font-size: 12px; font-weight: 600; opacity: 0.7;
    margin: 12px 0 6px;
  }
  canvas { display: block; margin-bottom: 8px; }
  .disclaimer {
    font-size: 10px; opacity: 0.4; padding: 8px 20px; text-align: center;
  }
</style>
</head>
<body>
<div class="header">
  <h2>预测分析</h2>
  <span class="info">股票池: ${r.poolName} | 预测周期: ${r.predictionMonths}个月</span>
</div>
<div class="overview">${overviewHtml}</div>
<div class="table-container">
  <table>
    <thead><tr>
      <th>排名</th><th>代码</th><th>名称</th><th>信号</th>
      <th>预测收益</th><th>PE</th><th>PB</th><th>市值</th>
      <th>最优策略</th><th>置信度</th><th>综合分</th><th>拟合度</th>
    </tr></thead>
    <tbody id="rankBody">${rankRowsHtml}</tbody>
  </table>
</div>

<div id="detailPanel">
  <div class="detail-header">
    <h3 id="detailTitle"></h3>
    <button class="detail-close" id="detailClose">收起</button>
  </div>
  <div class="detail-metrics" id="detailMetrics"></div>
  <div class="score-bars" id="scoreBars"></div>

  <div class="chart-title">历史价格 + 预测走势（含置信区间）</div>
  <canvas id="priceCanvas"></canvas>

  <div class="chart-title">历史策略权益曲线（回测拟合）</div>
  <canvas id="histEqCanvas"></canvas>

  <div class="chart-title">预测资金曲线（含乐观/悲观边界）</div>
  <canvas id="equityCanvas"></canvas>
</div>

<div class="disclaimer">
  以上预测基于多因子量化模型与历史回测，仅供参考，不构成投资建议。股市有风险，投资需谨慎。
</div>

<script>
var RD = ${dataJson};
var dpr = window.devicePixelRatio || 1;
var PAD = { top: 24, right: 64, bottom: 36, left: 24 };

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

  var sigColor = d.signal === '看涨' ? '#ef5350' : d.signal === '看跌' ? '#26a69a' : '#ffa726';
  document.getElementById('detailTitle').innerHTML =
    d.stockCode + ' ' + d.stockName +
    ' <span style="color:' + sigColor + ';font-size:13px">' + d.signal + '</span>';

  var retC = d.predictedReturnPct >= 0 ? '#ef5350' : '#26a69a';
  var confC = d.confidence === '高' ? '#ffd54f' : d.confidence === '中' ? '#81c784' : '#90a4ae';
  var fitC = d.fitScore >= 60 ? '#66bb6a' : d.fitScore >= 30 ? '#ffa726' : '#ef5350';
  document.getElementById('detailMetrics').innerHTML =
    mc('预测收益', (d.predictedReturnPct >= 0 ? '+' : '') + d.predictedReturnPct.toFixed(2) + '%', retC) +
    mc('年化收益', (d.predictedAnnualReturnPct >= 0 ? '+' : '') + d.predictedAnnualReturnPct.toFixed(2) + '%', retC) +
    mc('历史回测', (d.historicalReturnPct >= 0 ? '+' : '') + d.historicalReturnPct.toFixed(2) + '%') +
    mc('最优策略', d.bestStrategyLabel) +
    mc('置信度', d.confidence, confC) +
    mc('综合评分', d.scores.composite.toFixed(1)) +
    mc('拟合度 R²', d.fitScore.toFixed(1) + '%', fitC) +
    mc('月均收益', (d.monthlyReturnMean >= 0 ? '+' : '') + d.monthlyReturnMean.toFixed(2) + '%') +
    mc('月收益σ', d.monthlyReturnStd.toFixed(2) + '%');

  // Score bars
  var bars = [
    { label: '估值因子', value: d.scores.valuation, color: '#42a5f5' },
    { label: '趋势因子', value: d.scores.trend, color: '#66bb6a' },
    { label: '动量因子', value: d.scores.momentum, color: '#ffa726' },
    { label: '波动因子', value: d.scores.volatility, color: '#ab47bc' },
    { label: '量能因子', value: d.scores.volume, color: '#26c6da' },
  ];
  document.getElementById('scoreBars').innerHTML = bars.map(function(b) {
    return '<div class="score-bar">' +
      '<div class="sb-label">' + b.label + '</div>' +
      '<div class="sb-track"><div class="sb-fill" style="width:' + b.value + '%;background:' + b.color + '"></div></div>' +
      '<div class="sb-val" style="color:' + b.color + '">' + b.value.toFixed(1) + '</div>' +
    '</div>';
  }).join('');

  drawPriceChart(d);
  drawHistEqChart(d);
  drawEquityChart(d);
  panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function mc(label, value, color) {
  var c = color ? ' style="color:' + color + '"' : '';
  return '<div class="metric"><div class="ml">' + label + '</div><div class="mv"' + c + '>' + value + '</div></div>';
}

/* ===== Helpers ===== */
function initCanvas(id, h) {
  var canvas = document.getElementById(id);
  var ctx = canvas.getContext('2d');
  var w = window.innerWidth - 60;
  canvas.width = w * dpr; canvas.height = h * dpr;
  canvas.style.width = w + 'px'; canvas.style.height = h + 'px';
  ctx.setTransform(1,0,0,1,0,0); ctx.scale(dpr, dpr);
  ctx.clearRect(0,0,w,h);
  return { ctx: ctx, w: w, h: h };
}
function drawGrid(ctx, w, h, minV, maxV, rows) {
  var cH = h - PAD.top - PAD.bottom;
  ctx.strokeStyle = 'rgba(128,128,128,0.12)'; ctx.lineWidth = 1; ctx.setLineDash([4,4]);
  ctx.fillStyle = 'rgba(128,128,128,0.6)'; ctx.font = '10px monospace'; ctx.textAlign = 'right';
  for (var g = 0; g <= rows; g++) {
    var gy = PAD.top + cH * g / rows;
    var gv = maxV - (maxV - minV) * g / rows;
    ctx.beginPath(); ctx.moveTo(PAD.left, gy); ctx.lineTo(w - PAD.right, gy); ctx.stroke();
    ctx.fillText(gv.toFixed(gv > 10000 ? 0 : 2), w - 6, gy + 4);
  }
  ctx.setLineDash([]);
}

/* ===== Price + Projection Chart with confidence band ===== */
function drawPriceChart(d) {
  var c = initCanvas('priceCanvas', 320);
  var ctx = c.ctx, w = c.w, h = c.h;

  var hp = d.historicalPrices || [];
  var pp = d.projectedPrices || [];
  var ppOpt = d.projectedPricesOpt || [];
  var ppPes = d.projectedPricesPes || [];
  if (hp.length < 2) {
    ctx.fillStyle = 'rgba(128,128,128,0.5)'; ctx.font = '13px sans-serif';
    ctx.fillText('暂无数据', w/2 - 30, h/2); return;
  }

  var all = hp.concat(pp.slice(1));
  var allOpt = hp.concat(ppOpt.slice(1));
  var allPes = hp.concat(ppPes.slice(1));
  var allVals = all.map(function(p){ return p.value; })
    .concat(allOpt.map(function(p){ return p.value; }))
    .concat(allPes.map(function(p){ return p.value; }));
  var minV = Math.min.apply(null, allVals);
  var maxV = Math.max.apply(null, allVals);
  var pad = (maxV - minV) * 0.08 || maxV * 0.02;
  minV -= pad; maxV += pad;
  var cW = w - PAD.left - PAD.right;
  var cH = h - PAD.top - PAD.bottom;
  var range = maxV - minV || 1;
  var N = all.length;

  function xOf(i) { return PAD.left + cW * i / Math.max(1, N - 1); }
  function yOf(v) { return PAD.top + cH * (1 - (v - minV) / range); }

  drawGrid(ctx, w, h, minV, maxV, 5);

  // X labels
  ctx.fillStyle = 'rgba(128,128,128,0.6)'; ctx.font = '10px monospace'; ctx.textAlign = 'center';
  var xStep = Math.max(1, Math.floor(N / 7));
  for (var i = 0; i < N; i += xStep) ctx.fillText(all[i].date, xOf(i), h - PAD.bottom + 14);

  var divIdx = hp.length - 1;
  var divX = xOf(divIdx);

  // Vertical divider
  ctx.strokeStyle = 'rgba(255,255,255,0.2)'; ctx.lineWidth = 1; ctx.setLineDash([6,3]);
  ctx.beginPath(); ctx.moveTo(divX, PAD.top); ctx.lineTo(divX, PAD.top + cH); ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = 'rgba(255,255,255,0.3)'; ctx.font = '10px sans-serif'; ctx.textAlign = 'left';
  ctx.fillText('← 历史', divX - 50, PAD.top + 12);
  ctx.fillText('预测 →', divX + 6, PAD.top + 12);

  // Historical fill + line
  var grad1 = ctx.createLinearGradient(0, PAD.top, 0, PAD.top + cH);
  grad1.addColorStop(0, 'rgba(66,165,245,0.18)'); grad1.addColorStop(1, 'rgba(66,165,245,0.01)');
  ctx.beginPath();
  for (var i = 0; i <= divIdx; i++) { var x = xOf(i), y = yOf(hp[i].value); i===0?ctx.moveTo(x,y):ctx.lineTo(x,y); }
  ctx.lineTo(xOf(divIdx), PAD.top+cH); ctx.lineTo(xOf(0), PAD.top+cH);
  ctx.closePath(); ctx.fillStyle = grad1; ctx.fill();
  ctx.beginPath();
  for (var i = 0; i <= divIdx; i++) { var x = xOf(i), y = yOf(hp[i].value); i===0?ctx.moveTo(x,y):ctx.lineTo(x,y); }
  ctx.strokeStyle = '#42a5f5'; ctx.lineWidth = 1.8; ctx.stroke();

  // Confidence band (optimistic/pessimistic fill)
  if (ppOpt.length > 1 && ppPes.length > 1) {
    ctx.beginPath();
    for (var i = divIdx; i < allOpt.length; i++) { var x=xOf(i),y=yOf(allOpt[i].value); i===divIdx?ctx.moveTo(x,y):ctx.lineTo(x,y); }
    for (var i = allPes.length-1; i >= divIdx; i--) { ctx.lineTo(xOf(i), yOf(allPes[i].value)); }
    ctx.closePath();
    ctx.fillStyle = 'rgba(255,193,7,0.12)'; ctx.fill();

    // Optimistic dashed
    ctx.beginPath();
    for (var i = divIdx; i < allOpt.length; i++) { var x=xOf(i),y=yOf(allOpt[i].value); i===divIdx?ctx.moveTo(x,y):ctx.lineTo(x,y); }
    ctx.strokeStyle = 'rgba(255,193,7,0.5)'; ctx.lineWidth = 1; ctx.setLineDash([3,3]); ctx.stroke(); ctx.setLineDash([]);

    // Pessimistic dashed
    ctx.beginPath();
    for (var i = divIdx; i < allPes.length; i++) { var x=xOf(i),y=yOf(allPes[i].value); i===divIdx?ctx.moveTo(x,y):ctx.lineTo(x,y); }
    ctx.strokeStyle = 'rgba(255,193,7,0.5)'; ctx.lineWidth = 1; ctx.setLineDash([3,3]); ctx.stroke(); ctx.setLineDash([]);
  }

  // Base projection line + dots
  var projUp = pp.length > 1 && pp[pp.length-1].value >= pp[0].value;
  ctx.beginPath();
  for (var i = divIdx; i < N; i++) { var x=xOf(i),y=yOf(all[i].value); i===divIdx?ctx.moveTo(x,y):ctx.lineTo(x,y); }
  ctx.strokeStyle = projUp ? '#4caf50' : '#ef5350';
  ctx.lineWidth = 2; ctx.setLineDash([6,4]); ctx.stroke(); ctx.setLineDash([]);
  for (var i = divIdx+1; i < N; i++) {
    ctx.beginPath(); ctx.arc(xOf(i), yOf(all[i].value), 3, 0, Math.PI*2);
    ctx.fillStyle = projUp ? '#4caf50' : '#ef5350'; ctx.fill();
  }

  // End labels
  if (N > 0) {
    var last = all[N-1]; ctx.fillStyle = projUp ? '#4caf50' : '#ef5350';
    ctx.font = '11px monospace'; ctx.textAlign = 'left';
    ctx.fillText(last.value.toFixed(2), xOf(N-1)+6, yOf(last.value)+4);
  }
  if (allOpt.length > divIdx+1) {
    ctx.fillStyle = 'rgba(255,193,7,0.7)'; ctx.font = '9px monospace'; ctx.textAlign = 'left';
    ctx.fillText('乐观 ' + allOpt[allOpt.length-1].value.toFixed(2), xOf(N-1)+6, yOf(allOpt[allOpt.length-1].value)-4);
    ctx.fillText('悲观 ' + allPes[allPes.length-1].value.toFixed(2), xOf(N-1)+6, yOf(allPes[allPes.length-1].value)+12);
  }

  // Fit score badge
  var fitC = d.fitScore >= 60 ? '#66bb6a' : d.fitScore >= 30 ? '#ffa726' : '#ef5350';
  ctx.fillStyle = fitC; ctx.font = 'bold 11px sans-serif'; ctx.textAlign = 'left';
  ctx.fillText('R² 拟合度: ' + d.fitScore.toFixed(1) + '%', PAD.left + 4, PAD.top + 12);
}

/* ===== Historical Equity Curve (backtest fit) ===== */
function drawHistEqChart(d) {
  var heq = d.historicalEquity || [];
  if (heq.length < 3) return;

  var c = initCanvas('histEqCanvas', 240);
  var ctx = c.ctx, w = c.w, h = c.h;

  var vals = heq.map(function(p){ return p.value; });
  var minV = Math.min.apply(null, vals);
  var maxV = Math.max.apply(null, vals);
  var pad = (maxV - minV) * 0.06 || maxV * 0.02;
  minV -= pad; maxV += pad;
  var cW = w - PAD.left - PAD.right;
  var cH = h - PAD.top - PAD.bottom;
  var range = maxV - minV || 1;
  var N = heq.length;

  function xOf(i) { return PAD.left + cW * i / Math.max(1, N-1); }
  function yOf(v) { return PAD.top + cH * (1 - (v - minV) / range); }

  drawGrid(ctx, w, h, minV, maxV, 4);

  // X labels
  ctx.fillStyle = 'rgba(128,128,128,0.6)'; ctx.font = '10px monospace'; ctx.textAlign = 'center';
  var xStep = Math.max(1, Math.floor(N / 6));
  for (var i = 0; i < N; i += xStep) ctx.fillText(heq[i].date, xOf(i), h - PAD.bottom + 14);

  // Linear regression line (visual fit)
  var sumX=0,sumY=0,sumXY=0,sumX2=0;
  for (var i=0;i<N;i++) { sumX+=i; sumY+=vals[i]; sumXY+=i*vals[i]; sumX2+=i*i; }
  var denom = N*sumX2 - sumX*sumX;
  if (denom !== 0) {
    var b = (N*sumXY - sumX*sumY) / denom;
    var a = (sumY - b*sumX) / N;
    ctx.beginPath();
    ctx.moveTo(xOf(0), yOf(a));
    ctx.lineTo(xOf(N-1), yOf(a + b*(N-1)));
    ctx.strokeStyle = 'rgba(255,193,7,0.6)'; ctx.lineWidth = 1.5; ctx.setLineDash([8,4]); ctx.stroke(); ctx.setLineDash([]);
    ctx.fillStyle = 'rgba(255,193,7,0.6)'; ctx.font = '9px sans-serif'; ctx.textAlign = 'left';
    ctx.fillText('线性拟合', xOf(N-1)+4, yOf(a + b*(N-1))+4);
  }

  // Baseline
  var baseY = yOf(vals[0]);
  ctx.strokeStyle = 'rgba(255,255,255,0.1)'; ctx.lineWidth = 1; ctx.setLineDash([6,3]);
  ctx.beginPath(); ctx.moveTo(PAD.left, baseY); ctx.lineTo(w-PAD.right, baseY); ctx.stroke(); ctx.setLineDash([]);

  // Equity fill
  var up = vals[N-1] >= vals[0];
  var gc = up ? '66,165,245' : '239,83,80';
  var grad = ctx.createLinearGradient(0, PAD.top, 0, PAD.top+cH);
  grad.addColorStop(0, 'rgba('+gc+',0.22)'); grad.addColorStop(1, 'rgba('+gc+',0.02)');
  ctx.beginPath();
  for (var i=0;i<N;i++) { var x=xOf(i),y=yOf(vals[i]); i===0?ctx.moveTo(x,y):ctx.lineTo(x,y); }
  ctx.lineTo(xOf(N-1), PAD.top+cH); ctx.lineTo(xOf(0), PAD.top+cH);
  ctx.closePath(); ctx.fillStyle = grad; ctx.fill();

  // Equity line
  ctx.beginPath();
  for (var i=0;i<N;i++) { var x=xOf(i),y=yOf(vals[i]); i===0?ctx.moveTo(x,y):ctx.lineTo(x,y); }
  ctx.strokeStyle = up ? '#42a5f5' : '#ef5350'; ctx.lineWidth = 1.8; ctx.stroke();

  // Fit badge
  var fitC = d.fitScore >= 60 ? '#66bb6a' : d.fitScore >= 30 ? '#ffa726' : '#ef5350';
  ctx.fillStyle = fitC; ctx.font = 'bold 11px sans-serif'; ctx.textAlign = 'left';
  ctx.fillText('R² = ' + d.fitScore.toFixed(1) + '%', PAD.left + 4, PAD.top + 12);
}

/* ===== Equity Projection Chart with confidence band ===== */
function drawEquityChart(d) {
  var c = initCanvas('equityCanvas', 240);
  var ctx = c.ctx, w = c.w, h = c.h;

  var pts = d.projectedEquity || [];
  var ptsOpt = d.projectedEquityOpt || [];
  var ptsPes = d.projectedEquityPes || [];
  if (pts.length < 2) return;

  var allVals = pts.map(function(p){return p.value;})
    .concat(ptsOpt.map(function(p){return p.value;}))
    .concat(ptsPes.map(function(p){return p.value;}));
  var minV = Math.min.apply(null, allVals);
  var maxV = Math.max.apply(null, allVals);
  var pad = (maxV - minV) * 0.08 || maxV * 0.02;
  minV -= pad; maxV += pad;
  var cW = w - PAD.left - PAD.right;
  var cH = h - PAD.top - PAD.bottom;
  var range = maxV - minV || 1;
  var N = pts.length;

  function xOf(i) { return PAD.left + cW * i / Math.max(1, N-1); }
  function yOf(v) { return PAD.top + cH * (1 - (v - minV) / range); }

  drawGrid(ctx, w, h, minV, maxV, 4);

  // X labels
  ctx.fillStyle = 'rgba(128,128,128,0.6)'; ctx.font = '10px monospace'; ctx.textAlign = 'center';
  for (var i = 0; i < N; i++) ctx.fillText(pts[i].date, xOf(i), h - PAD.bottom + 14);

  // Baseline
  ctx.strokeStyle = 'rgba(255,255,255,0.15)'; ctx.lineWidth = 1; ctx.setLineDash([6,3]);
  ctx.beginPath(); ctx.moveTo(PAD.left, yOf(pts[0].value)); ctx.lineTo(w-PAD.right, yOf(pts[0].value)); ctx.stroke();
  ctx.setLineDash([]);

  // Confidence band fill
  if (ptsOpt.length > 1 && ptsPes.length > 1) {
    ctx.beginPath();
    for (var i=0;i<ptsOpt.length;i++) { var x=xOf(i),y=yOf(ptsOpt[i].value); i===0?ctx.moveTo(x,y):ctx.lineTo(x,y); }
    for (var i=ptsPes.length-1;i>=0;i--) { ctx.lineTo(xOf(i), yOf(ptsPes[i].value)); }
    ctx.closePath(); ctx.fillStyle = 'rgba(255,193,7,0.12)'; ctx.fill();

    // Opt/Pes dashed lines
    ctx.beginPath();
    for (var i=0;i<ptsOpt.length;i++) { var x=xOf(i),y=yOf(ptsOpt[i].value); i===0?ctx.moveTo(x,y):ctx.lineTo(x,y); }
    ctx.strokeStyle = 'rgba(255,193,7,0.5)'; ctx.lineWidth = 1; ctx.setLineDash([3,3]); ctx.stroke(); ctx.setLineDash([]);
    ctx.beginPath();
    for (var i=0;i<ptsPes.length;i++) { var x=xOf(i),y=yOf(ptsPes[i].value); i===0?ctx.moveTo(x,y):ctx.lineTo(x,y); }
    ctx.strokeStyle = 'rgba(255,193,7,0.5)'; ctx.lineWidth = 1; ctx.setLineDash([3,3]); ctx.stroke(); ctx.setLineDash([]);
  }

  // Base line + dots
  var vals = pts.map(function(p){return p.value;});
  var up = vals[N-1] >= vals[0];
  ctx.beginPath();
  for (var i=0;i<N;i++) { var x=xOf(i),y=yOf(vals[i]); i===0?ctx.moveTo(x,y):ctx.lineTo(x,y); }
  ctx.strokeStyle = up ? '#4caf50' : '#ef5350'; ctx.lineWidth = 2; ctx.setLineDash([6,4]); ctx.stroke(); ctx.setLineDash([]);

  for (var i=0;i<N;i++) {
    var x=xOf(i),y=yOf(vals[i]);
    ctx.beginPath(); ctx.arc(x,y,4,0,Math.PI*2);
    ctx.fillStyle = up ? '#4caf50' : '#ef5350'; ctx.fill();
    ctx.fillStyle = 'rgba(255,255,255,0.7)'; ctx.font = '10px monospace'; ctx.textAlign = 'center';
    ctx.fillText(vals[i].toFixed(0), x, y - 8);
  }

  // End labels for bands
  if (ptsOpt.length > 1) {
    ctx.fillStyle = 'rgba(255,193,7,0.7)'; ctx.font = '9px monospace'; ctx.textAlign = 'left';
    ctx.fillText('乐观 ' + ptsOpt[ptsOpt.length-1].value.toFixed(0), xOf(N-1)+6, yOf(ptsOpt[ptsOpt.length-1].value));
    ctx.fillText('悲观 ' + ptsPes[ptsPes.length-1].value.toFixed(0), xOf(N-1)+6, yOf(ptsPes[ptsPes.length-1].value)+10);
  }
}
</script>
</body>
</html>`;
    }

    dispose(): void {
        // nothing to clean up
    }
}
