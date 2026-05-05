from fastapi import FastAPI
from .database import engine, Base

# We will use Alembic for migrations, but this is a fallback
# Base.metadata.create_all(bind=engine)

app = FastAPI(title="StoryVoice AI API")

@app.get("/")
def read_root():
    return {"message": "Welcome to StoryVoice AI API"}
