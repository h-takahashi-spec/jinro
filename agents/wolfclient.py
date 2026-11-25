"""人柴村サーバー（Apps Script）用の Python クライアントとエージェントの土台。
追手門学院大学 理工学部「コンピュータインタラクション」授業ワーク
（ゲームの仕組みは人狼と同じ。WEREWOLF = 柴犬、POSSESSED = 柴推し）

学生はふつう、このファイルは触らずに Agent を継承したクラスを書きます（my_agent.py を参照）。

    agent = MyAgent(api_url, room_id, name="たなか")
    agent.run()      # ゲーム終了まで、ポーリングしながら talk / vote / night を呼びます
"""
from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import requests

ROLE_JA = {
    "WEREWOLF": "柴犬", "POSSESSED": "柴推し", "SEER": "占い師",
    "MEDIUM": "霊媒師", "BODYGUARD": "騎士", "VILLAGER": "村人",
}


class ApiError(Exception):
    pass


class WolfApi:
    """API を叩くだけの薄いクライアント。"""

    def __init__(self, url: str, timeout: float = 30):
        self.url = url
        self.timeout = timeout
        self.session = requests.Session()

    def call(self, action: str, **params) -> dict:
        body = {"action": action, **params}
        # Apps Script は text/plain で送るとそのまま受け取れる（ブラウザと同じ形式）
        for attempt in range(4):
            try:
                r = self.session.post(self.url, data=json.dumps(body),
                                      headers={"Content-Type": "text/plain;charset=utf-8"},
                                      timeout=self.timeout)
                data = r.json()
                break
            except (requests.RequestException, ValueError):
                if attempt == 3:
                    raise
                time.sleep(1.5 * (attempt + 1))
        if not data.get("ok"):
            raise ApiError(data.get("error", "unknown error"))
        return data

    # 便利メソッド
    def create_room(self, name="", size=5, **settings) -> dict:
        return self.call("createRoom", name=name, size=size, **settings)

    def join(self, room_id, name, kind="agent", avatar=None) -> dict:
        return self.call("join", roomId=room_id, name=name, kind=kind, avatar=avatar)

    def start(self, room_id, host_token, fill_cpu=False):
        return self.call("start", roomId=room_id, hostToken=host_token, fillCpu=fill_cpu)

    def list_rooms(self):
        return self.call("listRooms")["rooms"]


@dataclass
class Talk:
    idx: int
    day: int
    round: int
    frm: int          # 発言者の番号
    text: str
    tags: list


