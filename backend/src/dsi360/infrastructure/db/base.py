"""Accès PostgreSQL : moteur async et fabrique de sessions (SQLAlchemy 2 + asyncpg)."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from dsi360.config import get_settings

_engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    """Moteur async unique, réglé pour un serveur qui tombe souvent (cf. contexte AFG).

    - ``pool_pre_ping`` : teste la connexion avant usage — une base redémarrée ne renvoie pas une
      connexion morte à la première requête.
    - ``pool_recycle`` : jette les connexions de plus de 30 min (coupures réseau, redémarrages).
    - ``timeout`` / ``command_timeout`` / ``statement_timeout`` : rien ne pend indéfiniment. Une
      requête qui traîne est tuée à temps, sinon les connexions s'accumulent et l'app tombe avec
      la base. C'est la protection la plus importante face à un serveur lent ou saturé.
    - pool borné : on n'ouvre jamais plus de connexions que la base ne peut en tenir.
    """
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            get_settings().database_url,
            pool_pre_ping=True,
            pool_recycle=1800,
            pool_size=10,
            max_overflow=10,
            pool_timeout=10,
            connect_args={
                "timeout": 10,
                "command_timeout": 30,
                "server_settings": {
                    "statement_timeout": "30000",
                    "application_name": "dsi360",
                },
            },
        )
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def session_scope() -> AsyncIterator[AsyncSession]:
    """Dépendance FastAPI : une session par requête."""
    async with get_sessionmaker()() as session:
        yield session
