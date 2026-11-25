import subprocess, sys, time, json, os
from playwright.sync_api import sync_playwright
API = 'http://localhost:8787'; B = 'http://localhost:8080'; OUT = '/tmp/sui'; os.makedirs(OUT, exist_ok=True)
errs = []
def track(pg, tag): pg.on('pageerror', lambda e: errs.append(f'{tag}: {e}'))
with sync_playwright() as p:
    br = p.chromium.launch()
    T = br.new_context(viewport={'width': 1440, 'height': 900}).new_page(); track(T, 'teacher')
    T.goto(f'{B}/teacher.html?api={API}'); time.sleep(1.5); T.screenshot(path=f'{OUT}/t0_setup.png')
    T.click('#vSetup details.more summary'); T.fill('#sTalk', '15'); T.fill('#sRounds', '2'); T.fill('#sVote', '12'); T.click('#btnCreate'); time.sleep(2.5)
    sid = T.evaluate("localStorage.getItem('jinro_teacher_current')").strip('"'); print('session', sid)
    sim = subprocess.Popen([sys.executable, 'test/sim_students.py', sid, '9', '900'])
    # 人間モードの学生
    H = br.new_context(viewport={'width': 1366, 'height': 860}).new_page(); track(H, 'human')
    H.goto(f'{B}/index.html?api={API}&session={sid}'); H.wait_for_selector('#vEntry:not(.hidden)'); time.sleep(.8)
    H.fill('#eSid', '2501001A'); H.fill('#eNick', 'たかはし'); H.screenshot(path=f'{OUT}/h1_name.png'); H.click('#eNext'); time.sleep(.6)
    H.click('#eRand'); H.fill('#eProf', '理工学部の1年生。メロンパンと回路図が好き。'); H.screenshot(path=f'{OUT}/h2_avatar.png')
    H.click('#eNext'); time.sleep(2.2); H.screenshot(path=f'{OUT}/h4_story1.png')   # 最後のステップの「つぎへ」が「エントリーする！」
    H.click('#overlay'); time.sleep(.3); H.click('#overlay'); time.sleep(1.5); H.screenshot(path=f'{OUT}/h4_story2.png')
    H.click('#storySkip'); H.wait_for_selector('#vSWait:not(.hidden)', timeout=20000); time.sleep(1.5)
    # AI モードの学生
    A = br.new_context(viewport={'width': 1366, 'height': 860}).new_page(); track(A, 'ai')
    A.goto(f'{B}/index.html?api={API}&session={sid}&mode=ai'); A.wait_for_selector('#vEntry:not(.hidden)')
    A.fill('#eSid', '2501002B'); A.fill('#eNick', 'めいたんてい'); A.click('#eNext'); time.sleep(.5); A.click('#eNext'); time.sleep(.5)
    A.click('[data-pre="🔍 名探偵"]'); A.fill('#eStr', '占い師の結果をいちばん信じる。黙っている人を疑う。'); A.screenshot(path=f'{OUT}/a3_ai.png'); A.click('#eNext'); time.sleep(.5)
    time.sleep(1.2); A.click('#storySkip'); A.wait_for_selector('#vSWait:not(.hidden)', timeout=20000)
    time.sleep(4); H.screenshot(path=f'{OUT}/h5_wait.png'); T.screenshot(path=f'{OUT}/t1_entry.png', full_page=True)
    # 締め切り
    T.click('#btnStart'); time.sleep(4); T.screenshot(path=f'{OUT}/t2_running.png', full_page=True)
    H.wait_for_selector('#vGame:not(.hidden)', timeout=30000); A.wait_for_selector('#vGame:not(.hidden)', timeout=30000)
    shotH = shotA = False; t0 = time.time()
    def human_step():
        if H.locator('#overlay.show').count(): H.evaluate("document.getElementById('overlay').click()"); return
        if H.locator('#tSkip').count() and H.locator('#tSkip').is_enabled(): H.click('#tSkip')
        elif H.locator('#gAction .tbtn').count() and not H.locator('#gAction .tbtn.sel').count(): H.locator('#gAction .tbtn').first.click()
    while time.time() - t0 < 600:
        try: human_step()
        except Exception: pass
        if A.locator('#overlay.show').count(): A.evaluate("document.getElementById('overlay').click()")
        if not shotH and H.locator('#gStage .bubble').count(): time.sleep(.5); H.screenshot(path=f'{OUT}/h6_game.png'); shotH = True
        if not shotA and A.locator('.brow').count() >= 3: time.sleep(.5); A.screenshot(path=f'{OUT}/a6_ai_game.png'); shotA = True
        st = T.locator('#mTitle').inner_text()
        if '結果発表' in st: break
        time.sleep(1)
    print('round1 done', round(time.time() - t0), 's')
    time.sleep(8); T.screenshot(path=f'{OUT}/t3_results.png', full_page=True)
    try: H.evaluate("document.getElementById('overlay').click()")
    except Exception: pass
    time.sleep(1); H.screenshot(path=f'{OUT}/h7_end.png')
    # リトライ → 自動で次の村へ
    T.click('#btnRetry'); time.sleep(3)
    H.wait_for_function("document.querySelector('#gDay') && document.querySelector('#gDay').innerText.includes('1日目') && !document.querySelector('#vGame').classList.contains('hidden')", timeout=60000)
    time.sleep(2); print('human auto-joined round 2:', H.locator('#hdrRoom').inner_text()); H.screenshot(path=f'{OUT}/h8_round2.png')
    rid = A.evaluate("roomId")
    R = br.new_page(viewport={'width': 1366, 'height': 900}); track(R, 'results')
    sim.kill()
    # 1試合目の AI 学生の村の分析
    st = json.loads(subprocess.check_output(['curl', '-s', '-X', 'POST', API, '-d', json.dumps({'action': 'sessionState', 'sessionId': sid, 'adminKey': T.evaluate("JSON.parse(localStorage.getItem('jinro_teacher_sessions')).slice(-1)[0].adminKey")})]))
    print('rounds', [r['n'] for r in st['session']['rounds']])
    open('/tmp/sui/sid.txt', 'w').write(sid)
print('errors', errs)
