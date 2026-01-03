/**
 * 策略类型定义
 */

import { BaseEntity } from './common';

export type StrategyAction = 'BUY' | 'SELL' | 'HOLD';
export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH';

export interface Strategy extends BaseEntity {
    stockCode: string;
    stockName: string;
    action: StrategyAction;
    targetPrice?: number;
    stopLoss?: number;
    confidence: number; // 0-1
    reasoning: string;
    riskLevel: RiskLevel;
    timeHorizon: string; // 持仓周期
    aiModel: string;
}

export interface StrategyParams {
    stockCode: string;
    riskLevel?: RiskLevel;
    timeHorizon?: string;
    customPrompt?: string;
}

export interface StrategyScore {
    riskScore: number; // 0-100
    profitScore: number; // 0-100
    overallScore: number; // 0-100
}

