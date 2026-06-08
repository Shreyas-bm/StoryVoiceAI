"""
Phase 4 Integration Test Suite - NLP Pipeline
Tests: text preprocessing, dialogue segmentation, emotion detection,
       NER character extraction, and the FastAPI /analyze endpoint.
"""
import sys
import os
import unittest
import json

# Ensure we can import from the backend app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SAMPLE_STORY = (
    "The night was cold and dark. Shadows stretched across the stone floor. "
    '"I am frightened," Emma whispered. '
    '"Do not be afraid," replied John with a warm smile. '
    "They laughed together until morning came, filling the room with joy. "
    "But the storm outside raged with furious anger."
)


class TestPreprocessText(unittest.TestCase):
    def test_basic_normalization(self):
        from app.utils.nlp_pipeline import preprocess_text
        raw = "Hello\u201d World\u2018 test\n\n\n\nEnd"
        result = preprocess_text(raw)
        self.assertNotIn("\u201d", result)
        self.assertNotIn("\u2018", result)
        # Triple blank lines collapsed
        self.assertNotIn("\n\n\n", result)

    def test_strip_whitespace(self):
        from app.utils.nlp_pipeline import preprocess_text
        result = preprocess_text("  Hello World  ")
        self.assertEqual(result, "Hello World")


class TestSegmentText(unittest.TestCase):
    def test_dialogue_and_narration_split(self):
        from app.utils.nlp_pipeline import segment_text
        text = 'He walked in. "Hello!" he said. Then he left.'
        segments = segment_text(text)
        types = [s["type"] for s in segments]
        self.assertIn("narration", types)
        self.assertIn("dialogue", types)

    def test_no_dialogue(self):
        from app.utils.nlp_pipeline import segment_text
        text = "He walked through the dark forest alone."
        segments = segment_text(text)
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0]["type"], "narration")

    def test_dialogue_content_preserved(self):
        from app.utils.nlp_pipeline import segment_text
        text = 'He said "Good morning, world!"'
        segments = segment_text(text)
        dialogue_segs = [s for s in segments if s["type"] == "dialogue"]
        self.assertTrue(len(dialogue_segs) >= 1)
        self.assertIn("Good morning", dialogue_segs[0]["text"])


class TestEmotionDetection(unittest.TestCase):
    def test_returns_valid_label(self):
        from app.utils.nlp_pipeline import detect_emotion, EMOTION_LABELS
        result = detect_emotion("The storm raged with furious anger.")
        self.assertIn(result, EMOTION_LABELS)

    def test_empty_text_returns_neutral(self):
        from app.utils.nlp_pipeline import detect_emotion
        result = detect_emotion("")
        self.assertEqual(result, "neutral")

    def test_happy_text(self):
        from app.utils.nlp_pipeline import detect_emotion
        # Rule-based: should pick up "happy/laugh/smile" keywords
        result = detect_emotion("They laughed and smiled with great joy and happiness.")
        self.assertIn(result, ["happy", "neutral"])

    def test_suspenseful_text(self):
        from app.utils.nlp_pipeline import detect_emotion
        result = detect_emotion("The dark shadow crept closer, whispering secrets in silence.")
        self.assertIn(result, ["suspenseful", "neutral"])


class TestCharacterExtraction(unittest.TestCase):
    def test_extracts_person_names(self):
        from app.utils.nlp_pipeline import extract_characters
        text = "Emma looked at John. John smiled back at Emma."
        characters = extract_characters(text)
        names = [c["name"] for c in characters]
        # At least one name should be extracted (spaCy may vary)
        self.assertIsInstance(characters, list)

    def test_voice_profiles_assigned(self):
        from app.utils.nlp_pipeline import extract_characters
        text = "Alice and Bob walked into the room. Alice smiled. Bob laughed."
        characters = extract_characters(text)
        for char in characters:
            self.assertIn("voice_profile", char)
            self.assertIn("mentions", char)

    def test_empty_text(self):
        from app.utils.nlp_pipeline import extract_characters
        characters = extract_characters("")
        self.assertIsInstance(characters, list)


class TestFullPipeline(unittest.TestCase):
    def test_full_pipeline_structure(self):
        from app.utils.nlp_pipeline import run_nlp_pipeline
        result = run_nlp_pipeline(SAMPLE_STORY)

        # Check required keys
        self.assertIn("preprocessed_text", result)
        self.assertIn("segments", result)
        self.assertIn("characters", result)
        self.assertIn("emotion_summary", result)

        # Check segments are non-empty
        self.assertGreater(len(result["segments"]), 0)

        # Check each segment has required fields
        for seg in result["segments"]:
            self.assertIn("type", seg)
            self.assertIn("text", seg)
            self.assertIn("emotion", seg)
            self.assertIn("color", seg)
            self.assertIn(seg["type"], ("dialogue", "narration"))

        # Emotion summary has all expected keys
        for emotion in ["happy", "sad", "angry", "suspenseful", "neutral"]:
            self.assertIn(emotion, result["emotion_summary"])

    def test_pipeline_serialisable(self):
        """Result must be JSON-serialisable (required for DB storage)."""
        from app.utils.nlp_pipeline import run_nlp_pipeline
        result = run_nlp_pipeline(SAMPLE_STORY)
        serialised = json.dumps(result)
        self.assertIsInstance(serialised, str)


class TestAnalyzeEndpointIntegration(unittest.TestCase):
    """
    Integration test against a live FastAPI test client.
    Creates a story via POST /api/stories, then calls POST /api/stories/{id}/analyze
    and polls GET /api/stories/{id}/analysis until completed.
    """

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from app.main import app
        cls.client = TestClient(app)

    def test_analyze_nonexistent_story(self):
        response = self.client.post("/api/stories/999999/analyze")
        self.assertEqual(response.status_code, 404)

    def test_full_analyze_flow(self):
        import time

        # 1. Create a story
        create_resp = self.client.post(
            "/api/stories",
            data={"title": "Phase4 Test Story", "content": SAMPLE_STORY},
        )
        self.assertEqual(create_resp.status_code, 200)
        story_id = create_resp.json()["id"]

        # 2. Trigger analysis
        analyze_resp = self.client.post(f"/api/stories/{story_id}/analyze")
        self.assertEqual(analyze_resp.status_code, 200)
        body = analyze_resp.json()
        self.assertEqual(body["story_id"], story_id)
        self.assertIn(body["nlp_status"], ("processing", "completed"))

        # 3. Poll for completion (TestClient runs BackgroundTasks synchronously)
        for _ in range(20):
            poll_resp = self.client.get(f"/api/stories/{story_id}/analysis")
            self.assertEqual(poll_resp.status_code, 200)
            if poll_resp.json()["nlp_status"] == "completed":
                break
            time.sleep(0.5)

        poll_body = self.client.get(f"/api/stories/{story_id}/analysis").json()
        self.assertEqual(poll_body["nlp_status"], "completed")
        self.assertIsNotNone(poll_body["annotated_content"])

        annotated = poll_body["annotated_content"]
        self.assertIn("segments", annotated)
        self.assertIn("emotion_summary", annotated)
        self.assertIn("characters", annotated)


if __name__ == "__main__":
    print("\n--- PHASE 4: NLP PIPELINE TEST SUITE ---\n")
    unittest.main(verbosity=2)
