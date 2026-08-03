import importlib.util, os, sys
# Ensure our local `app` package is used for all imports.
_project_root = os.path.abspath(os.path.dirname(__file__))
_app_dir = os.path.join(_project_root, 'app')
_app_init = os.path.join(_app_dir, '__init__.py')
if os.path.exists(_app_init):
    spec = importlib.util.spec_from_file_location('app', _app_init)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules['app'] = module
    # Ensure subpackages can be found
    sys.path.insert(0, _project_root)
