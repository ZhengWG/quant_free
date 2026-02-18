/**
 * API客户端服务
 */

import * as vscode from 'vscode';
import axios, { AxiosInstance, AxiosRequestConfig } from 'axios';
import { ApiResponse } from '../types/common';
import { Stock, KLineData, HistoryData } from '../types/market';
import { Strategy, StrategyParams, BacktestParams, BacktestResult, BacktestTrade, SmartScreenParams, SmartScreenResult, RankedResult, ScreenedStock, PredictionParams, PredictionResult, PredictionItem, ProjectedPoint, FundamentalInfo, StrategyTestParams, StrategyTestResult, StrategyTestItem } from '../types/strategy';
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

    async runBacktest(params: BacktestParams): Promise<BacktestResult | null> {
        const payload: Record<string, any> = {
            stock_code: params.stockCode,
            strategy: params.strategy,
            start_date: params.startDate,
            end_date: params.endDate,
            initial_capital: params.initialCapital ?? 100000,
            short_window: params.shortWindow ?? 5,
            long_window: params.longWindow ?? 20,
        };
        if (params.stopLossPct != null) { payload.stop_loss_pct = params.stopLossPct; }
        if (params.trailingStopPct != null) { payload.trailing_stop_pct = params.trailingStopPct; }
        if (params.riskPerTrade != null) { payload.risk_per_trade = params.riskPerTrade; }
        if (params.maxPositionPct != null) { payload.max_position_pct = params.maxPositionPct; }
        if (params.trendMaLen != null) { payload.trend_ma_len = params.trendMaLen; }
        if (params.cooldownBars != null) { payload.cooldown_bars = params.cooldownBars; }
        const response = await this.client.post<ApiResponse<any>>('/api/v1/backtest/run', payload);
        if (!response.data.data) {
            return null;
        }
        const d = response.data.data;
        return {
            id: d.id,
            stockCode: d.stock_code,
            strategy: d.strategy,
            startDate: d.start_date,
            endDate: d.end_date,
            initialCapital: d.initial_capital,
            finalCapital: d.final_capital,
            totalReturn: d.total_return,
            totalReturnPercent: d.total_return_percent,
            maxDrawdown: d.max_drawdown,
            sharpeRatio: d.sharpe_ratio,
            winRate: d.win_rate,
            totalTrades: d.total_trades,
            trades: (d.trades || []).map((t: any) => ({
                date: t.date,
                action: t.action,
                price: t.price,
                quantity: t.quantity,
                profit: t.profit
            })),
            priceSeries: (d.price_series || []).map((p: any) => ({
                date: p.date,
                close: p.close,
            })),
        };
    }

    async runSmartScreen(params: SmartScreenParams): Promise<SmartScreenResult> {
        const payload: Record<string, any> = {
            stock_pool: params.stockPool,
            custom_codes: params.customCodes,
            screening_strategy: params.screeningStrategy,
            start_date: params.startDate,
            end_date: params.endDate,
            initial_capital: params.initialCapital ?? 100000,
            top_n: params.topN ?? 5,
            mode: params.mode ?? 'classic',
        };
        if (params.predictionMonths != null) { payload.prediction_months = params.predictionMonths; }
        if (params.stopLossPct != null) { payload.stop_loss_pct = params.stopLossPct; }
        if (params.trailingStopPct != null) { payload.trailing_stop_pct = params.trailingStopPct; }
        if (params.riskPerTrade != null) { payload.risk_per_trade = params.riskPerTrade; }
        if (params.maxPositionPct != null) { payload.max_position_pct = params.maxPositionPct; }
        if (params.trendMaLen != null) { payload.trend_ma_len = params.trendMaLen; }
        if (params.cooldownBars != null) { payload.cooldown_bars = params.cooldownBars; }
        const response = await this.client.post<ApiResponse<any>>('/api/v1/backtest/smart-screen', payload, {
            timeout: 300000,
        });
        if (!response.data.data) {
            throw new Error(response.data.message || '智能选股失败');
        }
        const d = response.data.data;

        const convertBacktest = (bt: any): BacktestResult | undefined => {
            if (!bt) { return undefined; }
            return {
                id: bt.id,
                stockCode: bt.stock_code,
                strategy: bt.strategy,
                startDate: bt.start_date,
                endDate: bt.end_date,
                initialCapital: bt.initial_capital,
                finalCapital: bt.final_capital,
                totalReturn: bt.total_return,
                totalReturnPercent: bt.total_return_percent,
                maxDrawdown: bt.max_drawdown,
                sharpeRatio: bt.sharpe_ratio,
                winRate: bt.win_rate,
                totalTrades: bt.total_trades,
                trades: (bt.trades || []).map((t: any) => ({
                    date: t.date,
                    action: t.action,
                    price: t.price,
                    quantity: t.quantity,
                    profit: t.profit,
                })),
                priceSeries: (bt.price_series || []).map((p: any) => ({
                    date: p.date,
                    close: p.close,
                })),
            };
        };

        const rankings: RankedResult[] = (d.rankings || []).map((r: any) => ({
            rank: r.rank,
            stockCode: r.stock_code,
            stockName: r.stock_name,
            strategy: r.strategy,
            strategyLabel: r.strategy_label,
            totalReturnPercent: r.total_return_percent,
            sharpeRatio: r.sharpe_ratio,
            maxDrawdown: r.max_drawdown,
            winRate: r.win_rate,
            totalTrades: r.total_trades,
            score: r.score,
            backtestResult: convertBacktest(r.backtest_result),
            valuationScore: r.valuation_score ?? undefined,
            confidenceScore: r.confidence_score ?? undefined,
            predictedReturnPct: r.predicted_return_pct ?? undefined,
            alphaPct: r.alpha_pct ?? undefined,
            pe: r.pe ?? undefined,
            pb: r.pb ?? undefined,
            roe: r.roe ?? undefined,
            industry: r.industry ?? undefined,
            revenueGrowth: r.revenue_growth ?? undefined,
            profitGrowth: r.profit_growth ?? undefined,
            grossMargin: r.gross_margin ?? undefined,
            signal: r.signal ?? undefined,
            aiScore: r.ai_score ?? undefined,
            aiAnalysis: r.ai_analysis ?? undefined,
            equityCurve: r.equity_curve ?? undefined,
            projectedEquity: r.projected_equity ?? undefined,
            fullPriceSeries: (r.full_price_series || []).map((p: any) => ({ date: p.date, close: p.close })),
            allTrades: (r.all_trades || []).map((t: any) => ({
                date: t.date, action: t.action, price: t.price,
                quantity: t.quantity, profit: t.profit,
            })),
            splitDate: r.split_date ?? undefined,
        }));

        const allScreened: ScreenedStock[] = (d.all_screened || []).map((s: any) => ({
            code: s.code,
            name: s.name,
            passed: s.passed,
            reason: s.reason,
        }));

        return {
            poolName: d.pool_name,
            screeningStrategy: d.screening_strategy,
            totalStocks: d.total_stocks,
            screenedStocks: d.screened_stocks,
            totalBacktests: d.total_backtests,
            timeTakenSeconds: d.time_taken_seconds,
            rankings,
            allScreened,
            mode: d.mode ?? 'classic',
            testBnhPct: d.test_bnh_pct ?? undefined,
            avgConfidence: d.avg_confidence ?? undefined,
            avgPredictedReturn: d.avg_predicted_return ?? undefined,
        };
    }

    async runPrediction(params: PredictionParams): Promise<PredictionResult> {
        const payload: Record<string, any> = {
            stock_pool: params.stockPool,
            custom_codes: params.customCodes,
            prediction_months: params.predictionMonths,
            initial_capital: params.initialCapital ?? 100000,
            top_n: params.topN ?? 10,
        };
        const response = await this.client.post<ApiResponse<any>>('/api/v1/backtest/predict', payload, {
            timeout: 300000,
        });
        if (!response.data.data) {
            throw new Error(response.data.message || '预测分析失败');
        }
        const d = response.data.data;

        const convertPoint = (p: any): ProjectedPoint => ({ date: p.date, value: p.value });
        const convertFund = (f: any): FundamentalInfo => ({
            peDynamic: f?.pe_dynamic ?? null,
            pb: f?.pb ?? null,
            marketCapYi: f?.market_cap_yi ?? null,
        });

        const rankings: PredictionItem[] = (d.rankings || []).map((r: any) => ({
            rank: r.rank,
            stockCode: r.stock_code,
            stockName: r.stock_name,
            fundamental: convertFund(r.fundamental),
            valuationScore: r.valuation_score,
            trendScore: r.trend_score,
            momentumScore: r.momentum_score,
            volatilityScore: r.volatility_score,
            volumeScore: r.volume_score,
            compositeScore: r.composite_score,
            predictedReturnPct: r.predicted_return_pct,
            predictedAnnualReturnPct: r.predicted_annual_return_pct,
            bestStrategy: r.best_strategy,
            bestStrategyLabel: r.best_strategy_label,
            historicalReturnPct: r.historical_return_pct,
            confidence: r.confidence,
            signal: r.signal,
            fitScore: r.fit_score ?? 0,
            monthlyReturnMean: r.monthly_return_mean ?? 0,
            monthlyReturnStd: r.monthly_return_std ?? 0,
            historicalPrices: (r.historical_prices || []).map(convertPoint),
            projectedPrices: (r.projected_prices || []).map(convertPoint),
            projectedPricesOptimistic: (r.projected_prices_optimistic || []).map(convertPoint),
            projectedPricesPessimistic: (r.projected_prices_pessimistic || []).map(convertPoint),
            projectedEquity: (r.projected_equity || []).map(convertPoint),
            projectedEquityOptimistic: (r.projected_equity_optimistic || []).map(convertPoint),
            projectedEquityPessimistic: (r.projected_equity_pessimistic || []).map(convertPoint),
            historicalEquity: (r.historical_equity || []).map(convertPoint),
        }));

        return {
            poolName: d.pool_name,
            predictionMonths: d.prediction_months,
            totalAnalyzed: d.total_analyzed,
            timeTakenSeconds: d.time_taken_seconds,
            rankings,
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

    async runStrategyTest(params: StrategyTestParams): Promise<StrategyTestResult> {
        const payload: Record<string, any> = {
            stock_code: params.stockCode,
            start_date: params.startDate,
            end_date: params.endDate,
        };
        if (params.initialCapital !== undefined) { payload.initial_capital = params.initialCapital; }
        if (params.trainRatio !== undefined) { payload.train_ratio = params.trainRatio; }

        const response = await this.client.post<ApiResponse<any>>('/api/v1/backtest/strategy-test', payload);
        if (!response.data.data) {
            throw new Error(response.data.message || '策略测试失败');
        }
        const d = response.data.data;
        const mapPt = (p: any): ProjectedPoint => ({ date: p.date, value: p.value });
        const mapItem = (it: any): StrategyTestItem => ({
            strategy: it.strategy,
            strategyLabel: it.strategy_label,
            trainStart: it.train_start,
            trainEnd: it.train_end,
            testStart: it.test_start,
            testEnd: it.test_end,
            trainBars: it.train_bars,
            testBars: it.test_bars,
            trainReturnPct: it.train_return_pct,
            trainSharpe: it.train_sharpe,
            trainMaxDrawdown: it.train_max_drawdown,
            trainWinRate: it.train_win_rate,
            trainTrades: it.train_trades,
            trainBnhPct: it.train_bnh_pct ?? 0,
            testBnhPct: it.test_bnh_pct ?? 0,
            predictedReturnPct: it.predicted_return_pct,
            predictedDirection: it.predicted_direction,
            actualReturnPct: it.actual_return_pct,
            actualSharpe: it.actual_sharpe,
            actualMaxDrawdown: it.actual_max_drawdown,
            actualWinRate: it.actual_win_rate,
            actualTrades: it.actual_trades,
            actualDirection: it.actual_direction,
            trainAlphaPct: it.train_alpha_pct ?? 0,
            testAlphaPct: it.test_alpha_pct ?? 0,
            directionCorrect: it.direction_correct,
            returnErrorPct: it.return_error_pct,
            confidenceScore: it.confidence_score,
            testHasTrades: it.test_has_trades !== false,
            trainEquity: (it.train_equity || []).map(mapPt),
            testEquityPredicted: (it.test_equity_predicted || []).map(mapPt),
            testEquityActual: (it.test_equity_actual || []).map(mapPt),
            testEquityBnh: (it.test_equity_bnh || []).map(mapPt),
            fullPriceSeries: (it.full_price_series || []).map(mapPt),
        });
        return {
            stockCode: d.stock_code,
            stockName: d.stock_name,
            fullStart: d.full_start,
            fullEnd: d.full_end,
            trainRatio: d.train_ratio,
            totalStrategies: d.total_strategies,
            avgConfidence: d.avg_confidence,
            bestStrategy: d.best_strategy,
            bestStrategyLabel: d.best_strategy_label,
            fullBnhPct: d.full_bnh_pct ?? 0,
            testBnhPct: d.test_bnh_pct ?? 0,
            timeTakenSeconds: d.time_taken_seconds,
            items: (d.items || []).map(mapItem),
        };
    }
}

