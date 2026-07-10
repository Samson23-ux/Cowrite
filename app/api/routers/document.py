from uuid import UUID
from fastapi import APIRouter, Request


from app.api.schemas.response import SuccessResponse
from app.deps import DocumentServiceDep, CurrentActiveUser
from app.api.schemas.document import DocumentResponse, DocumentCreate

router = APIRouter()


@router.post(
    "/documents",
    status_code=201,
    response_model=SuccessResponse[DocumentResponse],
    description="Create a document",
)
async def create_document(
    request: Request,
    curr_user: CurrentActiveUser,
    document_payload: DocumentCreate,
    document_service: DocumentServiceDep,
):
    document: DocumentResponse = await document_service.create_document(
        curr_user, document_payload
    )
    return SuccessResponse(message="Document created successfully!", data=document)


@router.get(
    "/documents/{id}",
    status_code=200,
    response_model=SuccessResponse[DocumentResponse],
    description="Get a document by id",
)
async def get_document(
    id: UUID,
    request: Request,
    curr_user: CurrentActiveUser,
    document_service: DocumentServiceDep,
):
    document: DocumentResponse = await document_service.get_document(curr_user, id)
    return SuccessResponse(message="Document retrieved successfully!", data=document)
