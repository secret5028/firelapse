from pathlib import Path
import re,json
root=Path('C:/Users/<user>/Desktop/소방 크로키 업-로컬웹앱')
refs={}
for p in (root/'개발/work').rglob('*'):
 if p.suffix not in {'.py','.js','.mjs','.cjs','.md','.txt','.spec'} or any(x in p.parts for x in ['hydraulic-deps','tool-deps','cad-tools','node_modules','local-resources','pyi-build','local-pyi','hydraulic-pyi']):continue
 try:s=p.read_text('utf8')
 except:continue
 for match in re.findall(r"C:[/\\]Users[/\\]<user>[/\\](?:Downloads|Desktop)[^\n\r'\"<>]+",s):
  if '소방 크로키 업-로컬웹앱' not in match:refs.setdefault(match,[]).append(str(p.relative_to(root)))
print(json.dumps(refs,ensure_ascii=False,indent=2))
