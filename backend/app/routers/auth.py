from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    generate_reset_token,
    hash_password,
    verify_password,
)
from app.deps import get_current_user, log_audit

router = APIRouter(prefix="/auth", tags=["auth"])

#: The only role a public, unauthenticated caller can ever be granted.
SELF_REGISTRATION_ROLE = "patient"


def _auth_user(u: models.User) -> schemas.AuthUser:
    return schemas.AuthUser(
        id=u.id, name=u.name, email=u.email, role=u.role, title=u.title,
        hospital=u.hospital, avatar_url=u.avatar_url,
    )


@router.post("/login", response_model=schemas.AuthSession)
def login(payload: schemas.Credentials, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token, expires_at = create_access_token(user.id, user.role)
    user.last_active = datetime.now(timezone.utc).isoformat()
    db.commit()
    log_audit(db, actor=user.email, action="login", target="auth", actor_role=user.role)
    return schemas.AuthSession(user=_auth_user(user), access_token=token, expires_at=expires_at.isoformat())


@router.post("/register", response_model=schemas.MutationResult[schemas.AuthUser])
def register(payload: schemas.RegisterPayload, db: Session = Depends(get_db)):
    """Public self-registration. Always creates a `patient` account.

    `payload.role` is accepted for wire-compatibility with the existing signup
    form but is deliberately ignored: honoring it would let any anonymous caller
    mint themselves a `doctor`/`admin` account and read every patient record.
    Privileged accounts are created by an admin via `POST /admin/users`.
    """
    if db.query(models.User).filter(models.User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = models.User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=SELF_REGISTRATION_ROLE,
        hospital=payload.hospital,
        specialization=payload.specialization,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    after = {"email": user.email, "granted_role": user.role}
    if payload.role != SELF_REGISTRATION_ROLE:
        # Recorded so an escalation attempt is visible in the audit trail.
        after["requested_role"] = payload.role
    log_audit(db, actor=user.email, action="register", target="auth",
              actor_role=user.role, after=after)
    return schemas.MutationResult(ok=True, data=_auth_user(user), message="Account created")


@router.post("/logout", response_model=schemas.MutationResult)
def logout(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    log_audit(db, actor=user.email, action="logout", target="auth", actor_role=user.role)
    return schemas.MutationResult(ok=True, message="Logged out")


@router.post("/forgot-password", response_model=schemas.MutationResult)
def forgot_password(payload: schemas.ForgotPasswordPayload, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if user:
        token = generate_reset_token()
        db.add(models.PasswordResetToken(
            user_id=user.id, token=token,
            expires_at=datetime.utcnow() + timedelta(hours=1),
        ))
        db.commit()
        # No transactional email provider is wired up yet; the token is
        # deliberately not leaked to the response outside of dev mode.
        from app.core.config import get_settings
        if get_settings().environment == "development":
            return schemas.MutationResult(
                ok=True,
                message="Reset token generated (dev mode — shown because no email provider is configured)",
                data={"resetToken": token},
            )
    return schemas.MutationResult(ok=True, message="If that email exists, a reset link has been sent")


@router.post("/reset-password", response_model=schemas.MutationResult)
def reset_password(payload: schemas.ResetPasswordPayload, db: Session = Depends(get_db)):
    record = (
        db.query(models.PasswordResetToken)
        .filter(models.PasswordResetToken.token == payload.token, models.PasswordResetToken.used.is_(False))
        .first()
    )
    if not record or record.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Reset token is invalid or has expired")
    user = db.get(models.User, record.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="Reset token is invalid or has expired")
    user.password_hash = hash_password(payload.password)
    record.used = True
    db.commit()
    log_audit(db, actor=user.email, action="reset_password", target="auth", actor_role=user.role)
    return schemas.MutationResult(ok=True, message="Password updated")


@router.get("/me", response_model=schemas.AuthUser)
def me(user: models.User = Depends(get_current_user)):
    return _auth_user(user)


@router.patch("/me", response_model=schemas.AuthUser)
def update_me(
    payload: schemas.ProfileUpdatePayload,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    for field in ("name", "title", "hospital", "avatar_url"):
        value = getattr(payload, field)
        if value is not None:
            setattr(user, field, value)
    db.commit()
    db.refresh(user)
    log_audit(db, actor=user.email, action="update_profile", target="auth", actor_role=user.role)
    return _auth_user(user)


@router.post("/change-password", response_model=schemas.MutationResult)
def change_password(
    payload: schemas.ChangePasswordPayload,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    log_audit(db, actor=user.email, action="change_password", target="auth", actor_role=user.role)
    return schemas.MutationResult(ok=True, message="Password updated")
