/**
 * 数据验证工具
 */

export function isValidStockCode(code: string): boolean {
    // A股：6位数字
    // 港股：5位数字
    // 美股：1-5位字母
    const aSharePattern = /^\d{6}$/;
    const hkSharePattern = /^\d{5}$/;
    const usSharePattern = /^[A-Z]{1,5}$/;
    
    return aSharePattern.test(code) || hkSharePattern.test(code) || usSharePattern.test(code);
}

export function validateOrder(order: {
    stockCode: string;
    quantity: number;
    price?: number;
    orderType: string;
}): { valid: boolean; error?: string } {
    if (!isValidStockCode(order.stockCode)) {
        return { valid: false, error: '无效的股票代码' };
    }

    if (order.quantity <= 0 || !Number.isInteger(order.quantity)) {
        return { valid: false, error: '数量必须为正整数' };
    }

    if (order.orderType === 'LIMIT' && (!order.price || order.price <= 0)) {
        return { valid: false, error: '限价单必须指定有效价格' };
    }

    return { valid: true };
}

