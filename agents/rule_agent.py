"""ルールベースのサンプルエージェント。

方針（わざとシンプルにしてあります。改良が課題です）:
  - 占い師: 1 ラウンド目に CO して最新の占い結果を発表。黒を出したらそこに投票。
  - 霊媒師: 霊媒結果が出たら CO して発表。
  - 狂人  : 1 日目に占い師を騙り、村人陣営の誰かに黒を出す。
  - 柴犬  : 目立たないように、占い師 CO していない村人チームに投票。連れ去りは占い師 CO 者優先。
  （柴犬 = 人狼、柴推し = 狂人 にあたる役です）
  - 村人  : 占い師 CO 者が出した黒に投票。なければ投票宣言の多い人に合わせる。
"""
import random

from wolfclient import Agent, Game, CO, DIVINED, IDENTIFIED, VOTE


def ja(result):
    return "柴犬" if result == "WEREWOLF" else "人間"


class RuleAgent(Agent):

    # ---------- 発言 ----------
    def talk(self, g: Game):
        if g.round == 1:
            return self.first_talk(g)
        if g.round == 2:
            t = self.vote(g)
            return f"{g.name(t)}（{t}番）に投票します。", [VOTE(t)]
        return None  # 3 ラウンド目以降は Over

    def first_talk(self, g: Game):
        role = g.my_role
        if role == "SEER" and g.divine_results:
            r = g.divine_results[-1]
            text = f"占い師です。{g.name(r['target'])}（{r['target']}番）を占った結果は{ja(r['result'])}でした。"
            return text, [CO("SEER"), DIVINED(r["target"], r["result"])]
        if role == "MEDIUM" and g.medium_results:
            r = g.medium_results[-1]
            return (f"霊媒師です。昨日追放された{g.name(r['target'])}は{ja(r['result'])}でした。",
                    [CO("MEDIUM"), IDENTIFIED(r["target"], r["result"])])
        if role == "POSSESSED":
            # 偽の占い結果を出し続ける
            fakes = self.memory.setdefault("fake", [])
            cands = [i for i in g.alive_ids() if i not in [f[0] for f in fakes]] or g.alive_ids()
            t = random.choice(cands)
            res = "WEREWOLF" if g.day == 1 else random.choice(["HUMAN", "WEREWOLF"])
            fakes.append((t, res))
            return (f"占い師です。{g.name(t)}（{t}番）は{ja(res)}でした。", [CO("SEER"), DIVINED(t, res)])
        if g.day == 1:
            return "よろしくお願いします。占い師の方は結果を教えてください。", []
        return None

    # ---------- 投票 ----------
    def vote(self, g: Game) -> int:
        alive = g.alive_ids()
        role = g.my_role

        if role == "WEREWOLF":
            co = g.co_list()
            safe = [i for i in alive if i not in g.wolves]
            # 黒を出された仲間がいるなら、他の人への投票を集める
            decl = g.vote_declarations()
            popular = self.most_common([t for t in decl.values() if t in safe])
            if popular:
                return popular
            non_co = [i for i in safe if i not in co]
            return random.choice(non_co or safe or alive)

        if role == "SEER":
            blacks = [r["target"] for r in g.divine_results if r["result"] == "WEREWOLF" and r["target"] in alive]
            if blacks:
                return blacks[-1]
            whites = {r["target"] for r in g.divine_results}
            # 自分以外の占い師 CO は偽物
            fake_seers = [i for i, r in g.co_list().items() if r == "SEER" and i in alive]
            if fake_seers:
                return fake_seers[0]
            return random.choice([i for i in alive if i not in whites] or alive)

        # 村人・霊媒師・騎士・狂人（狂人は村人のふりをしてランダム寄り）
        claimed = g.claimed_results("DIVINED")
        blacks = [c["target"] for c in claimed if c["result"] == "WEREWOLF" and c["target"] in alive]
        if role == "POSSESSED":
            # 自分が出した偽の黒に投票する
            mine = [c["target"] for c in claimed if c["from"] == g.my_id and c["target"] in alive]
            if mine:
                return mine[-1]
        if blacks:
            return self.most_common(blacks)
        decl = g.vote_declarations()
        popular = self.most_common([t for t in decl.values() if t in alive])
        if popular:
            return popular
        co = g.co_list()
        return random.choice([i for i in alive if i not in co] or alive)

    # ---------- 夜 ----------
    def night(self, g: Game) -> int:
        alive = g.alive_ids()
        action = g.me.get("nightAction")
        co = g.co_list()
        if action == "attack":
            cands = [i for i in alive if i not in g.wolves]
            seers = [i for i in cands if co.get(i) in ("SEER", "MEDIUM")]
            return random.choice(seers or cands)
        if action == "divine":
            done = {r["target"] for r in g.divine_results}
            return random.choice([i for i in alive if i not in done] or alive)
        if action == "guard":
            seers = [i for i in alive if co.get(i) == "SEER"]
            return random.choice(seers or alive)
        return random.choice(alive)

    @staticmethod
    def most_common(xs):
        if not xs:
            return None
        counts = {}
        for x in xs:
            counts[x] = counts.get(x, 0) + 1
        best = max(counts.values())
        return random.choice([k for k, v in counts.items() if v == best])
