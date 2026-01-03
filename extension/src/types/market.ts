/**
 * 行情数据类型定义
 */

import { MarketType } from './common';

export interface Stock {
    code: string;
    name: string;
    market: MarketType;
    price: number;
    change: number;
    changePercent: number;
    volume: number;
    amount: number;
    high: number;
    low: number;
    open: number;
    preClose: number;
    timestamp: Date;
}

export interface KLineData {
    date: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
    amount: number;
}

export interface HistoryData {
    date: string;
    price: number;
    volume: number;
    amount: number;
}

export interface TechnicalIndicator {
    ma5?: number;
    ma10?: number;
    ma20?: number;
    ma30?: number;
    ma60?: number;
    macd?: {
        dif: number;
        dea: number;
        macd: number;
    };
    kdj?: {
        k: number;
        d: number;
        j: number;
    };
    rsi?: number;
}

