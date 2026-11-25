"""エージェントをまとめて起動するスクリプト。

例) 新しい 5 人村を作り、ルール 3 体 + 自作 1 体 + CPU で埋めて対戦（10 回）
    python run_agents.py --api "$API" --create --agent rule:3 --agent my:1 --fill-cpu --games 10

例) 既存の村（人間が待っている村）にエージェントを 2 体参加させる
    python run_agents.py --api "$API" --room abc123 --agent llm:1 --agent rule:1

--agent の種類: rule（RuleAgent） / llm（LLMAgent） / my（my_agent.MyAgent） / random（Agent）
               モジュール名:クラス名:数 の形でも指定できます（例: teamA:TeamAAgent:2）
"""
import argparse
import importlib
import threading
import time
from collections import Counter

from wolfclient import Agent, WolfApi, ROLE_JA

BUILTIN = {
    "rule": ("rule_agent", "RuleAgent"),
    "llm": ("llm_agent", "LLMAgent"),
    "my": ("my_agent", "MyAgent"),
    "random": ("wolfclient", "Agent"),
}


def parse_spec(spec):
    parts = spec.split(":")
    if parts[0] in BUILTIN:
        mod, cls = BUILTIN[parts[0]]
        n = int(parts[1]) if len(parts) > 1 else 1
        label = parts[0]
    else:
        mod, cls = parts[0], parts[1]
        n = int(parts[2]) if len(parts) > 2 else 1
        label = cls
    return getattr(importlib.import_module(mod), cls), n, label


def play_once(api_url, room_id, specs, verbose, poll):
    agents = []
    for klass, n, label in specs:
        for i in range(n):
            a = klass(api_url, room_id, name=f"{label}{len(agents) + 1}", verbose=verbose)
            a.poll_interval = poll
            a.join()
            agents.append((label, a))
    results = {}
    threads = []
    for label, a in agents:
        th = threading.Thread(target=lambda a=a: results.__setitem__(a.name, a.run()), daemon=True)
        th.start()
        threads.append(th)
    return agents, threads, results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", required=True, help="Apps Script のウェブアプリ URL")
    ap.add_argument("--room", help="参加する村の ID")
    ap.add_argument("--create", action="store_true", help="新しく村を作る")
    ap.add_argument("--size", type=int, default=5)
    ap.add_argument("--agent", action="append", default=[], help="種類:数")
    ap.add_argument("--fill-cpu", action="store_true", help="足りない分を CPU で埋めて開始")
    ap.add_argument("--games", type=int, default=1, help="--create 時の連続対戦数")
    ap.add_argument("--talk-sec", type=int, default=60)
    ap.add_argument("--vote-sec", type=int, default=30)
    ap.add_argument("--night-sec", type=int, default=30)
    ap.add_argument("--poll", type=float, default=2.0, help="ポーリング間隔（秒）")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    specs = [parse_spec(s) for s in args.agent]
    api = WolfApi(args.api)
    stats = Counter()

    games = args.games if args.create else 1
    for gi in range(games):
        if args.create:
            r = api.create_room(name=f"agents-{int(time.time())}", size=args.size,
                                talkSec=args.talk_sec, voteSec=args.vote_sec, nightSec=args.night_sec)
            room_id, host = r["roomId"], r["hostToken"]
            print(f"村を作りました: {room_id}")
        else:
            room_id, host = args.room, None

        agents, threads, results = play_once(args.api, room_id, specs, not args.quiet, args.poll)
        if host:
            api.start(room_id, host, fill_cpu=args.fill_cpu)
        for th in threads:
            th.join()

        # 集計
        g = next(iter(results.values()), None)
        if g is None or not g.finished:
            print("ゲームが終わりませんでした")
            continue
        winner = g.raw["winner"]
        roles = {p["name"]: p.get("role") for p in g.players}
        for label, a in agents:
            role = roles.get(a.name)
            team = "WEREWOLF" if role in ("WEREWOLF", "POSSESSED") else "VILLAGER"
            stats[(label, "games")] += 1
            stats[(label, "wins")] += int(team == winner)
        print(f"[{gi + 1}/{games}] 勝者: {'村人チーム' if winner == 'VILLAGER' else '柴犬チーム'}  " +
              ", ".join(f"{n}={ROLE_JA.get(r, r)}" for n, r in roles.items()))

    labels = sorted({k[0] for k in stats})
    if labels:
        print("\n=== 勝率 ===")
        for lb in labels:
            n, w = stats[(lb, "games")], stats[(lb, "wins")]
            print(f"{lb:>10}: {w}/{n} = {w / n:.0%}")


if __name__ == "__main__":
    main()
