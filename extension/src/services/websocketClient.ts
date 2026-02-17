/**
 * WebSocket客户端服务
 */

import WebSocket = require('ws');
import http = require('http');

export interface WebSocketMessage {
    type: string;
    data: any;
}

export class WebSocketClient {
    private ws: WebSocket | null = null;
    private url: string;
    private reconnectInterval: number = 5000;
    private maxReconnectInterval: number = 60000;
    private reconnectAttempts: number = 0;
    private maxReconnectAttempts: number = 5;
    private reconnectTimer: NodeJS.Timeout | null = null;
    private subscribers: Map<string, Set<(data: any) => void>> = new Map();
    private manualDisconnect: boolean = false;

    constructor(url: string) {
        // 正确转换协议: http->ws, https->wss
        this.url = url.replace(/^https:/, 'wss:').replace(/^http:/, 'ws:');
        if (!this.url.endsWith('/ws')) {
            this.url = this.url.replace(/\/$/, '') + '/ws';
        }
    }

    async connect(): Promise<void> {
        this.manualDisconnect = false;

        return new Promise((resolve) => {
            try {
                // 使用独立的http.Agent绕过VSCode/Cursor的代理
                this.ws = new WebSocket(this.url, {
                    agent: new http.Agent(),
                    headers: {
                        'Origin': 'vscode-extension',
                    },
                    handshakeTimeout: 5000,
                });

                this.ws.on('open', () => {
                    console.log('[WebSocket] Connected to', this.url);
                    this.reconnectAttempts = 0;
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
                    console.warn('[WebSocket] Error:', error.message);
                });

                this.ws.on('close', () => {
                    console.log('[WebSocket] Disconnected');
                    if (!this.manualDisconnect) {
                        this.scheduleReconnect();
                    }
                    resolve();
                });
            } catch (error) {
                console.warn('[WebSocket] Failed to create connection:', error);
                resolve();
            }
        });
    }

    disconnect(): void {
        this.manualDisconnect = true;
        this.clearReconnectTimer();
        this.reconnectAttempts = 0;
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
        if (this.manualDisconnect) {
            return;
        }

        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.warn(`[WebSocket] Max reconnect attempts (${this.maxReconnectAttempts}) reached. Server may not be running.`);
            return;
        }

        this.clearReconnectTimer();
        this.reconnectAttempts++;

        const delay = Math.min(
            this.reconnectInterval * Math.pow(2, this.reconnectAttempts - 1),
            this.maxReconnectInterval
        );

        console.log(`[WebSocket] Reconnecting in ${delay / 1000}s (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);

        this.reconnectTimer = setTimeout(() => {
            this.connect().catch(error => {
                console.warn('[WebSocket] Reconnect failed:', error);
            });
        }, delay);
    }

    private clearReconnectTimer(): void {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
    }
}
