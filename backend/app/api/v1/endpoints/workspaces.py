import re
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership
from app.schemas.workspace import WorkspaceCreate, WorkspaceResponse, WorkspaceMemberAdd
from app.api.deps import get_current_user, get_current_workspace, get_workspace_admin

router = APIRouter()


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[\s_-]+", "-", text)


@router.get("", response_model=List[WorkspaceResponse])
def list_user_workspaces(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    memberships = (
        db.query(WorkspaceMembership)
        .filter(WorkspaceMembership.user_id == current_user.id)
        .all()
    )
    results = []
    for m in memberships:
        ws = m.workspace
        resp = WorkspaceResponse(
            id=ws.id,
            name=ws.name,
            slug=ws.slug,
            role=m.role,
            created_at=ws.created_at,
            updated_at=ws.updated_at,
        )
        results.append(resp)
    return results


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
def create_workspace(
    ws_in: WorkspaceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    base_slug = ws_in.slug or slugify(ws_in.name)
    slug = base_slug
    counter = 1
    while db.query(Workspace).filter(Workspace.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    workspace = Workspace(name=ws_in.name, slug=slug)
    db.add(workspace)
    db.flush()

    membership = WorkspaceMembership(
        user_id=current_user.id,
        workspace_id=workspace.id,
        role="owner",
    )
    db.add(membership)
    db.commit()
    db.refresh(workspace)

    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        slug=workspace.slug,
        role="owner",
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
    )


@router.post("/members", status_code=status.HTTP_201_CREATED)
def add_workspace_member(
    member_in: WorkspaceMemberAdd,
    db: Session = Depends(get_db),
    current_workspace: Workspace = Depends(get_current_workspace),
    admin_membership: WorkspaceMembership = Depends(get_workspace_admin),
):
    target_user = db.query(User).filter(User.email == member_in.user_email).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with email {member_in.user_email} not found.",
        )

    existing = (
        db.query(WorkspaceMembership)
        .filter(
            WorkspaceMembership.workspace_id == current_workspace.id,
            WorkspaceMembership.user_id == target_user.id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this workspace.",
        )

    new_member = WorkspaceMembership(
        user_id=target_user.id,
        workspace_id=current_workspace.id,
        role=member_in.role,
    )
    db.add(new_member)
    db.commit()
    return {"message": f"User {member_in.user_email} successfully added as {member_in.role}."}
