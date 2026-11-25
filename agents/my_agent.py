"""★ 学生が編集するファイル ★

RuleAgent か LLMAgent を継承して、気になるところだけ上書きしましょう。
使える情報は wolfclient.py の Game クラスを参照してください。

  g.my_id / g.my_role / g.day / g.round
  g.alive_ids()              生きている他のプレイヤーの番号
  g.talks(day)               会話ログ（t.frm, t.text, t.tags）
  g.co_list()                {番号: CO した役職}
  g.claimed_results()        発表された占い結果
  g.vote_declarations()      今日の投票宣言
  g.divine_results           （占い師）自分の占い結果
  g.wolves                   （柴犬）仲間の番号
  self.memory                自由に使える辞書（ゲーム中ずっと残る）
"""
import random

from rule_agent import RuleAgent
from wolfclient import Game, VOTE, ESTIMATE


class MyAgent(RuleAgent):
    # アバター工房で作ったアバターの JSON を貼ると、エージェントもそのアバターで登場します
    # avatar = {"bg": "night", "body": "cloak", "face": "oval", "eyes": "sly", "mouth": "smirk", "hair": "long", "hairC": 0}

    def talk(self, g: Game):
        # 例: 3 ラウンド目に、一番怪しいと思う人を「柴犬だと思う」と言う
        if g.round == 3 and g.my_role != "WEREWOLF":
            t = self.vote(g)
            return f"{g.name(t)}が柴犬だと思います。", [ESTIMATE(t, "WEREWOLF")]
        return super().talk(g)

    # def vote(self, g: Game) -> int:
    #     ...
    # def night(self, g: Game) -> int:
    #     ...
