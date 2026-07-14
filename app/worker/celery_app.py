import sentry_sdk
from celery import Celery
from celery.signals import worker_process_init, worker_process_shutdown

from app.worker import get_redis_client
from app.core.config import get_settings
from app.api.services.event import EventBus

SETTINGS = get_settings()

event_bus = None

sentry_sdk.init(
    dsn=SETTINGS.SENTRY_SDK_DSN,
    enable_logs=True,
    send_default_pii=True,
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
    profile_lifecycle="trace",
)

celery_app = Celery(
    main="celery_app",
    broker=SETTINGS.BROKER_URL,
    backend=SETTINGS.REDIS_URL,
)

celery_app.config_from_object("app.worker.celeryconfig")

@worker_process_init.connect
def on_worker_init(**kwargs):
    global event_bus
    redis = get_redis_client()

    event_bus = EventBus(sync_redis=redis)
    event_bus.sync_psubscribe("__keyspace@0__:typing:*")

@worker_process_shutdown.connect
def on_worker_shutdown(**kwargs):
    event_bus.sync_punsubscribe("__keyspace@0__:typing:*")
    event_bus._sync_pubsub.close()