@dataclass
class Game:
    """サーバーから届いた「自分に見えている情報」を扱いやすくしたもの。"""
    raw: dict
    me: dict = field(default_factory=dict)

    def __post_init__(self):
        self.me = self.raw.get("me") or {}

    # --- 基本情報 ---
    @property
    def day(self) -> int: return self.raw["day"]
    @property
    def phase(self) -> str: return self.raw["phase"]          # talk / vote / night / end
    @property
    def round(self) -> int: return self.raw["round"]
    @property
    def my_id(self) -> int: return self.me.get("id")
    @property
    def my_role(self) -> str: return self.me.get("role")
    @property
    def finished(self) -> bool: return self.raw["status"] == "finished"

    @property
    def players(self) -> list[dict]: return self.raw["players"]

    def name(self, pid: int) -> str:
        for p in self.players:
            if p["id"] == pid:
                return p["name"]
        return "?"

    def alive_ids(self, exclude_me=True) -> list[int]:
        return [p["id"] for p in self.players if p["alive"] and not (exclude_me and p["id"] == self.my_id)]

    def talks(self, day: Optional[int] = None) -> list[Talk]:
        out = [Talk(t["idx"], t["day"], t["round"], t["from"], t["text"], t.get("tags") or [])
               for t in self.raw["talks"]]
        return [t for t in out if day is None or t.day == day]

    # --- 自分だけが知っている情報 ---
    @property
    def divine_results(self) -> list[dict]:    # 占い師: [{"day", "target", "result"}]
        return self.me.get("divineResults", [])

    @property
    def medium_results(self) -> list[dict]:    # 霊媒師
        return self.me.get("mediumResults", [])

    @property
    def wolves(self) -> list[int]:             # 柴犬: 仲間の番号（自分を含む）
        return self.me.get("wolves", [])

    # --- タグ（構造化された発言）の集計 ---
    def co_list(self) -> dict[int, str]:
        """{番号: CO した役職}（最後の CO を採用）"""
        co = {}
        for t in self.talks():
            for g in t.tags:
                if g.get("type") == "CO":
                    co[t.frm] = g.get("role")
        return co

    def claimed_results(self, kind="DIVINED") -> list[dict]:
        """他の人が発表した占い(DIVINED)/霊媒(IDENTIFIED)結果: [{"from","target","result","day"}]"""
        out = []
        for t in self.talks():
            for g in t.tags:
                if g.get("type") == kind and "target" in g:
                    out.append({"from": t.frm, "target": g["target"], "result": g.get("result"), "day": t.day})
        return out

    def vote_declarations(self, day: Optional[int] = None) -> dict[int, int]:
        """今日「〇〇に投票する」と宣言した人: {宣言者: 対象}"""
        d = self.day if day is None else day
        out = {}
        for t in self.talks(d):
            for g in t.tags:
                if g.get("type") == "VOTE" and "target" in g:
                    out[t.frm] = g["target"]
        return out

    def summary_text(self) -> str:
        """LLM に渡すための、ゲーム状況の日本語まとめ。"""
        lines = [f"あなたは {self.my_id}番 {self.name(self.my_id)}、役職は{ROLE_JA.get(self.my_role, '?')}です。",
                 f"現在 {self.day}日目 / フェーズ: {self.phase}" + (f"（発言ラウンド {self.round}）" if self.phase == "talk" else "")]
        lines.append("プレイヤー: " + "、".join(
            f"{p['id']}番{p['name']}({'生存' if p['alive'] else '死亡'})" for p in self.players))
        lines.append("役職構成: " + "、".join(ROLE_JA[r] for r in self.raw.get("roleSet", [])))
        if self.divine_results:
            lines.append("あなたの占い結果: " + "、".join(
                f"{r['day']}日目 {r['target']}番{self.name(r['target'])}={'柴犬' if r['result']=='WEREWOLF' else '人間'}"
                for r in self.divine_results))
        if self.medium_results:
            lines.append("あなたの霊媒結果: " + "、".join(
                f"{r['target']}番{self.name(r['target'])}={'柴犬' if r['result']=='WEREWOLF' else '人間'}"
                for r in self.medium_results))
        if self.my_role == "WEREWOLF":
            lines.append("柴犬の仲間: " + "、".join(f"{w}番{self.name(w)}" for w in self.wolves))
        for e in self.raw["events"]:
            if e["type"] == "execute":
                lines.append(f"{e['day']}日目: {e['target']}番{self.name(e['target'])}が追放された")
            elif e["type"] == "attack":
                lines.append(f"{e['day']}日目の朝: {e['target']}番{self.name(e['target'])}が襲撃された")
            elif e["type"] == "noattack":
                lines.append(f"{e['day']}日目の朝: 誰も襲撃されなかった")
        for vh in self.raw["voteHistory"]:
            lines.append(f"{vh['day']}日目の投票: " + "、".join(
                f"{k}→{v}" for k, v in vh["votes"].items()))
        lines.append("--- これまでの会話 ---")
        for t in self.talks():
            lines.append(f"[{t.day}日目R{t.round}] {t.frm}番{self.name(t.frm)}: {t.text}")
        return "\n".join(lines)


