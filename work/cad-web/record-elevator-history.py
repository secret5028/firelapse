from pathlib import Path
import sqlite3,json,datetime
root=Path('C:/Users/예방/Desktop/소방 크로키 업-로컬웹앱/data')
job='80fe8228ff8c4082bc8bf9f83771895b'
now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
summary='2026-09-09 수정 · 1·2층 승강기 슬라이딩문·금색 문틀·벽 개구부 반영 / 두 손가락 이동 / 송수구 선택 시 흐름 전환 / 배관 표시 최적화'
with sqlite3.connect(root/'history.sqlite') as db:
 row=db.execute('SELECT name,status,message FROM jobs WHERE id=?',(job,)).fetchone()
 if not row:raise RuntimeError('Existing building history not found')
 if not (root/job/'result.html').exists():raise RuntimeError('Saved result missing')
 backup=root/job/'history-before-elevator-note.sqlite'
 if not backup.exists():
  with sqlite3.connect(backup) as dest:db.backup(dest)
 db.execute('CREATE TABLE IF NOT EXISTS job_work_notes (id INTEGER PRIMARY KEY, job_id TEXT, created TEXT, message TEXT, previous_message TEXT, verification TEXT)')
 if not db.execute('SELECT 1 FROM job_work_notes WHERE job_id=? AND message=?',(job,summary)).fetchone():
  db.execute('INSERT INTO job_work_notes(job_id,created,message,previous_message,verification) VALUES(?,?,?,?,?)',(job,now.isoformat(),summary,row[2],'코드 검사 완료. 승강기 문 최종 화면 확인 미완료.'))
 db.execute('UPDATE jobs SET message=? WHERE id=?',(summary,job))
 print(json.dumps(dict(job=job,message=db.execute('SELECT message FROM jobs WHERE id=?',(job,)).fetchone()[0]),ensure_ascii=True))
