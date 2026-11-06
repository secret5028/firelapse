"""Building-bound read-only assistant for the existing library viewer."""
import hashlib
from lite_ai_tools import Tools,read


class ModelTools(Tools):
    # Library assistant cannot route legacy write/run proposals to another building.
    names=tuple(n for n in Tools.names if not n.startswith('propose_'))
    def __init__(self,ident):
        import model_simulation as sim
        from model_library import model_path
        row=sim.entry(ident);path=model_path(row)
        self.ident=ident;self._case_cache={}
        self.buildings={ident:dict(id=ident,label=row['label'],path=path,sha=hashlib.sha256(path.read_bytes()).hexdigest())}
    def cases(self,key):
        meta,_=self.building(key)
        import model_operation,model_mc,fixed_calculation
        out={p.name:p/'playback.json' for p,_ in model_operation.jobs(self.ident)}
        for row in model_mc.cases(self.ident):out[row['id']]=model_mc.case_folder(self.ident,row['id'])/'playback.json'
        for folder in fixed_calculation.paths(meta['sha']):
            if read(folder/'status.json',{}).get('state')=='complete':out[folder.name]=folder/'playback.json'
        return out
    def case(self,a):
        self.building(a['building'])
        import model_operation
        return model_operation.playback(self.ident,a['case'])
    def get_building(self,a):
        # Parent enriches current geometry with the selected case's saved input.
        result=super().get_building(a)
        return result
    def get_ranking(self,a):
        self.building(a['building'])
        return dict(first=[],second=[],status='미평가 · 저장 결과 브리핑')


def service_for_hash(sha):
    from model_library import entries,model_path
    for row in entries():
        path=model_path(row)
        if row.get('execution_mode')=='library_lite' and path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==sha:
            return ModelTools(row['id'])
    return Tools()
