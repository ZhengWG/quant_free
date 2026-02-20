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

export interface BacktestParams {
    stockCode: string;
    strategy: string; // ma_cross, macd, kdj, rsi, bollinger
    startDate: string; // YYYY-MM-DD
    endDate: string; // YYYY-MM-DD
    initialCapital?: number;
    shortWindow?: number;
    longWindow?: number;
    stopLossPct?: number;
    trailingStopPct?: number;
    riskPerTrade?: number;
    maxPositionPct?: number;
    trendMaLen?: number;
    cooldownBars?: number;
}

export interface BacktestTrade {
    date: string;
    action: string; // BUY / SELL
    price: number;
    quantity: number;
    profit?: number;
}

export interface PricePoint {
    date: string;
    close: number;
}

export interface BacktestResult {
    id: string;
    stockCode: string;
    strategy: string;
    startDate: string;
    endDate: string;
    initialCapital: number;
    finalCapital: number;
    totalReturn: number;
    totalReturnPercent: number;
    maxDrawdown: number;
    sharpeRatio: number;
    winRate: number;
    totalTrades: number;
    trades: BacktestTrade[];
    priceSeries: PricePoint[];
}

export interface BacktestOptimizeParams {
    stockCode: string;
    strategy: string;
    startDate: string;
    endDate: string;
    initialCapital?: number;
    paramGrid?: Record<string, number[]>;  // e.g. { short_window: [5, 10], long_window: [20, 30] }
    topN?: number;
}

export interface BacktestOptimizeItem {
    params: Record<string, number>;
    totalReturnPercent: number;
    sharpeRatio: number;
    maxDrawdown: number;
    winRate: number;
    totalTrades: number;
}

export interface BacktestOptimizeResult {
    stockCode: string;
    strategy: string;
    startDate: string;
    endDate: string;
    bestParams: Record<string, number>;
    results: BacktestOptimizeItem[];
}

export interface SmartScreenParams {
    stockPool: string;
    customCodes?: string;
    screeningStrategy: string;
    startDate: string;
    endDate: string;
    initialCapital?: number;
    topN?: number;
    mode?: string;                  // "classic" | "smart_v2"
    predictionMonths?: number;      // smart_v2: 预测月数
    stopLossPct?: number;
    trailingStopPct?: number;
    riskPerTrade?: number;
    maxPositionPct?: number;
    trendMaLen?: number;
    cooldownBars?: number;
}

export interface ScreenedStock {
    code: string;
    name: string;
    passed: boolean;
    reason: string;
}

export interface RankedResult {
    rank: number;
    stockCode: string;
    stockName: string;
    strategy: string;
    strategyLabel: string;
    totalReturnPercent: number;
    sharpeRatio: number;
    maxDrawdown: number;
    winRate: number;
    totalTrades: number;
    score: number;
    backtestResult?: BacktestResult;
    // smart_v2 fields
    valuationScore?: number;
    confidenceScore?: number;
    predictedReturnPct?: number;
    alphaPct?: number;
    pe?: number | null;
    pb?: number | null;
    roe?: number | null;
    industry?: string;
    revenueGrowth?: number | null;
    profitGrowth?: number | null;
    grossMargin?: number | null;
    signal?: string;
    // AI fundamental analysis
    aiScore?: number;
    aiAnalysis?: string;
    // smart_v2 chart data
    equityCurve?: Array<{ date: string; value: number }>;
    projectedEquity?: Array<{ date: string; value: number }>;
    fullPriceSeries?: Array<{ date: string; close: number }>;
    allTrades?: BacktestTrade[];
    splitDate?: string;
}

export interface SmartScreenResult {
    poolName: string;
    screeningStrategy: string;
    totalStocks: number;
    screenedStocks: number;
    totalBacktests: number;
    timeTakenSeconds: number;
    rankings: RankedResult[];
    allScreened: ScreenedStock[];
    // smart_v2 fields
    mode?: string;
    testBnhPct?: number;
    avgConfidence?: number;
    avgPredictedReturn?: number;   // 未来 N 月预测收益均值
    predictionMonths?: number;     // 未来收益预测月数（表内预测收益即为此区间）
}

// ---------- 预测分析 ----------

