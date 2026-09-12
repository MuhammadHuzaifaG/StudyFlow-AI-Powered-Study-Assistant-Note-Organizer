# backend/run.py (Application Entry Point)
import os
from app import create_app, db
from models import User, Note, FlashcardSet, Flashcard, StudySession, AIMeeting, Collaboration, LearningGoal, StudyPlan
from dotenv import load_dotenv

load_dotenv()

app = create_app(os.getenv('FLASK_ENV', 'development'))

@app.shell_context_processor
def make_shell_context():
    """Context for Flask shell"""
    return {
        'db': db,
        'User': User,
        'Note': Note,
        'FlashcardSet': FlashcardSet,
        'Flashcard': Flashcard,
        'StudySession': StudySession,
        'AIMeeting': AIMeeting,
        'Collaboration': Collaboration,
        'LearningGoal': LearningGoal,
        'StudyPlan': StudyPlan
    }

@app.cli.command()
def init_db():
    """Initialize database"""
    db.create_all()
    print('Database initialized')

@app.cli.command()
def seed_db():
    """Seed database with sample data"""
    if User.query.first():
        print('Database already has data')
        return
    
    # Create sample user
    user = User(
        name='Demo User',
        email='demo@example.com'
    )
    user.set_password('DemoPass123')
    
    db.session.add(user)
    db.session.commit()
    
    # Create sample note
    note = Note(
        user_id=user.id,
        title='Introduction to Python',
        content='Python is a high-level programming language. Key concepts: variables, functions, loops, conditionals.',
        tags=['programming', 'python']
    )
    
    db.session.add(note)
    db.session.commit()
    
    print('Database seeded with sample data')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)