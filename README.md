# 🎙️ StoryVoice AI

StoryVoice AI is an advanced, offline-capable multi-voice audiobook generator. It dynamically analyzes text inputs or uploaded documents (PDF, DOCX, TXT), segments them into dialogue and narration blocks, classifies the underlying emotions (Happy, Sad, Angry, Suspenseful, Neutral), and renders them using character-specific voice profiles with emotional speech parameters.

---

## ✨ Features

- **🎭 Intelligent Multi-Voice Synthesis**: Maps distinct voices (e.g., masculine/feminine) to narrators and characters. Implements offline native text-to-speech (via `pyttsx3` wrapper for SAPI5/espeak) with automatic fallback to a custom mathematical chiptune synthesizer.
- **🧠 Advanced NLP Analysis Pipeline**:
  - Automatically splits raw text into dialogue (quotes) and narration blocks.
  - Classifies emotional tone per segment using Hugging Face Zero-Shot models (`cross-encoder/nli-distilroberta-base`) with a keyword-based fallback system.
  - Extracts unique characters using Named Entity Recognition (NER via `spaCy`) and assigns unique voice profiles.
- **🎨 Premium Visual Interface**: Modern dark-themed Next.js UI (`#0B0B0F` background, glowing gradients, interactive card layouts) featuring:
  - **Emotion Map Visualizer**: Highlights text chunks with corresponding emotion colors (Sad = Blue, Happy = Yellow, Angry = Red, Suspenseful = Purple, Neutral = Gray).
  - **Custom Immersive Audio Player**: Includes Play/Pause, timeline scrubbing, speed control (1x, 1.25x, 1.5x, 2x), and a volume/mute slider.
  - **Dynamic Loading Screen**: Displays real-time task statuses and shimmer animations during synthesis.
  - **Audio Download Action**: Save generated audiobooks directly as local `.wav` files.
- **⚡ Orchestration & Resiliency**: Built with asynchronous execution (Celery worker queues), local S3-compatible caching (MinIO), PostgreSQL integration, and automatic graceful fallbacks to SQLite and local directory storage.

---

## 🏗️ Architecture & Tech Stack

### Frontend
- **Framework**: Next.js 16 (App Router, React 19)
- **Styling**: Tailwind CSS, ShadCN UI, Lucide Icons
- **State Management**: Zustand
- **Communication**: Polling Client -> REST APIs

### Backend
- **Framework**: FastAPI (Python 3.13)
- **Database**: PostgreSQL (SQLAlchemy ORM) with local **SQLite fallback** (`storyvoice.db`)
- **Queue/Broker**: Redis + Celery (supporting synchronous **eager execution fallback** if Redis is offline)
- **Storage**: MinIO (S3-compatible) with local folder fallback (`/storage`)
- **TTS/NLP Libraries**: `pyttsx3`, `transformers`, `torch`, `spacy`, `pypdf`, `python-docx`

---

## 📂 Folder Structure

```text
├── backend/
│   ├── app/
│   │   ├── utils/
│   │   │   ├── audio_generator.py # Speech synthesis (pyttsx3 + Chiptune fallback)
│   │   │   ├── nlp_pipeline.py    # Segmenter, emotion detection, spaCy NER
│   │   │   ├── parser.py          # PDF/DOCX/TXT file parser
│   │   │   └── storage.py         # MinIO & Local storage wrapper
│   │   ├── database.py            # SQLite/PostgreSQL engine connection
│   │   ├── models.py              # User, Story, and Job SQL schemas
│   │   ├── celery_app.py          # Celery worker and eager runner configuration
│   │   └── main.py                # FastAPI route endpoints
│   ├── requirements.txt           # Python backend dependencies
│   ├── test_backend.py            # Phase 1 & 3 test suite
│   ├── test_phase4.py             # Phase 4 NLP test suite
│   └── test_phase5.py             # Phase 5 Audio pipeline test suite
│
├── frontend/
│   ├── src/app/
│   │   ├── page.tsx               # Main Dashboard UI & custom audio player logic
│   │   └── globals.css            # Global CSS, dark theme configuration
│   ├── package.json               # Node.js dependencies & dev scripts
│   └── tailwind.config.ts         # Tailwind theme setup
│
├── docs/                          # Project specifications and TODO checklists
└── docker-compose.yml             # Orchestration for PostgreSQL, Redis, and MinIO
```

---
```
