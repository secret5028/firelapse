import os,json,uuid
from pathlib import Path
os.environ['FIRE_SPACE_DATA']=str(Path('work/progress-test-data').resolve())
import local_app as a
events=[];original=a.update
def record(j,status,message,progress=None):
 original(j,status,message,progress)
 if progress is not None:events.append(int(progress))
a.update=record
j=uuid.uuid4().hex;folder=a.HOME/j;folder.mkdir()
with a.db() as c:c.execute('INSERT INTO jobs(id,name,status,message,created) VALUES(?,?,?,?,?)',(j,'진행률 검증','processing','',0))
(folder/'drawing.dwg').write_bytes(Path('work/cad-input/2.dwg').read_bytes())
(folder/'files.json').write_text(json.dumps([{'name':'1F.dwg','stored':'drawing.dwg'}]))
a.process(j)
assert events==sorted(events),events
assert events[-1]==100 and 93 in events and 98 in events,events
with a.db() as c:assert c.execute('SELECT progress FROM jobs WHERE id=?',(j,)).fetchone()[0]==100
a.update(j,'processing','retry',0);events.clear()
(folder/'drawing.dwg').write_bytes(b'bad')
a.process(j)
with a.db() as c:
 r=c.execute('SELECT status,progress FROM jobs WHERE id=?',(j,)).fetchone();assert r['status']=='error' and r['progress']<100,dict(r)
print('PASS monotonic DWG progress, generation/save stages, completion=100, error retains incomplete progress')
