from redis import Redis
from redis.retry import Retry
from redis.connection import ConnectionPool
from sqlalchemy import Engine, create_engine
from redis.backoff import ExponentialBackoff
from sqlalchemy.orm import Session, sessionmaker
from redis.exceptions import TimeoutError, ConnectionError

from app.core.config import get_settings

db_engine: Engine = create_engine(
    url=get_settings().SYNC_DB_URL,
    pool_size=10,
    pool_timeout=10.0,
    pool_pre_ping=True,
    max_overflow=5,
    connect_args={"options": "-c timezone=utc"},
)

db_session: Session = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

redis_pool = ConnectionPool.from_url(
    get_settings().REDIS_URL,
    decode_responses=True,
    max_connections=50,
    retry=Retry(ExponentialBackoff(cap=1.0, base=0.1), retries=5),
    retry_on_error=(TimeoutError, ConnectionError),
    retry_on_timeout=True,
)


def get_db_session() -> Session:
    return db_session()


def get_redis_client() -> Redis:
    redis = Redis(connection_pool=redis_pool)
    return redis
