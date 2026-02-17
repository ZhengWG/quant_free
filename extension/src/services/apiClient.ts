/**
 * API客户端服务
 */

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
        const response = await this.client.get<ApiResponse<any[]>>('/api/v1/market/realtime', {
            params: { codes: codes.join(',') }
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
        const response = await this.client.post<ApiResponse<Strategy>>('/api/v1/strategy/generate', params);
        if (!response.data.data) {
            throw new Error(response.data.message || '生成策略失败');
        }
        return response.data.data;
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
        const response = await this.client.post<ApiResponse<Order>>('/api/v1/trade/order', order);
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

