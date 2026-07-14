from celery.beat import crontab

task_acks_late = True
worker_concurrency = 100
timezone = "Africa/Lagos"
reject_on_worker_lost = True
worker_prefetch_multiplier = 1


beat_schedule = {
    "typing_event": {
        "task": "app.worker.tasks.event.expired_typing_event",
        "schedule": crontab(minute="*"),
    },
    "presence_event": {
        "task": "app.worker.tasks.event.expired_presence_event",
        "schedule": crontab(minute="*"),
    }
}
