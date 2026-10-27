"""Compare same-browser building/openings captures; does not run a simulation."""
import json
from pathlib import Path
from PIL import Image, ImageChops

out = Path(__file__).resolve().parents[2] / 'simulation/results/ui_refactor_stage3_openings_20261027'
rows = []
for view in ('front', 'back', 'top'):
    a = Image.open(out / f'{view}-baseline.png').convert('RGB')
    b = Image.open(out / f'{view}-layer.png').convert('RGB')
    assert a.size == b.size
    diff = ImageChops.difference(a, b)
    pixels = diff.get_flattened_data() if hasattr(diff, 'get_flattened_data') else diff.getdata()
    changed = sum(pixel != (0, 0, 0) for pixel in pixels)
    rows.append(dict(view=view, changed_pixels=changed, total_pixels=a.width*a.height,
                     max_channel_difference=max(pair[1] for pair in diff.getextrema())))
    diff.save(out / f'{view}-diff.png')
(out / 'capture-comparison.json').write_text(json.dumps(rows, indent=2), encoding='utf-8', newline='\n')
assert not any(row['changed_pixels'] for row in rows), rows
print(json.dumps(rows))
