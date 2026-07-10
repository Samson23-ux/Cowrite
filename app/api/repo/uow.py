from sqlalchemy.ext.asyncio import AsyncSession

"""
Share a session across different repo to ensure atomicity
"""


class UnitOfWorkRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def flush(self):
        await self._session.flush()

    async def refresh(self, model):
        await self._session.refresh(model)

    async def commit(self):
        await self._session.commit()

    async def rollback(self):
        await self._session.rollback()
