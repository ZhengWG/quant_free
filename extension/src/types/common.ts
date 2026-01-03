/**
 * 通用类型定义
 */

export interface ApiResponse<T = any> {
    success: boolean;
    data?: T;
    message?: string;
    error?: string;
}

export interface PaginationParams {
    page: number;
    pageSize: number;
}

export interface PaginationResult<T> {
    items: T[];
    total: number;
    page: number;
    pageSize: number;
}

export type MarketType = 'A股' | '港股' | '美股' | '基金' | '期货';

export interface BaseEntity {
    id: string;
    createdAt: Date;
    updatedAt: Date;
}

