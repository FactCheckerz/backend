from pydantic import BaseModel,Field

class TextIngestionRequest(BaseModel):
    mode: str = Field(...,pattern="^(general|medical)$")
    text: str = Field(...,min_length=1)

class URLIngestionRequest(BaseModel):
    mode: str = Field(...,pattern="^(general|medical)$")
    url: str = Field(...,min_length=1)
