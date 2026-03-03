import React from 'react';
import { GameState, PieceData } from '../hooks/useGame';

interface LeftPanelProps {
  gameState: GameState | null;
  aiThinking: boolean;
  agentResults?: any;
  onNewGame: () => void;
  onUndo: () => void;
}

export default function LeftPanel({
  gameState,
  aiThinking,
  agentResults,
  onNewGame,
  onUndo,
}: LeftPanelProps) {
  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  const agents = [
    { id: 'strategy', name: '전략 분석가', icon: '🎯' },
    { id: 'usecase', name: '사례 설계자', icon: '📋' },
    { id: 'winloss', name: '승패 분석가', icon: '📊' },
    { id: 'risk', name: '리스크 평가자', icon: '🛡️' },
    { id: 'report', name: '보고서 생성자', icon: '📝' },
  ];

  const turnLabel = gameState?.current_turn === 'cho' ? '초(楚)' : '한(漢)';
  const turnColor = gameState?.current_turn === 'cho' ? 'var(--accent-cho)' : 'var(--accent-han)';

  return (
    <div className="left-panel">
      {/* 앱 헤더 */}
      <div className="app-header">
        <h1>將棋 AI</h1>
        <div className="subtitle">JANGGI CHAMPION</div>
      </div>

      {/* 플레이어 정보 */}
      <div className="card">
        <div className="card-title">플레이어</div>
        <div className={`player-info ${gameState?.current_turn === 'cho' ? 'active' : ''}`}
             style={{ marginBottom: 8 }}>
          <div className="player-avatar cho">楚</div>
          <div>
            <div style={{ fontWeight: 600 }}>Human (초)</div>
            <div className="timer" style={{ color: 'var(--accent-cho)', fontSize: '1.1rem' }}>
              {formatTime(gameState?.cho_time || 0)}
            </div>
          </div>
        </div>
        <div className={`player-info ${gameState?.current_turn === 'han' ? 'active' : ''}`}>
          <div className="player-avatar han">漢</div>
          <div>
            <div style={{ fontWeight: 600 }}>AI (한)</div>
            <div className="timer" style={{ color: 'var(--accent-han)', fontSize: '1.1rem' }}>
              {formatTime(gameState?.han_time || 0)}
            </div>
          </div>
        </div>
      </div>

      {/* 현재 턴 */}
      <div className="card">
        <div className="card-title">현재 턴</div>
        <div style={{ textAlign: 'center', fontSize: '1.1rem', fontWeight: 700, color: turnColor }}>
          {aiThinking ? 'AI 사고 중...' : `${turnLabel} 차례`}
          {gameState?.is_check && (
            <span style={{ color: 'var(--danger)', marginLeft: 8 }}>장군!</span>
          )}
        </div>
        <div style={{ textAlign: 'center', fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: 4 }}>
          {gameState?.move_count || 0}수 · {
            gameState?.phase === 'opening' ? '초반' :
            gameState?.phase === 'midgame' ? '중반' : '종반'
          }
        </div>
      </div>

      {/* AI 에이전트 상태 */}
      <div className="card">
        <div className="card-title">AI 에이전트 상태</div>
        {agents.map((agent) => {
          const result = agentResults?.[agent.id];
          let ledClass = 'disabled';
          if (aiThinking && result?.status !== 'success' && result?.status !== 'error') {
            ledClass = 'running';
          } else if (result?.status === 'success') {
            ledClass = 'enabled';
          }
          return (
            <div key={agent.id} className="agent-status">
              <span className={`agent-led ${ledClass}`} />
              <span>{agent.icon} {agent.name}</span>
              {result?.time && (
                <span style={{ marginLeft: 'auto', fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                  {result.time}s
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* 포획된 기물 */}
      <div className="card">
        <div className="card-title">포획된 기물</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {(gameState?.captured_pieces || []).map((p, i) => (
            <span key={i} style={{
              color: p.team === 'cho' ? 'var(--accent-cho)' : 'var(--accent-han)',
              fontSize: '1.2rem',
              fontFamily: 'serif',
            }}>
              {p.hanja}
            </span>
          ))}
          {(!gameState?.captured_pieces || gameState.captured_pieces.length === 0) && (
            <span style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>없음</span>
          )}
        </div>
      </div>

      {/* 수 기록 */}
      <div className="card" style={{ flex: 1, minHeight: 0 }}>
        <div className="card-title">경기 기록</div>
        <div className="move-list">
          {gameState?.status === 'playing' ? (
            <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', padding: 8 }}>
              경기 진행 중...
            </div>
          ) : gameState?.status === 'cho_win' ? (
            <div style={{ color: 'var(--accent-cho)', fontWeight: 700, padding: 8 }}>
              초(楚) 승리!
            </div>
          ) : gameState?.status === 'han_win' ? (
            <div style={{ color: 'var(--accent-han)', fontWeight: 700, padding: 8 }}>
              한(漢) 승리!
            </div>
          ) : gameState?.status === 'draw' ? (
            <div style={{ fontWeight: 700, padding: 8 }}>무승부</div>
          ) : null}
        </div>
      </div>

      {/* 버튼 */}
      <div className="btn-group">
        <button className="btn btn-primary" onClick={onNewGame} style={{ flex: 1 }}>
          새 게임
        </button>
        <button className="btn btn-secondary" onClick={onUndo} style={{ flex: 1 }}
                disabled={!gameState || gameState.move_count < 2}>
          무르기
        </button>
      </div>
    </div>
  );
}
