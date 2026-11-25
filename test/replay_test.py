import time, sys, json, requests
from playwright.sync_api import sync_playwright
API='http://localhost:8787'; BASE=sys.argv[1] if len(sys.argv)>1 else 'http://localhost:8080'; OUT=sys.argv[2] if len(sys.argv)>2 else '/tmp/rp'
import os; os.makedirs(OUT,exist_ok=True)
r=requests.post(API,data=json.dumps({"action":"results"})).json()
g=sorted(r['games'],key=lambda g:-g['score'])[0]['roomId']
errs=[]; seenov=set(); t0=time.time()
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={'width':1440,'height':880})
    pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.goto(f'{BASE}/index.html?api={API}&replay={g}')
    pg.wait_for_selector('#rpPlay'); pg.select_option('#rpSpeed', sys.argv[3] if len(sys.argv)>3 else '2')
    shots=0; talkshot=False
    while time.time()-t0<240:
        if pg.locator('#overlay.show .otitle').count():
            try: k=pg.locator('#overlay.show .otitle').first.inner_text(timeout=1500).split('\n')[0][:6]
            except Exception: continue
            if k not in seenov:
                seenov.add(k); time.sleep(1.4); pg.screenshot(path=f'{OUT}/ov_{len(seenov):02d}_{k}.png')
                if '勝ち' in k: break
        elif not talkshot and pg.locator('#gStage .bubble').count():
            time.sleep(.5); pg.screenshot(path=f'{OUT}/talk.png'); talkshot=True
        time.sleep(.2)
    print('overlays', sorted(seenov))
    # seek test
    pg.evaluate("document.getElementById('overlay').click()"); time.sleep(1)
    pg.click('#gAction [data-day="2"]'); time.sleep(1.5)
    print('after seek day:', pg.locator('#gDay').inner_text(), pg.locator('#gPhase').inner_text())
    pg.screenshot(path=f'{OUT}/seek.png')
    pg.click('#rpPlay'); time.sleep(.3); print('btn', pg.locator('#rpPlay').inner_text())
print('errors', errs)
