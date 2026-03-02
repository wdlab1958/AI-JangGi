import React, { useState, useCallback, useRef, useEffect } from 'react';
import { PieceData } from '../hooks/useGame';

interface LastMoveInfo {
  from: [number, number];
  to: [number, number];
  team: string;
}

interface JanggiBoardProps {
  board: (PieceData | null)[][];
  currentTurn: string;
  humanTeam: string;
  isCheck: boolean;
  lastMove: LastMoveInfo | null;
  onMove: (fromRow: number, fromCol: number, toRow: number, toCol: number) => void;
  onGetValidMoves: (row: number, col: number) => Promise<[number, number][]>;
  disabled?: boolean;
}

const ROWS = 10;
const COLS = 9;
const CELL_SIZE = 68;
const PADDING = 40;
const BOARD_WIDTH = (COLS - 1) * CELL_SIZE + PADDING * 2;
const BOARD_HEIGHT = (ROWS - 1) * CELL_SIZE + PADDING * 2;
const PIECE_RADIUS = 28;

const BOARD_COLOR = '#d4a574';
const LINE_COLOR = '#5c3d1a';
const RIVER_COLOR = '#c4956e';
const CHO_COLOR = '#c0392b';
const HAN_COLOR = '#2471a3';
const HIGHLIGHT_COLOR = 'rgba(46, 204, 113, 0.5)';
const SELECTED_COLOR = 'rgba(241, 196, 15, 0.6)';
const CHECK_COLOR = 'rgba(231, 76, 60, 0.4)';
const AI_MOVE_FROM_COLOR = 'rgba(52, 152, 219, 0.3)';
const AI_MOVE_TO_COLOR = 'rgba(52, 152, 219, 0.45)';
const NO_MOVES_COLOR = 'rgba(255, 100, 100, 0.4)';

