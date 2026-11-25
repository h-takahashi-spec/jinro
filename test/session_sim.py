"""授業セッションの大規模シミュレーション
  - 先生: セッション作成 → エントリー締切 → 村分け → 進行監視 → AI分析 → リトライ
  - 学生: 人間モード（ランダムに行動）/ AIモード（aiAct を呼ぶ）/ 途中退出（エントリー直後 or 1日目のあとに消える）
usage: python test/session_sim.py [人数] [試合数]
"""
import json, random, sys, threading, time, requests
API = 'http://localhost:8787'
N = int(sys.argv[1]) if len(sys.argv) > 1 else 23
ROUNDS = int(sys.argv[2]) if len(sys.argv) > 2 else 2
S = requests.Session()
lock = threading.Lock()
stats = {'acts': 0, 'ai': 0, 'errors': []}

def call(**p):
    for i in range(5):
        try:
            r = S.post(API, data=json.dumps(p), timeout=60).json()
            break
        except Exception as e:
            time.sleep(1)
    if not r.get('ok'):
        raise RuntimeError(r.get('error'))
    return r

ses = call(action='createSession', name='テスト授業', talkSec=10, voteSec=10, nightSec=10, talkRounds=2)
SID, ADMIN = ses['sessionId'], ses['adminKey']
print('session', SID)
stop = threading.Event()

def student(i):
    mode = 'ai' if i % 3 == 0 else 'human'
    drop = 'entry' if i in (4, 11) else ('mid' if i in (7,) else None)
    av = {'kind': random.choice(['human', 'shiba', 'cat', 'ghost', 'robot']), 'furC': 1, 'hair': 'short'}
    ai = {'params': {k: random.randint(0, 100) for k in ['logic', 'emotion', 'active', 'skeptic', 'coop', 'bold']}, 'strategy': '占い師の結果を重視して、慎重に推理する。'} if mode == 'ai' else None
    e = call(action='entry', sessionId=SID, sid=f'S{1000+i}', nick=f'{"AI" if mode=="ai" else "人"}{i}', mode=mode, avatar=av, profile=f'プロフィール{i}', ai=ai)
    tok = e['token']
    if drop == 'entry':
        return
    played = set()
    while not stop.is_set():
        st = call(action='sessionState', sessionId=SID, token=tok)
        asg = st['me']['assignment']
        if not asg or asg['round'] in played:
            time.sleep(1.5); continue
        rid, ptok = asg['roomId'], asg['token']
        acted = set()
        while not stop.is_set():
            g = call(action='state', roomId=rid, token=ptok)['state']
            if g['status'] == 'finished':
                played.add(asg['round']); break
            if drop == 'mid' and g['day'] >= 2:
                return   # 2日目に入ったら消える
            me = g.get('me') or {}
            key = (g['day'], g['phase'], g['round'])
            if me.get('alive') and not me.get('done') and key not in acted:
                acted.add(key)
                try:
                    if mode == 'ai':
                        r = call(action='aiAct', roomId=rid, token=ptok)
                        with lock: stats['ai'] += 1 if r.get('done') else 0
                    else:
                        others = [p['id'] for p in g['players'] if p['alive'] and p['id'] != me['id']]
                        if g['phase'] == 'talk':
                            if random.random() < .5: call(action='talk', roomId=rid, token=ptok, text=random.choice(['えっ、怪しいと思う！', 'なぜそう思うの？', '私は村人です、信じて', 'よろしく']), tags=[])
                            else: call(action='talk', roomId=rid, token=ptok, skip=True)
                        elif g['phase'] == 'vote': call(action='vote', roomId=rid, token=ptok, target=random.choice(others))
                        elif g['phase'] == 'night' and me.get('nightAction'):
                            t = [p['id'] for p in g['players'] if p['alive'] and p['id'] != me['id'] and not (me['nightAction'] == 'attack' and p['id'] in (me.get('wolves') or []))]
                            call(action='night', roomId=rid, token=ptok, target=random.choice(t))
                    with lock: stats['acts'] += 1
                except Exception as ex:
                    if 'フェーズ' not in str(ex) and 'すでに' not in str(ex):
                        with lock: stats['errors'].append(str(ex))
            time.sleep(1)

ths = [threading.Thread(target=student, args=(i,), daemon=True) for i in range(N)]
for t in ths: t.start(); time.sleep(.05)
time.sleep(4)
t0 = time.time()
for rn in range(1, ROUNDS + 1):
    r = call(action='startRound', sessionId=SID, adminKey=ADMIN)
    print(f'round {rn}: sizes {r["sizes"]} rooms {r["rooms"]}')
    while True:
        st = call(action='sessionState', sessionId=SID, adminKey=ADMIN)
        if st['session']['status'] == 'results': break
        if time.time() - t0 > 1500: print('TIMEOUT'); break
        time.sleep(2)
    rooms = st['rooms']
    print('  finished:', [(x['name'], x['winner'], x['day'], sum(1 for p in x['players'] if p['kind']=='cpu')) for x in rooms], f'{time.time()-t0:.0f}s')
    while True:
        a = call(action='analyzeRound', sessionId=SID, adminKey=ADMIN, max=3)
        if not a['remaining']: break
    st = call(action='sessionState', sessionId=SID, adminKey=ADMIN)
    print('  analysis:', [ (x['analysis'] or {}).get('title') for x in st['rooms'] ])
    online = sum(1 for e in st['session']['entrants'] if e['online'])
    print(f'  entrants {len(st["session"]["entrants"])}, online {online}')
stop.set()
print('acts', stats['acts'], 'ai acts', stats['ai'], 'errors', stats['errors'][:5], len(stats['errors']))
# AI の推定履歴が残っているか
g = call(action='game', roomId=rooms[0]['id'])['game']
print('beliefs players:', {k: len(v) for k, v in g['beliefs'].items()})
print('SID', SID)
