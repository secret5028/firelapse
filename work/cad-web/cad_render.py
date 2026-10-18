import ezdxf
from ezdxf.addons.drawing import RenderContext,Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
import matplotlib.pyplot as plt
for i in [1,2,3,8]:
 d=ezdxf.readfile(f'work/cad-input/{i}.dxf');fig=plt.figure(figsize=(16,11));ax=fig.add_axes([0,0,1,1]);Frontend(RenderContext(d),MatplotlibBackend(ax)).draw_layout(d.modelspace(),finalize=True);fig.savefig(f'work/cad-input/{i}.png',dpi=120);plt.close(fig)
