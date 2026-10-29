#!/usr/bin/env bash
# JangGi formal/ — Three-Config gate (WDLAB-STD-VERIFY-001 §6.1) + optional reproduction tests.
#   ./formal/run_all.sh            # TLC only: MC=PASS(0), MC_bug=FAIL(12), MC_sanity=FAIL(12) + extra mutations
#   ./formal/run_all.sh --tests    # also run tests/test_ai_move_undo_race.py (must pass on fixed code)
# Env: TLA2TOOLS (jar path, default ~/.cache/proof-skills/tla2tools.jar), TLC_WORKERS (default 4), JAVA (default java)
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
JAR="${TLA2TOOLS:-$HOME/.cache/proof-skills/tla2tools.jar}"
JAVA="${JAVA:-java}"
WORKERS="${TLC_WORKERS:-4}"
[ -f "$JAR" ] || { echo "tla2tools.jar not found: $JAR (set TLA2TOOLS)"; exit 2; }
CP="$JAR"; [ -f "$(dirname "$JAR")/CommunityModules-deps.jar" ] && CP="$CP:$(dirname "$JAR")/CommunityModules-deps.jar"

CONCERN=ai-move-undo-race
TLA="$HERE/$CONCERN/tla"
OUT="$TLA/.tlc-out/run_all"; mkdir -p "$OUT"
fail=0

check() {  # check <cfg> <expected-exit> <label>
  local cfg="$1" want="$2" label="$3"
  ( cd "$TLA" && "$JAVA" -XX:+UseParallelGC -cp "$CP" tlc2.TLC -workers "$WORKERS" -config "$cfg" \
        -metadir "$OUT/states_$cfg" Spec.tla > "$OUT/$cfg.log" 2>&1 )
  local rc=$?
  rm -rf "$OUT/states_$cfg"
  rm -f "$TLA"/Spec_TTrace_*   # TLC trace-explorer leftovers
  local states; states="$(grep -m1 'distinct states' "$OUT/$cfg.log" | sed 's/^ *//')"
  if [ "$rc" = "$want" ]; then
    printf 'OK   %-18s exit %-3s (expected %-3s) %s — %s\n' "$cfg" "$rc" "$want" "$label" "$states"
  else
    printf 'FAIL %-18s exit %-3s (expected %-3s) %s — see %s\n' "$cfg" "$rc" "$want" "$label" "$OUT/$cfg.log"; fail=1
  fi
}

echo "== $CONCERN : Three-Config gate (TLC_WORKERS=$WORKERS) =="
check MC.cfg            0  "fix ON (UseLock+UndoTurnGuard) must PASS"
check MC_bug.cfg        12 "fix OFF must FAIL (TurnParity)"
check MC_sanity.cfg     12 "reachability sanity must FAIL (NeverUndone)"
echo "-- extra mutations / sanity --"
check MC_bug_record.cfg 12 "fix OFF, P2 only (RecordAlternates)"
check MC_lock_only.cfg  12 "lock only -> still FAIL (undo gap)"
check MC_guard_only.cfg 12 "guard only -> still FAIL (double ai_move)"
check MC_sanity2.cfg    12 "two ai_move in flight reachable"

if [ "${1:-}" = "--tests" ]; then
  echo "== reproduction tests (must pass on fixed code) =="
  ( cd "$ROOT" && python3 -m pytest tests/test_ai_move_undo_race.py -q -p no:cacheprovider ) || fail=1
fi

[ "$fail" = 0 ] && echo "RESULT: ALL EXPECTATIONS MET" || echo "RESULT: GATE FAILED"
exit $fail
