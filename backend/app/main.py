from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import os

from .database import engine, Base, get_db
from . import models
from .utils.parser import parse_document

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
    title: str = Form(...), 
    content: str = Form(...), 
    db: Session = Depends(get_db)
):
    if not title.strip() or not content.strip():
        raise HTTPException(status_code=400, detail="Title and Content cannot be empty")
        
    owner_id = get_default_user_id(db)
    story = models.Story(title=title, content=content, owner_id=owner_id)
    db.add(story)
    db.commit()
    db.refresh(story)
    return story

@app.post("/api/stories/upload")
async def upload_story_file(
    file: UploadFile = File(...),
    title: str = Form(None),
    db: Session = Depends(get_db)
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
    story = models.Story(title=title, content=content, owner_id=owner_id)
    db.add(story)
    db.commit()
    db.refresh(story)
    return story

