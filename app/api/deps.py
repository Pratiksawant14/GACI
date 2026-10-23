"""
API Dependencies and Common Context Resolvers.
Provides database session dependency and active business resolver.
"""

import uuid
from typing import Optional
from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.models.entities import Business


def get_active_business(
    business_id: Optional[uuid.UUID] = Query(None, description="Optional Business UUID. If omitted, uses active business."),
    db: Session = Depends(get_db)
) -> Business:
    """Resolves target business or auto-initializes the default wholesale business entity."""
    if business_id:
        biz = db.get(Business, business_id)
        if not biz:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Business with ID {business_id} not found."
            )
        return biz

    biz = db.scalars(select(Business).order_by(Business.created_at.asc())).first()
    if not biz:
        biz = Business(
            name="Apex Wholesale Distributors",
            currency="INR"
        )
        db.add(biz)
        db.commit()
        db.refresh(biz)
    return biz
