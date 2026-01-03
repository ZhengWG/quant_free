/**
 * 数据格式化工具
 */

export function formatPrice(price: number, decimals: number = 2): string {
    return price.toFixed(decimals);
}

export function formatPercent(value: number, decimals: number = 2): string {
    const sign = value >= 0 ? '+' : '';
    return `${sign}${value.toFixed(decimals)}%`;
}

export function formatVolume(volume: number): string {
    if (volume >= 100000000) {
        return `${(volume / 100000000).toFixed(2)}亿`;
    } else if (volume >= 10000) {
        return `${(volume / 10000).toFixed(2)}万`;
    }
    return volume.toString();
}

export function formatAmount(amount: number): string {
    if (amount >= 100000000) {
        return `${(amount / 100000000).toFixed(2)}亿`;
    } else if (amount >= 10000) {
        return `${(amount / 10000).toFixed(2)}万`;
    }
    return amount.toFixed(2);
}

export function formatDate(date: Date | string): string {
    const d = typeof date === 'string' ? new Date(date) : date;
    return d.toLocaleString('zh-CN');
}

export function getColorByChange(change: number): string {
    if (change > 0) {
        return '#ff4d4f'; // 红色（涨）
    } else if (change < 0) {
        return '#52c41a'; // 绿色（跌）
    }
    return '#8c8c8c'; // 灰色（平）
}

