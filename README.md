# StudyFlow-AI-Powered-Study-Assistant-Note-Organizer

> StudyFlow is an AI-powered learning management platform engineered to automate note organization, optimize retention using spaced repetition, and generate interactive practice materials.

---

## The Problem

Self-directed learners and students face significant workflow bottlenecks:

* **Information Overload:** Unstructured notes accumulate faster than they can be synthesized, leading to passive re-reading instead of active retrieval.
* **Inefficient Retention:** Standard study schedules do not account for memory decay, resulting in suboptimal review timing.
* **Manual Preparation:** Crafting flashcards, study schedules, and practice questions manually consumes time that could be spent learning.

<img width="1227" height="536" alt="ghh" src="https://github.com/user-attachments/assets/4ca240ed-be2b-472c-b5fe-df2e63c523fe" />

## Technical Solution

StudyFlow integrates active recall methodology with generative artificial intelligence:

1. **Automated Note Processing:** Converts unstructured text into key concept summaries, structured outlines, and practice sets.
2. **SM-2 Spaced Repetition:** Employs the SuperMemo-2 algorithm to schedule flashcard reviews precisely based on user recall performance.
3. **Contextual AI Assistance:** Provides on-demand explanations and generates targeted practice problems based on stored notes.
4. **Analytics & Focus Tracking:** Features integrated study session logging, learning goal tracking, and progress metrics.

## Expected Outcomes

* **Reduced Preparation Time:** Decreases time spent manually organizing notes and constructing flashcards.
* **Targeted Review:** Focuses study sessions on low-retention material via algorithmic scheduling.
* **Streamlined Workflow:** Unifies note processing, card generation, and performance tracking into a single interface.

---

## Key Features

* **AI Note Processing:** Automated summarization, structural layout formatting, and key concept extraction.
* **Spaced Repetition Engine:** Implementation of the SM-2 algorithm for individual card scheduling.
* **Context-Aware Tutor:** Generates topic-specific explanations and dynamic practice problems.
* **Analytics Dashboard:** Visual representation of study streaks, active sessions, and goal completion rates.
* **Collaboration Tools:** Note sharing mechanisms and group management options.
* **Authentication & Security:** JSON Web Token (JWT) based session management.

## Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | Vanilla JavaScript, HTML5, CSS3 (No external UI frameworks) |
| **Backend** | Python, Flask, Flask-SQLAlchemy, PyJWT |
| **Database** | SQLite (Development), PostgreSQL (Production) |
| **AI Integration** | OpenAI API |
| **Containerization & Deployment** | Docker, Docker Compose, Heroku |

## Local Development Setup

### Prerequisites

* Python 3.8 or higher
* Node.js 14 or higher
* Git
* OpenAI API Key

<img width="998" height="227" alt="dd" src="https://github.com/user-attachments/assets/1fbf5e4d-21dc-4efb-a16d-d44a56a40abd" />


### Backend Setup

```bash
# Clone repository
git clone https://github.com/MuhammadHuzaifaG/StudyFlow-AI-Powered-Study-Assistant-Note-Organizer.git
cd StudyFlow/backend

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env and supply OPENAI_API_KEY and SECRET_KEY values

# Initialize database schema
python run.py init-db

# Start backend server
python run.py

```

The backend server runs at `http://localhost:5000`.

---

### Frontend Setup

```bash
# Navigate to frontend directory
cd ../frontend

# Install dependencies
npm install

# Start development server
npm start

```

The frontend application runs at `http://localhost:3000`.

---

## Production Deployment

### Deployment via Docker Compose

```bash
# Build and run service containers
docker-compose up -d

# Initialize production database within container
docker-compose exec backend python run.py init-db

```

### Deployment via Heroku CLI

```bash
# Create Heroku application
heroku create studyflow-app

# Set configuration variables
heroku config:set OPENAI_API_KEY=your-openai-key
heroku config:set FLASK_ENV=production

# Deploy to remote branch
git push heroku main

```

---

## API Reference Overview

### Authentication

* `POST /api/auth/signup` - Register a new user account.
* `POST /api/auth/login` - Authenticate credentials and issue JWT.
* `GET /api/auth/profile` - Retrieve current user profile details.

### Notes

* `GET /api/notes` - Retrieve user notes.
* `POST /api/notes` - Create a note entry.
* `PUT /api/notes/<id>` - Update an existing note.
* `DELETE /api/notes/<id>` - Delete a note entry.
* `POST /api/notes/<id>/summarize` - Generate an AI summary for a note.
* `POST /api/notes/<id>/organize` - Generate a structured layout for a note.

### Flashcards

* `GET /api/flashcards/sets` - Fetch flashcard sets.
* `POST /api/flashcards/sets` - Create a flashcard set.
* `POST /api/flashcards/<id>/review` - Submit recall score to recalculate SM-2 interval.
* `POST /api/flashcards/sets/<id>/generate-from-note` - Generate cards from note content.

### AI Capabilities

* `POST /api/ai/tutor/ask` - Submit a prompt to the AI tutor.
* `POST /api/ai/study-plan/generate` - Produce a customized study schedule.
* `POST /api/ai/practice-problems` - Generate practice problems based on input topics. 

### Analytics & Collaboration

* `GET /api/analytics/dashboard` - Retrieve user analytics and study statistics.
* `POST /api/collaborate/share-note` - Share note resource with another account.
* `GET /api/collaborate/study-groups` - Fetch active study group memberships.

## Troubleshooting

| Issue | Cause | Solution |
| --- | --- | --- |
| **API Connection Failure** | Invalid CORS settings or port mismatch | Verify CORS configuration in `config.py` and confirm backend is running on port 5000. |
| **Database Failure** | Missing database tables or connection string errors | Execute `python run.py init-db`. Check `DATABASE_URL` format in configuration files. |
| **AI Request Failure** | Invalid API credentials or exceeded quota | Confirm `OPENAI_API_KEY` is present in `.env` and verify account usage limits. |

---

Built with ❤️ for Frontier Cascadia Hackathon
