from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ForbiddenError
from app.core.security import decode_access_token
from app.models import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.get(User, payload.get("sub"))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_roles(*roles: str):
    def _check(user: User = Depends(get_current_user)) -> User:
        if roles and user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return _check


def assert_patient_readable(patient, user: User) -> None:
    """A `patient`-role user may only access data tied to their own record.

    The single implementation of this rule. It previously existed in four
    places (here plus `PatientService`, `TwinService` and ad hoc router checks),
    which meant a change to the ownership definition could be applied to some
    endpoints and not others.

    Raises `ForbiddenError` rather than `HTTPException` so services can call it
    without importing FastAPI; `main.py` maps it to 403 either way.
    """
    if user.role == "patient" and patient.email != user.email:
        raise ForbiddenError("Not authorized to access this patient")


def log_audit(
    db: Session,
    actor: str,
    action: str,
    target: str,
    actor_role: str = "",
    before: dict | None = None,
    after: dict | None = None,
    ip: str = "internal",
) -> None:
    from app.models import AuditLogEntry

    db.add(AuditLogEntry(
        actor=actor, actor_role=actor_role, action=action, target=target,
        before=before, after=after, ip=ip,
    ))
    db.commit()
