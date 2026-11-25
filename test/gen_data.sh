#!/bin/sh
# モック環境にテスト用の試合を作る
cd "$(dirname "$0")/../agents"
export LLM_BASE_URL=http://localhost:8799 LLM_MODEL=dummy
python3 run_agents.py --api http://localhost:8787 --create --agent llm:3 --agent rule:2 --games ${N5:-8} --poll 0.2 --talk-sec 5 --vote-sec 5 --night-sec 5 --quiet | tail -1
python3 run_agents.py --api http://localhost:8787 --create --size 9 --agent llm:5 --agent rule:2 --agent my:2 --games ${N9:-4} --poll 0.2 --talk-sec 5 --vote-sec 5 --night-sec 5 --quiet | tail -1
