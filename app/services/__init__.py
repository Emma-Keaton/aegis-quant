# Expose backend services package
import os, sys
_backend_services = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend", "app", "services"))
if _backend_services not in __path__:
    __path__.append(_backend_services)
