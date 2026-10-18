from architecture_contract import bind_openings
"""Source-coordinate adapter shared by every preprocessed drawing, no building IDs."""
def model_fields(entities, width, height, source_page):
 px=lambda q:[round(q[0]*width,4),round(q[1]*height,4)]
 shapes=[];rooms=[]
 fire={'sourcePage':source_page,'ceilingOffsetM':.35,'heads':[],'pipes':[],'equipment':[]}
 for e in entities:
  if e['certainty']!='observed':continue
  kind=e['kind'];base={k:e[k] for k in ['id','evidence','label'] if k in e}
  if kind in ['wall','door','window']:
   shapes.append(base|{'type':kind,'a':px(e['points'][0]),'b':px(e['points'][1])}|{k:e[k] for k in ['openingKind','leaves','hinge','swingSide'] if k in e})
  elif kind=='head':fire['heads'].append(px(e['points'][0]))
  elif kind=='pipe':fire['pipes'].append(base|{'points':[px(q) for q in e['points']], 'nominalMm':e.get('diameterMm'),'system':e.get('system','unknown')})
  elif kind in ['inlet','pump','tank','hydrant','extinguisher','alarmValve']:
   fire['equipment'].append(base|{'type':kind,'point':px(e['points'][0])})
  elif kind=='room' and e.get('label'):rooms.append(base|{'name':e['label'],'point':px(e['points'][0])})
 shapes,validation=bind_openings(shapes,tolerance=max(2,min(width,height)*.003))
 result={'architecturalValidation':validation,'shapes':shapes,'roomLabels':rooms,'sourcePage':source_page}
 if any(fire[k] for k in ['heads','pipes','equipment']):result['fireFacilities']=fire
 return result
