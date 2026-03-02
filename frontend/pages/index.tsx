import React, { useEffect, useCallback, useState } from 'react';
import Head from 'next/head';
import dynamic from 'next/dynamic';
import { useGame } from '../hooks/useGame';
import LeftPanel from '../components/LeftPanel';
import RightPanel from '../components/RightPanel';

// JanggiBoard는 Canvas API를 사용하므로 SSR 비활성화
const JanggiBoard = dynamic(() => import('../components/JanggiBoard'), {
  ssr: false,
  loading: () => (
    <div style={{
      width: 620, height: 720,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      color: 'var(--text-secondary)',
    }}>
      장기판 로딩 중...
    </div>
  ),
});

export default function Home() {
  const {
    gameState,
    loading,
    aiThinking,
    lastAiAnalysis,
    createGame,
    makeMove,
    getValidMoves,
    undoMove,
  } = useGame();

  const [agentResults, setAgentResults] = useState<any>(null);
  const [lastAiMove, setLastAiMove] = useState<{ from: [number, number]; to: [number, number]; team: string } | null>(null);

  // 초기 게임 생성 (StrictMode 중복 방지)
  const initialized = React.useRef(false);
  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    createGame();
  }, []);

  // AI 분석 결과에서 에이전트 결과 + 마지막 수 추출
  useEffect(() => {
    if (lastAiAnalysis?.agent_results) {
      setAgentResults(lastAiAnalysis.agent_results);
    }
    if (lastAiAnalysis?.move) {
      const m = lastAiAnalysis.move;
      setLastAiMove({
        from: m.from as [number, number],
        to: m.to as [number, number],
        team: m.piece?.team || 'han',
      });
    }
  }, [lastAiAnalysis]);

  const handleMove = useCallback(async (
    fromRow: number, fromCol: number,
    toRow: number, toCol: number,
  ) => {
    await makeMove(fromRow, fromCol, toRow, toCol);
  }, [makeMove]);

  const handleGetValidMoves = useCallback(async (row: number, col: number) => {
    return await getValidMoves(row, col);
  }, [getValidMoves]);

  const handleNewGame = useCallback(async () => {
    await createGame();
    setAgentResults(null);
    setLastAiMove(null);
  }, [createGame]);

  const handleUndo = useCallback(async () => {
    await undoMove();
  }, [undoMove]);

  const emptyBoard = Array.from({ length: 10 }, () => Array(9).fill(null));

  return (
    <>
      <Head>
        <title>장기 챔피언 AI - JANGGI CHAMPION</title>
      </Head>

      <div className="app-container">
        {/* 좌측 패널: 플레이어 정보, 에이전트 상태, 경기 기록 */}
        <LeftPanel
          gameState={gameState}
          aiThinking={aiThinking}
          agentResults={agentResults}
          onNewGame={handleNewGame}
          onUndo={handleUndo}
        />

        {/* 중앙: 장기판 */}
        <div className="center-panel">
          {aiThinking && (
            <div style={{
              marginBottom: 12,
              padding: '8px 24px',
              background: 'rgba(52, 152, 219, 0.15)',
              border: '1px solid var(--accent-han)',
              borderRadius: 8,
              fontSize: '0.85rem',
              color: 'var(--accent-han)',
              animation: 'pulse 1.5s infinite',
            }}>
              AI 분석 중... 5개 에이전트 파이프라인 실행
            </div>
          )}
          <JanggiBoard
            board={gameState?.board || emptyBoard}
            currentTurn={gameState?.current_turn || 'cho'}
            humanTeam="cho"
            isCheck={gameState?.is_check || false}
            lastMove={lastAiMove}
            onMove={handleMove}
            onGetValidMoves={handleGetValidMoves}
            disabled={aiThinking || loading || (gameState != null && gameState.status !== 'playing')}
          />
          {gameState && gameState.status !== 'playing' && (
            <div style={{
              marginTop: 16,
              padding: '12px 32px',
              background: gameState.status === 'cho_win'
                ? 'rgba(192, 57, 43, 0.2)'
                : gameState.status === 'han_win'
                ? 'rgba(36, 113, 163, 0.2)'
                : 'rgba(255,255,255,0.1)',
              border: `1px solid ${
                gameState.status === 'cho_win' ? 'var(--accent-cho)' :
                gameState.status === 'han_win' ? 'var(--accent-han)' : 'var(--border-color)'
              }`,
              borderRadius: 8,
              textAlign: 'center',
              fontSize: '1.2rem',
              fontWeight: 700,
            }}>
              {gameState.status === 'cho_win' ? '초(楚) 승리!' :
               gameState.status === 'han_win' ? '한(漢) 승리!' : '무승부'}
            </div>
          )}
        </div>

        {/* 우측 패널: AI 분석 대시보드 */}
        <RightPanel
          gameState={gameState}
          aiAnalysis={lastAiAnalysis}
        />
      </div>
    </>
  );
}
