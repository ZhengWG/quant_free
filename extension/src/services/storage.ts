/**
 * 本地存储服务
 */

import * as vscode from 'vscode';

export class StorageService {
    private context: vscode.ExtensionContext;

    constructor(context: vscode.ExtensionContext) {
        this.context = context;
    }

    // 存储自选股列表
    async saveStocks(codes: string[]): Promise<void> {
        await this.context.globalState.update('quantFree.stocks', codes);
    }

    async getStocks(): Promise<string[]> {
        return this.context.globalState.get<string[]>('quantFree.stocks', []);
    }

    // 存储配置
    async saveConfig(key: string, value: any): Promise<void> {
        await this.context.globalState.update(`quantFree.config.${key}`, value);
    }

    async getConfig<T>(key: string, defaultValue: T): Promise<T> {
        return this.context.globalState.get<T>(`quantFree.config.${key}`, defaultValue);
    }

    // 存储敏感信息（使用SecretStorage）
    async saveSecret(key: string, value: string): Promise<void> {
        await this.context.secrets.store(key, value);
    }

    async getSecret(key: string): Promise<string | undefined> {
        return await this.context.secrets.get(key);
    }

    async deleteSecret(key: string): Promise<void> {
        await this.context.secrets.delete(key);
    }
}

