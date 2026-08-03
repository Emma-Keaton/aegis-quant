import os, sys
# Add backend implementation directory to this package's search path
_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend", "app"))
# Ensure the backend path is part of the package's __path__ for submodule imports
if _backend_path not in __path__:
    __path__.append(_backend_path)
# Also make sure it's on sys.path for any relative imports
if _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)
