from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email:    str = Field(..., min_length=5, max_length=120)
    password: str = Field(..., min_length=6)

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    username:     str
    email:        str

class CheckRequest(BaseModel):
    news_text: str = Field(..., min_length=10, max_length=8000)
    api_key:   Optional[str] = Field(default=None)   # Anthropic key (optional)

class MLSignals(BaseModel):
    boost: float

class MLResult(BaseModel):
    verdict:    str
    confidence: float
    fake_prob:  float
    real_prob:  float
    model:      str
    signals:    MLSignals

class AIResult(BaseModel):
    verdict:    str
    confidence: int
    summary:    str

class CheckResponse(BaseModel):
    id:               int
    ml:               MLResult
    ai:               AIResult
    final_verdict:    str
    final_score:      float
    checked_at:       datetime
