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
        // TODO: 实现删除选中股票
        this.view.refresh();
    }

    async openChart(code: string): Promise<void> {
        // TODO: 打开K线图
        vscode.window.showInformationMessage(`打开 ${code} 的K线图`);
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

