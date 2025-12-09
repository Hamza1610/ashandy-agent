from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union

# --- WhatsApp Schemas ---

class WhatsAppText(BaseModel):
    body: str

class WhatsAppImage(BaseModel):
    id: str
    caption: Optional[str] = None
    mime_type: Optional[str] = None
    sha256: Optional[str] = None

class WhatsAppMessage(BaseModel):
    from_: str = Field(..., alias="from")
    id: Optional[str] = None 
    timestamp:Optional[str] = None 
    type: Optional[str] = None
    text: Optional[WhatsAppText] = None
    image: Optional[WhatsAppImage] = None

class WhatsAppValue(BaseModel):
    messaging_product: str
    metadata: Dict[str, Any]
    contacts: List[Dict[str, Any]] = []
    messages: List[WhatsAppMessage] = []

class WhatsAppChange(BaseModel):
    value: WhatsAppValue
    field: str

class WhatsAppEntry(BaseModel):
    id: str
    changes: List[WhatsAppChange]

class WhatsAppWebhookPayload(BaseModel):
    object: str
    entry: List[WhatsAppEntry]


# --- Instagram Schemas ---

class InstagramMessage(BaseModel):
    mid: str
    text: Optional[str] = None
    attachments: Optional[List[Dict[str, Any]]] = None # Simplified for now

class InstagramMessagingEvent(BaseModel):
    sender: Dict[str, str]
    recipient: Dict[str, str]
    timestamp: int
    message: Optional[InstagramMessage] = None

class InstagramEntry(BaseModel):
    id: str
    time: int
    messaging: List[InstagramMessagingEvent] = []

class InstagramWebhookPayload(BaseModel):
    object: str
    entry: List[InstagramEntry]
