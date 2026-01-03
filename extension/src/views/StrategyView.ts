/**
 * 策略推荐视图
 */

import * as vscode from 'vscode';
import { ApiClient } from '../services/apiClient';
import { Strategy } from '../types/strategy';

export class StrategyView {
    private context: vscode.ExtensionContext;
    private apiClient: ApiClient;
    private outputChannel: vscode.OutputChannel;

    constructor(context: vscode.ExtensionContext, apiClient: ApiClient) {
        this.context = context;
        this.apiClient = apiClient;
        this.outputChannel = vscode.window.createOutputChannel('QuantFree Strategy');
        context.subscriptions.push(this.outputChannel);
    }

    async generateStrategy(code: string): Promise<void> {
        this.outputChannel.show();
        this.outputChannel.appendLine(`正在为 ${code} 生成策略推荐...`);

        try {
            const strategy = await this.apiClient.generateStrategy({
                stockCode: code
            });

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
            const message = error.message || '生成策略失败';
            this.outputChannel.appendLine(`\n错误：${message}`);
            vscode.window.showErrorMessage(`生成策略失败：${message}`);
        }
    }

    dispose(): void {
        this.outputChannel.dispose();
    }
}

