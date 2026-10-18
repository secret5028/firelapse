from pathlib import Path
p=Path('work/prepare_local.py');s=p.read_text('utf8');needle="Path('work/model-quality.js').read_text('utf-8')"
assert needle in s
s=s.replace(needle,needle+"+'\\n'+Path('work/water-supply-defaults.js').read_text('utf-8')")
p.write_text(s,'utf8')