export interface PredictionParams {
    stockPool: string;
    customCodes?: string;
    predictionMonths: number;
    initialCapital?: number;
    topN?: number;
}

export interface FundamentalInfo {
    peDynamic: number | null;
    pb: number | null;
    marketCapYi: number | null;
}export interface ProjectedPoint {
    date: string;
    value: number;
}

export interface PredictionItem {
    rank: number;
    stockCode: string;
    stockName: string;
    fundamental: FundamentalInfo;
    valuationScore: number;
    trendScore: number;
    momentumScore: number;
    volatilityScore: number;
    volumeScore: number;
    compositeScore: number;
    predictedReturnPct: number;
    predictedAnnualReturnPct: number;
    bestStrategy: string;
    bestStrategyLabel: string;
    historicalReturnPct: number;
    confidence: string;
    signal: string;
    fitScore: number;
    monthlyReturnMean: number;
    monthlyReturnStd: number;
    historicalPrices: ProjectedPoint[];
    projectedPrices: ProjectedPoint[];
    projectedPricesOptimistic: ProjectedPoint[];
    projectedPricesPessimistic: ProjectedPoint[];
    projectedEquity: ProjectedPoint[];
    projectedEquityOptimistic: ProjectedPoint[];
    projectedEquityPessimistic: ProjectedPoint[];
    historicalEquity: ProjectedPoint[];
}

export interface PredictionResult {
    poolName: string;
    predictionMonths: number;
    totalAnalyzed: number;
    timeTakenSeconds: number;
    rankings: PredictionItem[];
}

// ---------- 策略测试 ----------

export interface StrategyTestParams {
    stockCode: string;
    startDate: string;
    endDate: string;
    initialCapital?: number;
    trainRatio?: number;
}

export interface StrategyTestItem {
    strategy: string;
    strategyLabel: string;
    trainStart: string;
    trainEnd: string;
    testStart: string;
    testEnd: string;
    trainBars: number;
    testBars: number;
    trainReturnPct: number;
    trainSharpe: number;
    trainMaxDrawdown: number;
    trainWinRate: number;
    trainTrades: number;
    trainBnhPct: number;
    testBnhPct: number;
    predictedReturnPct: number;
    predictedDirection: string;
    actualReturnPct: number;
    actualSharpe: number;
    actualMaxDrawdown: number;
    actualWinRate: number;
    actualTrades: number;
    actualDirection: string;
    trainAlphaPct: number;
    testAlphaPct: number;
    directionCorrect: boolean;
    returnErrorPct: number;
    confidenceScore: number;
    testHasTrades: boolean;
    trainEquity: ProjectedPoint[];
    testEquityPredicted: ProjectedPoint[];
    testEquityActual: ProjectedPoint[];
    testEquityBnh: ProjectedPoint[];
    fullPriceSeries: ProjectedPoint[];
    /** 单股策略分析：未来收益预测月数 */
    predictionMonths?: number;
    /** 单股策略分析：未来该区间的预期收益率% */
    predictedFutureReturnPct?: number;
}

export interface StrategyTestResult {
    stockCode: string;
    stockName: string;
    fullStart: string;
    fullEnd: string;
    trainRatio: number;
    totalStrategies: number;
    avgConfidence: number;
    bestStrategy: string;
    bestStrategyLabel: string;
    fullBnhPct: number;
    testBnhPct: number;
    timeTakenSeconds: number;
    items: StrategyTestItem[];
}

// ---------- 单股策略分析（80/20 多策略 TopK + 未来收益预测）----------

export interface StrategyAnalyzeParams {
    stockCode: string;
    startDate: string;
    endDate: string;
    initialCapital?: number;
    trainRatio?: number;
    topK?: number;
    /** 未来收益预测月数（按训练期 CAGR 外推） */
    predictionMonths?: number;
}

export interface StrategyAnalyzeResult {
    stockCode: string;
    stockName: string;
    fullStart: string;
    fullEnd: string;
    trainRatio: number;
    fullBnhPct: number;
    testBnhPct: number;
    timeTakenSeconds: number;
    /** 未来预测月数（与请求一致） */
    predictionMonths?: number;
    strategies: StrategyTestItem[];
}
