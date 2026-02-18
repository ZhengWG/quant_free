/**
 * 策略测试视图（Walk-Forward Validation）v2
 * 支持 买入持有基准 + Alpha + CAGR 预测
 */

import * as vscode from 'vscode';
import { ApiClient } from '../services/apiClient';
import { StrategyTestParams, StrategyTestResult } from '../types/strategy';

export class StrategyTestView {
    private context: vscode.ExtensionContext;
    private apiClient: ApiClient;

    constructor(context: vscode.ExtensionContext, apiClient: ApiClient) {
        this.context = context;
        this.apiClient = apiClient;
    }

    async run(): Promise<void> {
        const stockCode = await vscode.window.showInputBox({
            prompt: '请输入股票代码',
            placeHolder: '例如：600519, 000858, HK00700',
            validateInput: v => v.trim() ? null : '请输入股票代码',
        });
        if (!stockCode) { return; }

        const now = new Date();
        const defaultEnd = now.toISOString().slice(0, 10);

        const rangePick = await vscode.window.showQuickPick(
            [
                { label: '近1年', value: '1', description: `${this._dateNYearsAgo(1)} ~ ${defaultEnd}` },
                { label: '近2年', value: '2', description: `${this._dateNYearsAgo(2)} ~ ${defaultEnd}` },
                { label: '近3年', value: '3', description: `${this._dateNYearsAgo(3)} ~ ${defaultEnd}` },
                { label: '近5年', value: '5', description: `${this._dateNYearsAgo(5)} ~ ${defaultEnd}` },
                { label: '自定义', value: 'custom', description: '手动输入起止日期' },
            ],
            { placeHolder: '请选择回测区间' }
        );
        if (!rangePick) { return; }

        let startDate: string;
        let endDate = defaultEnd;
        if (rangePick.value === 'custom') {
            const s = await vscode.window.showInputBox({ prompt: '开始日期 (YYYY-MM-DD)', value: this._dateNYearsAgo(3) });
            if (!s) { return; }
            const e = await vscode.window.showInputBox({ prompt: '结束日期 (YYYY-MM-DD)', value: defaultEnd });
            if (!e) { return; }
            startDate = s; endDate = e;
        } else {
            startDate = this._dateNYearsAgo(Number(rangePick.value));
        }

        const ratioPick = await vscode.window.showQuickPick(
            [
                { label: '80% / 20%', value: '0.8', description: '推荐' },
                { label: '70% / 30%', value: '0.7' },
                { label: '90% / 10%', value: '0.9' },
            ],
            { placeHolder: '训练集 / 测试集 比例' }
        );
        if (!ratioPick) { return; }

        const params: StrategyTestParams = {
            stockCode: stockCode.trim(), startDate, endDate,
            trainRatio: Number(ratioPick.value),
        };

        await vscode.window.withProgress(
            { location: vscode.ProgressLocation.Notification, title: `策略测试 ${params.stockCode} ...`, cancellable: false },
            async () => {
                try {
                    const result = await this.apiClient.runStrategyTest(params);
                    this._showResult(result);
                } catch (e: any) {
                    vscode.window.showErrorMessage(`策略测试失败：${e.message || e}`);
                }
            }
        );
    }

    private _showResult(result: StrategyTestResult) {
        const panel = vscode.window.createWebviewPanel(
            'strategyTestResult',
            `策略测试 - ${result.stockName}(${result.stockCode})`,
            vscode.ViewColumn.One,
            { enableScripts: true },
        );
        panel.webview.html = this._getHtml(result);
    }

