import { useEffect, useRef, useCallback, useState } from 'react';

interface WSMessage {
  event: string;
  data: any;
}

export function useWebSocket(gameId: string | null) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WSMessage | null>(null);
  const handlersRef = useRef<Map<string, (data: any) => void>>(new Map());

  const connect = useCallback(() => {
    if (!gameId) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.hostname;
    const ws = new WebSocket(`${protocol}//${host}:8001/ws/${gameId}`);

    ws.onopen = () => {
      setConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data);
        setLastMessage(msg);

        const handler = handlersRef.current.get(msg.event);
        if (handler) {
          handler(msg.data);
        }
      } catch (e) {
        console.error('WebSocket message parse error:', e);
      }
    };

    ws.onclose = () => {
      setConnected(false);
      // 재연결
      setTimeout(() => {
        if (gameId) connect();
      }, 3000);
    };

    ws.onerror = () => {
      ws.close();
    };

    wsRef.current = ws;
  }, [gameId]);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
    };
  }, [connect]);

  const send = useCallback((event: string, data: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ event, data }));
    }
  }, []);

  const on = useCallback((event: string, handler: (data: any) => void) => {
    handlersRef.current.set(event, handler);
  }, []);

  const off = useCallback((event: string) => {
    handlersRef.current.delete(event);
  }, []);

  return { connected, lastMessage, send, on, off };
}
