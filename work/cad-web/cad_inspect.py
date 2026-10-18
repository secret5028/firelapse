import ezdxf,collections
for i in range(1,9):
 d=ezdxf.readfile(f'work/cad-input/{i}.dxf');m=d.modelspace()
 print('\nFILE',i,'entities',len(m));print(collections.Counter(e.dxf.layer for e in m).most_common(16))
 print('TEXT',[(e.dxf.text if e.dxftype()=='TEXT' else e.plain_text()) for e in m if e.dxftype() in ('TEXT','MTEXT')][:100])
 print('XREF',[(b.name,b.block.dxf.xref_path) for b in d.blocks if b.block.dxf.flags & 4])
