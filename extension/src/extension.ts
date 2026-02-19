import * as vscode from 'vscode';
import { MarketDataView } from './views/MarketDataView';
import { StrategyView } from './views/StrategyView';
import { TradeView } from './views/TradeView';
import { SmartScreenView } from './views/SmartScreenView';
import { StrategyTestView } from './views/StrategyTestView';
import { ApiClient } from './services/apiClient';
import { WebSocketClient } from './services/websocketClient';
import { StorageService } from './services/storage';

let marketDataView: MarketDataView | undefined;
let strategyView: StrategyView | undefined;
let tradeView: TradeView | undefined;
let smartScreenView: SmartScreenView | undefined;
let strategyTestView: StrategyTestView | undefined;
let apiClient: ApiClient | undefined;
let wsClient: WebSocketClient | undefined;
let storageService: StorageService | undefined;

export async function activate(context: vscode.ExtensionContext) {
    console.log('QuantFree extension is now active!');

    // 初始化服务
    storageService = new StorageService(context);
    const config = vscode.workspace.getConfiguration('quantFree');
    const serverUrl = config.get<string>('serverUrl', 'http://localhost:3000');
    
    apiClient = new ApiClient(serverUrl);
    wsClient = new WebSocketClient(serverUrl);

    // 注册视图
    marketDataView = new MarketDataView(context, apiClient, wsClient, storageService);
    strategyView = new StrategyView(context, apiClient);
    tradeView = new TradeView(context, apiClient, storageService);
    smartScreenView = new SmartScreenView(context, apiClient);
    strategyTestView = new StrategyTestView(context, apiClient);

    // 注册命令
    const commands = [
        vscode.commands.registerCommand('quantFree.addStock', async () => {
            const code = await vscode.window.showInputBox({
                prompt: '请输入股票代码',
                placeHolder: '例如：000001, 600519'
            });
            if (code) {
                await marketDataView?.addStock(code);
            }
        }),
        vscode.commands.registerCommand('quantFree.removeStock', async () => {
            await marketDataView?.removeSelectedStock();
        }),
        vscode.commands.registerCommand('quantFree.generateStrategy', async () => {
            const code = await vscode.window.showInputBox({
                prompt: '请输入股票代码',
                placeHolder: '例如：000001'
            });
            if (code) {
                await strategyView?.generateStrategy(code);
            }
        }),
        vscode.commands.registerCommand('quantFree.placeOrder', async () => {
            await tradeView?.showOrderDialog();
        }),
        vscode.commands.registerCommand('quantFree.viewPositions', async () => {
            await tradeView?.refreshPositions();
        }),
        vscode.commands.registerCommand('quantFree.openChart', async () => {
            const code = await vscode.window.showInputBox({
                prompt: '请输入股票代码',
                placeHolder: '例如：000001'
            });
            if (code) {
                await marketDataView?.openChart(code);
            }
        }),
        vscode.commands.registerCommand('quantFree.smartScreen', async () => {
            await smartScreenView?.run();
        }),
        vscode.commands.registerCommand('quantFree.strategyAnalyze', async () => {
            await strategyTestView?.runAnalyze();
        }),
        vscode.commands.registerCommand('quantFree.exportTrades', async () => {
            const typePick = await vscode.window.showQuickPick(
                [
                    { label: '订单', value: 'orders' as const, description: '导出所有订单记录' },
                    { label: '持仓', value: 'positions' as const, description: '导出当前持仓' },
                    { label: '全部', value: 'all' as const, description: '订单 + 持仓' },
                ],
                { placeHolder: '选择导出类型' }
            );
            if (!typePick) { return; }
            const uri = await vscode.window.showSaveDialog({
                defaultUri: vscode.Uri.file(`trades_${typePick.value}_${Date.now()}.csv`),
                filters: { CSV: ['csv'] },
            });
            if (!uri) { return; }
            try {
                const buf = await apiClient?.exportTrades('csv', typePick.value);
                if (buf) {
                    await vscode.workspace.fs.writeFile(uri, new Uint8Array(buf));
                    vscode.window.showInformationMessage(`已导出: ${uri.fsPath}`);
                }
            } catch (e: any) {
                vscode.window.showErrorMessage(`导出失败: ${e.response?.data?.detail || e.message}`);
            }
        }),
        vscode.commands.registerCommand('quantFree.openConfig', async () => {
            await vscode.commands.executeCommand('workbench.action.openSettings', 'quantFree');
        })
    ];

    commands.forEach(command => context.subscriptions.push(command));

    // 初始化WebSocket连接（后端未启动时不阻塞插件激活）
    wsClient.connect().catch(() => {
        console.warn('[QuantFree] WebSocket initial connection failed. Will retry when server is available.');
    });
    
    // 监听配置变化
    context.subscriptions.push(
        vscode.workspace.onDidChangeConfiguration(async (e) => {
            if (e.affectsConfiguration('quantFree.serverUrl')) {
                const newUrl = vscode.workspace.getConfiguration('quantFree').get<string>('serverUrl', 'http://localhost:3000');
                apiClient?.updateServerUrl(newUrl);
                await wsClient?.disconnect();
                wsClient = new WebSocketClient(newUrl);
                await wsClient.connect();
            }
        })
    );
}

export function deactivate() {
    console.log('QuantFree extension is deactivating...');
    wsClient?.disconnect();
    marketDataView?.dispose();
    strategyView?.dispose();
    tradeView?.dispose();
    smartScreenView?.dispose();
    strategyTestView?.dispose();
}

