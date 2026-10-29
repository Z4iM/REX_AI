from typing import Annotated, Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from backend.app.catalog.upload_router import require_catalog_admin
from . import service, store


def identity(x_rex_reviewer: Annotated[str, Header(min_length=2, max_length=120)]):
    reviewer = x_rex_reviewer.strip()
    if len(reviewer) < 2:
        raise HTTPException(422, 'Enter your staff name')
    return reviewer


router = APIRouter(prefix='/api/v1/instructor', tags=['instructor-orchestrator'],
                   dependencies=[Depends(require_catalog_admin)])


class Message(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    message: str = Field(min_length=1, max_length=6000)
    request_id: UUID


class Confirmation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    confirmed: Literal[True]
    reviewed: bool = False


@router.get('/sessions')
def sessions(reviewer: str = Depends(identity)):
    return {'items': store.sessions(reviewer)}


@router.post('/sessions', status_code=201)
def new_session(reviewer: str = Depends(identity)):
    return store.create(reviewer)


@router.get('/sessions/{session_id}')
def session(session_id: UUID, reviewer: str = Depends(identity)):
    return store.get(str(session_id), reviewer)


@router.post('/sessions/{session_id}/messages')
async def message(session_id: UUID, body: Message, request: Request, reviewer: str = Depends(identity)):
    return await service.propose(request.app, request.headers['x-api-key'], str(session_id), reviewer,
                                 str(body.request_id), body.message)


@router.post('/sessions/{session_id}/runs/{run_id}/execute')
async def execute(session_id: UUID, run_id: UUID, body: Confirmation, request: Request,
                  reviewer: str = Depends(identity)):
    return await service.execute(request.app, request.headers['x-api-key'], str(session_id), str(run_id), reviewer, body.reviewed)


@router.post('/sessions/{session_id}/runs/{run_id}/cancel')
def cancel(session_id: UUID, run_id: UUID, reviewer: str = Depends(identity)):
    record = store.run(str(session_id), str(run_id), reviewer)
    if record['state'] != 'pending':
        raise HTTPException(409, 'Only pending actions can be cancelled')
    record.update(state='cancelled', cancelled_by=reviewer)
    return store.update(record, expected='pending')
