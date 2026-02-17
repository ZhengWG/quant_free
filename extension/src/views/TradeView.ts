/**
 * 交易执行视图
 */

import * as vscode from 'vscode';
import { ApiClient } from '../services/apiClient';
import { StorageService } from '../services/storage';
import { Order, Position } from '../types/trade';
import { validateOrder } from '../utils/validators';

export class TradeView {
    private context: vscode.ExtensionContext;
    private apiClient: ApiClient;
    private storageService: StorageService;
    private outputChannel: vscode.OutputChannel;

    constructor(
        context: vscode.ExtensionContext,
        apiClient: ApiClient,
        storageService: StorageService
    ) {
        this.context = context;
        this.apiClient = apiClient;
        this.storageService = storageService;
        this.outputChannel = vscode.window.createOutputChannel('QuantFree Trade');
        context.subscriptions.push(this.outputChannel);
    }

    async showOrderDialog(): Promise<void> {
        const stockCode = await vscode.window.showInputBox({
            prompt: '请输入股票代码',
            placeHolder: '例如：000001'
        });
        if (!stockCode) return;

        const orderType = await vscode.window.showQuickPick(['买入', '卖出'], {
            placeHolder: '选择操作类型'
        });
        if (!orderType) return;

        const priceType = await vscode.window.showQuickPick(['市价单', '限价单'], {
            placeHolder: '选择价格类型'
        });
        if (!priceType) return;

        let price: number | undefined;
        if (priceType === '限价单') {
            const priceStr = await vscode.window.showInputBox({
                prompt: '请输入价格',
                placeHolder: '例如：12.50'
            });
            if (priceStr) {
                price = parseFloat(priceStr);
            }
        }

        const quantityStr = await vscode.window.showInputBox({
            prompt: '请输入数量（股）',
            placeHolder: '例如：100'
        });
        if (!quantityStr) return;

        const quantity = parseInt(quantityStr);

        const validation = validateOrder({
            stockCode,
            quantity,
            price,
            orderType: priceType === '市价单' ? 'MARKET' : 'LIMIT'
        });

        if (!validation.valid) {
            vscode.window.showErrorMessage(validation.error || '订单验证失败');
            return;
        }

        // 确认订单
        const confirm = await vscode.window.showWarningMessage(
            `确认${orderType} ${stockCode} ${quantity}股${price ? ` @ ¥${price.toFixed(2)}` : ' (市价)'}？`,
            { modal: true },
            '确认'
        );

        if (confirm === '确认') {
            await this.placeOrder({
                stockCode,
                type: orderType === '买入' ? 'BUY' : 'SELL',
                orderType: priceType === '市价单' ? 'MARKET' : 'LIMIT',
                price,
                quantity
            });
        }
    }

    private async placeOrder(order: Partial<Order>): Promise<void> {
        this.outputChannel.show();
        this.outputChannel.appendLine('正在提交订单...');

        try {
            const result = await this.apiClient.placeOrder(order) as any;
            this.outputChannel.appendLine(`\n订单成交！`);
            this.outputChannel.appendLine(`订单号：${result.id}`);
            this.outputChannel.appendLine(`状态：${result.status}`);
            this.outputChannel.appendLine(`成交价：¥${(result.filled_price ?? 0).toFixed(2)} (滑点 ${(result.slippage ?? 0).toFixed(3)}%)`);
            this.outputChannel.appendLine(`─── 费用明细 ───`);
            this.outputChannel.appendLine(`  佣金：¥${(result.commission ?? 0).toFixed(2)}`);
            this.outputChannel.appendLine(`  印花税：¥${(result.stamp_tax ?? 0).toFixed(2)}`);
            this.outputChannel.appendLine(`  过户费：¥${(result.transfer_fee ?? 0).toFixed(2)}`);
            this.outputChannel.appendLine(`  总费用：¥${(result.total_fee ?? 0).toFixed(2)}`);
            vscode.window.showInformationMessage(`成交 @¥${(result.filled_price ?? 0).toFixed(2)}，费用 ¥${(result.total_fee ?? 0).toFixed(2)}`);
        } catch (error: any) {
            const detail = error.response?.data?.detail || error.message || '下单失败';
            this.outputChannel.appendLine(`\n错误：${detail}`);
            vscode.window.showErrorMessage(`下单失败：${detail}`);
        }
    }

    async refreshPositions(): Promise<void> {
        try {
            const positions = await this.apiClient.getPositions();
            this.outputChannel.show();
            this.outputChannel.appendLine('=== 当前持仓 ===');
            if (positions.length === 0) {
                this.outputChannel.appendLine('暂无持仓');
            } else {
                positions.forEach((p: any) => {
                    const name = p.stock_name ?? p.stockName;
                    const code = p.stock_code ?? p.stockCode;
                    const qty = p.quantity;
                    const cost = p.cost_price ?? p.costPrice;
                    const cur = p.current_price ?? p.currentPrice;
                    const pnl = p.profit;
                    const pnlPct = p.profit_percent ?? p.profitPercent;
                    const fees = p.total_fees ?? p.totalFees ?? 0;
                    this.outputChannel.appendLine(
                        `${name} (${code}): ${qty}股, ` +
                        `成本: ¥${cost.toFixed(2)}, ` +
                        `现价: ¥${cur.toFixed(2)}, ` +
                        `盈亏: ${pnl >= 0 ? '+' : ''}¥${pnl.toFixed(2)} (${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(2)}%), ` +
                        `累计费用: ¥${fees.toFixed(2)}`
                    );
                });
            }
        } catch (error: any) {
            vscode.window.showErrorMessage(`获取持仓失败：${error.message}`);
        }
    }

    dispose(): void {
        this.outputChannel.dispose();
    }
}

