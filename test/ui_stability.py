"""安定性: 通信断→復帰、書きかけの文章の保持、二重クリック、再読み込み、サーバーの異常応答"""
import time, json, subprocess
from playwright.sync_api import sync_playwright
API='http://localhost:8787'; B='http://localhost:8080'; errs=[]
def post(**p): return json.loads(subprocess.check_output(['curl','-s','-X','POST',API,'-d',json.dumps(p)]))
with sync_playwright() as p:
    br=p.chromium.launch(); ctx=br.new_context(viewport={'width':1366,'height':768}); pg=ctx.new_page()
    pg.on('pageerror',lambda e: errs.append(str(e)))
    ses=post(action='createSession',name='安定性テスト',talkSec=14,talkRounds=2,voteSec=12,nightSec=12)
    sid=ses['sessionId']
    sim=subprocess.Popen(['python3','test/sim_students.py',sid,'5','400'])
    pg.goto(f'{B}/index.html?api={API}&session={sid}'); pg.wait_for_selector('#vEntry:not(.hidden)')
    pg.fill('#eSid','2501001A'); pg.fill('#eNick','たかはし'); pg.keyboard.press('Enter'); pg.wait_for_timeout(400)
    pg.dblclick('#eNext'); pg.wait_for_timeout(1500)                      # 二度押ししても 1 回だけエントリー
    if pg.locator('#storySkip').count(): pg.click('#storySkip')
    pg.wait_for_selector('#vSWait:not(.hidden)'); pg.wait_for_timeout(3000)
    st=post(action='sessionState',sessionId=sid,adminKey=ses['adminKey']); print('entrants', len(st['session']['entrants']), '(expect 6)')
    post(action='startRound',sessionId=sid,adminKey=ses['adminKey'])
    pg.wait_for_selector('#vGame:not(.hidden)',timeout=20000)
    def skip():
        for _ in range(8):
            if pg.locator('#overlay.show').count(): pg.evaluate('skipNow()'); pg.wait_for_timeout(500)
            else: break
    skip(); pg.wait_for_selector('#tText',timeout=15000)
    # 1) 書きかけのままラウンドが終わっても、文章が残る
    pg.fill('#tText','これは書きかけの文章です'); r0=pg.evaluate('S.round'); t0=time.time()
    while time.time()-t0<40 and pg.evaluate('S.phase=="talk" && S.round')==r0: pg.wait_for_timeout(500); skip()
    skip(); pg.wait_for_timeout(1200)
    print('draft kept after round change:', pg.locator('#tText').count() and pg.input_value('#tText'), '| phase', pg.evaluate('S.phase'), 'round', pg.evaluate('S.round'))
    # 2) 通信が切れる → 表示が出る → 戻ると消えて続行
    ctx.route(lambda u: ':8787' in u, lambda route: route.abort()); pg.wait_for_timeout(7000)
    print('net banner while offline:', pg.locator('#net:not(.hidden)').count()==1, '| toasts shown:', pg.locator('#toast:not(.hidden)').count())
    v0=pg.evaluate('S.version'); ctx.unroute_all(); pg.wait_for_timeout(9000); skip()
    print('recovered:', pg.locator('#net.hidden').count()==1, '| state advanced:', pg.evaluate('S.version')>v0)
    # 3) サーバーが HTML（エラーページ）を返しても落ちない
    ctx.route(lambda u: ':8787' in u, lambda route: route.fulfill(status=200, content_type='text/html', body='<html>Service error</html>')); pg.wait_for_timeout(5000)
    print('html error -> banner:', pg.locator('#net:not(.hidden)').count()==1); ctx.unroute_all(); pg.wait_for_timeout(6000); skip()
    # 4) 試合の途中で再読み込み → 同じ村にもどる（役職発表は 2 回出ない）
    rid=pg.evaluate('roomId'); pg.reload(); pg.wait_for_selector('#vGame:not(.hidden)',timeout=20000); pg.wait_for_timeout(1500)
    print('reload -> same room:', pg.evaluate('roomId')==rid, '| in session:', pg.evaluate('IN_SESSION'), '| reveal again:', pg.locator('#overlay.show .reveal-card').count())
    # 5) 試合終了 → 待機所 → 再読み込みしても終わった村に入り直さない
    t0=time.time()
    while time.time()-t0<240 and pg.evaluate('S && S.status')!='finished':
        skip()
        try:
            if pg.locator('#tSkip').count() and pg.locator('#tSkip').is_enabled(): pg.click('#tSkip')
            elif pg.locator('#gAction .tbtn').count() and not pg.locator('#gAction .tbtn.sel').count(): pg.locator('#gAction .tbtn').first.click()
        except Exception: pass
        pg.wait_for_timeout(600)
    pg.wait_for_timeout(1000); skip(); pg.wait_for_timeout(600); skip(); pg.click('#bkWait'); pg.wait_for_selector('#vSWait:not(.hidden)'); pg.wait_for_timeout(4000)
    print('back to wait room, stays:', pg.locator('#vSWait:not(.hidden)').count()==1)
    pg.reload(); pg.wait_for_timeout(5000); print('after reload still in wait room:', pg.locator('#vSWait:not(.hidden)').count()==1)
    sim.kill(); print('errors', errs)
