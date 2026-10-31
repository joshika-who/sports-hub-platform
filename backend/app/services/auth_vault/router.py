from typing import List
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas import (
    DeviceTokenRequest,
    DocumentResponse,
    ProfileMetrics,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.security import get_current_user, require_role
from app.services.auth_vault.service import (
    authenticate_user,
    list_vault_documents,
    register_user,
    save_vault_document,
    update_device_token,
    update_user_metrics,
    verify_vault_document,
)
from app.services.notifications.dispatcher import NotificationDispatcher

auth_router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])
vault_router = APIRouter(prefix="/api/v1/vault", tags=["Document Vault"])


@auth_router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegisterRequest, db: Session = Depends(get_db)):
    return register_user(db, payload)


@auth_router.post("/login", response_model=TokenResponse)
def login(payload: UserLoginRequest, db: Session = Depends(get_db)):
    return authenticate_user(db, payload)


@auth_router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


@auth_router.put("/me/metrics", response_model=UserResponse)
def put_metrics(
    payload: ProfileMetrics,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    updated = update_user_metrics(db, current_user, payload)
    return UserResponse.model_validate(updated)


@auth_router.put("/me/device-token", response_model=UserResponse)
def put_device_token(
    payload: DeviceTokenRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    updated = update_device_token(db, current_user, payload.device_token)
    return UserResponse.model_validate(updated)


@vault_router.post("/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    doc_type: str = Form(..., description="Document type: ID | MEDICAL | WAIVER"),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return await save_vault_document(db, current_user, doc_type, file)


@vault_router.get("/documents", response_model=List[DocumentResponse])
def get_documents(
    all_users: bool = Query(False, description="Organizers can pass true to view all uploaded documents"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_vault_documents(db, current_user, all_users=all_users)


@vault_router.post("/documents/{doc_id}/verify", response_model=DocumentResponse)
def verify_document(
    doc_id: str,
    organizer: User = Depends(require_role("organizer")),
    db: Session = Depends(get_db),
):
    doc_resp = verify_vault_document(db, doc_id)
    NotificationDispatcher.dispatch(
        db=db,
        user_id=doc_resp.user_id,
        title="Document Verified",
        body=f"Your {doc_resp.doc_type} document has been verified by organizer {organizer.name}.",
        kind="DOCUMENT_VERIFIED",
    )
    return doc_resp

