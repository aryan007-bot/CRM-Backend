import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class EnvironmentResponse(BaseModel):
    id: uuid.UUID
    name: str
    environment_type: str
    status: str
    version: str
    region: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeploymentCreate(BaseModel):
    environment_id: uuid.UUID
    version: str
    commit_sha: str


class DeploymentRollbackRequest(BaseModel):
    target_version: Optional[str] = None


class DeploymentResponse(BaseModel):
    id: uuid.UUID
    scope: str
    environment_id: uuid.UUID
    version: str
    commit_sha: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    deployed_by: Optional[uuid.UUID] = None
    migration_status: str
    health_status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
