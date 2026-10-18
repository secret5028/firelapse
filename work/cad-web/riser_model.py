"""Connect registered riser anchors. Missing evidence never means nearest-node guessing."""
import math

def connect_risers(anchors, node, edge, tolerance=.5):
    issues=[]
    groups={}
    for a in anchors:
        if not a.get('riserId') or not a.get('sourcePage'):
            issues.append('입상관 식별자 또는 원본 위치 근거 누락');continue
        groups.setdefault((a.get('building'),a.get('system'),a['riserId']),[]).append(a)
    for key, entries in groups.items():
        entries.sort(key=lambda a:a['position'][1])
        if len(entries)<2:
            issues.append(str(key)+': 연결할 다른 층 입상 위치 누락');continue
        if len({a['floor'] for a in entries})!=len(entries):
            issues.append(str(key)+': 같은 층 입상 후보 중복');continue
        x=sum(a['position'][0] for a in entries)/len(entries)
        z=sum(a['position'][2] for a in entries)/len(entries)
        if any(math.hypot(a['position'][0]-x,a['position'][2]-z)>tolerance for a in entries):
            issues.append(str(key)+': 층간 좌표 오차 초과, 통리심 정합 필요');continue
        ends=[]
        for a in entries:
            q=(x,a['position'][1],z)
            anchor=node(q,a['floor']);anchor.update(name=a['riserId']+' 입상관',riserId=a['riserId'],sourcePage=a['sourcePage'])
            feed=a['feedNode'];elbow=node((x,q[1],feed['z']),a['floor'])
            edge(feed,elbow,a.get('nominalMm'),'도면 입상 후보에 대한 수평 연결 · 정합 근사')
            edge(elbow,anchor,a.get('nominalMm'),'도면 입상 후보에 대한 수평 연결 · 정합 근사')
            ends.append(anchor)
        for a,b in zip(ends,ends[1:]):
            edge(a,b,entries[0].get('nominalMm'),'도면 입상 후보 기반 수직 연결 · 층고 근사')
    return issues
