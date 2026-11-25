import subprocess, time, sys, os
from playwright.sync_api import sync_playwright
API='http://localhost:8787'
OUT=sys.argv[1] if len(sys.argv)>1 else '/tmp/shots'
os.makedirs(OUT,exist_ok=True)
errs=[]; shots={}
def snap(pg,name):
    if name in shots: return
    shots[name]=1; pg.screenshot(path=f'{OUT}/{name}.png')
with sync_playwright() as p:
    b=p.chromium.launch()
    pg=b.new_page(viewport={'width':1440,'height':900})
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('console', lambda m: m.type=='error' and 'favicon' not in m.text and '404' not in m.text and errs.append(m.text))
    pg.goto(f'http://localhost:8080/index.html?api={API}&free=1')
    pg.wait_for_selector('#vLobby:not(.hidden)'); time.sleep(1.8); snap(pg,'01_lobby')
    pg.fill('#myName','たかはし'); pg.fill('#roomName','3班の村'); pg.click('#vLobby details.more summary'); pg.fill('#talkSec','15'); pg.fill('#voteSec','12')
    pg.click('#btnCreate'); pg.wait_for_selector('#vWait:not(.hidden)')
    rid=pg.evaluate('roomId')
    ag=subprocess.Popen([sys.executable,'run_agents.py','--api',API,'--room',rid,'--agent','rule:2','--poll','0.5','--quiet'],cwd='agents')
    pg.wait_for_function("document.querySelectorAll('#wStage .seat:not(.empty-seat)').length>=3", timeout=15000)
    time.sleep(0.8); snap(pg,'02_wait')
    pg.click('#btnStart')
    acted=set(); t0=time.time(); ovseen={}
    while time.time()-t0<300:
        ov=pg.locator('#overlay.show')
        if ov.count():
            title=pg.locator('#overlay .otitle').first.inner_text() if pg.locator('#overlay .otitle').count() else '?'
            k=title.split('\n')[0][:8]
            if k not in ovseen:
                ovseen[k]=time.time()
            elif time.time()-ovseen[k]>2.6 and ('ov_'+k) not in shots:
                snap(pg,'ov_'+k)
                if '勝ち' not in title: pg.locator('#overlay').click()
            if '勝ち' in title and ('ov_'+k) in shots: break
            time.sleep(0.3); continue
        if pg.locator('#tSend').count() and pg.locator('#tSend').is_visible():
            k=('talk',pg.locator('#gDay').inner_text(),pg.locator('#gRounds').inner_html())
            if k not in acted:
                acted.add(k)
                if len([a for a in acted if a[0]=='talk'])==1:
                    time.sleep(1.5); snap(pg,'03_talk_bubbles')
                    pg.click('[data-q="sus"]'); pg.locator('#tQuick .tbtn').first.click()   # ひとことボタン →「○○さんがあやしい」
                    pg.click('#tSend')
                else: pg.click('#tSkip')
        elif pg.locator('#gAction .tbtn').count():
            k=('act',pg.locator('#gDay').inner_text(),pg.locator('#gPhase').inner_text())
            if k not in acted:
                acted.add(k)
                pg.locator('#gStage .seat.targetable').first.click(); time.sleep(0.8)
                snap(pg,'04_vote_select' if '投票' in k[2] else '05_night_select')
        time.sleep(0.3)
    time.sleep(3.5); snap(pg,'99_end_overlay')
    pg.locator('#overlay').click(); time.sleep(1.2); snap(pg,'99_end_board')
    m=b.new_page(viewport={'width':400,'height':860}); m.goto(f'http://localhost:8080/index.html?api={API}&room={rid}'); m.wait_for_selector('#vGame:not(.hidden)'); time.sleep(1.5)
    m.screenshot(path=f'{OUT}/98_mobile.png', full_page=False)
    ag.wait(timeout=60)
print('shots', sorted(shots)); print('errors', errs)
