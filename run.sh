#!/bin/bash
# 장기 챔피언 AI - 실행 스크립트

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_PORT=3005
BACKEND_PORT=8001

echo "======================================="
echo "  장기 챔피언 AI - JANGGI CHAMPION"
echo "======================================="
echo ""

# 백엔드 의존성 설치
echo "[1/4] 백엔드 의존성 설치..."
cd "$PROJECT_DIR"
pip3 install -q -r backend/requirements.txt

# 프론트엔드 의존성 설치
echo "[2/4] 프론트엔드 의존성 설치..."
cd "$PROJECT_DIR/frontend"
npm install --silent 2>/dev/null || npm install

# 프론트엔드 개발 서버 시작
echo "[3/4] 프론트엔드 개발 서버 시작 (port $FRONTEND_PORT)..."
npx next dev -p $FRONTEND_PORT &
FRONTEND_PID=$!

# 백엔드 시작
echo "[4/4] 백엔드 서버 시작 (port $BACKEND_PORT)..."
cd "$PROJECT_DIR"
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port $BACKEND_PORT --reload &
BACKEND_PID=$!

echo ""
echo "======================================="
echo "  서버가 시작되었습니다!"
echo "  프론트엔드: http://localhost:$FRONTEND_PORT"
echo "  백엔드 API: http://localhost:$BACKEND_PORT"
echo "  API 문서:   http://localhost:$BACKEND_PORT/docs"
echo "======================================="
echo ""
echo "종료하려면 Ctrl+C를 누르세요."

# 시그널 핸들링
trap "kill $FRONTEND_PID $BACKEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM

wait
