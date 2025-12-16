from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union

# --- WhatsApp Schemas ---

# --- WhatsApp Schemas ---

class WhatsAppProfile(BaseModel):
    name: Optional[str] = None

class WhatsAppContact(BaseModel):
    profile: Optional[WhatsAppProfile] = None
    wa_id: Optional[str] = None

class WhatsAppMetadata(BaseModel):
    display_phone_number: Optional[str] = None
    phone_number_id: Optional[str] = None

class WhatsAppText(BaseModel):
    body: Optional[str] = None

class WhatsAppImage(BaseModel):
    id: Optional[str] = None
    caption: Optional[str] = None
    mime_type: Optional[str] = None
    sha256: Optional[str] = None

class WhatsAppMessage(BaseModel):
    from_: Optional[str] = Field(None, alias="from")
    id: Optional[str] = None 
    timestamp: Optional[str] = None 
    type: Optional[str] = None
    text: Optional[WhatsAppText] = None
    image: Optional[WhatsAppImage] = None

class WhatsAppValue(BaseModel):
    messaging_product: Optional[str] = None
    metadata: Optional[WhatsAppMetadata] = None
    contacts: Optional[List[WhatsAppContact]] = []
    messages: Optional[List[WhatsAppMessage]] = []

class WhatsAppChange(BaseModel):
    value: Optional[WhatsAppValue] = None
    field: Optional[str] = None

class WhatsAppEntry(BaseModel):
    id: Optional[str] = None
    changes: Optional[List[WhatsAppChange]] = []

class WhatsAppWebhookPayload(BaseModel):
    object: Optional[str] = None
    entry: Optional[List[WhatsAppEntry]] = []


# --- Instagram Schemas ---

class InstagramReplyTo(BaseModel):
    """Context for story/post replies."""
    mid: Optional[str] = None  # Message ID being replied to
    story: Optional[Dict[str, Any]] = None  # Story context (url, id)
    post: Optional[Dict[str, Any]] = None  # Post context (url, id)

class InstagramMessage(BaseModel):
    mid: str
    text: Optional[str] = None
    attachments: Optional[List[Dict[str, Any]]] = None
    reply_to: Optional[InstagramReplyTo] = None  # Story/post reply context
    is_echo: Optional[bool] = None  # Skip echoed messages

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
