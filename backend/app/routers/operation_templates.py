from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.models.user import User
from app.schemas import OperationTemplateResponse
from app.services.operation_templates import get_operation_template, list_operation_templates


router = APIRouter(prefix="/operation-templates", tags=["operation-templates"])


@router.get("", response_model=List[OperationTemplateResponse])
def list_templates(
    insertable_only: bool = True,
    current_user: User = Depends(get_current_user),
):
    del current_user
    return [
        OperationTemplateResponse.model_validate(template)
        for template in list_operation_templates(insertable_only=insertable_only)
    ]


@router.get("/{template_id}", response_model=OperationTemplateResponse)
def get_template(
    template_id: str,
    current_user: User = Depends(get_current_user),
):
    del current_user
    try:
        return OperationTemplateResponse.model_validate(get_operation_template(template_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
