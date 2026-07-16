"""APScheduler 싱글턴 (설계서 §9 — 시나리오/타이머 트리거).

앱 lifespan에서 start/shutdown되고, scenario·timer 도메인이 잡을 등록한다.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler(timezone="Asia/Seoul")


def start_scheduler() -> None:
    if not scheduler.running:
        scheduler.start()


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
