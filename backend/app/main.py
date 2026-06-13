from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import os
import logging

from .database import engine, Base, get_db
from . import models
from .utils.parser import parse_document

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

# Ensure local storage directory exists and mount it as static files
storage_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "storage")
os.makedirs(storage_path, exist_ok=True)
app.mount("/static", StaticFiles(directory=storage_path), name="static")


# Helper function to get or create a default user for local testing
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
    stories = db.query(models.Story).order_by(models.Story.created_at.desc()).all()
    return stories


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
    title: str = Form(None),
    db: Session = Depends(get_db),
):
    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    if not title or not title.strip():
        title = os.path.splitext(file.filename)[0].replace("_", " ").replace("-", " ").title()

    try:
        content = parse_document(file_bytes, file.filename)
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

    db: Session = next(get_db())
    try:
        story = db.query(models.Story).filter(models.Story.id == story_id).first()
        if not story:
            return

        story.nlp_status = "processing"
        db.commit()

        result = run_nlp_pipeline(story.content)

        story.annotated_content = result
        story.nlp_status = "completed"
        db.commit()
        logger.info("NLP pipeline completed for story_id=%s", story_id)

    except Exception as exc:
        logger.error("NLP pipeline failed for story_id=%s: %s", story_id, exc)
        try:
            story = db.query(models.Story).filter(models.Story.id == story_id).first()
            if story:
                story.nlp_status = "failed"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


@app.post("/api/stories/{story_id}/analyze")
def analyze_story(
    story_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Task 4.6 — Trigger NLP analysis for a given story.
    Runs the full pipeline (preprocess -> segment -> emotion -> NER) and
    saves the result to `story.annotated_content`.

    Returns immediately with `nlp_status = processing` and runs the
    heavy work in a FastAPI BackgroundTask so the API stays responsive.
    """
    story = db.query(models.Story).filter(models.Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    if not story.content or not story.content.strip():
        raise HTTPException(status_code=400, detail="Story has no content to analyze")

    # Update status immediately so the client can poll
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
    Includes segments with emotion labels, character list, and emotion summary.
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
def trigger_audio_generation(story_id: int, db: Session = Depends(get_db)):
    """
    Task 5.6 & Celery Trigger — Trigger procedural audio generation for a story.
    Creates a new Job in the database and queues the Celery task.
    """
    story = db.query(models.Story).filter(models.Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
        
    if not story.annotated_content:
        raise HTTPException(
            status_code=400,
            detail="Story has not been analyzed yet. Run POST /api/stories/{story_id}/analyze first."
        )
        
    # Queue new audio generation job
    from .celery_app import generate_audio_task
    
    # Create the job
    job = models.Job(story_id=story_id, status=models.JobStatus.PENDING)
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Trigger Celery task asynchronously
    generate_audio_task.delay(job.id)
    
    return {
        "job_id": job.id,
        "story_id": story_id,
        "status": job.status.value,
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
        
    # Find latest job
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
        "status": latest_job.status.value,
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
        "status": job.status.value,
        "audio_url": job.audio_url,
        "created_at": job.created_at,
        "updated_at": job.updated_at
    }
