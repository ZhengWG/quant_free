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
            const result = await this.apiClient.placeOrder(order);
            this.outputChannel.appendLine(`\n订单提交成功！`);
            this.outputChannel.appendLine(`订单号：${result.id}`);
            this.outputChannel.appendLine(`状态：${result.status}`);
            vscode.window.showInformationMessage('订单提交成功！');
        } catch (error: any) {
            const message = error.message || '下单失败';
            this.outputChannel.appendLine(`\n错误：${message}`);
            vscode.window.showErrorMessage(`下单失败：${message}`);
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
                positions.forEach(pos => {
                    this.outputChannel.appendLine(
                        `${pos.stockName} (${pos.stockCode}): ${pos.quantity}股, ` +
                        `成本价: ¥${pos.costPrice.toFixed(2)}, ` +
                        `当前价: ¥${pos.currentPrice.toFixed(2)}, ` +
                        `盈亏: ${pos.profit >= 0 ? '+' : ''}¥${pos.profit.toFixed(2)} (${pos.profitPercent >= 0 ? '+' : ''}${pos.profitPercent.toFixed(2)}%)`
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

