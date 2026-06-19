"""File de tâches Celery et ordonnanceur (beat). Surveille les échéances SLA périodiquement."""

import asyncio

from celery import Celery

from dsi360.application.notifications import scanner_echeances, scanner_escalades
from dsi360.config import get_settings

_settings = get_settings()

app = Celery("dsi360", broker=_settings.redis_url, backend=_settings.redis_url)
app.conf.timezone = "UTC"
app.conf.beat_schedule = {
    "scan-sla": {"task": "dsi360.scanner_sla", "schedule": 300.0},  # toutes les 5 minutes
    "scan-escalades": {"task": "dsi360.scanner_escalades", "schedule": 300.0},
}


@app.task(name="dsi360.scanner_sla")  # type: ignore[untyped-decorator]
def scanner_sla() -> dict[str, int]:
    """Tâche périodique : crée les notifications d'approche / dépassement de SLA."""
    return asyncio.run(scanner_echeances())


@app.task(name="dsi360.scanner_escalades")  # type: ignore[untyped-decorator]
def scanner_escalades_tache() -> dict[str, int]:
    """Tâche périodique : escalade les tickets P1 non pris en charge dans les délais."""
    return asyncio.run(scanner_escalades())
