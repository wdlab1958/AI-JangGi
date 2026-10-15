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

    // 동일 출처(same-origin)로 연결. 개발 시 Next dev 프록시가 /ws → 백엔드(8007)로
    // 전달하고, 프로덕션에서는 FastAPI 가 직접 서빙하므로 포트 하드코딩이 불필요하다.
    // (이전: ':8001' 하드코딩 — 실제 백엔드는 8007 이라 항상 연결 실패하던 버그, G18)
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host; // hostname:port
    const ws = new WebSocket(`${protocol}//${host}/ws/${gameId}`);

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
