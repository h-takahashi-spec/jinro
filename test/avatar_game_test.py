import subprocess, time, sys, json
from playwright.sync_api import sync_playwright
API='http://localhost:8787'; B='http://localhost:8080'
errs=[]
AV={"v":1,"bg":"night","bgC":0,"body":"cloak","bodyC":11,"face":"oval","skin":2,"eyes":"sly","mouth":"smirk","hair":"long","hairC":0,"head":"none","accC":0,"glasses":"none","glsC":3}
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={'width':1440,'height':900})
    pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.goto(f'{B}/index.html?api={API}&free=1')
    pg.evaluate(f"localStorage.setItem('jinro_avatar', JSON.stringify({json.dumps(AV)}))"); pg.reload(); time.sleep(1.5)
    pg.screenshot(path='/tmp/ga_lobby.png')
    pg.fill('#myName','たかはし'); pg.fill('#roomName','アバター村'); pg.click('#vLobby details.more summary'); pg.fill('#talkSec','10'); pg.fill('#voteSec','8')
    pg.click('#btnCreate'); pg.wait_for_selector('#vWait:not(.hidden)')
    rid=pg.evaluate('roomId')
    ag=subprocess.Popen([sys.executable,'run_agents.py','--api',API,'--room',rid,'--agent','rule:2','--agent','my:1','--poll','0.4','--quiet'],cwd='agents')
    pg.wait_for_function("document.querySelectorAll('#wStage .seat:not(.empty-seat)').length>=4", timeout=20000); time.sleep(.8)
    pg.screenshot(path='/tmp/ga_wait.png')
    # 工房で変更 → 戻る → 自動反映
    pg.click('#wToWorkshop'); pg.wait_for_selector('#stage .ava'); time.sleep(.6)
    pg.click('.tab[data-k="head"]'); pg.locator('.opt').nth(5).click(); pg.click('#btnSave')
    pg.wait_for_selector('#vWait:not(.hidden)', timeout=15000); time.sleep(4)
    st=json.loads(subprocess.check_output(['curl','-s','-X','POST',API,'-d',json.dumps({"action":"state","roomId":rid})]))['state']
    print('server avatar head:', st['players'][0].get('avatar',{}).get('head'))
    pg.click('#btnStart'); 
    t0=time.time(); shot=False
    while time.time()-t0<200:
        if pg.locator('#overlay.show').count(): pg.evaluate("document.getElementById('overlay').click()"); time.sleep(.3); continue
        if pg.locator('#tSkip').count() and pg.locator('#tSkip').is_visible():
            if not shot: time.sleep(1.5); pg.screenshot(path='/tmp/ga_game.png'); shot=True
            pg.click('#tSkip')
        elif pg.locator('#gAction .tbtn').count(): pg.locator('#gAction .tbtn').first.click()
        if pg.locator('#gAction').inner_text().find('村の一覧へ')>=0: break
        time.sleep(.4)
    time.sleep(1); pg.screenshot(path='/tmp/ga_end.png')
    ag.wait(timeout=60)
    r=b.new_page(viewport={'width':1366,'height':900}); r.goto(f'{B}/results.html?api={API}&game={rid}'); time.sleep(3); r.screenshot(path='/tmp/ga_results.png')
print('errors',errs)
