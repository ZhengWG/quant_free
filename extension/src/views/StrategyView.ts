/**
 * 策略推荐视图
 */

import * as vscode from 'vscode';
import { ApiClient } from '../services/apiClient';
import { Strategy } from '../types/strategy';

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

    dispose(): void {
        this.outputChannel.dispose();
    }
}

