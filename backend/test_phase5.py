"""
Phase 5 Integration Test Suite - Audio Generation (TTS) Pipeline
Tests: procedural speech segment generation, audio concatenation,
       Celery audio task execution, and Phase 5 endpoints.
"""
import sys
import os
import unittest
import time
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure we can import from the backend app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app as fastapi_app
from app.database import Base, get_db
from app import models
from app.utils.audio_generator import generate_procedural_speech, concatenate_wav_files, get_voice_profile_for_segment
from app.utils.storage import LOCAL_STORAGE_DIR

# Define a mock annotated content for testing the audio generation
MOCK_ANNOTATED_CONTENT = {
    "preprocessed_text": "The dark room was silent. 'Hello Emma!' John said. Emma smiled.",
    "segments": [
        {"type": "narration", "text": "The dark room was silent.", "emotion": "suspenseful", "color": "#9B59B6"},
        {"type": "dialogue", "text": "Hello Emma!", "emotion": "happy", "color": "#F5C518"},
        {"type": "narration", "text": "John said. Emma smiled.", "emotion": "neutral", "color": "#A0A0A0"}
    ],
    "characters": [
        {"name": "John", "mentions": 1, "voice_profile": "character_deep"},
        {"name": "Emma", "mentions": 2, "voice_profile": "character_light"}
    ],
    "emotion_summary": {"happy": 1, "sad": 0, "angry": 0, "suspenseful": 1, "neutral": 1}
}


class TestAudioGeneratorUnit(unittest.TestCase):
    def test_voice_attribution(self):
        """Test voice profile mapping for different segments."""
        characters = MOCK_ANNOTATED_CONTENT["characters"]
        
        # Narration segment should get narrator_warm
        seg_narr = {"type": "narration", "text": "Emma walked in."}
        voice = get_voice_profile_for_segment(seg_narr, characters)
        self.assertEqual(voice, "narrator_warm")
        
        # Dialogue mentioning Emma should get character_light (Emma's voice profile)
        seg_dial_emma = {"type": "dialogue", "text": "Hello, my name is Emma."}
        voice = get_voice_profile_for_segment(seg_dial_emma, characters)
        self.assertEqual(voice, "character_light")
        
        # Dialogue segment where a character is mentioned in previous context
        seg_dial_john = {"type": "dialogue", "text": "How are you?"}
        voice = get_voice_profile_for_segment(seg_dial_john, characters, prev_text="John asked.")
        self.assertEqual(voice, "character_deep")

    def test_generate_and_concatenate(self):
        """Test that generate_procedural_speech and concatenate_wav_files create valid files."""
        seg1 = "test_seg1.wav"
        seg2 = "test_seg2.wav"
        out = "test_combined.wav"
        
        try:
            generate_procedural_speech("Hi", "character_light", "happy", seg1)
            self.assertTrue(os.path.exists(seg1))
            self.assertGreater(os.path.getsize(seg1), 44) # Wave header is 44 bytes
            
            generate_procedural_speech("Low tone test", "character_deep", "sad", seg2)
            self.assertTrue(os.path.exists(seg2))
            
            concatenate_wav_files([seg1, seg2], out)
            self.assertTrue(os.path.exists(out))
            self.assertGreater(os.path.getsize(out), os.path.getsize(seg1))
            
        finally:
            for path in [seg1, seg2, out]:
                if os.path.exists(path):
                    os.remove(path)


class TestAudioGenerationIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n--- PHASE 5: AUDIO INTEGRATION TEST SUITE ---")
        cls.test_db_path = "test_phase5_storyvoice.db"
        cls.test_db_url = f"sqlite:///{cls.test_db_path}"
        cls.engine = create_engine(cls.test_db_url, connect_args={"check_same_thread": False})
        cls.TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        
        # Patch the SessionLocal database connection pool singleton
        import app.database
        cls.original_session_local = app.database.SessionLocal
        app.database.SessionLocal = cls.TestingSessionLocal
        
        # Create schema
        Base.metadata.create_all(bind=cls.engine)
        
        # Override FastAPI Dependency
        def override_get_db():
            db = cls.TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()
        fastapi_app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(fastapi_app)
        
    @classmethod
    def tearDownClass(cls):
        import app.database
        app.database.SessionLocal = cls.original_session_local
        cls.engine.dispose()
        time.sleep(0.5)
        if os.path.exists(cls.test_db_path):
            try:
                os.remove(cls.test_db_path)
                print(f"Cleaned up test database file: {cls.test_db_path}")
            except Exception as e:
                print(f"Could not remove test database: {e}")

    def setUp(self):
        self.db = self.TestingSessionLocal()
        
    def tearDown(self):
        self.db.query(models.Job).delete()
        self.db.query(models.Story).delete()
        self.db.query(models.User).delete()
        self.db.commit()
        self.db.close()
        
    def test_audio_endpoints_and_celery_task(self):
        """Test the full flow: Create story -> Set annotated content -> Trigger Audio -> Poll Status."""
        # 1. Create a story
        owner = models.User(email="test_owner@storyvoice.ai")
        self.db.add(owner)
        self.db.commit()
        
        story = models.Story(
            title="A Dark and Quiet Room",
            content="The dark room was silent. 'Hello Emma!' John said. Emma smiled.",
            annotated_content=MOCK_ANNOTATED_CONTENT,
            nlp_status="completed",
            owner_id=owner.id
        )
        self.db.add(story)
        self.db.commit()
        self.db.refresh(story)
        
        story_id = story.id
        
        # 2. Trigger audio generation via POST endpoint
        resp = self.client.post(f"/api/stories/{story_id}/generate-audio")
        self.assertEqual(resp.status_code, 200)
        resp_data = resp.json()
        
        self.assertIn("job_id", resp_data)
        self.assertEqual(resp_data["status"], "pending") # Starts as pending before celery processes it
        job_id = resp_data["job_id"]
        
        # 3. Poll job status
        # Since celery runs in always_eager mode synchronously for tests, the background job executes immediately
        # during the .delay() call. Thus, it should already be completed!
        poll_resp = self.client.get(f"/api/stories/{story_id}/audio-status")
        self.assertEqual(poll_resp.status_code, 200)
        poll_data = poll_resp.json()
        
        self.assertEqual(poll_data["job_id"], job_id)
        self.assertEqual(poll_data["status"], "completed")
        self.assertIsNotNone(poll_data["audio_url"])
        
        # 4. Check specific job endpoint
        job_resp = self.client.get(f"/api/jobs/{job_id}")
        self.assertEqual(job_resp.status_code, 200)
        job_data = job_resp.json()
        self.assertEqual(job_data["status"], "completed")
        self.assertEqual(job_data["audio_url"], poll_data["audio_url"])
        
        # 5. Verify the audio file was written to storage (relative path verification)
        audio_url = job_data["audio_url"]
        if audio_url.startswith("/static/"):
            # Local storage fallback
            local_filename = audio_url.replace("/static/", "")
            local_filepath = os.path.join(LOCAL_STORAGE_DIR, local_filename)
            self.assertTrue(os.path.exists(local_filepath))
            self.assertGreater(os.path.getsize(local_filepath), 44)
            # Cleanup physical file generated
            os.remove(local_filepath)
            
    def test_audio_generation_for_unannotated_story(self):
        """Triggering audio generation for a story without annotated_content must return 400 Bad Request."""
        owner = models.User(email="test_owner2@storyvoice.ai")
        self.db.add(owner)
        self.db.commit()
        
        story = models.Story(
            title="Untested Story",
            content="Blah blah",
            annotated_content=None,
            nlp_status="pending",
            owner_id=owner.id
        )
        self.db.add(story)
        self.db.commit()
        
        resp = self.client.post(f"/api/stories/{story.id}/generate-audio")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("has not been analyzed yet", resp.json()["detail"])


if __name__ == "__main__":
    unittest.main()
