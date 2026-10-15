import React from 'react';
import { GameState, MoveRecord, GameSettings } from '../hooks/useGame';

interface LeftPanelProps {
  gameState: GameState | null;
  aiThinking: boolean;
  agentResults?: any;
  moveHistory: MoveRecord[];
  stats: any;
  settings: GameSettings;
  humanTeam: string;
  onSettingsChange: (s: GameSettings) => void;
  onNewGame: () => void;
  onUndo: () => void;
}

const FORMATIONS = ['내상외마', '외상내마', '좌상우마', '우상좌마'];

export default function LeftPanel({
  gameState,
  aiThinking,
  agentResults,
  moveHistory,
  stats,
  settings,
  humanTeam,
  onSettingsChange,
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

  const humanIsCho = humanTeam === 'cho';
  const update = (patch: Partial<GameSettings>) => onSettingsChange({ ...settings, ...patch });

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
            <div style={{ fontWeight: 600 }}>{humanIsCho ? 'Human' : 'AI'} (초)</div>
            <div className="timer" style={{ color: 'var(--accent-cho)', fontSize: '1.1rem' }}>
              {formatTime(gameState?.cho_time || 0)}
            </div>
          </div>
        </div>
        <div className={`player-info ${gameState?.current_turn === 'han' ? 'active' : ''}`}>
          <div className="player-avatar han">漢</div>
          <div>
            <div style={{ fontWeight: 600 }}>{humanIsCho ? 'AI' : 'Human'} (한)</div>
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

      {/* 게임 설정 (다음 '새 게임'부터 적용) */}
      <div className="card">
        <div className="card-title">게임 설정 <span style={{ fontSize: '0.65rem', color: 'var(--text-secondary)', fontWeight: 400 }}>· 새 게임부터 적용</span></div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: '0.8rem' }}>
          <label style={rowStyle}>
            <span>내 진영</span>
            <select value={settings.aiTeam}
              onChange={(e) => update({ aiTeam: e.target.value as 'cho' | 'han' })}
              style={selStyle}>
              <option value="han">초(楚) · 선수</option>
              <option value="cho">한(漢) · 후수</option>
            </select>
          </label>
          <label style={rowStyle}>
            <span>AI 난이도</span>
            <select value={settings.aiDepth}
              onChange={(e) => update({ aiDepth: Number(e.target.value) })}
              style={selStyle}>
              <option value={2}>쉬움 (깊이 2)</option>
              <option value={4}>보통 (깊이 4)</option>
              <option value={6}>어려움 (깊이 6)</option>
              <option value={8}>최고수 (깊이 8)</option>
            </select>
          </label>
          <label style={rowStyle}>
            <span>제한시간</span>
            <select value={settings.aiTimeLimit}
              onChange={(e) => update({ aiTimeLimit: Number(e.target.value) })}
              style={selStyle}>
              <option value={1}>1초</option>
              <option value={3}>3초</option>
              <option value={5}>5초</option>
              <option value={10}>10초</option>
            </select>
          </label>
          <label style={rowStyle}>
            <span>초 차림</span>
            <select value={settings.choFormation}
              onChange={(e) => update({ choFormation: e.target.value })}
              style={selStyle}>
              {FORMATIONS.map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
          </label>
          <label style={rowStyle}>
            <span>한 차림</span>
            <select value={settings.hanFormation}
              onChange={(e) => update({ hanFormation: e.target.value })}
              style={selStyle}>
              {FORMATIONS.map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
          </label>
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

      {/* 누적 전적 (Long-term Memory) */}
      {stats && (
        <div className="card">
          <div className="card-title">누적 전적</div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
            <span>총 {stats.total_games ?? 0}국</span>
            <span style={{ color: 'var(--success)' }}>{stats.wins ?? 0}승</span>
            <span style={{ color: 'var(--danger)' }}>{stats.losses ?? 0}패</span>
            <span>{stats.draws ?? 0}무</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: 4 }}>
            <span>ELO {stats.elo_rating ?? 1500}</span>
            <span>승률 {((stats.win_rate ?? 0) * 100).toFixed(1)}%</span>
            <span>연승 {stats.current_streak ?? 0}</span>
          </div>
        </div>
      )}

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

      {/* 경기 기록 (기보) */}
      <div className="card" style={{ flex: 1, minHeight: 80 }}>
        <div className="card-title">경기 기록 ({moveHistory.length}수)</div>
        <div className="move-list" style={{ maxHeight: 180, overflowY: 'auto', fontSize: '0.78rem' }}>
          {moveHistory.length === 0 ? (
            <div style={{ color: 'var(--text-secondary)', padding: 8 }}>아직 둔 수가 없습니다.</div>
          ) : (
            moveHistory.map((m) => (
              <div key={m.ply} style={{
                display: 'flex', gap: 6, padding: '2px 6px',
                color: m.team === 'cho' ? 'var(--accent-cho)' : 'var(--accent-han)',
              }}>
                <span style={{ width: 22, color: 'var(--text-secondary)' }}>{m.ply}.</span>
                <span style={{ fontFamily: 'serif' }}>{m.hanja}</span>
                <span style={{ color: 'var(--text-secondary)' }}>
                  ({m.from[0]},{m.from[1]})→({m.to[0]},{m.to[1]})
                </span>
                {m.captured && <span title="포획">×{m.captured}</span>}
              </div>
            ))
          )}
        </div>
      </div>

      {/* 버튼 */}
      <div className="btn-group">
        <button className="btn btn-primary" onClick={onNewGame} style={{ flex: 1 }}>
          새 게임
        </button>
        <button className="btn btn-secondary" onClick={onUndo} style={{ flex: 1 }}
                title="한 턴(인간+AI 2수)을 되돌립니다"
                disabled={!gameState || gameState.move_count < 2}>
          무르기
        </button>
      </div>
    </div>
  );
}

const rowStyle: React.CSSProperties = {
  display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8,
};

const selStyle: React.CSSProperties = {
  background: 'var(--bg-secondary, #16213e)',
  color: 'var(--text-primary, #eee)',
  border: '1px solid var(--border-color, #333)',
  borderRadius: 4,
  padding: '2px 6px',
  fontSize: '0.78rem',
};
