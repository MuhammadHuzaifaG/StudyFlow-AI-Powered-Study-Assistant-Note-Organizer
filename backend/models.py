# backend/models.py
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from datetime import datetime
import uuid
import json

db = SQLAlchemy()
bcrypt = Bcrypt()

class User(db.Model):
    """User model with authentication"""
    __tablename__ = 'users'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    avatar_url = db.Column(db.String(500))
    
    # Account settings
    study_goal_hours = db.Column(db.Integer, default=5)
    preferred_language = db.Column(db.String(10), default='en')
    theme = db.Column(db.String(10), default='light')
    
    # Gamification
    study_streak = db.Column(db.Integer, default=0)
    last_study_date = db.Column(db.DateTime)
    total_points = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    notes = db.relationship('Note', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    flashcard_sets = db.relationship('FlashcardSet', backref='creator', lazy='dynamic', cascade='all, delete-orphan')
    study_sessions = db.relationship('StudySession', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    study_plans = db.relationship('StudyPlan', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    
    def check_password(self, password):
        """Verify password"""
        return bcrypt.check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'avatar_url': self.avatar_url,
            'study_streak': self.study_streak,
            'total_points': self.total_points,
            'created_at': self.created_at.isoformat()
        }


class Note(db.Model):
    """Note model with AI features"""
    __tablename__ = 'notes'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    summary = db.Column(db.Text)  # AI-generated
    
    # Organization
    tags = db.Column(db.JSON, default=list)  # ["math", "algebra"]
    color = db.Column(db.String(10), default='#ffffff')
    is_flagged = db.Column(db.Boolean, default=False)
    
    # Sharing
    is_shared = db.Column(db.Boolean, default=False)
    share_token = db.Column(db.String(50), unique=True, index=True)
    shared_with = db.Column(db.JSON, default=list)  # list of user IDs
    
    # AI Features
    auto_organized = db.Column(db.Boolean, default=False)
    organization_suggestions = db.Column(db.JSON)
    key_concepts = db.Column(db.JSON, default=list)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_accessed = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    flashcard_sets = db.relationship('FlashcardSet', backref='source_note', lazy='dynamic', cascade='all, delete-orphan')
    study_sessions = db.relationship('StudySession', backref='note', lazy='dynamic')
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'summary': self.summary,
            'tags': self.tags,
            'is_flagged': self.is_flagged,
            'is_shared': self.is_shared,
            'key_concepts': self.key_concepts,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class FlashcardSet(db.Model):
    """Flashcard set model"""
    __tablename__ = 'flashcard_sets'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    note_id = db.Column(db.String(36), db.ForeignKey('notes.id'), nullable=True)
    
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(500))
    
    # Statistics
    total_cards = db.Column(db.Integer, default=0)
    reviewed_count = db.Column(db.Integer, default=0)
    
    # AI Generated
    auto_generated = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    cards = db.relationship('Flashcard', backref='set', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'cardCount': self.total_cards,
            'auto_generated': self.auto_generated,
            'created_at': self.created_at.isoformat()
        }


class Flashcard(db.Model):
    """Individual flashcard model"""
    __tablename__ = 'flashcards'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    set_id = db.Column(db.String(36), db.ForeignKey('flashcard_sets.id'), nullable=False, index=True)
    
    front = db.Column(db.Text, nullable=False)  # Question
    back = db.Column(db.Text, nullable=False)   # Answer
    
    # Spaced Repetition Algorithm (SRS)
    difficulty = db.Column(db.Float, default=2.5)  # SM-2 algorithm
    interval = db.Column(db.Integer, default=1)    # Days until next review
    repetitions = db.Column(db.Integer, default=0)
    ease_factor = db.Column(db.Float, default=2.5)
    
    next_review = db.Column(db.DateTime, default=datetime.utcnow)
    last_reviewed = db.Column(db.DateTime)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'front': self.front,
            'back': self.back,
            'difficulty': self.difficulty,
            'last_reviewed': self.last_reviewed.isoformat() if self.last_reviewed else None
        }


class StudySession(db.Model):
    """Study session tracking for analytics"""
    __tablename__ = 'study_sessions'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    note_id = db.Column(db.String(36), db.ForeignKey('notes.id'), nullable=True)
    
    session_type = db.Column(db.String(50))  # 'flashcard', 'reading', 'pomodoro'
    duration_minutes = db.Column(db.Integer, default=0)
    
    # Results
    cards_studied = db.Column(db.Integer, default=0)
    correct_answers = db.Column(db.Integer, default=0)
    accuracy_percentage = db.Column(db.Float, default=0.0)
    
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime)
    
    def calculate_accuracy(self):
        """Calculate accuracy percentage"""
        if self.cards_studied == 0:
            return 0.0
        return (self.correct_answers / self.cards_studied) * 100
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'session_type': self.session_type,
            'duration_minutes': self.duration_minutes,
            'accuracy_percentage': self.accuracy_percentage,
            'started_at': self.started_at.isoformat()
        }


class StudyPlan(db.Model):
    """AI-generated study plan"""
    __tablename__ = 'study_plans'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    # Plan content
    content = db.Column(db.JSON)  # Structured plan data
    duration_days = db.Column(db.Integer, default=7)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    progress_percentage = db.Column(db.Float, default=0.0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    target_date = db.Column(db.DateTime)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'duration_days': self.duration_days,
            'progress_percentage': self.progress_percentage,
            'created_at': self.created_at.isoformat()
        }


class AIMeeting(db.Model):
    """Conversation history with AI tutor"""
    __tablename__ = 'ai_meetings'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    
    # Context
    related_note_id = db.Column(db.String(36), db.ForeignKey('notes.id'))
    topic = db.Column(db.String(200))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    helpful = db.Column(db.Boolean)  # User feedback
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'question': self.question,
            'answer': self.answer,
            'topic': self.topic,
            'created_at': self.created_at.isoformat()
        }


class Collaboration(db.Model):
    """Note sharing and collaboration"""
    __tablename__ = 'collaborations'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    note_id = db.Column(db.String(36), db.ForeignKey('notes.id'), nullable=False, index=True)
    owner_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    shared_with_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    
    permission_level = db.Column(db.String(20), default='view')  # 'view', 'edit', 'admin'
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    accepted_at = db.Column(db.DateTime)
    
    owner = db.relationship('User', foreign_keys=[owner_id])
    shared_with = db.relationship('User', foreign_keys=[shared_with_id])
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'permission_level': self.permission_level,
            'owner': self.owner.to_dict(),
            'created_at': self.created_at.isoformat()
        }


class LearningGoal(db.Model):
    """User learning goals and progress"""
    __tablename__ = 'learning_goals'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    target_value = db.Column(db.Float, nullable=False)  # e.g., 100 flashcards
    current_value = db.Column(db.Float, default=0.0)
    goal_type = db.Column(db.String(50))  # 'flashcards', 'study_time', 'accuracy'
    
    priority = db.Column(db.String(20), default='medium')  # 'low', 'medium', 'high'
    is_completed = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    target_date = db.Column(db.DateTime, nullable=False)
    
    def progress_percentage(self):
        """Calculate progress"""
        if self.target_value == 0:
            return 0.0
        return min((self.current_value / self.target_value) * 100, 100.0)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'title': self.title,
            'target_value': self.target_value,
            'current_value': self.current_value,
            'progress_percentage': self.progress_percentage(),
            'is_completed': self.is_completed
        }