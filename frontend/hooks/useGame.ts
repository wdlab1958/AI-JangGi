import { useState, useCallback, useRef } from 'react';

// Next.js rewrite 프록시 사용 (CORS 회피) - next.config.js 에서 /api/* → localhost:8007/api/* 프록시
const API_BASE = '';

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

export interface MoveRecord {
  ply: number;
  team: string;
  from: [number, number];
  to: [number, number];
  hanja: string;
  captured: string | null;
}

export interface GameSettings {
  aiTeam: 'cho' | 'han';
  choFormation: string;
  hanFormation: string;
  aiDepth: number;
  aiTimeLimit: number;
}

export const DEFAULT_SETTINGS: GameSettings = {
  aiTeam: 'han',
  choFormation: '내상외마',
  hanFormation: '내상외마',
  aiDepth: 6,
  aiTimeLimit: 3.0,
};

function toRecord(ply: number, mv: any): MoveRecord | null {
  if (!mv?.move) return null;
  const m = mv.move;
  return {
    ply,
    team: m.piece?.team ?? 'unknown',
    from: m.from as [number, number],
    to: m.to as [number, number],
    hanja: m.piece?.hanja ?? '',
    captured: m.captured?.hanja ?? null,
  };
}

export function useGame() {
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [loading, setLoading] = useState(false);
  const [aiThinking, setAiThinking] = useState(false);
  const [lastAiAnalysis, setLastAiAnalysis] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [moveHistory, setMoveHistory] = useState<MoveRecord[]>([]);
  const [report, setReport] = useState<any>(null);
  const [stats, setStats] = useState<any>(null);
  // gameId/aiTeam 를 ref로 저장하여 콜백 클로저 문제 방지
  const gameIdRef = useRef<string | null>(null);
  const aiTeamRef = useRef<string>('han');
  const plyRef = useRef<number>(0);

  const clearError = useCallback(() => setError(null), []);

  const refreshStats = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/stats`);
      if (res.ok) setStats(await res.json());
    } catch (err) {
      console.error('[useGame] refreshStats error:', err);
    }
  }, []);

  const fetchReport = useCallback(async (gid: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/game/${gid}/report`);
      if (res.ok) setReport(await res.json());
    } catch (err) {
      console.error('[useGame] fetchReport error:', err);
    }
  }, []);

  const createGame = useCallback(async (settings: GameSettings = DEFAULT_SETTINGS) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/game/new`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          cho_formation: settings.choFormation,
          han_formation: settings.hanFormation,
          ai_team: settings.aiTeam,
          ai_depth: settings.aiDepth,
          ai_time_limit: settings.aiTimeLimit,
        }),
      });
      if (!res.ok) {
        setError(`새 게임 생성 실패 (HTTP ${res.status})`);
        return null;
      }
      const data = await res.json();
      gameIdRef.current = data.game_id;
      aiTeamRef.current = settings.aiTeam;
      plyRef.current = 0;
      setGameState(data);
      setLastAiAnalysis(null);
      setReport(null);
      setMoveHistory([]);

      // 인간이 한(漢)을 선택 → 초(楚)=AI 가 선수. AI 첫 수 트리거.
      if (data.current_turn === settings.aiTeam) {
        setAiThinking(true);
        try {
          const aiRes = await fetch(`${API_BASE}/api/game/${data.game_id}/ai-move`, { method: 'POST' });
          if (aiRes.ok) {
            const aiData = await aiRes.json();
            if (aiData.ai_move) {
              setLastAiAnalysis(aiData.ai_move);
              const rec = toRecord(++plyRef.current, aiData.ai_move);
              if (rec) setMoveHistory((h) => [...h, rec]);
            }
            const stateRes = await fetch(`${API_BASE}/api/game/${data.game_id}/state`);
            if (stateRes.ok) setGameState(await stateRes.json());
          }
        } finally {
          setAiThinking(false);
        }
      }
      return data;
    } catch (err) {
      console.error('[useGame] createGame error:', err);
      setError('서버에 연결할 수 없습니다.');
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
      setError('진행 중인 게임이 없습니다.');
      return null;
    }
    setAiThinking(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/game/${gid}/move`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          from_row: fromRow, from_col: fromCol,
          to_row: toRow, to_col: toCol,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        setError(`수를 둘 수 없습니다: ${err.detail ?? res.status}`);
        return null;
      }

      const data = await res.json();
      // 기보 기록: 인간 수 → AI 수 순
      const recs: MoveRecord[] = [];
      const hRec = toRecord(++plyRef.current, data.human_move);
      if (hRec) recs.push(hRec);
      if (data.ai_move) {
        setLastAiAnalysis(data.ai_move);
        const aRec = toRecord(++plyRef.current, data.ai_move);
        if (aRec) recs.push(aRec);
      }
      if (recs.length) setMoveHistory((h) => [...h, ...recs]);

      // 상태 갱신
      const stateRes = await fetch(`${API_BASE}/api/game/${gid}/state`);
      let newState: GameState | null = null;
      if (stateRes.ok) {
        newState = await stateRes.json();
        setGameState(newState);
      }

      // 게임 종료 시 보고서/통계 갱신
      if (newState && newState.status !== 'playing') {
        await fetchReport(gid);
        await refreshStats();
      }

      return data;
    } catch (err) {
      console.error('[useGame] makeMove error:', err);
      setError('수를 처리하는 중 오류가 발생했습니다.');
      return null;
    } finally {
      setAiThinking(false);
    }
  }, [fetchReport, refreshStats]);

  const getValidMoves = useCallback(async (row: number, col: number): Promise<[number, number][]> => {
    const gid = gameIdRef.current;
    if (!gid) return [];
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
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/game/${gid}/undo`, { method: 'POST' });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        setError(`무르기 실패: ${err.detail ?? res.status}`);
        return;
      }
      // 무르기는 한 턴(인간+AI 2수)을 되돌린다 → 기보도 2개 제거
      setMoveHistory((h) => h.slice(0, Math.max(0, h.length - 2)));
      plyRef.current = Math.max(0, plyRef.current - 2);
      const stateRes = await fetch(`${API_BASE}/api/game/${gid}/state`);
      if (stateRes.ok) setGameState(await stateRes.json());
    } catch (err) {
      console.error('[useGame] undoMove error:', err);
      setError('무르기 중 오류가 발생했습니다.');
    }
  }, []);

  return {
    gameState,
    setGameState,
    loading,
    aiThinking,
    lastAiAnalysis,
    error,
    clearError,
    moveHistory,
    report,
    stats,
    refreshStats,
    createGame,
    makeMove,
    getValidMoves,
    undoMove,
  };
}
