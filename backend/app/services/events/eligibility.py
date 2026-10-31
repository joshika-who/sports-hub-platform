from typing import List
from sqlalchemy.orm import Session

from app.models import Document, Event, User
from app.schemas import EligibilityCheckItem, EligibilityResponse


def evaluate_event_eligibility(db: Session, user: User, event: Event) -> EligibilityResponse:
    requirements: List[str] = list(event.mandatory_requirements or [])
    if not requirements:
        return EligibilityResponse(eligible=True, checks=[])

    user_docs = db.query(Document).filter(Document.user_id == user.id).all()
    verified_types = {d.doc_type.upper() for d in user_docs if d.is_verified}
    unverified_types = {d.doc_type.upper() for d in user_docs if not d.is_verified}

    metrics = user.profile_metrics or {}
    user_age = metrics.get("age")

    checks: List[EligibilityCheckItem] = []

    for raw_req in requirements:
        req = str(raw_req).strip().upper()
        if req.startswith("MIN_AGE:"):
            try:
                min_age = int(req.split(":", 1)[1])
            except ValueError:
                min_age = 0

            if user_age is not None and int(user_age) >= min_age:
                checks.append(
                    EligibilityCheckItem(
                        requirement=req,
                        passed=True,
                        message=f"Age requirement met ({user_age} >= {min_age}).",
                    )
                )
            else:
                checks.append(
                    EligibilityCheckItem(
                        requirement=req,
                        passed=False,
                        message=f"Missing requirement {req}: minimum age is {min_age} (your profile age is {user_age or 'unset'}).",
                    )
                )

        elif req in {"ID", "MEDICAL", "WAIVER"}:
            if req in verified_types:
                checks.append(
                    EligibilityCheckItem(
                        requirement=req,
                        passed=True,
                        message=f"Verified {req} document found in Document Vault.",
                    )
                )
            elif req in unverified_types:
                checks.append(
                    EligibilityCheckItem(
                        requirement=req,
                        passed=False,
                        message=f"Missing verified {req} document: uploaded {req} document is still pending organizer verification.",
                    )
                )
            else:
                checks.append(
                    EligibilityCheckItem(
                        requirement=req,
                        passed=False,
                        message=f"Missing mandatory {req} document: please upload and verify your {req} in the Document Vault.",
                    )
                )
        else:
            # Generic fallback for any custom requirement tag
            checks.append(
                EligibilityCheckItem(
                    requirement=req,
                    passed=True,
                    message=f"Requirement {req} acknowledged.",
                )
            )

    all_passed = all(c.passed for c in checks)
    return EligibilityResponse(eligible=all_passed, checks=checks)

