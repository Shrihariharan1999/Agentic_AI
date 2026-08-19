from pydantic import BaseModel, Field

from app.schemas.website import WebsiteMap


class DiscoveryResult(BaseModel):
    website: WebsiteMap
    discovery_complete: bool = False
    limitations: list[str] = Field(default_factory=list)