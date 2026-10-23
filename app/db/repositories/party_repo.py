"""
Party and Account Repositories.
Implements data access for Business, Customer, Supplier, and BankAccount entities.
"""

import uuid
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.repositories.base_repo import BaseRepository
from app.models.entities import Business, Customer, Supplier, BankAccount


class BusinessRepository(BaseRepository[Business]):
    def __init__(self, session: Session):
        super().__init__(Business, session)

    def get_first(self) -> Optional[Business]:
        return self.session.scalars(select(Business).limit(1)).first()


class CustomerRepository(BaseRepository[Customer]):
    def __init__(self, session: Session):
        super().__init__(Customer, session)

    def get_by_name(self, business_id: uuid.UUID, name: str) -> Optional[Customer]:
        stmt = select(Customer).where(Customer.business_id == business_id, Customer.name == name)
        return self.session.scalars(stmt).first()

    def get_by_business(self, business_id: uuid.UUID) -> List[Customer]:
        stmt = select(Customer).where(Customer.business_id == business_id)
        return list(self.session.scalars(stmt).all())


class SupplierRepository(BaseRepository[Supplier]):
    def __init__(self, session: Session):
        super().__init__(Supplier, session)

    def get_by_name(self, business_id: uuid.UUID, name: str) -> Optional[Supplier]:
        stmt = select(Supplier).where(Supplier.business_id == business_id, Supplier.name == name)
        return self.session.scalars(stmt).first()

    def get_by_business(self, business_id: uuid.UUID) -> List[Supplier]:
        stmt = select(Supplier).where(Supplier.business_id == business_id)
        return list(self.session.scalars(stmt).all())


class BankAccountRepository(BaseRepository[BankAccount]):
    def __init__(self, session: Session):
        super().__init__(BankAccount, session)

    def get_by_business(self, business_id: uuid.UUID) -> List[BankAccount]:
        stmt = select(BankAccount).where(BankAccount.business_id == business_id)
        return list(self.session.scalars(stmt).all())
