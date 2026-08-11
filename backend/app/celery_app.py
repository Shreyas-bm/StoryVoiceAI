import os
import threading
import logging
from dotenv import load_dotenv

load_dotenv()

# Zero-dependency background task runner replacing Celery/Redis
class MockAsyncResult:
    def __init__(self, thread, result_val=True):
        self.thread = thread
        self.result_val = result_val

    def get(self, timeout=None):
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout)
        return self.result_val

class MockTask:
    def __init__(self, func):
        self.func = func

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)

    def delay(self, *args, **kwargs):
        # Run in a background thread so the API remains non-blocking
        t = threading.Thread(target=self.func, args=args, kwargs=kwargs)
        t.start()
        return MockAsyncResult(t)

class MockCelery:
    def __init__(self, *args, **kwargs):
        self.conf = type("Conf", (), {"update": lambda self, *args, **kwargs: None})()

    def task(self, *args, **kwargs):
        def decorator(func):
            return MockTask(func)
        return decorator

celery_app = MockCelery()

@celery_app.task(name="dummy_task")
def dummy_task():
    return True


@celery_app.task(name="generate_audio_task")
def generate_audio_task(job_id: int, narrator_voice: str = "male"):
    """
    Background task that retrieves annotated text, generates audio segments,
    concatenates them, uploads to storage, and updates the Job.
    """
    from .database import SessionLocal, flag_modified
    from .models import Job, JobStatus, Story
    from .utils.audio_generator import generate_procedural_speech, concatenate_wav_files, get_voice_profile_for_segment
    from .utils.storage import upload_file
    import tempfile
    
    task_logger = logging.getLogger("generate_audio_task")
    task_logger.info(f"Starting audio generation for job_id={job_id}")
    
    db = SessionLocal()
    temp_files = []
    temp_out_path = None
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
            
        prev_text = ""
        
        # Generate audio segments for each text chunk
        for idx, segment in enumerate(segments):
            voice = get_voice_profile_for_segment(segment, characters, prev_text, narrator_voice=narrator_voice)
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
            
            # Get duration of generated WAV
            seg_duration = 0.0
            try:
                import wave
                with wave.open(temp_seg_path, 'rb') as wf:
                    frames = wf.getnframes()
                    rate = wf.getframerate()
                    if rate > 0:
                        seg_duration = frames / float(rate)
            except Exception as e:
                task_logger.warning(f"Failed to read WAV duration for segment {idx}: {e}")
            
            segment["duration"] = seg_duration
            print(f"[TASK DEBUG] Segment {idx} text={text[:15]} duration={seg_duration}")
            temp_files.append(temp_seg_path)
            prev_text = text
            
        # Concatenate segment files
        temp_out_fd, temp_out_path = tempfile.mkstemp(suffix="_final.wav")
        os.close(temp_out_fd)
        
        concatenate_wav_files(temp_files, temp_out_path)
        
        # Upload final concatenated audio file
        object_name = f"jobs/{job_id}/audio.wav"
        audio_url = upload_file(temp_out_path, object_name)
        
        # Update Story record with updated segments containing durations
        import copy
        
        new_annotated = copy.deepcopy(annotated)
        new_annotated["segments"] = segments
        story.annotated_content = new_annotated
        flag_modified(story, "annotated_content")
        db.add(story)
        
        # Update Job record
        job.audio_url = audio_url
        job.status = JobStatus.COMPLETED
        db.commit()
        
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
        # Cleanup temporary files
        for f in temp_files:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception as e:
                task_logger.warning(f"Could not remove temp segment file {f}: {e}")
                
        if temp_out_path:
            try:
                if os.path.exists(temp_out_path):
                    os.remove(temp_out_path)
            except Exception as e:
                task_logger.warning(f"Could not remove temp output file {temp_out_path}: {e}")
        db.close()
