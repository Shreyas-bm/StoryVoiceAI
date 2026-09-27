from pathlib import Path
import logging
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .database import engine, Base, get_db
from . import models
from .utils.parser import parse_document
from .utils.storage import IN_MEMORY_STORAGE

logger = logging.getLogger(__name__)

# Force database tables creation on start (especially useful for SQLite)
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="StoryVoice AI API")

# Configure CORS so Next.js frontend can call our endpoints
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/static/{file_path:path}")
def serve_static_in_memory(file_path: str):
    key = file_path.replace("\\", "/")
    if key in IN_MEMORY_STORAGE:
        return Response(content=IN_MEMORY_STORAGE[key], media_type="audio/wav")
    raise HTTPException(status_code=404, detail="File not found in memory")


def get_default_user_id(db: Session) -> int:
    default_user = db.query(models.User).filter_by(email="guest@storyvoice.ai").first()
    if not default_user:
        default_user = models.User(email="guest@storyvoice.ai")
        db.add(default_user)
        db.commit()
        db.refresh(default_user)
    return default_user.id


# ---------------------------------------------------------------------------
# Phase 1 / Phase 3 Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
def read_root():
    return {"message": "Welcome to StoryVoice AI API"}


@app.get("/api/stories")
def list_stories(db: Session = Depends(get_db)):
    return db.query(models.Story).order_by(models.Story.created_at.desc()).all()


@app.get("/api/stories/{story_id}")
def get_story(story_id: int, db: Session = Depends(get_db)):
    story = db.query(models.Story).filter(models.Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    return story


@app.post("/api/stories")
def create_story(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db),
):
    if not title.strip() or not content.strip():
        raise HTTPException(status_code=400, detail="Title and Content cannot be empty")

    owner_id = get_default_user_id(db)
    story = models.Story(title=title, content=content, owner_id=owner_id, nlp_status="processing")
    db.add(story)
    db.commit()
    db.refresh(story)
    
    background_tasks.add_task(_run_and_save_pipeline, story.id)
    return story


@app.post("/api/stories/upload")
async def upload_story_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="File is empty")

    filename = file.filename or "uploaded_story.txt"
    if not title or not title.strip():
        title = Path(filename).stem.replace("_", " ").replace("-", " ").title()

    try:
        content = parse_document(file_bytes, filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not content.strip():
        raise HTTPException(status_code=400, detail="Extracted text from document is empty")

    owner_id = get_default_user_id(db)
    story = models.Story(title=title, content=content, owner_id=owner_id, nlp_status="processing")
    db.add(story)
    db.commit()
    db.refresh(story)
    
    background_tasks.add_task(_run_and_save_pipeline, story.id)
    return story


# ---------------------------------------------------------------------------
# Phase 4: NLP Pipeline Endpoints
# ---------------------------------------------------------------------------

def _run_and_save_pipeline(story_id: int):
    """Background worker: run NLP pipeline and persist results."""
    from .utils.nlp_pipeline import run_nlp_pipeline
    print(f"[BG TASK] Started for story_id={story_id}")

    db: Session = next(get_db())
    try:
        story = db.query(models.Story).filter(models.Story.id == story_id).first()
        if not story:
            print(f"[BG TASK] Story {story_id} not found!")
            return

        story.nlp_status = "processing"
        db.commit()
        print(f"[BG TASK] Story {story_id} status set to processing")

        result = run_nlp_pipeline(story.content)
        print(f"[BG TASK] NLP pipeline finished running for story_id={story_id}")

        story.annotated_content = result
        story.nlp_status = "completed"
        db.commit()
        print(f"[BG TASK] Story {story_id} status set to completed")
        logger.info("NLP pipeline completed for story_id=%s", story_id)

    except Exception as exc:
        print(f"[BG TASK] Exception in pipeline for story_id={story_id}: {exc}")
        logger.error("NLP pipeline failed for story_id=%s: %s", story_id, exc)
        try:
            story = db.query(models.Story).filter(models.Story.id == story_id).first()
            if story:
                story.nlp_status = "failed"
                db.commit()
        except Exception as e:
            print(f"[BG TASK] Error setting failed status: {e}")
    finally:
        db.close()


@app.post("/api/stories/{story_id}/analyze")
def analyze_story(
    story_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Trigger NLP analysis for a given story.
    Runs the full pipeline (preprocess -> segment -> emotion -> NER) and
    saves the result to `story.annotated_content`.
    """
    story = db.query(models.Story).filter(models.Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    if not story.content or not story.content.strip():
        raise HTTPException(status_code=400, detail="Story has no content to analyze")

    story.nlp_status = "processing"
    db.commit()

    background_tasks.add_task(_run_and_save_pipeline, story_id)

    return {
        "story_id": story_id,
        "nlp_status": "processing",
        "message": "NLP analysis started. Poll GET /api/stories/{story_id}/analysis for results.",
    }


@app.get("/api/stories/{story_id}/analysis")
def get_story_analysis(story_id: int, db: Session = Depends(get_db)):
    """
    Return the NLP analysis result for a story.
    """
    story = db.query(models.Story).filter(models.Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    return {
        "story_id": story_id,
        "title": story.title,
        "nlp_status": story.nlp_status,
        "annotated_content": story.annotated_content,
    }


# ---------------------------------------------------------------------------
# Phase 5: Audio Generation Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/stories/{story_id}/generate-audio")
def trigger_audio_generation(
    story_id: int, 
    narrator_voice: str = "male", 
    db: Session = Depends(get_db)
):
    """
    Trigger procedural audio generation for a story.
    Creates a new Job in the database and queues the Celery task.
    """
    if narrator_voice not in ("male", "female"):
        raise HTTPException(status_code=400, detail="narrator_voice must be either 'male' or 'female'")

    story = db.query(models.Story).filter(models.Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
        
    if not story.annotated_content:
        raise HTTPException(
            status_code=400,
            detail="Story has not been analyzed yet. Run POST /api/stories/{story_id}/analyze first."
        )
        
    from .celery_app import generate_audio_task
    
    job = models.Job(story_id=story_id, status=models.JobStatus.PENDING)
    db.add(job)
    db.commit()
    db.refresh(job)
    
    generate_audio_task.delay(job.id, narrator_voice=narrator_voice)
    
    return {
        "job_id": job.id,
        "story_id": story_id,
        "status": getattr(job.status, "value", job.status),
        "message": "Audio generation started. Poll GET /api/stories/{story_id}/audio-status for results."
    }


@app.get("/api/stories/{story_id}/audio-status")
def get_latest_audio_status(story_id: int, db: Session = Depends(get_db)):
    """
    Get the status of the latest audio generation job for a story.
    """
    story = db.query(models.Story).filter(models.Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
        
    latest_job = db.query(models.Job).filter(models.Job.story_id == story_id).order_by(models.Job.created_at.desc()).first()
    if not latest_job:
        return {
            "story_id": story_id,
            "status": "none",
            "message": "No audio generation job has been triggered for this story."
        }
        
    return {
        "job_id": latest_job.id,
        "story_id": story_id,
        "status": getattr(latest_job.status, "value", latest_job.status),
        "audio_url": latest_job.audio_url,
        "created_at": latest_job.created_at,
        "updated_at": latest_job.updated_at
    }


@app.get("/api/jobs/{job_id}")
def get_job_status(job_id: int, db: Session = Depends(get_db)):
    """
    Get the status of a specific audio generation job.
    """
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    return {
        "job_id": job.id,
        "story_id": job.story_id,
        "status": getattr(job.status, "value", job.status),
        "audio_url": job.audio_url,
        "created_at": job.created_at,
        "updated_at": job.updated_at
    }

