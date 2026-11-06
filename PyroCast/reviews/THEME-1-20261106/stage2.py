from pathlib import Path
import json,re,shutil
ROOT=Path('C:/Users/예방/Documents/ChatGPT/PyroCast');OUT=Path(__file__).parent
data=json.loads((OUT/'tokens.json').read_text('utf8'));base=data['base']
dark={**base,'bg-panel':'#0d141c','bg-card':'#1a2733','bg-control':'#223240','bg-control-hover':'#2b3d4d','bg-selected':'#173a4f','border':'#2e3f4e','border-strong':'#44586a','text':'#d8e2ea','text-muted':'#8fa3b5','accent':'#8fd3ff','accent-fg':'#0b1a26','shadow':'#0002'}
light={**dark,'bg-scene':'#dfe7ee','bg-panel':'#f4f7f9','bg-card':'#ffffff','bg-control':'#e9eef3','bg-control-hover':'#dde5ec','bg-selected':'#d6ecfa','border':'#c5d0da','border-strong':'#9fb0bf','text':'#1b2630','text-strong':'#0b1118','text-muted':'#5d6f80','accent':'#0a6fb8','accent-fg':'#ffffff','ok':'#1e8f5a','busy':'#b86e00','error':'#c43c1a'}
groups={
 'bg-panel':'07131d 0a1c29 0b1e2d 102838 10283a 132c3b 182d3d 17181a 1d1d1f 222428',
 'bg-card':'16364c 17384d 193648 19384e 19394d 1c3545',
 'bg-selected':'153f64 1d4f75 245166 2a4d63',
 'bg-control':'234357 235e79 26628e 2b6cb0 345c6a 3a3c40',
 'accent':'2baed4 2f7fb8 34c1df 38bdf8 3f93cc 428ac0 42cce7 42e8ff 46ede2 5793bd 72e3f7 7fb0e6 9af3ff 9bd3ff 9cdcff a2efff a8d5dc',
 'border':'304c5e 304d60 355468 365164 365268 416275 426278 436072 486678 ffffff12 ffffff1f ffffff30',
 'border-strong':'59798d 5a839c 617786 698493 6a8d9f 6d8796 7292a3 7296aa 7f9cae 8099aa 86a4b7 8eacbc',
 'text-muted':'93a7bb 9eb2c4 a9bfcd a9cfdf afc6d4 b6c9d8 b6cedb bfd3df c1d2dd c4d8e4 c8dbe7 c9d9e4 cbe2ed ced9df d6d6d2',
 'text':'d6e8f3 dcebf3 e0ccfa e4edf4 e5f3ff e8e8e6 e9f8ff ebf5ff eef5fa eff7fb f2f7fa f4f4f2',
 'busy':'e6bd68 e7be66 f0d18e f4d38b eea746 ffbd85 ffbf57 ffc959 ffd174 ffd18a ffd35b ffe098 ffe0a5',
 'error':'9c223a ffb5a6 ffb6a7 ffc1b0',
 'ok':'62dcb0', 'accent-fg':'082633'
}
mapping={s:k for k,ss in groups.items() for s in ss.split()}
# These are semantic legend samples, deliberately not theme colors.
semantic={'2563eb','55baff','ff3b09','ff7a14','ffa824','fff08c','2c73bc','f3b441','e64b26','9b1337'}
aliases={}
for k,v in data['compat'].items():
 c=v.lstrip('#').lower()
 if c in semantic:aliases[k]=v;continue
 if v=='white':aliases[k]='var(--text-strong)';continue
 if c in ('0002','0008'):aliases[k]='var(--shadow)';continue
 if c=='ffffffee':aliases[k]='var(--text-strong)';continue
 if c in mapping:aliases[k]='var(--'+mapping[c]+')';continue
 if len(c)==8:
  stem=c[:6];role=mapping.get(stem, {'142b3b':'bg-panel','102331':'bg-scene','42c4e8':'accent'}.get(stem))
  if role:aliases[k]=f'color-mix(in srgb,var(--{role}) {int(c[6:],16)/255*100:.6f}%,transparent)';continue
 raise RuntimeError('Unmapped compatibility color '+k+' '+v)
files=json.loads((OUT/'stage1-files.json').read_text('utf8'))
for rel in files:
 p=ROOT/rel
 if p.suffix not in ('.js','.css','.html') or p.name=='theme.css':continue
 raw=p.read_bytes();t=raw.decode('utf8');old=t
 for k,v in aliases.items():t=t.replace('var(--'+k+')',v)
 # Presentation values only. Do not edit Three.js materials or dimensions.
 t=re.sub(r'(font-size\s*:\s*)(?:10(?:\.5)?|12)px',r'\g<1>13px',t)
 t=re.sub(r'(font-size\s*:\s*)19px',r'\g<1>20px',t)
 t=re.sub(r'(font\s*:[^;{}]*?)(?:10(?:\.5)?|12)px(?=[/\s])',r'\g<1>13px',t)
 # Small captions are 11px; all pre-existing 11px captions remain untouched.
 t=t.replace('.resultDetail{font-size:13px','.resultDetail{font-size:11px').replace('.resultEngine{flex:none;font-size:13px','.resultEngine{flex:none;font-size:11px')
 if t!=old:
  b=OUT/'stage1-source'/rel;b.parent.mkdir(parents=True,exist_ok=True);b.write_bytes(raw);p.write_bytes(t.encode('utf8'))
