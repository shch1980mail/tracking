import structlog

from services.gps_service import refresh_all

log = structlog.get_logger()

def start(maker, minutes: int):
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
    except ImportError:
        log.warning("apscheduler_unavailable")
        return None

    async def job():
        async with maker() as s:
            log.info("gps_batch", **await refresh_all(s))

    sch = AsyncIOScheduler()
    sch.add_job(job, "interval", minutes=minutes, max_instances=1, coalesce=True)
    sch.start()
    return sch
