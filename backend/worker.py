"""Aegis Quant worker process — runs trading engines (Engine A + Engine B).

Deployed as the Render 'worker' service. Keeps an asyncio loop alive with a
periodic heartbeat so Render doesn't idle it out. Set AEGIS_ROLE=worker (or all)
in this service's environment.
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone

from app.config import get_settings
from app.database import init_db, close_db

logger = logging.getLogger("aegis-worker")


async def heartbeat_loop() -> None:
    while True:
        logger.info("[WORKER] heartbeat %s", datetime.now(timezone.utc).isoformat())
        await asyncio.sleep(300)


async def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    logger.info("[WORKER] Aegis Quant worker starting (role=%s)", settings.AEGIS_ROLE)

    await init_db()

    from app.engines.engine_scheduler import start_engines, stop_engines
    await start_engines()

    try:
        await heartbeat_loop()
    finally:
        await stop_engines()
        await close_db()
        logger.info("[WORKER] Aegis Quant worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
