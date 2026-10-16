#!/usr/bin/env bash
# 같은 파일을 JSON(base64 한 번에), REST 스트리밍(바이너리 본문), gRPC(64KB client-streaming)로 업로드해 전송량·시간·최대 메모리를 잰다.
# 조건마다 서버를 새로 띄워 이전 실행의 메모리가 섞이지 않게 한다.
set -euo pipefail
cd "$(dirname "$0")"

SIZES=${SIZES:-"50 200"}   # MB
TRIALS=${TRIALS:-2}

[ -d .venv ] || { uv venv -q .venv && uv pip install -q -p .venv/bin/python grpcio==1.66.2 grpcio-tools==1.66.2 protobuf; }
PY=.venv/bin/python
$PY -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. upload.proto

for s in $SIZES; do
  [ -f "f$s.bin" ] || head -c $((s * 1000000)) /dev/urandom > "f$s.bin"
done

port=19100
: > results.jsonl
for s in $SIZES; do
  for mode in json rest grpc; do
    for _ in $(seq "$TRIALS"); do
      port=$((port + 1))
      $PY servers.py "$mode" "$port" & sp=$!
      sleep 1.5
      $PY client.py "$mode" "$port" "f$s.bin" | tee -a results.jsonl
      kill "$sp" 2>/dev/null || true; wait "$sp" 2>/dev/null || true
    done
  done
done