    private _getHtml(r: StrategyTestResult): string {
        const trainPct = Math.round(r.trainRatio * 100);
        const testPct = 100 - trainPct;
        const itemsJson = JSON.stringify(r.items);

        return `<!DOCTYPE html>
<html lang="zh"><head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<style>
:root{--bg:#1e1e2e;--card:#2a2a3e;--border:#3a3a5a;--text:#e0e0e0;--text2:#999;--green:#4ec9b0;--red:#f44747;--blue:#569cd6;--yellow:#dcdcaa;--orange:#ce9178;--purple:#c586c0}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;padding:16px}
h1{font-size:20px;margin-bottom:4px}
.sub{color:var(--text2);font-size:13px;margin-bottom:16px}
.cards{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}
.card{background:var(--card);border-radius:8px;padding:14px 18px;min-width:130px;border:1px solid var(--border)}
.card .lb{font-size:11px;color:var(--text2);margin-bottom:4px}
.card .vl{font-size:20px;font-weight:700}
.green{color:var(--green)}.red{color:var(--red)}.blue{color:var(--blue)}.yellow{color:var(--yellow)}.orange{color:var(--orange)}.purple{color:var(--purple)}
table{width:100%;border-collapse:collapse;font-size:12px;margin-bottom:20px}
th{background:#2a2a4a;padding:7px 8px;text-align:left;color:var(--text2);position:sticky;top:0;white-space:nowrap}
td{padding:7px 8px;border-bottom:1px solid var(--border);white-space:nowrap}
tr:hover{background:#2e2e48;cursor:pointer}
.badge{display:inline-block;padding:2px 7px;border-radius:10px;font-size:10px;font-weight:600}
.bg{background:#1a3a2a;color:var(--green)}.br{background:#3a1a1a;color:var(--red)}.bb{background:#1a2a3a;color:var(--blue)}
.detail{display:none;background:var(--card);border-radius:10px;padding:20px;margin-bottom:20px;border:1px solid var(--border)}
.detail.active{display:block}
.detail h3{margin-bottom:10px;font-size:16px}
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:8px;margin-bottom:14px}
.mt{background:#232340;border-radius:6px;padding:9px 11px}
.mt .ml{font-size:10px;color:var(--text2)}.mt .mv{font-size:15px;font-weight:600;margin-top:2px}
.chart-row{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:14px}
.chart-box{flex:1;min-width:300px}
.chart-box h4{font-size:12px;color:var(--text2);margin-bottom:5px}
canvas{width:100%;border-radius:6px;background:#181828}
.conf-bar{height:7px;border-radius:4px;background:#333;margin-top:3px}
.conf-fill{height:100%;border-radius:4px}
</style></head><body>
<h1>📊 策略测试 - ${r.stockName}(${r.stockCode})</h1>
<div class="sub">${r.fullStart} ~ ${r.fullEnd} · 训练${trainPct}%/测试${testPct}% · ${r.totalStrategies}个策略 · 耗时${r.timeTakenSeconds}s</div>

<div class="cards">
  <div class="card"><div class="lb">平均置信度</div><div class="vl ${r.avgConfidence>=60?'green':r.avgConfidence>=40?'yellow':'red'}">${r.avgConfidence}%</div></div>
  <div class="card"><div class="lb">最佳策略</div><div class="vl blue">${r.bestStrategyLabel||'-'}</div></div>
  <div class="card"><div class="lb">全区间买入持有</div><div class="vl ${r.fullBnhPct>=0?'green':'red'}">${r.fullBnhPct.toFixed(2)}%</div></div>
  <div class="card"><div class="lb">测试期买入持有</div><div class="vl ${r.testBnhPct>=0?'green':'red'}">${r.testBnhPct.toFixed(2)}%</div></div>
</div>

<table><thead><tr>
  <th>#</th><th>策略</th><th>置信度</th><th>方向</th>
  <th>预测收益</th><th>实际收益</th><th>买入持有</th><th>Alpha</th>
  <th>误差</th><th>训练收益</th><th>训练Alpha</th><th>夏普</th>
</tr></thead><tbody id="tb"></tbody></table>
<div id="dp" class="detail"></div>

<script>
const items=${itemsJson};
const tb=document.getElementById('tb');
const dp=document.getElementById('dp');
function cc(c){return c>=60?'green':c>=40?'yellow':'red';}
function rc(v){return v>0?'var(--green)':v<0?'var(--red)':'var(--text)';}
function ac(v){return v>0?'bg':v<0?'br':'bb';}
function f(v,d){return v!=null?v.toFixed(d):'--';}
function db(dir,ok){return '<span class="badge '+(ok?'bg':'br')+'">'+dir+(ok?' ✓':' ✗')+'</span>';}

items.forEach((it,idx)=>{
  const tr=document.createElement('tr');
  tr.innerHTML=
    '<td>'+(idx+1)+'</td>'+
    '<td><b>'+it.strategyLabel+'</b></td>'+
    '<td><span style="color:var(--'+cc(it.confidenceScore)+')">'+f(it.confidenceScore,1)+'%</span>'+
      '<div class="conf-bar"><div class="conf-fill" style="width:'+it.confidenceScore+'%;background:var(--'+cc(it.confidenceScore)+')"></div></div></td>'+
    '<td>'+db(it.predictedDirection+' → '+it.actualDirection, it.directionCorrect)+'</td>'+
    '<td style="color:'+rc(it.predictedReturnPct)+'">'+f(it.predictedReturnPct,2)+'%</td>'+
    '<td style="color:'+rc(it.actualReturnPct)+'">'+(it.testHasTrades?'':'<span class="orange" style="font-size:10px">持有 </span>')+f(it.actualReturnPct,2)+'%</td>'+
    '<td style="color:'+rc(it.testBnhPct)+'">'+f(it.testBnhPct,2)+'%</td>'+
    '<td><span class="badge '+ac(it.testAlphaPct)+'">'+f(it.testAlphaPct,2)+'%</span></td>'+
    '<td>'+f(it.returnErrorPct,2)+'%</td>'+
    '<td style="color:'+rc(it.trainReturnPct)+'">'+f(it.trainReturnPct,2)+'%</td>'+
    '<td><span class="badge '+ac(it.trainAlphaPct)+'">'+f(it.trainAlphaPct,2)+'%</span></td>'+
    '<td>'+f(it.trainSharpe,2)+'</td>';
  tr.addEventListener('click',()=>showDetail(idx));
  tb.appendChild(tr);
});

function showDetail(idx){
  const it=items[idx];
  dp.className='detail active';
  let h='<h3>'+it.strategyLabel+' 策略测试详情</h3>';
  h+='<div class="metrics">';
  h+=mc('置信度',f(it.confidenceScore,1)+'%',cc(it.confidenceScore));
  h+=mc('方向预测',it.directionCorrect?'✓ 正确':'✗ 错误',it.directionCorrect?'green':'red');
  h+=mc('预测收益',f(it.predictedReturnPct,2)+'%',it.predictedReturnPct>=0?'green':'red');
  h+=mc('实际收益',f(it.actualReturnPct,2)+'%'+(it.testHasTrades?'':' (持有)'),it.actualReturnPct>=0?'green':'red');
  h+=mc('测试买入持有',f(it.testBnhPct,2)+'%',it.testBnhPct>=0?'green':'red');
  h+=mc('测试Alpha',f(it.testAlphaPct,2)+'%',it.testAlphaPct>=0?'green':'red');
  h+=mc('训练Alpha',f(it.trainAlphaPct,2)+'%',it.trainAlphaPct>=0?'green':'red');
  h+=mc('收益误差',f(it.returnErrorPct,2)+'%',it.returnErrorPct<10?'green':it.returnErrorPct<20?'yellow':'red');
  h+=mc('训练交易',it.trainTrades+'次');
  h+=mc('测试交易',it.testHasTrades?it.actualTrades+'次':'0次 (无信号)',it.testHasTrades?'':'orange');
  h+=mc('训练夏普',f(it.trainSharpe,2));
  h+=mc('测试夏普',f(it.actualSharpe,2));
  h+=mc('训练最大回撤',f(it.trainMaxDrawdown,2)+'%','red');
  h+=mc('测试最大回撤',f(it.actualMaxDrawdown,2)+'%','red');
  h+=mc('训练胜率',f(it.trainWinRate,1)+'%');
  h+='</div>';
  h+='<div class="sub">训练: '+it.trainStart+' ~ '+it.trainEnd+' ('+it.trainBars+'个交易日) · 测试: '+it.testStart+' ~ '+it.testEnd+' ('+it.testBars+'个交易日)</div>';
  h+='<div class="chart-row"><div class="chart-box"><h4>价格走势 (全区间)</h4><canvas id="pc" width="700" height="280"></canvas></div></div>';
  h+='<div class="chart-row"><div class="chart-box"><h4>权益曲线：策略(蓝/绿) vs 预测(黄虚线) vs 买入持有(紫)</h4><canvas id="ec" width="700" height="280"></canvas></div></div>';
  dp.innerHTML=h;
  dp.scrollIntoView({behavior:'smooth'});
  setTimeout(()=>{drawPrice(it);drawEquity(it);},50);
}

function mc(l,v,c){return '<div class="mt"><div class="ml">'+l+'</div><div class="mv"'+(c?' style="color:var(--'+c+')"':'')+'>'+v+'</div></div>';}

function initC(id){
  const c=document.getElementById(id);if(!c)return null;
  const d=window.devicePixelRatio||1,w=c.clientWidth||700,h=c.clientHeight||280;
  c.width=w*d;c.height=h*d;const x=c.getContext('2d');x.scale(d,d);return{x,w,h};
}
function grid(x,w,h,p,mn,mx,dt){
  x.fillStyle='#181828';x.fillRect(0,0,w,h);
  x.strokeStyle='#2a2a4a';x.lineWidth=.5;
  for(let i=0;i<5;i++){
    const y=p.t+(h-p.t-p.b)*i/4;
    x.beginPath();x.moveTo(p.l,y);x.lineTo(w-p.r,y);x.stroke();
    x.fillStyle='#888';x.font='10px sans-serif';x.textAlign='right';
    x.fillText((mx-(mx-mn)*i/4).toFixed(mx>1000?0:2),p.l-4,y+3);
  }
  if(dt&&dt.length){x.textAlign='center';x.fillStyle='#666';x.font='9px sans-serif';
    const s=Math.max(1,Math.floor(dt.length/6));
    for(let i=0;i<dt.length;i+=s){x.fillText(dt[i],p.l+(w-p.l-p.r)*i/(dt.length-1||1),h-p.b+14);}
  }
}

function drawPrice(it){
  const r=initC('pc');if(!r)return;const{x,w,h}=r;
  const pts=it.fullPriceSeries||[];if(pts.length<2)return;
  const p={t:20,r:20,b:30,l:60};
  const vs=pts.map(q=>q.value);let mn=Math.min(...vs),mx=Math.max(...vs);
  const rg=mx-mn||1;mn-=rg*.05;mx+=rg*.05;
  grid(x,w,h,p,mn,mx,pts.map(q=>q.date));
  const cw=w-p.l-p.r,ch=h-p.t-p.b;
  const tx=i=>p.l+cw*i/(pts.length-1||1);
  const ty=v=>p.t+ch*(1-(v-mn)/(mx-mn));
  let si=pts.findIndex(q=>q.date>=it.testStart);if(si<0)si=pts.length;
  if(si<pts.length){
    x.fillStyle='rgba(86,156,214,.08)';x.fillRect(tx(si),p.t,tx(pts.length-1)-tx(si),ch);
    x.strokeStyle='rgba(86,156,214,.4)';x.lineWidth=1;x.setLineDash([4,4]);
    x.beginPath();x.moveTo(tx(si),p.t);x.lineTo(tx(si),p.t+ch);x.stroke();x.setLineDash([]);
    x.fillStyle='#569cd6';x.font='10px sans-serif';x.textAlign='left';
    x.fillText('← 训练 | 测试 →',tx(si)+4,p.t+12);
  }
  x.strokeStyle='#569cd6';x.lineWidth=1.5;x.beginPath();
  for(let i=0;i<=Math.min(si,pts.length-1);i++){i===0?x.moveTo(tx(i),ty(vs[i])):x.lineTo(tx(i),ty(vs[i]));}
  x.stroke();
  if(si<pts.length){x.strokeStyle='#4ec9b0';x.lineWidth=1.5;x.beginPath();
    for(let i=Math.max(0,si-1);i<pts.length;i++){i===Math.max(0,si-1)?x.moveTo(tx(i),ty(vs[i])):x.lineTo(tx(i),ty(vs[i]));}
    x.stroke();
  }
}

function drawEquity(it){
  const r=initC('ec');if(!r)return;const{x,w,h}=r;
  const te=it.trainEquity||[],pe=it.testEquityPredicted||[],ae=it.testEquityActual||[],be=it.testEquityBnh||[];
  const all=[...te,...pe,...ae,...be];if(all.length<2)return;
  const p={t:20,r:20,b:30,l:70};
  const av=all.map(q=>q.value);let mn=Math.min(...av),mx=Math.max(...av);
  const rg=mx-mn||1;mn-=rg*.05;mx+=rg*.05;
  const ad=[...new Set(all.map(q=>q.date))].sort();
  grid(x,w,h,p,mn,mx,ad);
  const cw=w-p.l-p.r,ch=h-p.t-p.b;
  const dx=d=>{const i=ad.indexOf(d);return p.l+cw*i/(ad.length-1||1);};
  const ty=v=>p.t+ch*(1-(v-mn)/(mx-mn));
  function dl(pts,col,dash){
    if(pts.length<2)return;x.strokeStyle=col;x.lineWidth=dash?2:1.5;x.setLineDash(dash||[]);
    x.beginPath();pts.forEach((q,i)=>{const px=dx(q.date),py=ty(q.value);i===0?x.moveTo(px,py):x.lineTo(px,py);});
    x.stroke();x.setLineDash([]);
  }
  dl(te,'#569cd6',null);
  dl(pe,'#dcdcaa',[6,3]);
  dl(ae,'#4ec9b0',null);
  dl(be,'#c586c0',[3,3]);
  x.font='10px sans-serif';
  const lg=[{c:'#569cd6',l:'训练权益'},{c:'#4ec9b0',l:'实际权益'},{c:'#dcdcaa',l:'预测权益'},{c:'#c586c0',l:'买入持有'}];
  let lx=p.l+8;lg.forEach(({c,l})=>{x.fillStyle=c;x.fillRect(lx,p.t+4,10,3);lx+=13;x.fillText(l,lx,p.t+9);lx+=60;});
  [pe,ae,be].forEach((pts,i)=>{if(!pts.length)return;const last=pts[pts.length-1];
    const cols=['#dcdcaa','#4ec9b0','#c586c0'];const lbs=['预测','实际','持有'];
    x.fillStyle=cols[i];x.font='10px sans-serif';x.textAlign='right';
    x.fillText(lbs[i]+': '+last.value.toFixed(0),w-p.r,ty(last.value)-4+i*14);
  });
}
</script></body></html>`;
    }

    private _dateNYearsAgo(n: number): string {
        const d = new Date();
        d.setFullYear(d.getFullYear() - n);
        return d.toISOString().slice(0, 10);
    }

    dispose() {}
}
