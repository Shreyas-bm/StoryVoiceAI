import datetime
import enum
from .database import Base, ModelAttribute

class JobStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class User(Base):
    id = ModelAttribute("id")
    email = ModelAttribute("email")
    created_at = ModelAttribute("created_at")

    def __init__(self, email: str, id: int = None, created_at = None):
        self.id = id
        self.email = email
        self.created_at = created_at or datetime.datetime.utcnow()

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime.datetime) else self.created_at
        }

    @classmethod
    def from_dict(cls, data):
        if not data:
            return None
        created_at = data.get("created_at")
        if created_at and isinstance(created_at, str):
            created_at = datetime.datetime.fromisoformat(created_at)
        return cls(
            email=data["email"],
            id=data["id"],
            created_at=created_at
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

    def __init__(self, title: str, content: str, owner_id: int, nlp_status: str = "pending", annotated_content = None, id: int = None, created_at = None):
        self.id = id
        self.title = title
        self.content = content
        self.annotated_content = annotated_content
        self.nlp_status = nlp_status
        self.owner_id = owner_id
        self.created_at = created_at or datetime.datetime.utcnow()

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "annotated_content": self.annotated_content,
            "nlp_status": self.nlp_status,
            "owner_id": self.owner_id,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime.datetime) else self.created_at
        }

    @classmethod
    def from_dict(cls, data):
        if not data:
            return None
        created_at = data.get("created_at")
        if created_at and isinstance(created_at, str):
            created_at = datetime.datetime.fromisoformat(created_at)
        return cls(
            title=data["title"],
            content=data["content"],
            owner_id=data["owner_id"],
            nlp_status=data.get("nlp_status", "pending"),
            annotated_content=data.get("annotated_content"),
            id=data["id"],
            created_at=created_at
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

    def __init__(self, story_id: int, status: JobStatus = JobStatus.PENDING, audio_url: str = None, id: int = None, created_at = None, updated_at = None):
        self.id = id
        self.story_id = story_id
        self.status = status
        self.audio_url = audio_url
        self.created_at = created_at or datetime.datetime.utcnow()
        self.updated_at = updated_at or datetime.datetime.utcnow()

    def to_dict(self):
        return {
            "id": self.id,
            "story_id": self.story_id,
            "status": self.status.value if isinstance(self.status, enum.Enum) else self.status,
            "audio_url": self.audio_url,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime.datetime) else self.created_at,
            "updated_at": self.updated_at.isoformat() if isinstance(self.updated_at, datetime.datetime) else self.updated_at
        }

    @classmethod
    def from_dict(cls, data):
        if not data:
            return None
        created_at = data.get("created_at")
        if created_at and isinstance(created_at, str):
            created_at = datetime.datetime.fromisoformat(created_at)
        updated_at = data.get("updated_at")
        if updated_at and isinstance(updated_at, str):
            updated_at = datetime.datetime.fromisoformat(updated_at)
        status_val = data.get("status", "pending")
        try:
            status = JobStatus(status_val)
        except ValueError:
            status = JobStatus.PENDING
        return cls(
            story_id=data["story_id"],
            status=status,
            audio_url=data.get("audio_url"),
            id=data["id"],
            created_at=created_at,
            updated_at=updated_at
        )

    @property
    def story(self):
        return None
