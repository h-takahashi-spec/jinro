"""既存の授業セッションに、擬似学生を参加させる（人間モード=ランダム行動 / AIモード=aiAct / 途中退出）
usage: python test/sim_students.py SESSION_ID 人数 [秒数]   （SESSION_ID に auto と書くと、いま開いている授業に入る）
本番の Apps Script につなぐとき: JINRO_API=https://script.google.com/macros/s/…/exec python test/sim_students.py auto 5"""
import json, os, random, sys, threading, time, requests
API = os.environ.get('JINRO_API', 'http://localhost:8787')
SID, N = sys.argv[1], int(sys.argv[2]); DUR = int(sys.argv[3]) if len(sys.argv) > 3 else 600
S = requests.Session()
if SID == 'auto':   # いま開いている授業に入る
    SID = (S.post(API, data=json.dumps({'action': 'currentSession'}), timeout=60).json().get('session') or {}).get('id') or sys.exit('開いている授業がありません')
    print('授業ID:', SID)
def call(**p):
    for i in range(5):
        try: r = S.post(API, data=json.dumps(p), timeout=60).json(); break
        except Exception: time.sleep(1)
    if not r.get('ok'): raise RuntimeError(r.get('error'))
    return r
NAMES = ['しばっち', 'もちこ', 'たまご', 'ぽんず', 'こむぎ', 'みかん', 'あんこ', 'くるみ', 'だいふく', 'わさび', 'ちくわ', 'ごま', 'きなこ', 'のり']
KINDS = ['human', 'shiba', 'cat', 'rabbit', 'fox', 'ghost', 'spirit', 'robot']
end = time.time() + DUR
def student(i):
    mode = 'ai' if (os.environ.get('ALL_AI') or i % 2 == 0) else 'human'
    av = {'kind': random.choice(KINDS), 'furC': random.randint(0, 3), 'hair': random.choice(['short', 'bob', 'long', 'none']), 'eyes': random.choice(['round', 'happy', 'sly', 'dot']), 'mouth': random.choice(['smile', 'cat', 'grin']), 'body': random.choice(['tee', 'hoodie', 'shirt', 'robe']), 'bgC': random.randint(0, 9)}
    ai = {'params': {k: random.randint(10, 90) for k in ['logic', 'emotion', 'active', 'skeptic', 'coop', 'bold']}, 'strategy': '占い結果を重視する。'} if mode == 'ai' else None
    nick = NAMES[i % len(NAMES)] + ('' if i < len(NAMES) else str(i))
    e = call(action='entry', sessionId=SID, sid=f'25{i:05d}', nick=nick, mode=mode, avatar=av, profile=f'{nick}です。理工学部1年。よろしく！', ai=ai)
    tok, played = e['token'], set()
    while time.time() < end:
        st = call(action='sessionState', sessionId=SID, token=tok)
        if st['session']['status'] == 'closed': return
        a = st['me']['assignment']
        if not a or a['round'] in played: time.sleep(2); continue
        rid, pt, acted = a['roomId'], a['token'], set()
        while time.time() < end:
            g = call(action='state', roomId=rid, token=pt)['state']
            if g['status'] == 'finished': played.add(a['round']); break
            me = g.get('me') or {}; key = (g['day'], g['phase'], g['round'])
            if me.get('alive') and not me.get('done') and key not in acted:
                acted.add(key)
                try:
                    if mode == 'ai': call(action='aiAct', roomId=rid, token=pt)
                    else:
                        others = [p['id'] for p in g['players'] if p['alive'] and p['id'] != me['id']]
                        if g['phase'] == 'talk':
                            t = random.choice([None, 'なんか怪しい人がいる気がする！', 'みんなはどう思う？', '私は村人です。信じて！', '占い師さんの結果が知りたいな'])
                            call(action='talk', roomId=rid, token=pt, text=t or '', skip=t is None)
                        elif g['phase'] == 'vote': call(action='vote', roomId=rid, token=pt, target=random.choice(others))
                        elif me.get('nightAction'):
                            ts = [p['id'] for p in g['players'] if p['alive'] and p['id'] != me['id'] and not (me['nightAction'] == 'attack' and p['id'] in (me.get('wolves') or []))]
                            call(action='night', roomId=rid, token=pt, target=random.choice(ts))
                except Exception: pass
            time.sleep(1.2)
for i in range(N):
    threading.Thread(target=student, args=(i,), daemon=True).start(); time.sleep(.1)
while time.time() < end: time.sleep(2)
