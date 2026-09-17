"""Generic CRUD router factory for the straightforward entities.

Optional eng_of_obj / eng_of_payload resolvers let the factory enforce
agent-token engagement scope (humans/unscoped tokens are unaffected)."""
from datetime import datetime
from typing import Callable, Optional, Type

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlmodel import Session, select

from .authz import agent_scope, assert_in_scope
from .db import get_session
from .deps import Principal, current_reader, current_writer


def make_crud_router(*, model: Type, create_schema: Type[BaseModel],
                     update_schema: Type[BaseModel], prefix: str, tag: str,
                     filter_fields: Optional[list[str]] = None,
                     set_author: bool = False,
                     eng_of_obj: Optional[Callable[[Session, object], Optional[int]]] = None,
                     eng_of_payload: Optional[Callable[[Session, dict], Optional[int]]] = None) -> APIRouter:
    router = APIRouter(prefix=f"/{prefix}", tags=[tag])
    filter_fields = filter_fields or []

    def _guard_obj(session, p, obj):
        if eng_of_obj and agent_scope(p) is not None:
            assert_in_scope(p, eng_of_obj(session, obj))

    @router.get("")
    def list_items(request: Request, limit: int = 200, offset: int = 0,
                   session: Session = Depends(get_session),
                   p: Principal = Depends(current_reader)):
        stmt = select(model)
        for f in filter_fields:
            val = request.query_params.get(f)
            if val is not None:
                col = getattr(model, f)
                stmt = stmt.where(col == (int(val) if val.lstrip("-").isdigit() else val))
        stmt = stmt.order_by(model.id.desc()).offset(offset).limit(min(limit, 1000))
        rows = session.exec(stmt).all()
        if eng_of_obj and agent_scope(p) is not None:
            scope = agent_scope(p)
            rows = [o for o in rows if eng_of_obj(session, o) == scope]
        return rows

    @router.post("", status_code=status.HTTP_201_CREATED)
    def create_item(payload: create_schema, session: Session = Depends(get_session),
                    p: Principal = Depends(current_writer)):
        data = payload.model_dump()
        if eng_of_payload and agent_scope(p) is not None:
            assert_in_scope(p, eng_of_payload(session, data))
        if set_author:
            data["author"] = p.actor
        obj = model(**data)
        session.add(obj); session.commit(); session.refresh(obj)
        return obj

    @router.get("/{item_id}")
    def get_item(item_id: int, session: Session = Depends(get_session),
                 p: Principal = Depends(current_reader)):
        obj = session.get(model, item_id)
        if not obj:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"{tag} not found")
        _guard_obj(session, p, obj)
        return obj

    @router.patch("/{item_id}")
    def update_item(item_id: int, payload: update_schema,
                    session: Session = Depends(get_session),
                    p: Principal = Depends(current_writer)):
        obj = session.get(model, item_id)
        if not obj:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"{tag} not found")
        _guard_obj(session, p, obj)
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(obj, k, v)
        if hasattr(obj, "updated_at"):
            obj.updated_at = datetime.utcnow()
        session.add(obj); session.commit(); session.refresh(obj)
        return obj

    @router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_item(item_id: int, session: Session = Depends(get_session),
                    p: Principal = Depends(current_writer)):
        obj = session.get(model, item_id)
        if not obj:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"{tag} not found")
        _guard_obj(session, p, obj)
        session.delete(obj); session.commit()

    return router
