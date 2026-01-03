/**
 * 交易类型定义
 */

import { BaseEntity } from './common';

export type OrderType = 'BUY' | 'SELL';
export type OrderStatus = 'PENDING' | 'FILLED' | 'CANCELLED' | 'REJECTED';
export type PriceType = 'MARKET' | 'LIMIT';

export interface Order extends BaseEntity {
    stockCode: string;
    stockName: string;
    type: OrderType;
    orderType: PriceType;
    price?: number; // 限价单价格
    quantity: number;
    status: OrderStatus;
    filledQuantity: number;
    filledPrice: number;
}

export interface Position {
    stockCode: string;
    stockName: string;
    quantity: number;
    costPrice: number;
    currentPrice: number;
    marketValue: number;
    profit: number;
    profitPercent: number;
}

export interface AccountInfo {
    totalAsset: number;
    availableCash: number;
    marketValue: number;
    profit: number;
    profitPercent: number;
}

