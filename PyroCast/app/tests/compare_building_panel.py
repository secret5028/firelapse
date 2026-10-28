"""Compare controlled WebGL captures, excluding the entire risk layer on both sides."""
import json
from pathlib import Path
from PIL import Image, ImageChops

folder = Path(__file__).resolve().parents[2] / 'simulation/results/ui_refactor_stage4_item5_20261028'
rows = []
for scene in ['S09-1800', 'S09-1420', 'S06-890', 'all-core']:
    before = Image.open(folder / f'{scene}-stage3-3d.png').convert('RGB')
    after = Image.open(folder / f'{scene}-modern-3d.png').convert('RGB')
    assert before.size == after.size == (1000, 600)
    delta = ImageChops.difference(before, after)
    changed = sum(any(p) for p in delta.getdata())
    rows.append(dict(scene=scene, changed_pixels=changed, bbox=delta.getbbox(), size=list(before.size)))
(folder / 'pixel-comparison.json').write_text(json.dumps(rows, indent=2) + '\n', encoding='utf-8', newline='\n')
print(json.dumps(rows))
assert all(r['changed_pixels'] == 0 for r in rows), 'Unexpected 3D rendering difference'
