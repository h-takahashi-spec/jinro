import time, sys, json, requests
from playwright.sync_api import sync_playwright
API='http://localhost:8787'; BASE=sys.argv[1] if len(sys.argv)>1 else 'http://localhost:8080'
errs=[]
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={'width':1366,'height':900})
    pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.goto(f'{BASE}/results.html?api={API}'); time.sleep(2.5)
    pg.screenshot(path='/tmp/r_overview.png', full_page=True)
    pg.click('#teamSeg button[data-team="WEREWOLF"]'); time.sleep(.5); pg.screenshot(path='/tmp/r_overview_wolf.png', full_page=True)
    pg.click('#teamSeg button[data-team="all"]')
    pg.click('.tab[data-tab="games"]'); time.sleep(.5); pg.screenshot(path='/tmp/r_games.png')
    pg.locator('[data-detail]').first.click(); time.sleep(1.5); pg.screenshot(path='/tmp/r_detail.png')
    pg.locator('.pcard').nth(1).click(); time.sleep(.5); pg.screenshot(path='/tmp/r_detail_sel.png', full_page=True)
    pg.click('.tab[data-tab="players"]'); time.sleep(.5); pg.screenshot(path='/tmp/r_players.png')
    pg.locator('tr[data-key]').first.click(); time.sleep(1.5); pg.screenshot(path='/tmp/r_player.png', full_page=True)
    m=b.new_page(viewport={'width':400,'height':860}); m.goto(f'{BASE}/results.html?api={API}'); time.sleep(2); m.screenshot(path='/tmp/r_mobile.png', full_page=True)
print('errors',errs)
