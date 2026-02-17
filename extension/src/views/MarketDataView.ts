/**
 * 行情监控视图
 */

import * as vscode from 'vscode';
import { ApiClient } from '../services/apiClient';
import { WebSocketClient } from '../services/websocketClient';
import { StorageService } from '../services/storage';
import { Stock } from '../types/market';

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
        const stocks = await this.storageService.getStocks();
        if (!stocks.includes(code)) {
            stocks.push(code);
            await this.storageService.saveStocks(stocks);
            this.view.refresh();
            this.wsClient.subscribeMarketData([code]);
        }
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
            const klineData = await this.apiClient.getKLineData(code);
            if (!klineData || klineData.length === 0) {
                vscode.window.showWarningMessage(`暂无 ${code} 的K线数据`);
                return;
            }

            // 使用OutputChannel展示K线数据
            const channel = vscode.window.createOutputChannel(`K线图 - ${code}`);
            channel.clear();
            channel.appendLine(`=== ${code} K线数据 ===`);
            channel.appendLine('');
            channel.appendLine('日期            开盘     最高     最低     收盘     成交量');
            channel.appendLine('─'.repeat(70));

            for (const k of klineData) {
                const line = [
                    k.date.padEnd(16),
                    k.open.toFixed(2).padStart(8),
                    k.high.toFixed(2).padStart(8),
                    k.low.toFixed(2).padStart(8),
                    k.close.toFixed(2).padStart(8),
                    Math.round(k.volume).toString().padStart(12),
                ].join(' ');
                channel.appendLine(line);
            }

            channel.appendLine('');
            channel.appendLine(`共 ${klineData.length} 条数据`);
            channel.show();
        } catch (error) {
            vscode.window.showErrorMessage(`获取K线数据失败: ${error}`);
        }
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
        public readonly stock: Stock,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState
    ) {
        super(stock.name, collapsibleState);
        this.tooltip = `${stock.code} - ${stock.name}`;
        this.description = `¥${stock.price.toFixed(2)} ${stock.changePercent >= 0 ? '+' : ''}${stock.changePercent.toFixed(2)}%`;
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
            stocks.forEach(stock => {
                this.stocks.set(stock.code, stock);
            });

            return stocks.map(stock => new StockItem(stock, vscode.TreeItemCollapsibleState.None));
        } catch (error) {
            console.error('Failed to get market data:', error);
            return [];
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