export default function JanggiBoard({
  board,
  currentTurn,
  humanTeam,
  isCheck,
  lastMove,
  onMove,
  onGetValidMoves,
  disabled = false,
}: JanggiBoardProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [selectedPiece, setSelectedPiece] = useState<{ row: number; col: number } | null>(null);
  const [validMoves, setValidMoves] = useState<[number, number][]>([]);
  const [animating, setAnimating] = useState(false);
  const [hoverPos, setHoverPos] = useState<{ row: number; col: number } | null>(null);
  const [noMovesPos, setNoMovesPos] = useState<{ row: number; col: number } | null>(null);

  // 보드를 뒤집어서 인간(초) 기물이 아래쪽에 표시되도록 한다
  const displayRow = (logicalRow: number) => (ROWS - 1) - logicalRow;

  // 논리 좌표 → 캔버스 좌표 (뒤집기 적용)
  const getCanvasPos = (row: number, col: number) => ({
    x: PADDING + col * CELL_SIZE,
    y: PADDING + displayRow(row) * CELL_SIZE,
  });

  // 캔버스 좌표 → 논리 좌표 (뒤집기 역변환)
  const getBoardPos = (canvasX: number, canvasY: number) => {
    const col = Math.round((canvasX - PADDING) / CELL_SIZE);
    const dispRow = Math.round((canvasY - PADDING) / CELL_SIZE);

    if (dispRow >= 0 && dispRow < ROWS && col >= 0 && col < COLS) {
      const logicalRow = (ROWS - 1) - dispRow;
      const pos = getCanvasPos(logicalRow, col);
      const dist = Math.sqrt((canvasX - pos.x) ** 2 + (canvasY - pos.y) ** 2);
      if (dist <= CELL_SIZE / 2) {
        return { row: logicalRow, col };
      }
    }
    return null;
  };

  const getCanvasCoords = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    return {
      x: (e.clientX - rect.left) * scaleX,
      y: (e.clientY - rect.top) * scaleY,
    };
  };

  // "이동 가능한 수 없음" 표시 자동 제거
  useEffect(() => {
    if (noMovesPos) {
      const timer = setTimeout(() => setNoMovesPos(null), 800);
      return () => clearTimeout(timer);
    }
  }, [noMovesPos]);

  // --- Drawing ---
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Board background
    ctx.fillStyle = BOARD_COLOR;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Border
    ctx.strokeStyle = LINE_COLOR;
    ctx.lineWidth = 3;
    ctx.strokeRect(PADDING - 5, PADDING - 5,
      (COLS - 1) * CELL_SIZE + 10, (ROWS - 1) * CELL_SIZE + 10);

    // Grid lines
    ctx.strokeStyle = LINE_COLOR;
    ctx.lineWidth = 1;
    for (let r = 0; r < ROWS; r++) {
      const y = PADDING + r * CELL_SIZE;
      ctx.beginPath();
      ctx.moveTo(PADDING, y);
      ctx.lineTo(PADDING + (COLS - 1) * CELL_SIZE, y);
      ctx.stroke();
    }
    for (let c = 0; c < COLS; c++) {
      const x = PADDING + c * CELL_SIZE;
      ctx.beginPath();
      ctx.moveTo(x, PADDING);
      ctx.lineTo(x, PADDING + (ROWS - 1) * CELL_SIZE);
      ctx.stroke();
    }

    // River (한강) - 화면 기준 위에서 5번째~6번째 줄 사이
    // 뒤집힌 상태: 논리 row 4~5 = 화면 row 4~5
    const riverDisplayY = PADDING + 4 * CELL_SIZE + 1;
    ctx.fillStyle = RIVER_COLOR;
    ctx.fillRect(PADDING, riverDisplayY, (COLS - 1) * CELL_SIZE, CELL_SIZE - 2);
    ctx.fillStyle = LINE_COLOR;
    ctx.font = 'bold 22px serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('漢  界        楚  河',
      PADDING + (COLS - 1) * CELL_SIZE / 2,
      riverDisplayY + (CELL_SIZE - 2) / 2);

    // Palace diagonal lines (궁성)
    // CHO 궁성: 논리 rows 0-2 → 화면 rows 7-9 (아래쪽)
    // HAN 궁성: 논리 rows 7-9 → 화면 rows 0-2 (위쪽)
    ctx.strokeStyle = LINE_COLOR;
    ctx.lineWidth = 1;
    drawPalaceDiag(ctx, 0, 3, 2, 5); // CHO (화면 아래)
    drawPalaceDiag(ctx, 7, 3, 9, 5); // HAN (화면 위)

    // AI 마지막 이동 하이라이트
    if (lastMove) {
      const fromPos = getCanvasPos(lastMove.from[0], lastMove.from[1]);
      ctx.save();
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = 'rgba(52, 152, 219, 0.6)';
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.arc(fromPos.x, fromPos.y, PIECE_RADIUS + 2, 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = AI_MOVE_FROM_COLOR;
      ctx.beginPath();
      ctx.arc(fromPos.x, fromPos.y, PIECE_RADIUS, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();

      const toPos = getCanvasPos(lastMove.to[0], lastMove.to[1]);
      ctx.save();
      ctx.fillStyle = AI_MOVE_TO_COLOR;
      ctx.beginPath();
      ctx.arc(toPos.x, toPos.y, PIECE_RADIUS + 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = 'rgba(52, 152, 219, 0.85)';
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.arc(toPos.x, toPos.y, PIECE_RADIUS + 4, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();

      ctx.save();
      ctx.strokeStyle = 'rgba(52, 152, 219, 0.4)';
      ctx.lineWidth = 2;
      ctx.setLineDash([6, 4]);
      ctx.beginPath();
      ctx.moveTo(fromPos.x, fromPos.y);
      ctx.lineTo(toPos.x, toPos.y);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.restore();
    }

    // Check highlight
    if (isCheck) {
      for (let r = 0; r < ROWS; r++) {
        for (let c = 0; c < COLS; c++) {
          const piece = board[r]?.[c];
          if (piece && piece.type === 'king' && piece.team === currentTurn) {
            const pos = getCanvasPos(r, c);
            ctx.fillStyle = CHECK_COLOR;
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, PIECE_RADIUS + 8, 0, Math.PI * 2);
            ctx.fill();
          }
        }
      }
    }

    // "이동 가능한 수 없음" 표시
    if (noMovesPos) {
      const pos = getCanvasPos(noMovesPos.row, noMovesPos.col);
      ctx.save();
      ctx.fillStyle = NO_MOVES_COLOR;
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, PIECE_RADIUS + 6, 0, Math.PI * 2);
      ctx.fill();
      // X 표시 (기물 위에 중앙 정렬)
      ctx.strokeStyle = 'rgba(220, 50, 50, 0.7)';
      ctx.lineWidth = 3;
      const s = 12;
      ctx.beginPath();
      ctx.moveTo(pos.x - s, pos.y - s);
      ctx.lineTo(pos.x + s, pos.y + s);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(pos.x + s, pos.y - s);
      ctx.lineTo(pos.x - s, pos.y + s);
      ctx.stroke();
      ctx.restore();
    }

    // Selected piece highlight
    if (selectedPiece) {
      const pos = getCanvasPos(selectedPiece.row, selectedPiece.col);
      ctx.fillStyle = SELECTED_COLOR;
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, PIECE_RADIUS + 6, 0, Math.PI * 2);
      ctx.fill();
    }

    // Valid moves highlight
    for (const [mr, mc] of validMoves) {
      const pos = getCanvasPos(mr, mc);
      const target = board[mr]?.[mc];
      if (target) {
        ctx.strokeStyle = '#e74c3c';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, PIECE_RADIUS + 4, 0, Math.PI * 2);
        ctx.stroke();
      } else {
        ctx.fillStyle = HIGHLIGHT_COLOR;
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, 14, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // Draw pieces
    for (let r = 0; r < ROWS; r++) {
      for (let c = 0; c < COLS; c++) {
        const piece = board[r]?.[c];
        if (piece && !piece.captured) {
          drawPiece(ctx, r, c, piece);
        }
      }
    }

    // Hover effect
    if (hoverPos && !selectedPiece && !disabled) {
      const piece = board[hoverPos.row]?.[hoverPos.col];
      if (piece && piece.team === humanTeam && currentTurn === humanTeam) {
        const pos = getCanvasPos(hoverPos.row, hoverPos.col);
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, PIECE_RADIUS + 3, 0, Math.PI * 2);
        ctx.stroke();
      }
    }
  }, [board, selectedPiece, validMoves, isCheck, currentTurn, humanTeam, hoverPos, disabled, lastMove, noMovesPos]);

  function drawPalaceDiag(ctx: CanvasRenderingContext2D,
    r1: number, c1: number, r2: number, c2: number) {
    const tl = getCanvasPos(r1, c1);
    const br = getCanvasPos(r2, c2);
    const tr = getCanvasPos(r1, c2);
    const bl = getCanvasPos(r2, c1);
    ctx.beginPath();
    ctx.moveTo(tl.x, tl.y);
    ctx.lineTo(br.x, br.y);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(tr.x, tr.y);
    ctx.lineTo(bl.x, bl.y);
    ctx.stroke();
  }

  function drawPiece(ctx: CanvasRenderingContext2D, row: number, col: number, piece: PieceData) {
    const pos = getCanvasPos(row, col);
    const isCho = piece.team === 'cho';

    ctx.save();
    ctx.beginPath();
    const r = PIECE_RADIUS;
    const sides = 8;
    for (let i = 0; i < sides; i++) {
      const angle = (Math.PI * 2 * i) / sides - Math.PI / 8;
      const x = pos.x + r * Math.cos(angle);
      const y = pos.y + r * Math.sin(angle);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.closePath();

    const grad = ctx.createRadialGradient(
      pos.x - 5, pos.y - 5, 2,
      pos.x, pos.y, r
    );
    grad.addColorStop(0, '#fdf6e3');
    grad.addColorStop(1, '#e8dcc8');
    ctx.fillStyle = grad;
    ctx.fill();

    ctx.strokeStyle = isCho ? CHO_COLOR : HAN_COLOR;
    ctx.lineWidth = 2.5;
    ctx.stroke();

    ctx.beginPath();
    const r2 = r - 4;
    for (let i = 0; i < sides; i++) {
      const angle = (Math.PI * 2 * i) / sides - Math.PI / 8;
      const x = pos.x + r2 * Math.cos(angle);
      const y = pos.y + r2 * Math.sin(angle);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.strokeStyle = isCho ? CHO_COLOR : HAN_COLOR;
    ctx.lineWidth = 1;
    ctx.stroke();

    ctx.fillStyle = isCho ? CHO_COLOR : HAN_COLOR;
    ctx.font = `bold ${piece.type === 'king' ? 24 : 22}px 'Noto Serif KR', serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(piece.hanja, pos.x, pos.y + 1);
    ctx.restore();
  }

  useEffect(() => {
    draw();
  }, [draw]);

  // --- Event Handlers ---
  const handleClick = async (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (disabled || animating) return;
    if (currentTurn !== humanTeam) return;

    const coords = getCanvasCoords(e);
    if (!coords) return;

    const pos = getBoardPos(coords.x, coords.y);
    if (!pos) {
      setSelectedPiece(null);
      setValidMoves([]);
      return;
    }

    if (selectedPiece) {
      const isValidTarget = validMoves.some(([r, c]) => r === pos.row && c === pos.col);
      if (isValidTarget) {
        setAnimating(true);
        try {
          await onMove(selectedPiece.row, selectedPiece.col, pos.row, pos.col);
        } catch (err) {
          console.error('[JanggiBoard] move failed:', err);
        } finally {
          setAnimating(false);
        }
        setSelectedPiece(null);
        setValidMoves([]);
        return;
      }

      const piece = board[pos.row]?.[pos.col];
      if (piece && piece.team === humanTeam) {
        setSelectedPiece(pos);
        const moves = await onGetValidMoves(pos.row, pos.col);
        setValidMoves(moves);
        if (moves.length === 0) {
          setNoMovesPos(pos);
        }
        return;
      }

      setSelectedPiece(null);
      setValidMoves([]);
      return;
    }

    // 기물 선택
    const piece = board[pos.row]?.[pos.col];
    if (piece && piece.team === humanTeam) {
      setSelectedPiece(pos);
      const moves = await onGetValidMoves(pos.row, pos.col);
      setValidMoves(moves);
      if (moves.length === 0) {
        setNoMovesPos(pos);
      }
    }
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const coords = getCanvasCoords(e);
    if (!coords) { setHoverPos(null); return; }
    const pos = getBoardPos(coords.x, coords.y);
    setHoverPos(pos);
  };

  const handleMouseLeave = () => {
    setHoverPos(null);
  };

  return (
    <canvas
      ref={canvasRef}
      width={BOARD_WIDTH}
      height={BOARD_HEIGHT}
      onClick={handleClick}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      style={{
        cursor: disabled ? 'not-allowed' : (hoverPos ? 'pointer' : 'default'),
        borderRadius: '8px',
        boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
      }}
    />
  );
}
