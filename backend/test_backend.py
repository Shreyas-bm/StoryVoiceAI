import os
import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import backend modules
from app.main import app
from app.database import Base, get_db, DATABASE_URL
from app.models import User, Story, Job, JobStatus
from app.utils.storage import upload_file, LOCAL_STORAGE_DIR
from app.celery_app import dummy_task
from app.utils.parser import parse_document

class TestStoryVoiceBackend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n--- PHASE 1 & 3: INTEGRATION TEST SUITE ---")
        # Ensure we are testing on a test database
        cls.test_db_path = "test_storyvoice.db"
        cls.test_db_url = f"sqlite:///{cls.test_db_path}"
        cls.engine = create_engine(cls.test_db_url, connect_args={"check_same_thread": False})
        cls.TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        
        # Create the tables
        Base.metadata.create_all(bind=cls.engine)
        
        # Override the FastAPI db dependency
        def override_get_db():
            db = cls.TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()
        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app)
        
    @classmethod
    def tearDownClass(cls):
        # Clean up database file
        import time
        # Close engine connection pool
        cls.engine.dispose()
        # Give OS a moment to release file lock
        time.sleep(0.5)
        if os.path.exists(cls.test_db_path):
            try:
                os.remove(cls.test_db_path)
                print(f"Cleaned up test database file: {cls.test_db_path}")
            except Exception as e:
                print(f"Could not remove test database file: {e}")

    def setUp(self):
        # Create a clean session for database assertion checks
        self.db = self.TestingSessionLocal()
        
    def tearDown(self):
        self.db.query(Story).delete()
        self.db.query(User).delete()
        self.db.query(Job).delete()
        self.db.commit()
        self.db.close()

    # === PHASE 1 TESTS ===
    
    def test_phase1_database_connectivity(self):
        """Test database connection, schema setup, and base model operations."""
        print("Running Phase 1: Database verification...")
        # Add user
        user = User(email="test_user@storyvoice.ai")
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        
        self.assertIsNotNone(user.id)
        self.assertEqual(user.email, "test_user@storyvoice.ai")
        
        # Verify fetch
        fetched_user = self.db.query(User).filter_by(email="test_user@storyvoice.ai").first()
        self.assertEqual(fetched_user.id, user.id)

    def test_phase1_storage_utility(self):
        """Test local file system storage fallback upload and download path structure."""
        print("Running Phase 1: Storage utility verification...")
        test_file_path = "test_upload_temp.txt"
        with open(test_file_path, "w") as f:
            f.write("This is a temporary file for storage testing.")
            
        try:
            url = upload_file(test_file_path, "test/temp_file.txt")
            self.assertTrue(url.startswith("/static/") or url.startswith("http"))
            
            # Verify file exists in local storage if falling back
            if url.startswith("/static/"):
                local_path = os.path.join(LOCAL_STORAGE_DIR, "test/temp_file.txt")
                self.assertTrue(os.path.exists(local_path))
                with open(local_path, "r") as f:
                    content = f.read()
                self.assertEqual(content, "This is a temporary file for storage testing.")
        finally:
            if os.path.exists(test_file_path):
                os.remove(test_file_path)
            # Cleanup static file copy
            local_copy = os.path.join(LOCAL_STORAGE_DIR, "test/temp_file.txt")
            if os.path.exists(local_copy):
                os.remove(local_copy)

    def test_phase1_celery_eager_execution(self):
        """Test celery task registration and synchronous eager fallback execution."""
        print("Running Phase 1: Celery/Redis workflow verification...")
        # Trigger task execution (using Celery's .delay() or direct run)
        result = dummy_task.delay()
        # In eager mode, .get() retrieves the result synchronously
        self.assertTrue(result.get())

    # === PHASE 3 TESTS ===

    def test_phase3_document_parsing_txt(self):
        """Test text parsing logic from raw TXT bytes."""
        print("Running Phase 3: TXT document parsing verification...")
        txt_bytes = b"Hello, this is a plain text story content."
        parsed_text = parse_document(txt_bytes, "story.txt")
        self.assertEqual(parsed_text, "Hello, this is a plain text story content.")

    def test_phase3_api_story_creation_raw_text(self):
        """Test POST /api/stories endpoint for manual text submission."""
        print("Running Phase 3: POST /api/stories verification...")
        response = self.client.post(
            "/api/stories",
            data={"title": "The Golden Journey", "content": "Once upon a time, there was a golden journey."}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["title"], "The Golden Journey")
        self.assertEqual(data["content"], "Once upon a time, there was a golden journey.")
        self.assertIsNotNone(data["id"])

        # Check DB directly
        db_story = self.db.query(Story).filter_by(id=data["id"]).first()
        self.assertIsNotNone(db_story)
        self.assertEqual(db_story.title, "The Golden Journey")

    def test_phase3_api_story_upload_txt(self):
        """Test POST /api/stories/upload endpoint for TXT file parsing and saving."""
        print("Running Phase 3: POST /api/stories/upload (TXT file) verification...")
        file_content = b"Once upon a time in a faraway forest, a young wolf learned to howl."
        
        response = self.client.post(
            "/api/stories/upload",
            files={"file": ("howling_wolf.txt", file_content, "text/plain")},
            data={"title": "Custom Wolf Story"}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["title"], "Custom Wolf Story")
        self.assertEqual(data["content"], "Once upon a time in a faraway forest, a young wolf learned to howl.")
        
        # Verify it saved in DB
        db_story = self.db.query(Story).filter_by(id=data["id"]).first()
        self.assertIsNotNone(db_story)

    def test_phase3_api_story_upload_pdf(self):
        """Test POST /api/stories/upload endpoint with PDF parsing using dummy PDF contents."""
        print("Running Phase 3: POST /api/stories/upload (PDF file) verification...")
        # Since pypdf parses PDF structures, passing random bytes will throw a ValueError
        # Let's verify that a bad PDF throws a 400 Bad Request error correctly
        response = self.client.post(
            "/api/stories/upload",
            files={"file": ("invalid_story.pdf", b"not-a-pdf-structure", "application/pdf")},
            data={"title": "Bad PDF Test"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Failed to parse PDF", response.json()["detail"])

if __name__ == "__main__":
    unittest.main()
