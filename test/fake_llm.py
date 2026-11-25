# OpenAI 互換のダミー LLM（テスト用）
#  - エージェントの発言: いろいろな話し方の文をランダムに返す
#  - 発話分類: 発言一覧を読み、キーワード + ランダムでカテゴリを返す
import json, random, re
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
TALKS = [
 ("{t}番の発言、さっきと矛盾していませんか？昨日は占い師を信じると言っていたのに。", [{"type":"ESTIMATE","role":"WEREWOLF"}]),
 ("{t}番、嘘つきなのはバレバレですよ。いい加減認めたらどうですか！", []),
 ("えっ、まさかあの人が襲われるなんて…怖いです。", []),
 ("私は村人です。疑われるのは心外です、信じてください。", []),
 ("占い結果が二人で食い違っている以上、どちらかが偽物です。だから今日は{t}番に投票しましょう。", [{"type":"VOTE"}]),
 ("{t}番はどう思いますか？理由も聞きたいです。", []),
 ("なるほど、確かにその通りですね。", []),
 ("{t}番が人狼だと思います。なんとなく発言が少ないので。", [{"type":"ESTIMATE","role":"WEREWOLF"}]),
 ("ふざけないでください、{t}番こそ怪しすぎます！", []),
 ("昨夜の襲撃先から考えると、人狼は占い師を避けている。つまり占い師は偽物の可能性が高い。", []),
]
class H(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        u=body['messages'][-1]['content']
        if 'キャッチコピー' in u:
            c=json.dumps({"title":"うたがいの夜明け","summary":"占い師の結果をめぐって白熱した試合でした。最後は投票がわかれて大接戦に。","mvp":{"name":"llm1","reason":"話し合いをリードした"},"turning":{"day":2,"text":"占い結果がわかれた"},"highlights":["対抗CO","護衛成功","最後の一票"]},ensure_ascii=False)
        elif '発言一覧' in u:
            items=[]
            for m in re.finditer(r'#(\d+) \[[^\]]*\] [^「]*「([^」]*)」', u):
                i,t=int(m.group(1)),m.group(2)
                c=('PROVOKE' if re.search('嘘つき|ふざけ|バレバレ',t) else 'EMOTION' if re.search('えっ|怖',t) else 'DEFEND' if '信じて' in t else
                   'QUESTION' if '？' in t else 'PROPOSE' if '投票しましょう' in t or '投票します' in t else 'INFO' if re.search('占い師|でした',t) else
                   'REASON' if re.search('つまり|矛盾|考えると',t) else 'ESTIMATE' if '思います' in t else random.choice(['OTHER','REASON']))
                items.append({"i":i,"c":c})
            c=json.dumps({"items":items},ensure_ascii=False)
        elif '選べる番号' in u:
            nums=re.findall(r'\d+', u.split('選べる番号:')[1])
            c='```json\n'+json.dumps({"target":int(random.choice(nums)),"reason":"なんとなく"})+'\n```'
        else:
            nums=re.findall(r'(\d+)番[^(（]*\(生存\)', u) or ['1']
            t=random.choice(nums)
            if random.random()<.15: c='{"skip":true}'
            else:
                txt,tags=random.choice(TALKS); tags=[dict(g,target=int(t)) for g in tags]
                c=json.dumps({"text":txt.format(t=t),"tags":tags},ensure_ascii=False)
        out={"choices":[{"message":{"content":c}}]}
        b=json.dumps(out).encode(); self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers(); self.wfile.write(b)
ThreadingHTTPServer(('localhost',8799),H).serve_forever()
