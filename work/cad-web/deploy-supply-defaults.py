from pathlib import Path
import shutil,sqlite3,datetime
root=Path('C:/Users/<user>/Desktop/소방 크로키 업-로컬웹앱')
code=Path('work/water-supply-defaults.js').read_text('utf8')
for rel in ['_internal/folder_review.html','소스/folder_review.html']:
 p=root/rel
 if p.parent.exists():shutil.copyfile('work/local-resources/folder_review.html',p)
shutil.copyfile('work/water-supply-defaults.js',root/'소스/water-supply-defaults.js')
for job in ['80fe8228ff8c4082bc8bf9f83771895b','1b8e6ebc75a74661b81047d7da38be68']:
 p=root/'data'/job/'result.html';s=p.read_text('utf8');marker='<script id="waterSupplyDefaults">'
 if marker in s:s=s[:s.index(marker)]
 p.write_text(s+'\n'+marker+code+'</script>','utf8')
 with sqlite3.connect(root/'data/history.sqlite') as db:
  row=db.execute('SELECT message FROM jobs WHERE id=?',(job,)).fetchone()
  db.execute('CREATE TABLE IF NOT EXISTS job_work_notes (id INTEGER PRIMARY KEY, job_id TEXT, created TEXT, message TEXT, previous_message TEXT, verification TEXT)')
  db.execute('INSERT INTO job_work_notes(job_id,created,message,previous_message,verification) VALUES(?,?,?,?,?)',(job,datetime.datetime.now().isoformat(),'수조·펌프 표시 기본 규칙 공통화. 등록 설비가 있는 건물에 적용하며, 연결살수 전용 건물은 송수구 시작 및 수조·펌프 항목 비활성화.',row[0],'수조·펌프 보유 / 송수구 전용 분기 검사 통과'))
print('Templates, both results and work history updated')
