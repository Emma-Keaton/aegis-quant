"""Public app configuration — non-sensitive settings exposed to the frontend."""

import logging

from fastapi import APIRouter

from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["config"])


@router.get("/api/config")
async def get_config():
    """Return public app config. Secrets are stripped."""
    s = get_settings()
    return {
        "status": "ok",
        "app": {
            "name": s.APP_NAME,
            "version": s.APP_VERSION,
            "environment": s.ENVIRONMENT,
        },
        "walletConnect": {
            "projectId": s.WALLET_CONNECT_PROJECT_ID or None,
        },
        "frontendUrl": s.APP_URL or None,
        "grafanaUrl": s.GRAFANA_URL or None,
        "prometheusUrl": f"{s.API_PUBLIC_URL}/metrics" if s.API_PUBLIC_URL else None,
        "kronosUrl": s.KRONOS_SERVICE_URL or None,
    }
