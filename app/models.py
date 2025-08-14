"""
Database models for the IoT Dashboard
"""

from datetime import datetime
from typing import Optional, Union
from sqlmodel import SQLModel, Field
from pydantic import BaseModel, EmailStr


class UserBase(SQLModel):
    """Base user model"""
    email: EmailStr = Field(unique=True, index=True)
    username: str = Field(min_length=3, max_length=50)
    full_name: Optional[str] = None
    is_active: bool = Field(default=True)


class User(UserBase, table=True):
    """User database model"""
    id: Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class UserCreate(BaseModel):
    """User creation model"""
    email: EmailStr
    username: str
    full_name: Optional[str] = None
    password: str


class UserLogin(BaseModel):
    """User login model"""
    email: EmailStr
    password: str


class Token(BaseModel):
    """JWT token model"""
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Token data model following FastAPI tutorial"""
    email: Union[str, None] = None


class DeviceData(BaseModel):
    """Device data model for API responses"""
    dev_eui: str
    name: str
    status: str
    last_seen: str
    message_count: int
    decoded_data: dict
    rssi: Optional[float] = None
    snr: Optional[float] = None


class SwitchCommand(BaseModel):
    """Switch control command model"""
    action: str  # "on" or "off"
    switch: Optional[str] = None  # "switch_1", "switch_2", or None for both


class DeviceState(SQLModel, table=True):
    """Device last known state storage"""
    id: Optional[int] = Field(default=None, primary_key=True)
    device_eui: str = Field(unique=True, index=True)
    device_name: str
    last_seen: datetime = Field(default_factory=datetime.utcnow)
    decoded_data: str = Field(default="{}")  # JSON string of last decoded data
    message_count: int = Field(default=0)
    rssi: Optional[float] = None
    snr: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