# Explicit status classes only; source conditions/data/control flow are unchanged.
def edit(rel,pairs):
 p=ROOT/rel;t=p.read_text('utf8');b=OUT/'stage1-source'/rel;b.parent.mkdir(parents=True,exist_ok=True)
 if not b.exists():b.write_bytes(p.read_bytes())
 for before,after in pairs:
  if before not in t:raise ValueError('Missing status anchor '+rel+' '+before[:80])
  t=t.replace(before,after,1)
 p.write_text(t,encoding='utf8',newline='\r\n')
edit('app/web/panels/results.js',[("state.textContent=coverage.status;state.hidden=!room;", "state.textContent=coverage.status;state.className=coverage.evaluated?'status-ok':'';state.hidden=!room;")])
edit('app/web/panels/explore.js',[
 ("$('exploreOriginRun').disabled=payload?", "$('exploreCalculateStatus').className=calculation.error?'status-error':calculating?'status-busy':calculation.state==='complete'?'status-ok':'';\n  $('exploreMCStatus').className=/실패|시간초과|차단|미완료|오류/.test($('exploreMCStatus').textContent)?'status-error':(mcJob.running||mcPending)?'status-busy':/완료/.test($('exploreMCStatus').textContent)?'status-ok':'';\n  $('exploreEstimate').className=estimate===null?'':'status-busy';\n  $('exploreOriginRun').disabled=payload?"),
 ("const c=value.comparison;", "$('exploreStatus').className=progress?.error?'status-error':progress?.running?'status-busy':'';\n  const c=value.comparison;")])
edit('app/web/panels/export.js',[
 ("status.textContent=' 묶는 중…';", "status.textContent=' 묶는 중…';status.className='status-busy';"),
 ("const blob=await response.blob(),large=", "status.className='status-ok';const blob=await response.blob(),large="),
 ("}catch(e){status.textContent=' '+e.message;", "}catch(e){status.className='status-error';status.textContent=' '+e.message;")])
theme='/* THEME-1: palette values only; dark is default. Semantic 3D/index colors stay in their source. */\n'
for selector,values in [(':root',dark),('[data-theme=light]',light)]:theme+=selector+'{\n'+''.join('  --'+k+':'+v+';\n' for k,v in values.items())+'}\n'
theme+='''
/* Existing elements only: typography and control colors, no layout changes. */
#pyroShellHeader,#pyroShellSidebar,#pyroShellTimeline{font-size:13px;font-variant-numeric:tabular-nums}
#pyroShellSidebar :is(#resultContent,#exploreContent,#fuelSettings,#shellPane-display){font-size:13px;color:var(--text)}
#pyroShellSidebar .workflowStep>h3{font-size:14px;color:var(--text-strong)}
#pyroShellSidebar :is(#resultContent,#routeRiskSummary)>h3,#pyroShellSidebar #resultContent section>h3,#shellPane-display h3{font-size:14px;color:var(--text-strong)}
#pyroShellHeader .brand strong,#resultRoomTitle{font-size:20px;color:var(--text-strong)}
#pyroShellSidebar .resultPeakValue,#sceneResultList .resultDetail,#sceneResultList .resultEngine,.aiEvidence,.timelineRiskLabel{font-size:11px;color:var(--text-muted)}
#pyroShellSidebar :is(th,td){font-size:13px;font-variant-numeric:tabular-nums}
#pyroShellSidebar #pyroShellTabs button[aria-selected=true]{background:var(--bg-selected);color:var(--accent)}
#pyroShellSidebar :is(button,select):not(#exploreCalculateRun):not(#aiSend):not([aria-selected=true]){background:var(--bg-control)}
#pyroShellSidebar :is(#exploreCalculateRun,#aiSend){background:var(--accent);border-color:var(--accent);color:var(--accent-fg)}
#pyroShellSidebar :is(#exploreCalculateRun,#aiSend):not(:disabled){background:var(--accent);border-color:var(--accent);color:var(--accent-fg)}
#pyroShellSidebar #resultMCWorst{border:0;border-top:1px solid var(--border)}
#pyroShellSidebar #resultMCWorst strong{color:var(--text-strong)}
#sceneResultList button,#sceneResultList .resultEngine{border:0;border-top:1px solid var(--border)}
#sceneResultList button[aria-current=true]{border-color:var(--accent)}
#pyroShellSidebar .status-ok{color:var(--ok)!important}
#pyroShellSidebar .status-busy{color:var(--busy)!important}
#pyroShellSidebar .status-error{color:var(--error)!important}
'''
(OUT/'stage1-source/simulation/viewer').mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/'simulation/viewer/theme.css',OUT/'stage1-source/simulation/viewer/theme.css')
(ROOT/'simulation/viewer/theme.css').write_text(theme,encoding='utf8')
(OUT/'stage2-alias-map.json').write_text(json.dumps(aliases,ensure_ascii=False,indent=2),'utf8')
print('Stage 2 palette and presentation classes applied')
