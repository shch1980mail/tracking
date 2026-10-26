from models.audit import AuditLog

async def audit(session, request, action: str, entity: str, entity_id=None, payload: dict | None = None) -> None:
    st = request.state
    session.add(AuditLog(user_id=getattr(st, "user_id", None), login=getattr(st, "user", None), action=action,
                         entity=entity, entity_id=None if entity_id is None else str(entity_id), payload=payload))
    await session.commit()
