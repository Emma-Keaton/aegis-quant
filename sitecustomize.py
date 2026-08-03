import sys, os, importlib.util
# Ensure project root is first in sys.path
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# Pre‑load our local `app` package to shadow any installed one.
_app_dir = os.path.join(project_root, "app")
_app_init = os.path.join(_app_dir, "__init__.py")
if os.path.exists(_app_init):
    spec = importlib.util.spec_from_file_location("app", _app_init)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules["app"] = module

