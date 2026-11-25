"""LLM（大規模言語モデル）を使うサンプルエージェント。

OpenAI 互換の Chat Completions API なら何でも使えます（環境変数で切り替え）:

    LLM_BASE_URL  例) https://api.openai.com/v1
                      https://generativelanguage.googleapis.com/v1beta/openai   (Gemini)
                      https://api.anthropic.com/v1                              (Claude)
                      http://localhost:11434/v1                                 (Ollama)
    LLM_API_KEY   API キー（Ollama なら適当な文字列で可）
    LLM_MODEL     使うモデル名

LLM の返答が壊れていたり時間がかかりすぎたりしたときは、RuleAgent の判断に切り替えます。
"""
import json
import os
import re

import requests

from rule_agent import RuleAgent
from wolfclient import Game, ROLE_JA

SYSTEM_PROMPT = """あなたは「人柴村（じんしばむら）」のプレイヤーです。人狼ゲームと同じルールで、舞台はほのぼのした RIKOU 村です。
勝利のために、自分の役職に合った行動をしてください。
- 柴犬＝人に化けて村にまぎれこんだ柴犬。人狼にあたる役で、夜にひとりを「もふもふの国」へ連れていく。
- 柴推し＝柴犬の味方をする人間（狂人にあたる役）。柴犬が誰かは知らない。
- 村人チーム（村人・占い師・霊媒師・騎士）は柴犬を全員追放すれば勝ち。
- 柴犬チーム（柴犬・柴推し）は柴犬の数が人間の数以上になれば勝ち。
- 柴犬と柴推しは嘘をついてよい。村人チームは基本的に正直に話す。
- 村の雰囲気はほのぼのしているので、言葉づかいはやわらかく。
発言は日本語で、1 回 120 文字以内。返答は必ず指定された JSON だけを出力してください。"""

TALK_INSTRUCTION = """今は発言の番です。次の JSON で答えてください。
{"text": "発言内容", "tags": [ ...任意... ]}
特に言うことがなければ {"skip": true}。
tags には発言の要点を構造化して入れてください（他のエージェントが読みます）:
  {"type":"CO","role":"SEER"}                       … 役職のカミングアウト（SEER/MEDIUM/BODYGUARD/VILLAGER/WEREWOLF/POSSESSED）
  {"type":"DIVINED","target":3,"result":"WEREWOLF"}  … 占い結果の発表（HUMAN か WEREWOLF）
  {"type":"IDENTIFIED","target":3,"result":"HUMAN"}  … 霊媒結果の発表
  {"type":"VOTE","target":2}                         … 投票先の宣言
  {"type":"ESTIMATE","target":4,"role":"WEREWOLF"}   … 「4番は柴犬だと思う」（role は WEREWOLF）"""

TARGET_INSTRUCTION = """{what}の対象を 1 人選び、次の JSON で答えてください。
{{"target": 番号, "reason": "短い理由"}}
選べる番号: {cands}"""


class LLMAgent(RuleAgent):

    def __init__(self, *a, model=None, base_url=None, api_key=None, temperature=0.7, **kw):
        super().__init__(*a, **kw)
        self.model = model or os.environ.get("LLM_MODEL")
        self.base_url = (base_url or os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.api_key = api_key or os.environ.get("LLM_API_KEY", "")
        self.temperature = temperature
        if not self.model:
            raise ValueError("LLM_MODEL を設定してください")

    # ---------- LLM 呼び出し ----------
    def ask(self, g: Game, instruction: str) -> dict | None:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": g.summary_text() + "\n\n" + instruction},
        ]
        try:
            r = requests.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={"model": self.model, "messages": messages, "temperature": self.temperature},
                timeout=60,
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            self.log("LLM 呼び出し失敗 → ルールで代行:", e)
            return None
        return parse_json(content)

    # ---------- 行動 ----------
    def talk(self, g: Game):
        if g.round > 3:
            return None
        res = self.ask(g, TALK_INSTRUCTION)
        if res is None:
            return super().talk(g)
        if res.get("skip"):
            return None
        text = str(res.get("text", "")).strip()[:200]
        tags = res.get("tags") or []
        if not isinstance(tags, list):
            tags = []
        return (text, tags) if text else None

    def vote(self, g: Game) -> int:
        return self.choose(g, "追放のための投票", g.alive_ids(), super().vote)

    def night(self, g: Game) -> int:
        what = {"attack": "今夜の襲撃", "divine": "今夜の占い", "guard": "今夜の護衛"}[g.me["nightAction"]]
        cands = g.alive_ids()
        if g.my_role == "WEREWOLF":
            cands = [i for i in cands if i not in g.wolves]
        return self.choose(g, what, cands, super().night)

    def choose(self, g, what, cands, fallback):
        res = self.ask(g, TARGET_INSTRUCTION.format(what=what, cands=", ".join(map(str, cands))))
        try:
            t = int(res["target"])
            if t in cands:
                self.log(f"{what}: {t}番（{res.get('reason', '')}）")
                return t
        except Exception:
            pass
        return fallback(g)


def parse_json(text: str) -> dict | None:
    """LLM の返答から最初の JSON オブジェクトを取り出す（```json ... ``` にも対応）。"""
    text = re.sub(r"```(?:json)?", "", text)
    start = text.find("{")
    while start >= 0:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    return None
