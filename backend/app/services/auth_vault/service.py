import os
import uuid
from typing import List
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Document, User
from app.schemas import (
    DocumentResponse,
    ProfileMetrics,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.security import create_access_token, hash_password, verify_password

VALID_DOC_TYPES = {"ID", "MEDICAL", "WAIVER"}


def register_user(db: Session, payload: UserRegisterRequest) -> TokenResponse:
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists.",
        )

    metrics = (
        payload.profile_metrics.model_dump()
        if payload.profile_metrics
        else {"height": 175, "weight": 70, "age": 22, "fitness_score": 80}
    )

    user = User(
        name=payload.name.strip(),
        email=payload.email.lower().strip(),
        password_hash=hash_password(payload.password),
        role=payload.role,
        profile_metrics=metrics,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=user.id, role=user.role)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


def authenticate_user(db: Session, payload: UserLoginRequest) -> TokenResponse:
    user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    token = create_access_token(subject=user.id, role=user.role)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


def update_user_metrics(db: Session, user: User, metrics: ProfileMetrics) -> User:
    current = dict(user.profile_metrics or {})
    current.update(metrics.model_dump(exclude_none=True))
    user.profile_metrics = current
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_device_token(db: Session, user: User, device_token: str) -> User:
    user.device_token = device_token.strip()
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


async def save_vault_document(
    db: Session,
    user: User,
    doc_type: str,
    upload_file: UploadFile,
) -> DocumentResponse:
    normalized_type = doc_type.strip().upper()
    if normalized_type not in VALID_DOC_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid doc_type '{doc_type}'. Must be one of: {', '.join(sorted(VALID_DOC_TYPES))}",
        )

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    orig_name = upload_file.filename or "document.bin"
    _, ext = os.path.splitext(orig_name)
    safe_ext = ext[:10] if ext else ".pdf"
    random_filename = f"{normalized_type.lower()}_{uuid.uuid4().hex}{safe_ext}"
    dest_path = os.path.join(settings.UPLOAD_DIR, random_filename)

    content = await upload_file.read()
    with open(dest_path, "wb") as f:
        f.write(content)

    storage_ref = f"uploads/{random_filename}"

    doc = Document(
        user_id=user.id,
        doc_type=normalized_type,
        storage_url=storage_ref,
        is_verified=False,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return DocumentResponse(
        id=doc.id,
        user_id=doc.user_id,
        user_name=user.name,
        user_email=user.email,
        doc_type=doc.doc_type,
        storage_url=doc.storage_url,
        is_verified=doc.is_verified,
        uploaded_at=doc.uploaded_at,
    )


def list_vault_documents(db: Session, user: User, all_users: bool = False) -> List[DocumentResponse]:
    query = db.query(Document)
    if not (user.role == "organizer" and all_users):
        query = query.filter(Document.user_id == user.id)

    docs = query.order_by(Document.uploaded_at.desc()).all()
    user_map = {
        u.id: u
        for u in db.query(User).filter(User.id.in_({d.user_id for d in docs})).all()
    } if docs else {}

    result: List[DocumentResponse] = []
    for d in docs:
        owner = user_map.get(d.user_id)
        result.append(
            DocumentResponse(
                id=d.id,
                user_id=d.user_id,
                user_name=owner.name if owner else None,
                user_email=owner.email if owner else None,
                doc_type=d.doc_type,
                storage_url=d.storage_url,
                is_verified=d.is_verified,
                uploaded_at=d.uploaded_at,
            )
        )
    return result


def verify_vault_document(db: Session, doc_id: str) -> DocumentResponse:
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    doc.is_verified = True
    db.add(doc)
    db.commit()
    db.refresh(doc)

    owner = db.query(User).filter(User.id == doc.user_id).first()
    return DocumentResponse(
        id=doc.id,
        user_id=doc.user_id,
        user_name=owner.name if owner else None,
        user_email=owner.email if owner else None,
        doc_type=doc.doc_type,
        storage_url=doc.storage_url,
        is_verified=doc.is_verified,
        uploaded_at=doc.uploaded_at,
    )

