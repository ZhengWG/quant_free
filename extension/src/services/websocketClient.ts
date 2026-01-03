/**
 * WebSocket客户端服务
 */

import WebSocket = require('ws');
import { Stock } from '../types/market';
import { Order } from '../types/trade';

export interface WebSocketMessage {
    type: string;
    data: any;
}

export class WebSocketClient {
    private ws: WebSocket | null = null;
    private url: string;
    private reconnectInterval: number = 5000;
    private reconnectTimer: NodeJS.Timeout | null = null;
    private subscribers: Map<string, Set<(data: any) => void>> = new Map();

    constructor(url: string) {
        this.url = url.replace('http', 'ws');
    }

    async connect(): Promise<void> {
        return new Promise((resolve, reject) => {
            try {
                this.ws = new WebSocket(this.url);

                this.ws.on('open', () => {
                    console.log('[WebSocket] Connected');
                    this.clearReconnectTimer();
                    resolve();
                });

                this.ws.on('message', (data: WebSocket.Data) => {
                    try {
                        const message: WebSocketMessage = JSON.parse(data.toString());
                        this.handleMessage(message);
                    } catch (error) {
                        console.error('[WebSocket] Parse message error:', error);
                    }
                });

                this.ws.on('error', (error: Error) => {
                    console.error('[WebSocket] Error:', error);
                    reject(error);
                });

                this.ws.on('close', () => {
                    console.log('[WebSocket] Disconnected');
                    this.scheduleReconnect();
                });
            } catch (error) {
                reject(error);
            }
        });
    }

    disconnect(): void {
        this.clearReconnectTimer();
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }

    subscribe(event: string, callback: (data: any) => void): () => void {
        if (!this.subscribers.has(event)) {
            this.subscribers.set(event, new Set());
        }
        this.subscribers.get(event)!.add(callback);

        // 返回取消订阅函数
        return () => {
            this.subscribers.get(event)?.delete(callback);
        };
    }

    private handleMessage(message: WebSocketMessage): void {
        const callbacks = this.subscribers.get(message.type);
        if (callbacks) {
            callbacks.forEach(callback => {
                try {
                    callback(message.data);
                } catch (error) {
                    console.error(`[WebSocket] Callback error for ${message.type}:`, error);
                }
            });
        }
    }

    send(message: WebSocketMessage): void {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message));
        } else {
            console.warn('[WebSocket] Not connected, message not sent:', message);
        }
    }

    subscribeMarketData(codes: string[]): void {
        this.send({
            type: 'subscribe',
            data: { codes }
        });
    }

    unsubscribeMarketData(codes: string[]): void {
        this.send({
            type: 'unsubscribe',
            data: { codes }
        });
    }

    private scheduleReconnect(): void {
        this.clearReconnectTimer();
        this.reconnectTimer = setTimeout(() => {
            console.log('[WebSocket] Attempting to reconnect...');
            this.connect().catch(error => {
                console.error('[WebSocket] Reconnect failed:', error);
            });
        }, this.reconnectInterval);
    }

    private clearReconnectTimer(): void {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
    }
}

