from pathlib import Path
import urllib.request, hashlib, json
out=Path(__file__).resolve().parent/'nist-fuels';out.mkdir(exist_ok=True)
sources={
 'SP1021.pdf':'https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication1021.pdf',
 'NCSTAR1-5e.pdf':'https://nvlpubs.nist.gov/nistpubs/Legacy/NCSTAR/ncstar1-5e.pdf',
 'exp-tree.json':'https://api.github.com/repos/firemodels/exp/git/trees/master?recursive=1',
}
manifest=[]
for name,url in sources.items():
 p=out/name
 if not p.exists():
  req=urllib.request.Request(url,headers={'User-Agent':'Codex research'})
  p.write_bytes(urllib.request.urlopen(req,timeout=60).read())
 manifest.append(dict(file=name,url=url,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size))
(out/'download-manifest.json').write_text(json.dumps(manifest,indent=2),'utf8')
tree=json.loads((out/'exp-tree.json').read_text())
print('\n'.join(i['path'] for i in tree['tree'] if any(w in i['path'].lower() for w in ['workstation','cook','wtc','desk'])))
print(json.dumps(manifest))
