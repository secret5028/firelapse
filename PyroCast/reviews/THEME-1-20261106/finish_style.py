from pathlib import Path
ROOT=Path('C:/Users/예방/Documents/ChatGPT/PyroCast')
def change(rel,pairs):
 p=ROOT/rel;t=p.read_text('utf8')
 for a,b in pairs:
  if a not in t:raise ValueError(rel+' missing '+a[:60])
  t=t.replace(a,b)
 p.write_text(t,encoding='utf8',newline='\n')
change('app/web/panels/explore.js',[("calculating?'status-busy':calculation.state==='complete'?'status-ok':''", "calculating?'status-busy':$('exploreCalculateStatus').textContent==='계산 완료'?'status-ok':''")])
change('app/web/panels/assistant.js',[(".aiEvidence{font-size:13px", ".aiEvidence{font-size:11px")])
change('app/web/panels/timeline_risk.js',[("font-size:13px;line-height:14px", "font-size:11px;line-height:14px")])
change('app/web/panels/shell.js',[("button[aria-selected=true]{border-bottom-color:var(--accent);color:var(--accent);background:var(--bg-scene)","button[aria-selected=true]{border-bottom-color:var(--accent);color:var(--accent);background:var(--bg-selected)"),("button[aria-selected=true]{background:var(--bg-scene);color:var(--accent)","button[aria-selected=true]{background:var(--bg-selected);color:var(--accent)")])
change('app/web/panels/result_list.js',[("background:color-mix(in srgb,var(--bg-panel) 90.980392%,transparent)","background:color-mix(in srgb,var(--bg-card) 90.980392%,transparent)")])
change('app/web/panels/results.js',[("$('resultMCStatus').textContent=summary?", "$('resultMCStatus').className=summary?.rows.some(r=>!r.complete)?'status-error':summary?'status-ok':'';$('resultMCStatus').textContent=summary?")])
change('app/web/controller.js',[("$('resultMCStatus').textContent=error.message;", "$('resultMCStatus').className='status-error';$('resultMCStatus').textContent=error.message;"),("if(!disposed)$('resultMCStatus').textContent='집계 읽기 실패 · '+error.message;", "if(!disposed){$('resultMCStatus').className='status-error';$('resultMCStatus').textContent='집계 읽기 실패 · '+error.message;}"),("if(!mcSummary)return;$('resultMCLoad').disabled=true;", "if(!mcSummary)return;$('resultMCLoad').disabled=true;$('resultMCStatus').className='status-busy';")])
p=ROOT/'simulation/viewer/theme.css'
with p.open('a',encoding='utf8') as f:f.write('''
/* Dynamic panel style tags are inserted later; these selectors keep the type scale stable. */
body.pyroShell #pyroShellSidebar .workflowStep>h3,
body.pyroShell #pyroShellSidebar #resultContent h3,
body.pyroShell #pyroShellSidebar #routeRiskSummary h3,
body.pyroShell #pyroShellSidebar #shellPane-display h3{font-size:14px;color:var(--text-strong)}
body.pyroShell #pyroShellSidebar .aiEvidence,body.pyroShell #pyroShellTimeline .timelineRiskLabel{font-size:11px;color:var(--text-muted)}
body.pyroShell #pyroShellSidebar .exploreEngineButtons button[aria-pressed=true]{background:var(--bg-selected);border-color:var(--accent);color:var(--text-strong)}
''')
