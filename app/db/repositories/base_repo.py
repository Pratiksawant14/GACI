"""
Generic Base Repository.
Provides standard CRUD and querying operations for SQLAlchemy models.
"""

import uuid
from typing import Generic, TypeVar, Type, Optional, List
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.base import UUIDModel

ModelType = TypeVar("ModelType", bound=UUIDModel)


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], session: Session):
        self.model = model
        self.session = session

    def get_by_id(self, entity_id: uuid.UUID) -> Optional[ModelType]:
        return self.session.get(self.model, entity_id)

    def get_all(self, limit: int = 100, offset: int = 0) -> List[ModelType]:
        statement = select(self.model).limit(limit).offset(offset)
        return list(self.session.scalars(statement).all())

    def create(self, entity: ModelType) -> ModelType:
        self.session.add(entity)
        self.session.flush()
        return entity

    def update(self, entity: ModelType) -> ModelType:
        self.session.merge(entity)
        self.session.flush()
        return entity

    def delete(self, entity_id: uuid.UUID) -> bool:
        entity = self.get_by_id(entity_id)
        if entity:
            self.session.delete(entity)
            self.session.flush()
            return True
        return False
