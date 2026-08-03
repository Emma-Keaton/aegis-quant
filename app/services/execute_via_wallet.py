# Proxy to the actual implementation in backend/app/services/execute_via_wallet.py
import importlib.util, os, sys
_backend_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend", "app", "services", "execute_via_wallet.py"))
_spec = importlib.util.spec_from_file_location("app.services.execute_via_wallet", _backend_file)
module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(module)
# Re-export symbols expected by tests
execute_trade_via_llm = module.execute_trade_via_llm
ExecutionError = module.ExecutionError