class Agent:
    """エージェントの土台。talk / vote / night を上書きしてください。"""

    poll_interval = 2.0

    # アバター（アバター工房の「決定」で保存される JSON と同じ形式）。None なら名前から自動生成されます。
    # 例: {"bg": "night", "body": "robe", "face": "oval", "eyes": "sly", "mouth": "smirk", "hair": "long", "hairC": 0}
    avatar = None

    def __init__(self, api_url: str, room_id: str, name: str = "Agent", verbose: bool = True):
        self.api = WolfApi(api_url)
        self.room_id = room_id
        self.name = name
        self.verbose = verbose
        self.token = None
        self.player_id = None
        self.memory: dict[str, Any] = {}   # 自由に使える記憶領域

    # ===== 上書きするメソッド =====
    def talk(self, g: Game) -> Optional[tuple[str, list]]:
        """発言。(文章, タグのリスト) を返す。None を返すとこのラウンドは発言しない（Over）。"""
        return None

    def vote(self, g: Game) -> int:
        """追放したい人の番号を返す。"""
        return random.choice(g.alive_ids())

    def night(self, g: Game) -> int:
        """夜の行動（占い・護衛・襲撃）の対象番号を返す。g.me['nightAction'] で種類がわかる。"""
        cands = g.alive_ids()
        if g.my_role == "WEREWOLF":
            cands = [i for i in cands if i not in g.wolves]
        return random.choice(cands)

    def on_game_start(self, g: Game): pass
    def on_game_end(self, g: Game): pass

    # ===== ここから下は通常いじらなくて OK =====
    def log(self, *a):
        if self.verbose:
            print(f"[{self.name}]", *a, flush=True)

    def join(self):
        r = self.api.join(self.room_id, self.name, kind="agent", avatar=self.avatar)
        self.token, self.player_id = r["token"], r["playerId"]
        self.log(f"参加しました: {self.player_id}番")

    def run(self, max_minutes: float = 120):
        if not self.token:
            self.join()
        version = None
        acted = set()
        started = False
        g = None
        end_at = time.time() + max_minutes * 60
        while time.time() < end_at:
            try:
                r = self.api.call("state", roomId=self.room_id, token=self.token, v=version)
            except Exception as e:  # 通信エラーは少し待って再試行
                self.log("通信エラー:", e)
                time.sleep(self.poll_interval * 2)
                continue
            if r.get("unchanged"):
                time.sleep(self.poll_interval)
                continue
            st = r["state"]
            version = st["version"]
            g = Game(st)
            if g.raw["status"] == "playing" and not started:
                started = True
                self.log(f"ゲーム開始: 役職は {ROLE_JA.get(g.my_role)}")
                self.on_game_start(g)
            if g.finished:
                self.log(f"ゲーム終了: 勝者 = {'村人チーム' if g.raw['winner']=='VILLAGER' else '柴犬チーム'}")
                self.on_game_end(g)
                return g
            key = (g.day, g.phase, g.round)
            if g.raw["status"] == "playing" and g.me.get("alive") and not g.me.get("done") and key not in acted:
                acted.add(key)
                try:
                    self._act(g)
                except ApiError as e:
                    self.log("行動できませんでした:", e)
                except Exception as e:
                    self.log("エージェント内でエラー:", repr(e))
                continue
            time.sleep(self.poll_interval)
        return g

    def _act(self, g: Game):
        if g.phase == "talk":
            res = self.talk(g)
            if not res:
                self.api.call("talk", roomId=self.room_id, token=self.token, skip=True)
            else:
                text, tags = res if isinstance(res, tuple) else (res, [])
                self.log(f"発言: {text}")
                self.api.call("talk", roomId=self.room_id, token=self.token, text=text, tags=tags or [])
        elif g.phase == "vote":
            t = self.vote(g)
            self.log(f"投票: {t}番")
            self.api.call("vote", roomId=self.room_id, token=self.token, target=int(t))
        elif g.phase == "night" and g.me.get("nightAction"):
            t = self.night(g)
            self.log(f"夜行動({g.me['nightAction']}): {t}番")
            self.api.call("night", roomId=self.room_id, token=self.token, target=int(t))


# タグを作る小さなヘルパー
def CO(role): return {"type": "CO", "role": role}
def DIVINED(target, result): return {"type": "DIVINED", "target": target, "result": result}
def IDENTIFIED(target, result): return {"type": "IDENTIFIED", "target": target, "result": result}
def VOTE(target): return {"type": "VOTE", "target": target}
def ESTIMATE(target, role): return {"type": "ESTIMATE", "target": target, "role": role}
