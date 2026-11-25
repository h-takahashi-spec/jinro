"""AIサバイバル戦の通しテスト: 先生の画面で開始→各回→決勝→優勝。学生1人はブラウザで観戦/脱落表示を確認"""
import json, os, subprocess, sys, time
from playwright.sync_api import sync_playwright
API = 'http://localhost:8787'; B = 'http://localhost:8080'; OUT = '/tmp/sv'; os.makedirs(OUT, exist_ok=True)
N = int(sys.argv[1]) if len(sys.argv) > 1 else 22
errs = []
with sync_playwright() as p:
    br = p.chromium.launch()
    T = br.new_context(viewport={'width': 1440, 'height': 900}).new_page(); T.on('pageerror', lambda e: errs.append('T ' + str(e)))
    T.goto(f'{B}/teacher.html?api={API}'); time.sleep(1.5)
    if T.locator('#btnSwitch').is_visible(): T.click('#btnSwitch'); time.sleep(.4)
    T.click('#btnCreate'); time.sleep(2)
    sid = T.evaluate("localStorage.getItem('jinro_teacher_current')").strip('"')
    sim = subprocess.Popen([sys.executable, 'test/sim_students.py', sid, str(N), '1500'], env={**os.environ, 'ALL_AI': '1'})
    # 人間モードの観戦者
    H = br.new_context(viewport={'width': 1366, 'height': 860}).new_page(); H.on('pageerror', lambda e: errs.append('H ' + str(e)))
    H.goto(f'{B}/index.html?api={API}&session={sid}'); H.wait_for_selector('#vEntry:not(.hidden)')
    H.fill('#eSid', '2509999'); H.fill('#eNick', 'おうえん'); H.click('#eNext'); time.sleep(.4); H.click('#eNext'); time.sleep(1); H.click('#storySkip')
    H.wait_for_selector('#vSWait:not(.hidden)', timeout=20000)
    time.sleep(10); T.screenshot(path=f'{OUT}/0_entry.png', full_page=True)
    T.click('[data-sv="start"]'); time.sleep(5)
    stage = 1; t0 = time.time(); shots = set()
    while time.time() - t0 < 1200:
        title = T.locator('#mTitle').inner_text()
        if '試合中' not in title and '回戦' in title and '結果' not in title or '決勝' in title and '優勝' not in title and not T.locator('[data-sv="next"]').count():
            if f'run{stage}' not in shots: time.sleep(3); T.screenshot(path=f'{OUT}/run{stage}.png', full_page=True); H.screenshot(path=f'{OUT}/h_run{stage}.png'); shots.add(f'run{stage}')
        if T.locator('[data-sv="next"]').count():
            time.sleep(3); T.screenshot(path=f'{OUT}/res{stage}.png', full_page=True); print('stage', stage, 'done', round(time.time() - t0), 's ->', T.locator('[data-sv="next"]').inner_text())
            T.click('[data-sv="next"]'); stage += 1; time.sleep(5); continue
        if '優勝決定' in title:
            time.sleep(4); T.screenshot(path=f'{OUT}/champion.png', full_page=True); H.screenshot(path=f'{OUT}/h_champion.png'); print('champion after', stage, 'stages', round(time.time() - t0), 's'); break
        time.sleep(2)
    adm = json.loads(T.evaluate("localStorage.getItem('jinro_teacher_sessions')"))[-1]['adminKey']
    st = json.loads(subprocess.check_output(['curl', '-s', '-X', 'POST', API, '-d', json.dumps({'action': 'sessionState', 'sessionId': sid, 'adminKey': adm})]))
    sv = st['session']['survival']
    print('history', [(h['stage'], len(h['entrants']), len(h['advanced'] or []), h['final']) for h in sv['history']], 'champions', sv['champions'])
    sim.kill()
print('errors', errs)
