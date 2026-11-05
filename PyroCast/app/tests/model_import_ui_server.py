"""Isolated UI fixture server. Never import from production; no real AI calls."""
import importlib.util, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
import model_import, model_library, serve_model_library

root=Path(__file__).resolve().parents[2]/'reviews/new-building-20261105/ui-fixture'
root.mkdir(parents=True,exist_ok=True)
model_import.ROOT=model_library.ROOT=root
model_import.STAGING=root/'data/model-imports'
model_library.REGISTRY=root/'config/model-library.json'
model_library.LIBRARY_URL='http://127.0.0.1:8865'
model_import.atomic_json(model_library.REGISTRY,{'models':[]})
spec=importlib.util.spec_from_file_location('import_test',Path(__file__).with_name('model_import.test.py'))
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
model_import.configured=lambda:True
model_import.interpret=lambda image:module.interpretation()
(root/'1F.png').write_bytes(module.scan_bytes())
ThreadingHTTPServer(('127.0.0.1',8865),serve_model_library.Handler).serve_forever()
