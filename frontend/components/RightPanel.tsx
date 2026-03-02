import React, { useEffect, useRef } from 'react';
import { GameState } from '../hooks/useGame';

interface RightPanelProps {
  gameState: GameState | null;
  aiAnalysis: any;
}

export default function RightPanel({ gameState, aiAnalysis }: RightPanelProps) {
  const chartRef = useRef<HTMLCanvasElement>(null);
  const winHistoryRef = useRef<number[]>([]);

  const evaluation = gameState?.evaluation || {};
  const report = aiAnalysis?.report || {};
  const summary = report?.summary || {};
  const dashboard = report?.dashboard || {};
  const aiThinking = report?.ai_thinking || [];
  const winProb = aiAnalysis?.win_probability ?? gameState?.win_probability ?? 50;

  // 승률 히스토리 업데이트
  useEffect(() => {
    if (winProb !== undefined) {
      winHistoryRef.current.push(winProb);
      if (winHistoryRef.current.length > 50) {
        winHistoryRef.current = winHistoryRef.current.slice(-50);
      }
      drawChart();
    }
  }, [winProb]);

  const drawChart = () => {
    const canvas = chartRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const history = winHistoryRef.current;
    const w = canvas.width;
    const h = canvas.height;

    ctx.clearRect(0, 0, w, h);

    // Background
    ctx.fillStyle = 'rgba(15, 52, 96, 0.5)';
    ctx.fillRect(0, 0, w, h);

    // 50% line
    ctx.strokeStyle = 'rgba(255,255,255,0.2)';
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(0, h / 2);
    ctx.lineTo(w, h / 2);
    ctx.stroke();
    ctx.setLineDash([]);

    if (history.length < 2) return;

    // Draw line
    const stepX = w / Math.max(history.length - 1, 1);
    ctx.strokeStyle = '#3498db';
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (let i = 0; i < history.length; i++) {
      const x = i * stepX;
      const y = h - (history[i] / 100) * h;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Fill area under line
    ctx.lineTo((history.length - 1) * stepX, h);
    ctx.lineTo(0, h);
    ctx.closePath();
    ctx.fillStyle = 'rgba(52, 152, 219, 0.15)';
    ctx.fill();

    // Current point
    const lastX = (history.length - 1) * stepX;
    const lastY = h - (history[history.length - 1] / 100) * h;
    ctx.fillStyle = '#3498db';
    ctx.beginPath();
    ctx.arc(lastX, lastY, 4, 0, Math.PI * 2);
    ctx.fill();
  };

  const riskGrade = dashboard?.risk_indicator?.grade || 'UNKNOWN';
  const riskClass = riskGrade === 'LOW' ? 'risk-low' :
    riskGrade === 'MEDIUM' ? 'risk-medium' :
    riskGrade === 'HIGH' ? 'risk-high' : 'risk-critical';

  const evalBreakdown = dashboard?.evaluation_breakdown || evaluation?.weighted || {};

  return (
    <div className="right-panel">
      {/* AI 분석 대시보드 */}
      <div className="card">
        <div className="card-title">AI 분석 대시보드</div>

        {/* 승률 게이지 */}
        <div style={{ marginBottom: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', marginBottom: 4 }}>
            <span style={{ color: 'var(--accent-cho)' }}>초 {(100 - winProb).toFixed(1)}%</span>
            <span style={{ color: 'var(--accent-han)' }}>한 {winProb.toFixed(1)}%</span>
          </div>
          <div className="win-gauge">
            <div className="win-gauge-fill" style={{ width: `${winProb}%` }} />
            <div className="win-gauge-label">AI {winProb.toFixed(0)}%</div>
          </div>
        </div>

        {/* 상태 요약 */}
        {summary.status && (
          <div style={{ textAlign: 'center', marginBottom: 8 }}>
            <span style={{
              fontWeight: 700,
              color: winProb > 55 ? 'var(--success)' :
                     winProb > 45 ? 'var(--text-primary)' : 'var(--danger)',
            }}>
              {summary.status}
            </span>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: 2 }}>
              {summary.outlook}
            </div>
          </div>
        )}
      </div>

      {/* 승률 추이 차트 */}
      <div className="card">
        <div className="card-title">승률 추이</div>
        <canvas
          ref={chartRef}
          width={360}
          height={120}
          style={{ width: '100%', borderRadius: 4 }}
        />
      </div>

      {/* 판면 평가 */}
      <div className="card">
        <div className="card-title">판면 평가</div>
        <EvalBar label="기물 (Material)" value={evalBreakdown.material || 0} maxVal={10} />
        <EvalBar label="위치 (Position)" value={evalBreakdown.position || 0} maxVal={5} />
        <EvalBar label="기동성 (Mobility)" value={evalBreakdown.mobility || 0} maxVal={5} />
        <EvalBar label="왕 안전 (King Safety)" value={evalBreakdown.king_safety || 0} maxVal={5} />
        <div style={{ textAlign: 'right', fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: 4 }}>
          종합: {evaluation?.total ?? '-'}
        </div>
      </div>

      {/* 리스크 지표 */}
      <div className="card">
        <div className="card-title">리스크 지표</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span className={`risk-badge ${riskClass}`}>{riskGrade}</span>
          <span style={{ fontSize: '0.8rem' }}>
            점수: {dashboard?.risk_indicator?.score ?? '-'} / 100
          </span>
        </div>
        {/* 안전 경고 */}
        {aiAnalysis?.report?.summary?.risk_grade === 'CRITICAL' && (
          <div className="warning-banner" style={{ marginTop: 8 }}>
            위험! 긴급 방어 모드 권장
          </div>
        )}
      </div>

      {/* AI 사고 과정 */}
      <div className="card" style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
        <div className="card-title">AI 사고 과정</div>
        {aiThinking.length > 0 ? (
          aiThinking.map((item: any, i: number) => (
            <div key={i} className="thinking-item">
              <div className="thinking-agent">{item.agent}</div>
              <div style={{ marginTop: 4 }}>{item.summary}</div>
              <div style={{
                fontSize: '0.7rem',
                color: 'var(--text-secondary)',
                marginTop: 2,
              }}>
                신뢰도: {((item.confidence || 0) * 100).toFixed(0)}%
              </div>
            </div>
          ))
        ) : (
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', padding: 8 }}>
            게임을 시작하면 AI 분석이 표시됩니다.
          </div>
        )}
      </div>
    </div>
  );
}

function EvalBar({ label, value, maxVal }: { label: string; value: number; maxVal: number }) {
  const pct = Math.min(100, Math.max(0, ((value / maxVal) + 1) * 50));
  const isPositive = value >= 0;

  return (
    <div style={{ marginBottom: 6 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', marginBottom: 2 }}>
        <span>{label}</span>
        <span style={{ color: isPositive ? 'var(--success)' : 'var(--danger)' }}>
          {value > 0 ? '+' : ''}{typeof value === 'number' ? value.toFixed(2) : value}
        </span>
      </div>
      <div style={{
        height: 6,
        background: 'rgba(255,255,255,0.1)',
        borderRadius: 3,
        overflow: 'hidden',
      }}>
        <div style={{
          height: '100%',
          width: `${pct}%`,
          background: isPositive
            ? 'linear-gradient(90deg, #2ecc71, #27ae60)'
            : 'linear-gradient(90deg, #e74c3c, #c0392b)',
          borderRadius: 3,
          transition: 'width 0.5s ease',
        }} />
      </div>
    </div>
  );
}
