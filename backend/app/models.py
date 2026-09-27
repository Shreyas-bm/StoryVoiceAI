import datetime
import enum
from typing import Any, Optional, Dict
from .database import Base, ModelAttribute

def _format_dt(val: Any) -> Optional[str]:
    """Serialize datetime or passthrough value."""
    return val.isoformat() if isinstance(val, datetime.datetime) else val

def _parse_dt(val: Any) -> Optional[datetime.datetime]:
    """Parse ISO datetime string to datetime object if applicable."""
    if isinstance(val, str):
        try:
            return datetime.datetime.fromisoformat(val)
        except ValueError:
            return None
    return val if isinstance(val, datetime.datetime) else None

class JobStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class User(Base):
    id = ModelAttribute("id")
    email = ModelAttribute("email")
    created_at = ModelAttribute("created_at")

    def __init__(self, email: str, id: Optional[int] = None, created_at: Optional[datetime.datetime] = None):
        self.id = id
        self.email = email
        self.created_at = created_at or datetime.datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "email": self.email,
            "created_at": _format_dt(self.created_at),
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional["User"]:
        if not data:
            return None
        return cls(
            email=data["email"],
            id=data.get("id"),
            created_at=_parse_dt(data.get("created_at")),
        )

    @property
    def stories(self):
        return []

class Story(Base):
    id = ModelAttribute("id")
    title = ModelAttribute("title")
    content = ModelAttribute("content")
    annotated_content = ModelAttribute("annotated_content")
    nlp_status = ModelAttribute("nlp_status")
    owner_id = ModelAttribute("owner_id")
    created_at = ModelAttribute("created_at")

    def __init__(
        self, 
        title: str, 
        content: str, 
        owner_id: int, 
        nlp_status: str = "pending", 
        annotated_content: Optional[Dict[str, Any]] = None, 
        id: Optional[int] = None, 
        created_at: Optional[datetime.datetime] = None
    ):
        self.id = id
        self.title = title
        self.content = content
        self.annotated_content = annotated_content
        self.nlp_status = nlp_status
        self.owner_id = owner_id
        self.created_at = created_at or datetime.datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "annotated_content": self.annotated_content,
            "nlp_status": self.nlp_status,
            "owner_id": self.owner_id,
            "created_at": _format_dt(self.created_at),
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional["Story"]:
        if not data:
            return None
        return cls(
            title=data["title"],
            content=data["content"],
            owner_id=data["owner_id"],
            nlp_status=data.get("nlp_status", "pending"),
            annotated_content=data.get("annotated_content"),
            id=data.get("id"),
            created_at=_parse_dt(data.get("created_at")),
        )

    @property
    def owner(self):
        return None

    @property
    def jobs(self):
        return []

class Job(Base):
    id = ModelAttribute("id")
    story_id = ModelAttribute("story_id")
    status = ModelAttribute("status")
    audio_url = ModelAttribute("audio_url")
    created_at = ModelAttribute("created_at")
    updated_at = ModelAttribute("updated_at")

    def __init__(
        self, 
        story_id: int, 
        status: JobStatus = JobStatus.PENDING, 
        audio_url: Optional[str] = None, 
        id: Optional[int] = None, 
        created_at: Optional[datetime.datetime] = None, 
        updated_at: Optional[datetime.datetime] = None
    ):
        self.id = id
        self.story_id = story_id
        self.status = status
        self.audio_url = audio_url
        self.created_at = created_at or datetime.datetime.utcnow()
        self.updated_at = updated_at or datetime.datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "story_id": self.story_id,
            "status": getattr(self.status, "value", self.status),
            "audio_url": self.audio_url,
            "created_at": _format_dt(self.created_at),
            "updated_at": _format_dt(self.updated_at),
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional["Job"]:
        if not data:
            return None
        status_val = data.get("status", "pending")
        try:
            status = JobStatus(status_val)
        except ValueError:
            status = JobStatus.PENDING
        return cls(
            story_id=data["story_id"],
            status=status,
            audio_url=data.get("audio_url"),
            id=data.get("id"),
            created_at=_parse_dt(data.get("created_at")),
            updated_at=_parse_dt(data.get("updated_at")),
        )

    @property
    def story(self):
        return None

