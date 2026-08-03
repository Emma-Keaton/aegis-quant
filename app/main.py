# Proxy to the FastAPI application defined in backend/app/main.py
import importlib.util, os, sys
_backend_main = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend", "app", "main.py"))
_spec = importlib.util.spec_from_file_location("backend.app.main", _backend_main)
module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(module)
# Expose the FastAPI app instance
app = module.app
