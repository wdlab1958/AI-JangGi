import { useState, useCallback, useRef } from 'react';

const API_BASE = 'http://localhost:8001';

export interface PieceData {
  type: string;
  team: string;
  row: number;
  col: number;
  captured: boolean;
  hanja: string;
  value: number;
}

export interface GameState {
  game_id: string;
  board: (PieceData | null)[][];
  current_turn: string;
  status: string;
  move_count: number;
  phase: string;
  is_check: boolean;
  cho_time: number;
  han_time: number;
  captured_pieces: PieceData[];
  evaluation: any;
  win_probability?: number;
}

export function useGame() {
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [loading, setLoading] = useState(false);
  const [aiThinking, setAiThinking] = useState(false);
  const [lastAiAnalysis, setLastAiAnalysis] = useState<any>(null);
  // gameId를 ref로 저장하여 콜백 클로저 문제 방지
  const gameIdRef = useRef<string | null>(null);

  const createGame = useCallback(async (
    choFormation = '내상외마',
    hanFormation = '내상외마',
    aiTeam = 'han',
  ) => {
    setLoading(true);
    try {
      console.log('[useGame] creating new game...');
      const res = await fetch(`${API_BASE}/api/game/new`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          cho_formation: choFormation,
          han_formation: hanFormation,
          ai_team: aiTeam,
        }),
      });
      if (!res.ok) {
        console.error('[useGame] createGame failed:', res.status, res.statusText);
        return null;
      }
      const data = await res.json();
      console.log('[useGame] game created:', data.game_id, 'status:', data.status);
      gameIdRef.current = data.game_id;
      setGameState(data);
      setLastAiAnalysis(null);
      return data;
    } catch (err) {
      console.error('[useGame] createGame error:', err);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const makeMove = useCallback(async (
    fromRow: number, fromCol: number,
    toRow: number, toCol: number,
  ) => {
    const gid = gameIdRef.current;
    if (!gid) {
      console.error('[useGame] makeMove: no game_id');
      return null;
    }
    setAiThinking(true);
    try {
      console.log('[useGame] making move:', fromRow, fromCol, '->', toRow, toCol);
      const res = await fetch(`${API_BASE}/api/game/${gid}/move`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          from_row: fromRow,
          from_col: fromCol,
          to_row: toRow,
          to_col: toCol,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        console.error('[useGame] makeMove failed:', err);
        return null;
      }

      const data = await res.json();
      console.log('[useGame] move result:', data.human_move?.success, 'ai:', data.ai_move?.success);

      if (data.ai_move) {
        setLastAiAnalysis(data.ai_move);
      }

      // 상태 갱신
      const stateRes = await fetch(`${API_BASE}/api/game/${gid}/state`);
      if (stateRes.ok) {
        const stateData = await stateRes.json();
        setGameState(stateData);
      }

      return data;
    } catch (err) {
      console.error('[useGame] makeMove error:', err);
      return null;
    } finally {
      setAiThinking(false);
    }
  }, []);

  const getValidMoves = useCallback(async (row: number, col: number): Promise<[number, number][]> => {
    const gid = gameIdRef.current;
    if (!gid) {
      console.error('[useGame] getValidMoves: no game_id');
      return [];
    }
    try {
      const res = await fetch(`${API_BASE}/api/game/${gid}/valid-moves`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ row, col }),
      });
      if (res.ok) {
        const data = await res.json();
        return data.valid_moves || [];
      }
      console.error('[useGame] getValidMoves failed:', res.status);
    } catch (err) {
      console.error('[useGame] getValidMoves error:', err);
    }
    return [];
  }, []);

  const undoMove = useCallback(async () => {
    const gid = gameIdRef.current;
    if (!gid) return;
    try {
      const res = await fetch(`${API_BASE}/api/game/${gid}/undo`, { method: 'POST' });
      if (res.ok) {
        const stateRes = await fetch(`${API_BASE}/api/game/${gid}/state`);
        if (stateRes.ok) {
          const stateData = await stateRes.json();
          setGameState(stateData);
        }
      }
    } catch (err) {
      console.error('[useGame] undoMove error:', err);
    }
  }, []);

  return {
    gameState,
    setGameState,
    loading,
    aiThinking,
    lastAiAnalysis,
    createGame,
    makeMove,
    getValidMoves,
    undoMove,
  };
}
