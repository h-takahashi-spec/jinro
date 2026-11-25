"""サーバーなしで、作った状態を画面に流しこんで撮る（見た目の確認用）。先に sh test/start_servers.sh で静的サーバーを起動しておく。
usage: python test/ui_scenes.py OUT W H scenario[,scenario...]   例: python test/ui_scenes.py /tmp/scenes 1366 768 talk,vote,ov_end"""
import sys, time, os, json
from playwright.sync_api import sync_playwright
OUT=sys.argv[1]; W=int(sys.argv[2]); Hh=int(sys.argv[3]); SC=sys.argv[4].split(',')
os.makedirs(OUT,exist_ok=True)
B=os.environ.get('BASE','http://localhost:8080')
JS = r"""
(sc) => {
  const names=['しばっち','もちこ','たまご','ぽんず','こむぎ','みかん','あんこ','たかはしひでゆき'];
  const n = sc.n||8;
  const players=names.slice(0,n).map((nm,i)=>({id:i+1,name:nm,kind:i%3==1?'ai':i==4?'cpu':'human',alive:!(sc.dead||[]).includes(i+1),avatar:i==n-1?null:Avatar.compact(Avatar.random('s'+i)),profile:'理工学部1年'}));
  const talks=[]; let idx=0;
  const T=(day,round,from,text,tags)=>talks.push({idx:idx++,day,round,from,text,tags:tags||[]});
  T(1,1,1,'おはよう！まずは占い師さんの話を聞きたいです。');
  T(1,1,2,'わたしは占い師です。たまごさんを占ったら、人間でした。',[{type:'CO',role:'SEER'},{type:'DIVINED',target:3,result:'HUMAN'}]);
  T(1,1,4,'えっ、わたしも占い師です！もちこさんは柴犬でした。',[{type:'CO',role:'SEER'},{type:'DIVINED',target:2,result:'WEREWOLF'}]);
  T(1,2,5,'占い師が2人いる以上、どちらかが偽物です。もちこさんがあやしいと思います。',[{type:'ESTIMATE',target:2,role:'WEREWOLF'}]);
  T(1,2,6,'今日はぽんずさんに投票します。',[{type:'VOTE',target:4}]);
  const day=sc.day||1, events=[{day:1,type:'start'}], vh=[];
  if(day>=2){ vh.push({day:1,votes:{1:4,2:4,3:2,4:2,5:4,6:4,7:2,8:4},executed:4,tie:false}); events.push({day:1,type:'execute',target:4},{day:2,type:'attack',target:6}); players[3].alive=false; players[5].alive=false;
    T(2,1,1,'みかんさんが連れていかれた…。'); T(2,1,3,'もちこさんは信じられると思います。',[{type:'ESTIMATE',target:2,role:'VILLAGER'}]); }
  const role=sc.role||'VILLAGER', me={id:n,name:names[n-1],role,alive:!(sc.dead||[]).includes(n),team:['WEREWOLF','POSSESSED'].includes(role)?'WEREWOLF':'VILLAGER',kind:sc.ai?'ai':'human',done:!!sc.done,
    nightAction:sc.phase==='night'?({WEREWOLF:'attack',SEER:'divine',BODYGUARD:'guard'}[role]||null):null, myVote:sc.sel||null, myNightTarget:sc.sel||null};
  if(role==='SEER') me.divineResults=[{day:0,target:3,result:'HUMAN'},{day:1,target:5,result:'WEREWOLF'}];
  if(role==='MEDIUM') me.mediumResults=day>=2?[{day:1,target:4,result:'HUMAN'}]:[];
  if(role==='WEREWOLF'){ me.wolves=[5,n]; if(sc.phase==='night') me.wolfAttackVotes={5:2}; }
  if(role==='BODYGUARD') me.guardHistory=day>=2?[{day:1,target:2}]:[];
  if(sc.ai){ me.ai={params:{logic:90,emotion:20,active:70,skeptic:80,coop:30,bold:40},strategy:''}; me.beliefs=[{day:1,phase:'talk',act:'talk',by:'llm',text:'もちこさんがあやしいと思います。',probs:{1:.12,2:.61,3:.08,4:.33,5:.2,6:.15,7:.1},reasons:{2:[{d:1,r:'占い師に柴犬と言われた'}],4:[{d:1,r:'占い師を名乗ったが対抗がいる'}],3:[{d:-1,r:'占い師に人間と言われた'}]}}]; }
  const fin=sc.phase==='end';
  if(fin){ const rs=['VILLAGER','SEER','VILLAGER','POSSESSED','WEREWOLF','BODYGUARD','MEDIUM',role==='WEREWOLF'?'VILLAGER':role]; if(role==='WEREWOLF') rs[4]='VILLAGER', rs[n-1]='WEREWOLF', rs[2]='WEREWOLF'; else rs[2]='WEREWOLF'; players.forEach((p,i)=>p.role=rs[i]); }
  setFree(false); IN_SESSION = sc.free?false:1; if(sc.free) setFree(true);
  roomId='fake'+(sc.key||''); 
  const base={roomId, name:'第1試合・はちみつ村', size:n, settings:{talkSec:60,voteSec:30,nightSec:30,talkRounds:3}, status:fin?'finished':'playing', phase:sc.phase||'talk', day, round:sc.round||2,
    deadline:Date.now()+(sc.left||42)*1000, now:Date.now(), version:1, winner:fin?(sc.winner||'VILLAGER'):null, roleSet:['WEREWOLF','WEREWOLF','SEER','MEDIUM','BODYGUARD','VILLAGER','VILLAGER','VILLAGER'].slice(0,n),
    players, talks, voteHistory:vh, events, progress:sc.phase==='night'||fin?null:{done:3,total:players.filter(p=>p.alive).length}, me: sc.spec?null:me};
  // 1回目: 演出なしで入る
  seen.key=null; store.set('rv',{[roomId+'_'+n]:1});
  P0=S; S=base; clockSkew=0; render();
  if(sc.bubble){ const t={idx:99,day,round:1,from:sc.bubble,text:'えっ、わたしも占い師です！もちこさんは柴犬でした。',tags:[{type:'DIVINED',target:2,result:'WEREWOLF'}]}; S.talks.push(t); render(); }
  if(sc.ov==='tally') enqueue(()=>ovTally({day:1,votes:{1:4,2:4,3:2,4:2,5:4,6:4,7:2,8:4},executed:4,tie:false}));
  if(sc.ov==='reveal') enqueue(()=>ovReveal(role));
  if(sc.ov==='morning') enqueue(()=>ovMorning({day:2,type:'attack',target:6}));
  if(sc.ov==='end') enqueue(()=>ovEnd());
  if(sc.ribbon){ seen.ribbon=''; phaseRibbon(); }
  if(sc.help) openHelp();
  if(sc.quick){ document.querySelector('[data-q="'+sc.quick+'"]').click(); }
  return true;
}
"""
SCN = {
 'talk': dict(role='SEER'), 'talk_pick': dict(role='VILLAGER', quick='sus'), 'talk_done': dict(role='VILLAGER', done=True),
 'vote': dict(phase='vote', role='VILLAGER', bubble=4), 'vote_sel': dict(phase='vote', role='WEREWOLF', sel=2, ribbon=True),
 'night_wolf': dict(phase='night', role='WEREWOLF', day=1), 'night_seer': dict(phase='night', role='SEER', day=2, sel=1), 'night_idle': dict(phase='night', role='VILLAGER', ribbon=True),
 'dead': dict(role='VILLAGER', day=2, dead=[8]), 'spec': dict(spec=True, free=True, day=2), 'ai': dict(ai=True, role='VILLAGER'),
 'end': dict(phase='end', day=2, role='SEER'), 'end_free': dict(phase='end', day=2, role='SEER', free=True),
 'ov_tally': dict(phase='night', ov='tally', wait=3.3), 'ov_tally2': dict(phase='night', ov='tally', wait=8.2), 'ov_reveal': dict(ov='reveal', role='WEREWOLF', wait=3.2), 'ov_morning': dict(day=2, ov='morning', wait=2.6),
 'ov_end': dict(phase='end', day=2, role='WEREWOLF', winner='WEREWOLF', ov='end', wait=3.5), 'ov_end_v': dict(phase='end', day=2, role='SEER', ov='end', wait=3.5),
 'help': dict(role='VILLAGER', help=True), 'six': dict(n=6, role='BODYGUARD', day=1), 'talk5': dict(n=5, role='MEDIUM', day=1),
}
errs=[]
with sync_playwright() as p:
    br=p.chromium.launch(); ctx=br.new_context(viewport={'width':W,'height':Hh})
    pg=ctx.new_page(); pg.on('pageerror',lambda e: errs.append(str(e))); pg.on('console',lambda m: errs.append('console:'+m.text) if m.type=='error' else None)
    pg.goto(f'{B}/index.html?api=http://localhost:8787&free=1'); pg.wait_for_selector('#vLobby:not(.hidden)'); time.sleep(.6)
    for name in SC:
        sc=dict(SCN[name]); sc['key']=name; w=sc.pop('wait',1.0)
        pg.evaluate("clearOverlay(); closeHelp(); pick=null; actionKey=''; roleKey=''; seatsKey=''; bubbleRoom=null;")
        pg.evaluate(JS, sc); time.sleep(w)
        pg.screenshot(path=f'{OUT}/{name}.png', full_page=bool(os.environ.get('FULL')))
    print('errors',errs[:8])
