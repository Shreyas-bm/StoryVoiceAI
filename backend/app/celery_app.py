from celery import Celery
import os
from dotenv import load_dotenv
import redis

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Check if Redis is running, otherwise fallback to Celery's eager execution mode
use_eager = False
try:
    r = redis.from_url(REDIS_URL, socket_timeout=2)
    r.ping()
    print("Connected to Redis successfully.")
except Exception as e:
    print(f"Redis connection failed: {e}. Celery falling back to eager execution mode.")
    use_eager = True

celery_app = Celery(
    "storyvoice_worker",
    broker=REDIS_URL if not use_eager else "memory://",
    backend=REDIS_URL if not use_eager else "cache+memory://"
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_always_eager=use_eager,
    task_eager_propagates=use_eager
)

@celery_app.task(name="dummy_task")
def dummy_task():
    return True


@celery_app.task(name="generate_audio_task")
def generate_audio_task(job_id: int):
    """
    Celery task that retrieves annotated text, generates audio segments,
    concatenates them, uploads to storage, and updates the database Job.
    """
    import logging
    from .database import SessionLocal
    from .models import Job, JobStatus, Story
    from .utils.audio_generator import generate_procedural_speech, concatenate_wav_files, get_voice_profile_for_segment
    from .utils.storage import upload_file
    import tempfile
    
    task_logger = logging.getLogger("generate_audio_task")
    task_logger.info(f"Starting audio generation for job_id={job_id}")
    
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            task_logger.error(f"Job {job_id} not found in database.")
            return False
            
        job.status = JobStatus.PROCESSING
        db.commit()
        
        story = db.query(Story).filter(Story.id == job.story_id).first()
        if not story:
            task_logger.error(f"Story associated with job_id={job_id} not found.")
            job.status = JobStatus.FAILED
            db.commit()
            return False
            
        if not story.annotated_content:
            task_logger.error(f"Story {story.id} has no annotated content. Cannot generate audio.")
            job.status = JobStatus.FAILED
            db.commit()
            return False
            
        annotated = story.annotated_content
        segments = annotated.get("segments", [])
        characters = annotated.get("characters", [])
        
        if not segments:
            task_logger.error(f"No segments found in annotated content of story {story.id}.")
            job.status = JobStatus.FAILED
            db.commit()
            return False
            
        temp_files = []
        prev_text = ""
        
        # Generate audio segments for each text chunk
        for idx, segment in enumerate(segments):
            voice = get_voice_profile_for_segment(segment, characters, prev_text)
            emotion = segment.get("emotion", "neutral")
            text = segment.get("text", "")
            
            # Create a temporary file path
            temp_seg_fd, temp_seg_path = tempfile.mkstemp(suffix=f"_seg_{idx}.wav")
            os.close(temp_seg_fd)
            
            generate_procedural_speech(
                text=text,
                voice_profile=voice,
                emotion=emotion,
                output_path=temp_seg_path
            )
            
            temp_files.append(temp_seg_path)
            prev_text = text
            
        # Concatenate segment files
        temp_out_fd, temp_out_path = tempfile.mkstemp(suffix="_final.wav")
        os.close(temp_out_fd)
        
        concatenate_wav_files(temp_files, temp_out_path)
        
        # Upload final concatenated audio file
        object_name = f"jobs/{job_id}/audio.wav"
        audio_url = upload_file(temp_out_path, object_name)
        
        # Update Job record
        job.audio_url = audio_url
        job.status = JobStatus.COMPLETED
        db.commit()
        
        # Cleanup temporary files
        for f in temp_files:
            try:
                os.remove(f)
            except Exception as e:
                task_logger.warning(f"Could not remove temp segment file {f}: {e}")
                
        try:
            os.remove(temp_out_path)
        except Exception as e:
            task_logger.warning(f"Could not remove temp output file {temp_out_path}: {e}")
            
        task_logger.info(f"Audio generation job {job_id} completed successfully. URL: {audio_url}")
        return True
        
    except Exception as e:
        task_logger.exception(f"Error executing audio generation job {job_id}: {e}")
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = JobStatus.FAILED
                db.commit()
        except Exception:
            pass
        return False
    finally:
        db.close()

