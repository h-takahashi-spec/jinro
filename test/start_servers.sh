#!/bin/sh
# ローカル検証用: ダミーLLM(8799)・Apps Script モック(8787)・静的サーバー(8080) を起動
cd "$(dirname "$0")/.."
pkill -f fake_llm.py; pkill -f gas_mock_server.js; pkill -f "http.server 8080"; sleep 0.5
nohup python3 test/fake_llm.py > /tmp/llm.log 2>&1 &
AWAY_SEC=${AWAY_SEC:-25} AWAY_GRACE_SEC=${AWAY_GRACE_SEC:-40} OPENAI_API_KEY=dummy OPENAI_MODEL=dummy OPENAI_BASE_URL=http://localhost:8799 nohup node test/gas_mock_server.js 8787 > /tmp/mock.log 2>&1 &
nohup python3 -m http.server 8080 > /tmp/http.log 2>&1 &
sleep 1.5; echo started
