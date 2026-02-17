/**
 * API客户端服务
 */

import * as vscode from 'vscode';
import axios, { AxiosInstance, AxiosRequestConfig } from 'axios';
import { ApiResponse } from '../types/common';
import { Stock, KLineData, HistoryData } from '../types/market';
import { Strategy, StrategyParams } from '../types/strategy';
import { Order, Position, AccountInfo } from '../types/trade';

export class ApiClient {
    private client: AxiosInstance;
    private baseURL: string;

    constructor(baseURL: string = 'http://localhost:3000') {
        this.baseURL = baseURL;
        this.client = axios.create({
            baseURL,
            timeout: 30000,
            headers: {
                'Content-Type': 'application/json'
            }
        });

        // 请求拦截器
        this.client.interceptors.request.use(
            (config) => {
                console.log(`[API Request] ${config.method?.toUpperCase()} ${config.url}`);
                return config;
            },
            (error) => {
                console.error('[API Request Error]', error);
                return Promise.reject(error);
            }
        );

        // 响应拦截器
        this.client.interceptors.response.use(
            (response) => {
                return response;
            },
            (error) => {
                console.error('[API Response Error]', error);
                return Promise.reject(error);
            }
        );
    }

    updateServerUrl(url: string) {
        this.baseURL = url;
        this.client.defaults.baseURL = url;
    }

    // 行情数据API
    async getRealTimeData(codes: string[]): Promise<Stock[]> {
        const source = vscode.workspace.getConfiguration('quantFree').get<string>('dataSource', 'auto');
        const response = await this.client.get<ApiResponse<any[]>>('/api/v1/market/realtime', {
            params: { codes: codes.join(','), source }
        });
        // Backend returns snake_case, frontend expects camelCase
        return (response.data.data || []).map((item: any) => ({
            ...item,
            changePercent: item.change_percent ?? item.changePercent ?? 0,
            preClose: item.pre_close ?? item.preClose ?? 0,
        }));
    }

    async getHistoryData(code: string, period: string = '1d'): Promise<HistoryData[]> {
        const response = await this.client.get<ApiResponse<HistoryData[]>>(`/api/v1/market/history/${code}`, {
            params: { period }
        });
        return response.data.data || [];
    }

    async getKLineData(code: string, type: string = 'day'): Promise<KLineData[]> {
        const response = await this.client.get<ApiResponse<KLineData[]>>(`/api/v1/market/kline/${code}`, {
            params: { type }
        });
        return response.data.data || [];
    }

    // 策略API
    async generateStrategy(params: StrategyParams): Promise<Strategy> {
        // 转换为后端 snake_case 格式
        const payload = {
            stock_code: params.stockCode,
            risk_level: params.riskLevel || 'MEDIUM',
            time_horizon: params.timeHorizon || '短期',
            custom_prompt: params.customPrompt
        };
        const response = await this.client.post<ApiResponse<any>>('/api/v1/strategy/generate', payload);
        if (!response.data.data) {
            throw new Error(response.data.message || '生成策略失败');
        }
        // 转换后端 snake_case 响应为前端 camelCase
        const d = response.data.data;
        return {
            id: d.id,
            stockCode: d.stock_code,
            stockName: d.stock_name,
            action: d.action,
            targetPrice: d.target_price,
            stopLoss: d.stop_loss,
            confidence: d.confidence,
            reasoning: d.reasoning,
            riskLevel: d.risk_level,
            timeHorizon: d.time_horizon,
            aiModel: d.ai_model,
            createdAt: d.created_at,
            updatedAt: d.updated_at
        };
    }

    async getStrategy(id: string): Promise<Strategy> {
        const response = await this.client.get<ApiResponse<Strategy>>(`/api/v1/strategy/${id}`);
        if (!response.data.data) {
            throw new Error(response.data.message || '获取策略失败');
        }
        return response.data.data;
    }

    // 交易API
    async placeOrder(order: Partial<Order>): Promise<Order> {
        // 转换为后端 snake_case 格式
        const payload = {
            stock_code: order.stockCode,
            type: order.type,
            order_type: order.orderType,
            price: order.price,
            quantity: order.quantity
        };
        const response = await this.client.post<ApiResponse<any>>('/api/v1/trade/order', payload);
        if (!response.data.data) {
            throw new Error(response.data.message || '下单失败');
        }
        return response.data.data;
    }

    async cancelOrder(orderId: string): Promise<boolean> {
        const response = await this.client.delete<ApiResponse<boolean>>(`/api/v1/trade/order/${orderId}`);
        return response.data.success || false;
    }

    async getOrders(status?: string): Promise<Order[]> {
        const response = await this.client.get<ApiResponse<Order[]>>('/api/v1/trade/orders', {
            params: { status }
        });
        return response.data.data || [];
    }

    async getPositions(): Promise<Position[]> {
        const response = await this.client.get<ApiResponse<Position[]>>('/api/v1/trade/positions');
        return response.data.data || [];
    }

    async getAccountInfo(): Promise<AccountInfo> {
        const response = await this.client.get<ApiResponse<AccountInfo>>('/api/v1/trade/account');
        if (!response.data.data) {
            throw new Error(response.data.message || '获取账户信息失败');
        }
        return response.data.data;
    }
}

