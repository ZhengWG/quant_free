/**
 * 交易执行视图
 */

import * as vscode from 'vscode';
import { ApiClient } from '../services/apiClient';
import { StorageService } from '../services/storage';
import { Order, Position } from '../types/trade';
import { validateOrder } from '../utils/validators';

class PositionItem extends vscode.TreeItem {
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

class TradeTreeDataProvider implements vscode.TreeDataProvider<PositionItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<PositionItem | undefined | null | void>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

    private positions: any[] = [];
    private accountInfo: any = null;

    getTreeItem(element: PositionItem): vscode.TreeItem {
        return element;
    }

    async getChildren(element?: PositionItem): Promise<PositionItem[]> {
        const items: PositionItem[] = [];

        if (this.accountInfo) {
            const a = this.accountInfo;
            const totalAsset = a.total_asset ?? a.totalAsset ?? 0;
            const cash = a.available_cash ?? a.availableCash ?? 0;
            const pnl = a.profit ?? 0;
            const pnlPct = a.profit_percent ?? a.profitPercent ?? 0;
            items.push(new PositionItem(
                '账户总资产',
                `¥${totalAsset.toFixed(2)}`,
                vscode.TreeItemCollapsibleState.None,
                new vscode.ThemeIcon('wallet')
            ));
            items.push(new PositionItem(
                '可用资金',
                `¥${cash.toFixed(2)}`,
                vscode.TreeItemCollapsibleState.None,
                new vscode.ThemeIcon('credit-card')
            ));
            const pnlIcon = pnl >= 0
                ? new vscode.ThemeIcon('arrow-up', new vscode.ThemeColor('charts.green'))
                : new vscode.ThemeIcon('arrow-down', new vscode.ThemeColor('charts.red'));
            items.push(new PositionItem(
                '总盈亏',
                `${pnl >= 0 ? '+' : ''}¥${pnl.toFixed(2)} (${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(2)}%)`,
                vscode.TreeItemCollapsibleState.None,
                pnlIcon
            ));
        }

        if (this.positions.length > 0) {
            items.push(new PositionItem('── 持仓 ──', `${this.positions.length}只`, vscode.TreeItemCollapsibleState.None, new vscode.ThemeIcon('briefcase')));
            for (const p of this.positions) {
                const name = p.stock_name ?? p.stockName ?? '未知';
                const code = p.stock_code ?? p.stockCode ?? '';
                const qty = p.quantity ?? 0;
                const cost = p.cost_price ?? p.costPrice ?? 0;
                const cur = p.current_price ?? p.currentPrice ?? 0;
                const pnl = p.profit ?? 0;
                const pnlPct = p.profit_percent ?? p.profitPercent ?? 0;
                const icon = pnl >= 0
                    ? new vscode.ThemeIcon('arrow-up', new vscode.ThemeColor('charts.green'))
                    : new vscode.ThemeIcon('arrow-down', new vscode.ThemeColor('charts.red'));
                items.push(new PositionItem(
                    `${name} (${code})`,
                    `${qty}股 | 成本¥${cost.toFixed(2)} | 现价¥${cur.toFixed(2)} | ${pnl >= 0 ? '+' : ''}${pnlPct.toFixed(2)}%`,
                    vscode.TreeItemCollapsibleState.None,
                    icon
                ));
            }
        }

        return items;
    }

    update(positions: any[], accountInfo?: any): void {
        this.positions = positions;
        if (accountInfo) {
            this.accountInfo = accountInfo;
        }
        this._onDidChangeTreeData.fire();
    }

    refresh(): void {
        this._onDidChangeTreeData.fire();
    }
}

export class TradeView {
    private context: vscode.ExtensionContext;
    private apiClient: ApiClient;
    private storageService: StorageService;
    private outputChannel: vscode.OutputChannel;
    private treeProvider: TradeTreeDataProvider;

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

        this.treeProvider = new TradeTreeDataProvider();
        const treeView = vscode.window.createTreeView('quantFree.trade', {
            treeDataProvider: this.treeProvider,
            showCollapseAll: false
        });
        context.subscriptions.push(treeView);
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

            // 下单成功后自动刷新持仓
            await this.refreshPositions();
        } catch (error: any) {
            const detail = error.response?.data?.detail || error.message || '下单失败';
            this.outputChannel.appendLine(`\n错误：${detail}`);
            vscode.window.showErrorMessage(`下单失败：${detail}`);
        }
    }

    async refreshPositions(): Promise<void> {
        try {
            const positions = await this.apiClient.getPositions();
            let accountInfo: any = null;
            try {
                accountInfo = await this.apiClient.getAccountInfo();
            } catch (_) {
                // 账户信息获取失败不阻塞
            }

            // 更新侧边栏 TreeView
            this.treeProvider.update(positions as any[], accountInfo);

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

