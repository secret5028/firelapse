"""Read source drawing arcs in building coordinates; do not rerun room extraction."""
import argparse,hashlib,json,math,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'simulation/deps'),str(ROOT/'simulation/plot_deps'),str(ROOT/'simulation')]
from cad_connectivity_shared import geometry
from shapely.geometry import LineString,Point
from shapely.strtree import STRtree

def extract(building,drawings,reader,converter,work,render_dir=None):
    sys.path.insert(0,str(reader))
    from cadio import load,units_to_m
    result=[];work.mkdir(parents=True,exist_ok=True)
    for f in building['floors']:
        source=drawings/f['src'];dwg=source.with_suffix('.dwg')
        if not source.exists():
            source=work/Path(f['src']).name
            if not source.exists():
                subprocess.run([str(converter),'-y','-o',str(source),str(dwg)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=180,check=True)
        doc,prims,_=load(str(source));unit=units_to_m(doc,prims)
        scale=f.get('scale',1);shift=f.get('shift',[0,0]);origin=building['origin']
        def xy(p):return [round(p[i]*unit*scale+shift[i]-origin[i],6) for i in (0,1)]
        envelope=geometry(f['slab']);arcs=[];outside=0
        if render_dir is not None:
            from PIL import Image,ImageDraw,ImageFont
            render_dir.mkdir(parents=True,exist_ok=True)
            x0,y0,x1,y1=envelope.bounds;sc=min(2000/max(x1-x0,1),2000/max(y1-y0,1))
            im=Image.new('RGB',(int((x1-x0)*sc)+40,int((y1-y0)*sc)+40),'white');draw=ImageDraw.Draw(im)
            def pixel(q):return (20+(q[0]-x0)*sc,20+(y1-q[1])*sc)
            for primitive in prims:
                pts=[xy(q) for q in primitive.pts]
                if len(pts)<2 or max(q[0] for q in pts)<x0 or min(q[0] for q in pts)>x1 or max(q[1] for q in pts)<y0 or min(q[1] for q in pts)>y1:continue
                draw.line([pixel(q) for q in pts],fill='#197fa0' if primitive.arc else '#555555',width=1)
            for room in f['rooms']:
                point=geometry(room['polys']).representative_point()
                draw.text(pixel((point.x,point.y)),room['id'],fill='#c22c25')
            im.save(render_dir/('source-'+f['name']+'.png'))
        lines=[LineString([xy(p.pts[0]),xy(p.pts[-1])]) for p in prims if p.arc is None and p.kind=='LINE' and len(p.pts)==2]
        tree=STRtree(lines)
        for p in prims:
            if p.arc is None:continue
            cx,cy,r,a0,a1=p.arc;sweep=(a1-a0)%360
            if sweep<=0:continue
            pts=[xy((cx+r*math.cos(math.radians(a0+sweep*i/32)),cy+r*math.sin(math.radians(a0+sweep*i/32)))) for i in range(33)]
            center=xy((cx,cy));inside=envelope.buffer(.02).covers(LineString(pts)) and envelope.buffer(.02).covers(Point(center))
            if not inside:outside+=1;continue
            identity=json.dumps([center,round(r*unit*scale,6),round(a0,6),round(sweep,6)],separators=(',',':'))
            arc_id='ARC_'+hashlib.sha256(identity.encode()).hexdigest()[:12]
            if any(a['id']==arc_id for a in arcs):continue
            support=[]
            for endpoint in (pts[0],pts[-1]):
                radial=LineString([center,endpoint]);found=False
                for i in tree.query(radial.buffer(.03)):
                    ln=lines[i]
                    if abs(ln.length-radial.length)<=.06 and ln.hausdorff_distance(radial)<=.03:
                        found=True;break
                support.append(found)
            arcs.append(dict(id=arc_id,center=center,radius_m=round(r*unit*scale,6),start=pts[0],end=pts[-1],radial_line_support=support,
                sweep_deg=sweep,points=pts,layer=p.layer,entity_kind=p.kind,source=p.source,inside_building=True))
        result.append(dict(floor=f['name'],source=str(dwg if dwg.exists() else source),
            source_sha256=hashlib.sha256((dwg if dwg.exists() else source).read_bytes()).hexdigest(),
            dxf_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),interior_arcs=arcs,exterior_arcs=outside,
            reader_sha256=hashlib.sha256((reader/'cadio.py').read_bytes()).hexdigest()))
        print(f"{f['name']}: interior arcs {len(arcs)}, exterior {outside}",flush=True)
    return dict(rule='user_assumption_all_interior_arcs_are_doors',floors=result)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--building',required=True);p.add_argument('--drawings',type=Path,required=True);p.add_argument('--cad-reader',type=Path,required=True);p.add_argument('--dwg2dxf',type=Path,required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=extract(json.loads(Path(a.building).read_text('utf-8')),a.drawings,a.cad_reader,a.dwg2dxf,a.work)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n','utf-8')
