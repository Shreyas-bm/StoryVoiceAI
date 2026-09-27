import os
import copy
import wave
import tempfile
import threading
import logging
from typing import Any, Optional
from dotenv import load_dotenv

load_dotenv()

# Zero-dependency background task runner replacing Celery/Redis
class MockAsyncResult:
    def __init__(self, thread: threading.Thread, result_val: Any = True):
        self.thread = thread
        self.result_val = result_val

    def get(self, timeout: Optional[float] = None) -> Any:
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout)
        return self.result_val

class MockTask:
    def __init__(self, func: Any):
        self.func = func

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.func(*args, **kwargs)

    def delay(self, *args: Any, **kwargs: Any) -> MockAsyncResult:
        # Run in a background thread so the API remains non-blocking
        t = threading.Thread(target=self.func, args=args, kwargs=kwargs)
        t.start()
        return MockAsyncResult(t)

class MockCelery:
    def __init__(self, *args: Any, **kwargs: Any):
        self.conf = type("Conf", (), {"update": lambda self, *args, **kwargs: None})()

    def task(self, *args: Any, **kwargs: Any):
        def decorator(func: Any) -> MockTask:
            return MockTask(func)
        return decorator

celery_app = MockCelery()

@celery_app.task(name="dummy_task")
def dummy_task() -> bool:
    return True


@celery_app.task(name="generate_audio_task")
def generate_audio_task(job_id: int, narrator_voice: str = "male") -> bool:
    """
    Background task that retrieves annotated text, generates audio segments,
    concatenates them, uploads to storage, and updates the Job.
    """
    from .database import SessionLocal, flag_modified
    from .models import Job, JobStatus, Story
    from .utils.audio_generator import generate_procedural_speech, concatenate_wav_files, get_voice_profile_for_segment
    from .utils.storage import upload_file
    
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
        if not story or not story.annotated_content:
            task_logger.error(f"Story for job_id={job_id} is missing or has no annotated content.")
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
            
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_files = []
            prev_text = ""
            
            # Generate audio segments for each text chunk
            for idx, segment in enumerate(segments):
                voice = get_voice_profile_for_segment(segment, characters, prev_text, narrator_voice=narrator_voice)
                emotion = segment.get("emotion", "neutral")
                text = segment.get("text", "")
                
                temp_seg_path = os.path.join(temp_dir, f"seg_{idx}.wav")
                generate_procedural_speech(
                    text=text,
                    voice_profile=voice,
                    emotion=emotion,
                    output_path=temp_seg_path
                )
                
                # Get duration of generated WAV
                seg_duration = 0.0
                try:
                    with wave.open(temp_seg_path, 'rb') as wf:
                        rate = wf.getframerate()
                        if rate > 0:
                            seg_duration = wf.getnframes() / float(rate)
                except Exception as e:
                    task_logger.warning(f"Failed to read WAV duration for segment {idx}: {e}")
                
                segment["duration"] = seg_duration
                print(f"[TASK DEBUG] Segment {idx} text={text[:15]} duration={seg_duration}")
                temp_files.append(temp_seg_path)
                prev_text = text
                
            # Concatenate segment files
            temp_out_path = os.path.join(temp_dir, "final.wav")
            concatenate_wav_files(temp_files, temp_out_path)
            
            # Upload final concatenated audio file
            object_name = f"jobs/{job_id}/audio.wav"
            audio_url = upload_file(temp_out_path, object_name)
            
            # Update Story record with updated segments containing durations
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
        db.close()

