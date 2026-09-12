# backend/routes.py (Part 1 - Auth Routes)
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from functools import wraps
import validators
from datetime import datetime

from models import db, User, Note
from config import Config

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

def validate_email(email):
    """Validate email format"""
    return validators.email(email)

def validate_password(password):
    """Validate password strength"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not any(c.isupper() for c in password):
        return False, "Password must contain uppercase letter"
    if not any(c.isdigit() for c in password):
        return False, "Password must contain number"
    return True, "Valid"

@auth_bp.route('/signup', methods=['POST'])
def signup():
    """Register new user"""
    try:
        data = request.get_json()
        
        # Validate input
        if not data or not all(k in data for k in ['name', 'email', 'password']):
            return jsonify({'error': 'Missing required fields'}), 400
        
        name = data.get('name', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not name or len(name) < 2:
            return jsonify({'error': 'Name must be at least 2 characters'}), 400
        
        if not validate_email(email):
            return jsonify({'error': 'Invalid email format'}), 400
        
        is_valid, message = validate_password(password)
        if not is_valid:
            return jsonify({'error': message}), 400
        
        # Check if user exists
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email already registered'}), 409
        
        # Create user
        user = User(name=name, email=email)
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        # Create JWT token
        access_token = create_access_token(identity=user.id)
        
        return jsonify({
            'message': 'Account created successfully',
            'token': access_token,
            'user': user.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Signup failed', 'message': str(e)}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    """Login user"""
    try:
        data = request.get_json()
        
        if not data or not all(k in data for k in ['email', 'password']):
            return jsonify({'error': 'Missing email or password'}), 400
        
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        user = User.query.filter_by(email=email).first()
        
        if not user or not user.check_password(password):
            return jsonify({'error': 'Invalid email or password'}), 401
        
        # Update last login
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Create JWT token
        access_token = create_access_token(identity=user.id)
        
        return jsonify({
            'message': 'Login successful',
            'token': access_token,
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Login failed', 'message': str(e)}), 500

@auth_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """Get current user profile"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify({
            'user': user.to_dict(),
            'stats': {
                'notes_count': Note.query.filter_by(user_id=user_id).count(),
                'study_streak': user.study_streak,
                'total_points': user.total_points
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to fetch profile', 'message': str(e)}), 500

@auth_bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    """Update user profile"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        
        if 'name' in data:
            user.name = data['name'].strip()
        if 'avatar_url' in data:
            user.avatar_url = data['avatar_url']
        if 'theme' in data:
            user.theme = data['theme']
        if 'study_goal_hours' in data:
            user.study_goal_hours = int(data['study_goal_hours'])
        
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Profile updated',
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to update profile', 'message': str(e)}), 500

@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """Change user password"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        
        if not data or not all(k in data for k in ['old_password', 'new_password']):
            return jsonify({'error': 'Missing required fields'}), 400
        
        if not user.check_password(data['old_password']):
            return jsonify({'error': 'Incorrect current password'}), 401
        
        is_valid, message = validate_password(data['new_password'])
        if not is_valid:
            return jsonify({'error': message}), 400
        
        user.set_password(data['new_password'])
        db.session.commit()
        
        return jsonify({'message': 'Password changed successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to change password', 'message': str(e)}), 500

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """Logout user (token blacklisting would be added in production)"""
    return jsonify({'message': 'Logout successful'}), 200

# backend/routes.py (Part 2 - Notes Routes)
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
import uuid
import secrets

from models import db, User, Note, FlashcardSet, Flashcard, StudySession, AIMeeting
from config import Config
from services import AIService, NoteService

notes_bp = Blueprint('notes', __name__, url_prefix='/api/notes')
ai_service = AIService()
note_service = NoteService()

@notes_bp.route('', methods=['GET'])
@jwt_required()
def get_notes():
    """Get all notes for current user with filtering"""
    try:
        user_id = get_jwt_identity()
        
        # Get query parameters
        filter_type = request.args.get('filter', 'all')
        sort_by = request.args.get('sort', 'updated')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # Build query
        query = Note.query.filter_by(user_id=user_id)
        
        # Apply filters
        if filter_type == 'flagged':
            query = query.filter_by(is_flagged=True)
        elif filter_type == 'shared':
            query = query.filter_by(is_shared=True)
        elif filter_type == 'recent':
            query = query.filter(Note.last_accessed >= datetime.utcnow() - timedelta(days=7))
        
        # Apply sorting
        if sort_by == 'created':
            query = query.order_by(Note.created_at.desc())
        elif sort_by == 'title':
            query = query.order_by(Note.title.asc())
        else:  # 'updated'
            query = query.order_by(Note.updated_at.desc())
        
        # Paginate
        paginated = query.paginate(page=page, per_page=per_page)
        
        notes_data = [note.to_dict() for note in paginated.items]
        
        return jsonify({
            'notes': notes_data,
            'pagination': {
                'total': paginated.total,
                'pages': paginated.pages,
                'current_page': page,
                'per_page': per_page
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to fetch notes', 'message': str(e)}), 500

@notes_bp.route('/<note_id>', methods=['GET'])
@jwt_required()
def get_note(note_id):
    """Get single note by ID"""
    try:
        user_id = get_jwt_identity()
        note = Note.query.filter_by(id=note_id, user_id=user_id).first()
        
        if not note:
            return jsonify({'error': 'Note not found'}), 404
        
        # Update last accessed time
        note.last_accessed = datetime.utcnow()
        db.session.commit()
        
        return jsonify(note.to_dict()), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to fetch note', 'message': str(e)}), 500

@notes_bp.route('', methods=['POST'])
@jwt_required()
def create_note():
    """Create new note"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        # Validate input
        if not data or 'title' not in data or 'content' not in data:
            return jsonify({'error': 'Missing title or content'}), 400
        
        title = data.get('title', '').strip()
        content = data.get('content', '').strip()
        tags = data.get('tags', [])
        
        if not title or len(title) < 1:
            return jsonify({'error': 'Title is required'}), 400
        
        if not content or len(content) < 10:
            return jsonify({'error': 'Content must be at least 10 characters'}), 400
        
        if len(title) > 200:
            return jsonify({'error': 'Title too long (max 200 characters)'}), 400
        
        # Validate tags
        if not isinstance(tags, list):
            tags = []
        tags = [tag.strip() for tag in tags if isinstance(tag, str) and tag.strip()][:10]
        
        # Create note
        note = Note(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=title,
            content=content,
            tags=tags
        )
        
        db.session.add(note)
        db.session.commit()
        
        return jsonify({
            'message': 'Note created successfully',
            'note': note.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to create note', 'message': str(e)}), 500

@notes_bp.route('/<note_id>', methods=['PUT'])
@jwt_required()
def update_note(note_id):
    """Update existing note"""
    try:
        user_id = get_jwt_identity()
        note = Note.query.filter_by(id=note_id, user_id=user_id).first()
        
        if not note:
            return jsonify({'error': 'Note not found'}), 404
        
        data = request.get_json()
        
        if 'title' in data:
            title = data['title'].strip()
            if len(title) > 0 and len(title) <= 200:
                note.title = title
        
        if 'content' in data:
            content = data['content'].strip()
            if len(content) >= 10:
                note.content = content
        
        if 'tags' in data:
            tags = data['tags']
            if isinstance(tags, list):
                note.tags = [tag.strip() for tag in tags if isinstance(tag, str)][:10]
        
        if 'color' in data:
            note.color = data['color']
        
        note.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Note updated successfully',
            'note': note.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to update note', 'message': str(e)}), 500

@notes_bp.route('/<note_id>', methods=['DELETE'])
@jwt_required()
def delete_note(note_id):
    """Delete note"""
    try:
        user_id = get_jwt_identity()
        note = Note.query.filter_by(id=note_id, user_id=user_id).first()
        
        if not note:
            return jsonify({'error': 'Note not found'}), 404
        
        db.session.delete(note)
        db.session.commit()
        
        return jsonify({'message': 'Note deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to delete note', 'message': str(e)}), 500

@notes_bp.route('/<note_id>/flag', methods=['POST'])
@jwt_required()
def flag_note(note_id):
    """Flag/unflag note as important"""
    try:
        user_id = get_jwt_identity()
        note = Note.query.filter_by(id=note_id, user_id=user_id).first()
        
        if not note:
            return jsonify({'error': 'Note not found'}), 404
        
        note.is_flagged = not note.is_flagged
        db.session.commit()
        
        return jsonify({
            'message': f'Note {"flagged" if note.is_flagged else "unflagged"}',
            'is_flagged': note.is_flagged
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to flag note', 'message': str(e)}), 500

@notes_bp.route('/<note_id>/summarize', methods=['POST'])
@jwt_required()
def summarize_note(note_id):
    """Generate AI summary of note"""
    try:
        user_id = get_jwt_identity()
        note = Note.query.filter_by(id=note_id, user_id=user_id).first()
        
        if not note:
            return jsonify({'error': 'Note not found'}), 404
        
        # Generate summary using AI
        summary = ai_service.generate_summary(note.content)
        
        if not summary:
            return jsonify({'error': 'Failed to generate summary'}), 500
        
        note.summary = summary
        db.session.commit()
        
        return jsonify({
            'message': 'Summary generated successfully',
            'summary': summary
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to summarize note', 'message': str(e)}), 500

@notes_bp.route('/<note_id>/organize', methods=['POST'])
@jwt_required()
def organize_note(note_id):
    """AI-powered note organization"""
    try:
        user_id = get_jwt_identity()
        note = Note.query.filter_by(id=note_id, user_id=user_id).first()
        
        if not note:
            return jsonify({'error': 'Note not found'}), 404
        
        # Organize content
        organized_content = ai_service.organize_content(note.content)
        key_concepts = ai_service.extract_key_concepts(note.content)
        
        if not organized_content:
            return jsonify({'error': 'Failed to organize note'}), 500
        
        note.content = organized_content
        note.key_concepts = key_concepts
        note.auto_organized = True
        db.session.commit()
        
        return jsonify({
            'message': 'Note organized successfully',
            'organized_content': organized_content,
            'key_concepts': key_concepts
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to organize note', 'message': str(e)}), 500

@notes_bp.route('/<note_id>/share', methods=['POST'])
@jwt_required()
def share_note(note_id):
    """Generate share link for note"""
    try:
        user_id = get_jwt_identity()
        note = Note.query.filter_by(id=note_id, user_id=user_id).first()
        
        if not note:
            return jsonify({'error': 'Note not found'}), 404
        
        # Generate unique share token
        if not note.share_token:
            note.share_token = secrets.token_urlsafe(32)
        
        note.is_shared = True
        db.session.commit()
        
        share_url = f"{Config.APP_URL}/shared/{note.share_token}"
        
        return jsonify({
            'message': 'Note sharing enabled',
            'share_url': share_url,
            'share_token': note.share_token
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to share note', 'message': str(e)}), 500

@notes_bp.route('/shared/<share_token>', methods=['GET'])
def view_shared_note(share_token):
    """View shared note without authentication"""
    try:
        note = Note.query.filter_by(share_token=share_token, is_shared=True).first()
        
        if not note:
            return jsonify({'error': 'Shared note not found'}), 404
        
        return jsonify({
            'note': {
                'title': note.title,
                'content': note.content,
                'summary': note.summary,
                'tags': note.tags,
                'author': note.author.name,
                'created_at': note.created_at.isoformat()
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to fetch shared note', 'message': str(e)}), 500

@notes_bp.route('/search', methods=['GET'])
@jwt_required()
def search_notes():
    """Search notes by query"""
    try:
        user_id = get_jwt_identity()
        query = request.args.get('q', '').strip()
        
        if not query or len(query) < 2:
            return jsonify({'error': 'Search query too short (min 2 characters)'}), 400
        
        notes = Note.query.filter_by(user_id=user_id).filter(
            (Note.title.ilike(f'%{query}%')) |
            (Note.content.ilike(f'%{query}%')) |
            (Note.tags.astext.ilike(f'%{query}%'))
        ).limit(20).all()
        
        return jsonify({
            'query': query,
            'results': [note.to_dict() for note in notes],
            'count': len(notes)
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Search failed', 'message': str(e)}), 500

@notes_bp.route('/<note_id>/export', methods=['GET'])
@jwt_required()
def export_note(note_id):
    """Export note as PDF or text"""
    try:
        user_id = get_jwt_identity()
        note = Note.query.filter_by(id=note_id, user_id=user_id).first()
        
        if not note:
            return jsonify({'error': 'Note not found'}), 404
        
        export_format = request.args.get('format', 'text')
        
        if export_format == 'text':
            content = f"{note.title}\n\n{note.content}"
            return jsonify({
                'format': 'text',
                'content': content,
                'filename': f"{note.title.replace(' ', '_')}.txt"
            }), 200
        
        elif export_format == 'markdown':
            content = f"# {note.title}\n\n{note.content}"
            return jsonify({
                'format': 'markdown',
                'content': content,
                'filename': f"{note.title.replace(' ', '_')}.md"
            }), 200
        
        else:
            return jsonify({'error': 'Invalid export format'}), 400
            
    except Exception as e:
        return jsonify({'error': 'Export failed', 'message': str(e)}), 500

@notes_bp.route('/<note_id>/key-concepts', methods=['GET'])
@jwt_required()
def get_key_concepts(note_id):
    """Get AI-extracted key concepts from note"""
    try:
        user_id = get_jwt_identity()
        note = Note.query.filter_by(id=note_id, user_id=user_id).first()
        
        if not note:
            return jsonify({'error': 'Note not found'}), 404
        
        if not note.key_concepts:
            concepts = ai_service.extract_key_concepts(note.content)
            note.key_concepts = concepts
            db.session.commit()
        
        return jsonify({
            'key_concepts': note.key_concepts
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to extract concepts', 'message': str(e)}), 500

@notes_bp.route('/bulk/delete', methods=['POST'])
@jwt_required()
def bulk_delete_notes():
    """Delete multiple notes at once"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data or 'note_ids' not in data:
            return jsonify({'error': 'Missing note_ids'}), 400
        
        note_ids = data.get('note_ids', [])
        
        if not isinstance(note_ids, list) or len(note_ids) == 0:
            return jsonify({'error': 'Invalid note_ids'}), 400
        
        deleted_count = Note.query.filter(
            Note.id.in_(note_ids),
            Note.user_id == user_id
        ).delete()
        
        db.session.commit()
        
        return jsonify({
            'message': f'{deleted_count} notes deleted',
            'deleted_count': deleted_count
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Bulk delete failed', 'message': str(e)}), 500

@notes_bp.route('/<note_id>/duplicate', methods=['POST'])
@jwt_required()
def duplicate_note(note_id):
    """Create a duplicate of a note"""
    try:
        user_id = get_jwt_identity()
        original_note = Note.query.filter_by(id=note_id, user_id=user_id).first()
        
        if not original_note:
            return jsonify({'error': 'Note not found'}), 404
        
        # Create duplicate
        duplicated_note = Note(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=f"{original_note.title} (Copy)",
            content=original_note.content,
            tags=original_note.tags.copy() if original_note.tags else [],
            color=original_note.color
        )
        
        db.session.add(duplicated_note)
        db.session.commit()
        
        return jsonify({
            'message': 'Note duplicated successfully',
            'note': duplicated_note.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to duplicate note', 'message': str(e)}), 500

@notes_bp.route('/batch/tag', methods=['POST'])
@jwt_required()
def batch_tag_notes():
    """Add tags to multiple notes"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data or 'note_ids' not in data or 'tags' not in data:
            return jsonify({'error': 'Missing note_ids or tags'}), 400
        
        note_ids = data.get('note_ids', [])
        new_tags = data.get('tags', [])
        
        notes = Note.query.filter(
            Note.id.in_(note_ids),
            Note.user_id == user_id
        ).all()
        
        updated_count = 0
        for note in notes:
            existing_tags = note.tags or []
            note.tags = list(set(existing_tags + new_tags))[:10]
            updated_count += 1
        
        db.session.commit()
        
        return jsonify({
            'message': f'{updated_count} notes tagged',
            'updated_count': updated_count
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Batch tag failed', 'message': str(e)}), 500

# backend/routes.py (Part 3 - Flashcards Routes)
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
import uuid
import math

from models import db, Flashcard, FlashcardSet, StudySession, Note
from services import AIService, SpacedRepetitionService

flashcards_bp = Blueprint('flashcards', __name__, url_prefix='/api/flashcards')
ai_service = AIService()
sr_service = SpacedRepetitionService()

@flashcards_bp.route('/sets', methods=['GET'])
@jwt_required()
def get_flashcard_sets():
    """Get all flashcard sets for current user"""
    try:
        user_id = get_jwt_identity()
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        sort_by = request.args.get('sort', 'updated')
        
        query = FlashcardSet.query.filter_by(user_id=user_id)
        
        if sort_by == 'created':
            query = query.order_by(FlashcardSet.created_at.desc())
        elif sort_by == 'name':
            query = query.order_by(FlashcardSet.name.asc())
        else:
            query = query.order_by(FlashcardSet.updated_at.desc())
        
        paginated = query.paginate(page=page, per_page=per_page)
        
        sets_data = []
        for fset in paginated.items:
            set_dict = fset.to_dict()
            set_dict['cards_due'] = Flashcard.query.filter(
                Flashcard.set_id == fset.id,
                Flashcard.next_review <= datetime.utcnow()
            ).count()
            sets_data.append(set_dict)
        
        return jsonify({
            'sets': sets_data,
            'pagination': {
                'total': paginated.total,
                'pages': paginated.pages,
                'current_page': page,
                'per_page': per_page
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to fetch flashcard sets', 'message': str(e)}), 500

@flashcards_bp.route('/sets', methods=['POST'])
@jwt_required()
def create_flashcard_set():
    """Create new flashcard set"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data or 'name' not in data:
            return jsonify({'error': 'Name is required'}), 400
        
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        
        if not name or len(name) < 2:
            return jsonify({'error': 'Name must be at least 2 characters'}), 400
        
        if len(name) > 200:
            return jsonify({'error': 'Name too long (max 200 characters)'}), 400
        
        note_id = data.get('note_id')
        auto_generated = data.get('auto_generated', False)
        
        flashcard_set = FlashcardSet(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=name,
            description=description,
            note_id=note_id,
            auto_generated=auto_generated
        )
        
        db.session.add(flashcard_set)
        db.session.commit()
        
        return jsonify({
            'message': 'Flashcard set created successfully',
            'set': flashcard_set.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to create flashcard set', 'message': str(e)}), 500

@flashcards_bp.route('/sets/<set_id>', methods=['GET'])
@jwt_required()
def get_flashcard_set(set_id):
    """Get flashcard set with all cards"""
    try:
        user_id = get_jwt_identity()
        fset = FlashcardSet.query.filter_by(id=set_id, user_id=user_id).first()
        
        if not fset:
            return jsonify({'error': 'Flashcard set not found'}), 404
        
        cards = Flashcard.query.filter_by(set_id=set_id).all()
        
        return jsonify({
            'set': fset.to_dict(),
            'cards': [card.to_dict() for card in cards],
            'stats': {
                'total_cards': len(cards),
                'cards_due': sum(1 for c in cards if c.next_review <= datetime.utcnow()),
                'mastered': sum(1 for c in cards if c.ease_factor >= 2.9),
                'learning': sum(1 for c in cards if c.repetitions < 3)
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to fetch flashcard set', 'message': str(e)}), 500

@flashcards_bp.route('/sets/<set_id>', methods=['PUT'])
@jwt_required()
def update_flashcard_set(set_id):
    """Update flashcard set"""
    try:
        user_id = get_jwt_identity()
        fset = FlashcardSet.query.filter_by(id=set_id, user_id=user_id).first()
        
        if not fset:
            return jsonify({'error': 'Flashcard set not found'}), 404
        
        data = request.get_json()
        
        if 'name' in data:
            name = data['name'].strip()
            if len(name) > 0 and len(name) <= 200:
                fset.name = name
        
        if 'description' in data:
            fset.description = data['description'].strip()
        
        fset.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Flashcard set updated',
            'set': fset.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to update flashcard set', 'message': str(e)}), 500

@flashcards_bp.route('/sets/<set_id>', methods=['DELETE'])
@jwt_required()
def delete_flashcard_set(set_id):
    """Delete flashcard set"""
    try:
        user_id = get_jwt_identity()
        fset = FlashcardSet.query.filter_by(id=set_id, user_id=user_id).first()
        
        if not fset:
            return jsonify({'error': 'Flashcard set not found'}), 404
        
        db.session.delete(fset)
        db.session.commit()
        
        return jsonify({'message': 'Flashcard set deleted'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to delete flashcard set', 'message': str(e)}), 500

@flashcards_bp.route('/<set_id>/add', methods=['POST'])
@jwt_required()
def add_flashcard(set_id):
    """Add flashcard to set"""
    try:
        user_id = get_jwt_identity()
        fset = FlashcardSet.query.filter_by(id=set_id, user_id=user_id).first()
        
        if not fset:
            return jsonify({'error': 'Flashcard set not found'}), 404
        
        data = request.get_json()
        
        if not data or 'front' not in data or 'back' not in data:
            return jsonify({'error': 'Front and back are required'}), 400
        
        front = data.get('front', '').strip()
        back = data.get('back', '').strip()
        
        if not front or not back:
            return jsonify({'error': 'Front and back cannot be empty'}), 400
        
        card = Flashcard(
            id=str(uuid.uuid4()),
            set_id=set_id,
            front=front,
            back=back
        )
        
        db.session.add(card)
        fset.total_cards += 1
        db.session.commit()
        
        return jsonify({
            'message': 'Flashcard added',
            'card': card.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to add flashcard', 'message': str(e)}), 500

@flashcards_bp.route('/<card_id>', methods=['PUT'])
@jwt_required()
def update_flashcard(card_id):
    """Update flashcard"""
    try:
        user_id = get_jwt_identity()
        card = Flashcard.query.join(FlashcardSet).filter(
            Flashcard.id == card_id,
            FlashcardSet.user_id == user_id
        ).first()
        
        if not card:
            return jsonify({'error': 'Flashcard not found'}), 404
        
        data = request.get_json()
        
        if 'front' in data:
            front = data['front'].strip()
            if front:
                card.front = front
        
        if 'back' in data:
            back = data['back'].strip()
            if back:
                card.back = back
        
        db.session.commit()
        
        return jsonify({
            'message': 'Flashcard updated',
            'card': card.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to update flashcard', 'message': str(e)}), 500

@flashcards_bp.route('/<card_id>', methods=['DELETE'])
@jwt_required()
def delete_flashcard(card_id):
    """Delete flashcard"""
    try:
        user_id = get_jwt_identity()
        card = Flashcard.query.join(FlashcardSet).filter(
            Flashcard.id == card_id,
            FlashcardSet.user_id == user_id
        ).first()
        
        if not card:
            return jsonify({'error': 'Flashcard not found'}), 404
        
        set_id = card.set_id
        db.session.delete(card)
        
        fset = FlashcardSet.query.get(set_id)
        if fset:
            fset.total_cards = max(0, fset.total_cards - 1)
        
        db.session.commit()
        
        return jsonify({'message': 'Flashcard deleted'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to delete flashcard', 'message': str(e)}), 500

@flashcards_bp.route('/sets/<set_id>/generate-from-note', methods=['POST'])
@jwt_required()
def generate_flashcards_from_note(set_id):
    """Generate flashcards from a note using AI"""
    try:
        user_id = get_jwt_identity()
        
        fset = FlashcardSet.query.filter_by(id=set_id, user_id=user_id).first()
        if not fset:
            return jsonify({'error': 'Flashcard set not found'}), 404
        
        data = request.get_json()
        note_id = data.get('note_id')
        num_cards = data.get('num_cards', 10)
        
        if not note_id:
            return jsonify({'error': 'note_id is required'}), 400
        
        note = Note.query.filter_by(id=note_id, user_id=user_id).first()
        if not note:
            return jsonify({'error': 'Note not found'}), 404
        
        # Generate flashcards using AI
        generated_cards = ai_service.generate_flashcards(note.content, num_cards)
        
        if not generated_cards:
            return jsonify({'error': 'Failed to generate flashcards'}), 500
        
        # Add cards to set
        added_cards = []
        for card_data in generated_cards:
            card = Flashcard(
                id=str(uuid.uuid4()),
                set_id=set_id,
                front=card_data['front'],
                back=card_data['back']
            )
            db.session.add(card)
            added_cards.append(card.to_dict())
        
        fset.total_cards += len(added_cards)
        fset.auto_generated = True
        db.session.commit()
        
        return jsonify({
            'message': f'{len(added_cards)} flashcards generated',
            'cards': added_cards
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to generate flashcards', 'message': str(e)}), 500

@flashcards_bp.route('/sets/<set_id>/study', methods=['GET'])
@jwt_required()
def get_study_cards(set_id):
    """Get cards due for review (spaced repetition)"""
    try:
        user_id = get_jwt_identity()
        fset = FlashcardSet.query.filter_by(id=set_id, user_id=user_id).first()
        
        if not fset:
            return jsonify({'error': 'Flashcard set not found'}), 404
        
        # Get cards due for review
        cards_due = Flashcard.query.filter(
            Flashcard.set_id == set_id,
            Flashcard.next_review <= datetime.utcnow()
        ).all()
        
        if not cards_due:
            # If no cards due, get new cards
            cards_due = Flashcard.query.filter_by(set_id=set_id).filter(
                Flashcard.repetitions == 0
            ).limit(10).all()
        
        return jsonify({
            'set': fset.to_dict(),
            'cards': [card.to_dict() for card in cards_due],
            'total_due': len(cards_due)
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get study cards', 'message': str(e)}), 500

@flashcards_bp.route('/<card_id>/review', methods=['POST'])
@jwt_required()
def review_flashcard(card_id):
    """Record flashcard review and apply spaced repetition algorithm"""
    try:
        user_id = get_jwt_identity()
        
        card = Flashcard.query.join(FlashcardSet).filter(
            Flashcard.id == card_id,
            FlashcardSet.user_id == user_id
        ).first()
        
        if not card:
            return jsonify({'error': 'Flashcard not found'}), 404
        
        data = request.get_json()
        
        if 'quality' not in data:
            return jsonify({'error': 'Quality rating is required'}), 400
        
        quality = data.get('quality')  # 0-5 scale
        
        if not isinstance(quality, int) or quality < 0 or quality > 5:
            return jsonify({'error': 'Quality must be between 0 and 5'}), 400
        
        # Apply SM-2 algorithm
        card = sr_service.apply_sm2(card, quality)
        card.last_reviewed = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Card review recorded',
            'card': card.to_dict(),
            'next_review': card.next_review.isoformat()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to record review', 'message': str(e)}), 500

@flashcards_bp.route('/sets/<set_id>/bulk-add', methods=['POST'])
@jwt_required()
def bulk_add_flashcards(set_id):
    """Add multiple flashcards at once"""
    try:
        user_id = get_jwt_identity()
        fset = FlashcardSet.query.filter_by(id=set_id, user_id=user_id).first()
        
        if not fset:
            return jsonify({'error': 'Flashcard set not found'}), 404
        
        data = request.get_json()
        
        if not data or 'cards' not in data:
            return jsonify({'error': 'Cards array is required'}), 400
        
        cards_data = data.get('cards', [])
        
        if not isinstance(cards_data, list) or len(cards_data) == 0:
            return jsonify({'error': 'Invalid cards format'}), 400
        
        if len(cards_data) > 100:
            return jsonify({'error': 'Maximum 100 cards per request'}), 400
        
        added_cards = []
        for card_data in cards_data:
            front = card_data.get('front', '').strip()
            back = card_data.get('back', '').strip()
            
            if front and back:
                card = Flashcard(
                    id=str(uuid.uuid4()),
                    set_id=set_id,
                    front=front,
                    back=back
                )
                db.session.add(card)
                added_cards.append(card.to_dict())
        
        fset.total_cards += len(added_cards)
        db.session.commit()
        
        return jsonify({
            'message': f'{len(added_cards)} flashcards added',
            'cards': added_cards
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to add flashcards', 'message': str(e)}), 500

@flashcards_bp.route('/sets/<set_id>/stats', methods=['GET'])
@jwt_required()
def get_set_statistics(set_id):
    """Get detailed statistics for a flashcard set"""
    try:
        user_id = get_jwt_identity()
        fset = FlashcardSet.query.filter_by(id=set_id, user_id=user_id).first()
        
        if not fset:
            return jsonify({'error': 'Flashcard set not found'}), 404
        
        cards = Flashcard.query.filter_by(set_id=set_id).all()
        
        total_cards = len(cards)
        cards_due = sum(1 for c in cards if c.next_review <= datetime.utcnow())
        mastered = sum(1 for c in cards if c.ease_factor >= 2.9)
        learning = sum(1 for c in cards if 0 < c.repetitions < 3)
        new = sum(1 for c in cards if c.repetitions == 0)
        
        if total_cards == 0:
            accuracy = 0
        else:
            total_correct = sum(1 for c in cards if c.ease_factor > 2.5)
            accuracy = (total_correct / total_cards) * 100
        
        avg_ease = sum(c.ease_factor for c in cards) / total_cards if total_cards > 0 else 0
        avg_interval = sum(c.interval for c in cards) / total_cards if total_cards > 0 else 0
        
        return jsonify({
            'set_name': fset.name,
            'stats': {
                'total_cards': total_cards,
                'cards_due': cards_due,
                'mastered': mastered,
                'learning': learning,
                'new': new,
                'accuracy_percentage': round(accuracy, 2),
                'average_ease': round(avg_ease, 2),
                'average_interval_days': round(avg_interval, 2),
                'total_reviews': fset.reviewed_count
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get statistics', 'message': str(e)}), 500

@flashcards_bp.route('/export/<set_id>', methods=['GET'])
@jwt_required()
def export_flashcards(set_id):
    """Export flashcard set"""
    try:
        user_id = get_jwt_identity()
        fset = FlashcardSet.query.filter_by(id=set_id, user_id=user_id).first()
        
        if not fset:
            return jsonify({'error': 'Flashcard set not found'}), 404
        
        cards = Flashcard.query.filter_by(set_id=set_id).all()
        
        export_format = request.args.get('format', 'csv')
        
        if export_format == 'csv':
            csv_content = "Front,Back\n"
            for card in cards:
                csv_content += f'"{card.front}","{card.back}"\n'
            
            return jsonify({
                'format': 'csv',
                'content': csv_content,
                'filename': f"{fset.name.replace(' ', '_')}.csv"
            }), 200
        
        elif export_format == 'json':
            return jsonify({
                'format': 'json',
                'set': fset.to_dict(),
                'cards': [card.to_dict() for card in cards],
                'filename': f"{fset.name.replace(' ', '_')}.json"
            }), 200
        
        else:
            return jsonify({'error': 'Invalid export format'}), 400
            
    except Exception as e:
        return jsonify({'error': 'Export failed', 'message': str(e)}), 500

# backend/routes.py (Part 4 - Analytics Routes)
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta

from models import db, StudySession, Note, FlashcardSet, Flashcard, User, LearningGoal
from services import AnalyticsService, SpacedRepetitionService

analytics_bp = Blueprint('analytics', __name__, url_prefix='/api/analytics')

@analytics_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def get_dashboard_stats():
    """Get dashboard statistics"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        stats = AnalyticsService.get_user_study_stats(user_id, days=30)
        weekly_time = AnalyticsService.get_weekly_study_time(user_id)
        performance = AnalyticsService.get_performance_metrics(user_id)
        topic_dist = AnalyticsService.get_topic_distribution(user_id)
        
        return jsonify({
            'user': {
                'name': user.name,
                'study_streak': user.study_streak,
                'total_points': user.total_points
            },
            'stats': stats,
            'weekly_time': weekly_time,
            'performance': performance,
            'topics': topic_dist
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to fetch analytics', 'message': str(e)}), 500

@analytics_bp.route('/study-sessions', methods=['GET'])
@jwt_required()
def get_study_sessions():
    """Get user's study sessions"""
    try:
        user_id = get_jwt_identity()
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        session_type = request.args.get('type')
        
        query = StudySession.query.filter_by(user_id=user_id)
        
        if session_type:
            query = query.filter_by(session_type=session_type)
        
        paginated = query.order_by(StudySession.started_at.desc()).paginate(
            page=page,
            per_page=per_page
        )
        
        return jsonify({
            'sessions': [s.to_dict() for s in paginated.items],
            'pagination': {
                'total': paginated.total,
                'pages': paginated.pages,
                'current_page': page
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to fetch sessions', 'message': str(e)}), 500

@analytics_bp.route('/study-session', methods=['POST'])
@jwt_required()
def create_study_session():
    """Create new study session"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        session_type = data.get('session_type', 'general')
        duration_minutes = data.get('duration_minutes', 0)
        cards_studied = data.get('cards_studied', 0)
        correct_answers = data.get('correct_answers', 0)
        note_id = data.get('note_id')
        
        session = StudySession(
            user_id=user_id,
            note_id=note_id,
            session_type=session_type,
            duration_minutes=duration_minutes,
            cards_studied=cards_studied,
            correct_answers=correct_answers
        )
        
        session.accuracy_percentage = session.calculate_accuracy()
        
        db.session.add(session)
        
        # Update user's study streak
        user = User.query.get(user_id)
        today = datetime.utcnow().date()
        last_study = user.last_study_date.date() if user.last_study_date else None
        
        if last_study != today:
            if last_study == today - timedelta(days=1):
                user.study_streak += 1
            else:
                user.study_streak = 1
            user.last_study_date = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Study session recorded',
            'session': session.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to create session', 'message': str(e)}), 500

@analytics_bp.route('/learning-goals', methods=['GET'])
@jwt_required()
def get_learning_goals():
    """Get user's learning goals"""
    try:
        user_id = get_jwt_identity()
        
        goals = LearningGoal.query.filter_by(user_id=user_id).order_by(
            LearningGoal.target_date.asc()
        ).all()
        
        return jsonify({
            'goals': [g.to_dict() for g in goals]
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to fetch goals', 'message': str(e)}), 500

@analytics_bp.route('/learning-goals', methods=['POST'])
@jwt_required()
def create_learning_goal():
    """Create new learning goal"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data or 'title' not in data or 'target_value' not in data:
            return jsonify({'error': 'Missing required fields'}), 400
        
        title = data.get('title', '').strip()
        target_value = data.get('target_value', 0)
        goal_type = data.get('goal_type', 'general')
        priority = data.get('priority', 'medium')
        target_date = data.get('target_date')
        description = data.get('description', '')
        
        if not title or target_value <= 0:
            return jsonify({'error': 'Invalid goal parameters'}), 400
        
        if target_date:
            target_date = datetime.fromisoformat(target_date)
        else:
            target_date = datetime.utcnow() + timedelta(days=30)
        
        goal = LearningGoal(
            user_id=user_id,
            title=title,
            description=description,
            target_value=target_value,
            goal_type=goal_type,
            priority=priority,
            target_date=target_date
        )
        
        db.session.add(goal)
        db.session.commit()
        
        return jsonify({
            'message': 'Learning goal created',
            'goal': goal.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to create goal', 'message': str(e)}), 500

@analytics_bp.route('/learning-goals/<goal_id>', methods=['PUT'])
@jwt_required()
def update_learning_goal(goal_id):
    """Update learning goal progress"""
    try:
        user_id = get_jwt_identity()
        goal = LearningGoal.query.filter_by(id=goal_id, user_id=user_id).first()
        
        if not goal:
            return jsonify({'error': 'Goal not found'}), 404
        
        data = request.get_json()
        
        if 'current_value' in data:
            goal.current_value = data['current_value']
            
            if goal.current_value >= goal.target_value:
                goal.is_completed = True
        
        if 'title' in data:
            goal.title = data['title'].strip()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Goal updated',
            'goal': goal.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to update goal', 'message': str(e)}), 500

@analytics_bp.route('/learning-goals/<goal_id>', methods=['DELETE'])
@jwt_required()
def delete_learning_goal(goal_id):
    """Delete learning goal"""
    try:
        user_id = get_jwt_identity()
        goal = LearningGoal.query.filter_by(id=goal_id, user_id=user_id).first()
        
        if not goal:
            return jsonify({'error': 'Goal not found'}), 404
        
        db.session.delete(goal)
        db.session.commit()
        
        return jsonify({'message': 'Goal deleted'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to delete goal', 'message': str(e)}), 500

@analytics_bp.route('/progress', methods=['GET'])
@jwt_required()
def get_progress_report():
    """Get comprehensive progress report"""
    try:
        user_id = get_jwt_identity()
        
        days = request.args.get('days', 30, type=int)
        start_date = datetime.utcnow() - timedelta(days=days)
        
        stats = AnalyticsService.get_user_study_stats(user_id, days=days)
        performance = AnalyticsService.get_performance_metrics(user_id, days=days)
        
        goals = LearningGoal.query.filter_by(user_id=user_id).all()
        
        return jsonify({
            'period_days': days,
            'stats': stats,
            'performance': performance,
            'goals': [g.to_dict() for g in goals],
            'report_generated_at': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to generate report', 'message': str(e)}), 500

# backend/routes.py (Part 5 - AI Tutor Routes)
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
import uuid

from models import db, User, Note, AIMeeting, Collaboration, FlashcardSet
from services import AIService

ai_bp = Blueprint('ai', __name__, url_prefix='/api/ai')
ai_service = AIService()

@ai_bp.route('/tutor/ask', methods=['POST'])
@jwt_required()
def ask_tutor():
    """AI Tutor - Answer student questions"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data or 'question' not in data:
            return jsonify({'error': 'Question is required'}), 400
        
        question = data.get('question', '').strip()
        note_id = data.get('note_id')
        topic = data.get('topic')
        
        if not question or len(question) < 3:
            return jsonify({'error': 'Question too short (min 3 characters)'}), 400
        
        if len(question) > 2000:
            return jsonify({'error': 'Question too long (max 2000 characters)'}), 400
        
        # Get context from note if provided
        context = None
        if note_id:
            note = Note.query.filter_by(id=note_id, user_id=user_id).first()
            if note:
                context = note.content[:1500]
        
        # Generate answer using AI
        answer = ai_service.answer_question(question, context)
        
        if not answer:
            return jsonify({'error': 'Failed to generate answer'}), 500
        
        # Save conversation
        meeting = AIMeeting(
            id=str(uuid.uuid4()),
            user_id=user_id,
            question=question,
            answer=answer,
            related_note_id=note_id,
            topic=topic
        )
        
        db.session.add(meeting)
        db.session.commit()
        
        return jsonify({
            'message': 'Answer generated',
            'question': question,
            'answer': answer,
            'meeting_id': meeting.id
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to get answer', 'message': str(e)}), 500

@ai_bp.route('/tutor/history', methods=['GET'])
@jwt_required()
def get_tutor_history():
    """Get AI tutor conversation history"""
    try:
        user_id = get_jwt_identity()
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        topic = request.args.get('topic')
        
        query = AIMeeting.query.filter_by(user_id=user_id)
        
        if topic:
            query = query.filter_by(topic=topic)
        
        paginated = query.order_by(AIMeeting.created_at.desc()).paginate(
            page=page,
            per_page=per_page
        )
        
        return jsonify({
            'history': [m.to_dict() for m in paginated.items],
            'pagination': {
                'total': paginated.total,
                'pages': paginated.pages,
                'current_page': page
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to fetch history', 'message': str(e)}), 500

@ai_bp.route('/tutor/feedback/<meeting_id>', methods=['POST'])
@jwt_required()
def rate_answer(meeting_id):
    """Rate AI tutor answer helpfulness"""
    try:
        user_id = get_jwt_identity()
        
        meeting = AIMeeting.query.filter_by(id=meeting_id, user_id=user_id).first()
        if not meeting:
            return jsonify({'error': 'Meeting not found'}), 404
        
        data = request.get_json()
        helpful = data.get('helpful', True)
        
        meeting.helpful = helpful
        db.session.commit()
        
        return jsonify({
            'message': 'Feedback recorded',
            'helpful': helpful
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to record feedback', 'message': str(e)}), 500

@ai_bp.route('/study-plan/generate', methods=['POST'])
@jwt_required()
def generate_study_plan():
    """Generate personalized AI study plan"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        duration_days = data.get('duration_days', 7)
        note_ids = data.get('note_ids', [])
        
        if not isinstance(note_ids, list) or len(note_ids) == 0:
            return jsonify({'error': 'At least one note is required'}), 400
        
        if duration_days < 1 or duration_days > 90:
            return jsonify({'error': 'Duration must be between 1 and 90 days'}), 400
        
        # Get notes content
        notes = Note.query.filter(
            Note.id.in_(note_ids),
            Note.user_id == user_id
        ).all()
        
        if not notes:
            return jsonify({'error': 'Notes not found'}), 404
        
        notes_content = [n.content for n in notes]
        
        # Generate plan using AI
        plan_data = ai_service.generate_study_plan(notes_content, duration_days)
        
        if not plan_data:
            return jsonify({'error': 'Failed to generate plan'}), 500
        
        from models import StudyPlan
        
        study_plan = StudyPlan(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=f"Study Plan - {', '.join([n.title for n in notes[:2]])}",
            description=f"AI-generated plan for {len(notes)} notes over {duration_days} days",
            content=plan_data,
            duration_days=duration_days,
            target_date=datetime.utcnow() + __import__('datetime').timedelta(days=duration_days)
        )
        
        db.session.add(study_plan)
        db.session.commit()
        
        return jsonify({
            'message': 'Study plan generated',
            'plan': study_plan.to_dict(),
            'plan_content': plan_data.get('plan')
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to generate plan', 'message': str(e)}), 500

@ai_bp.route('/study-plan/<plan_id>', methods=['GET'])
@jwt_required()
def get_study_plan(plan_id):
    """Get study plan details"""
    try:
        user_id = get_jwt_identity()
        from models import StudyPlan
        
        plan = StudyPlan.query.filter_by(id=plan_id, user_id=user_id).first()
        
        if not plan:
            return jsonify({'error': 'Study plan not found'}), 404
        
        return jsonify({
            'plan': plan.to_dict(),
            'content': plan.content
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to fetch plan', 'message': str(e)}), 500

@ai_bp.route('/study-plan/<plan_id>/update-progress', methods=['POST'])
@jwt_required()
def update_plan_progress(plan_id):
    """Update study plan progress"""
    try:
        user_id = get_jwt_identity()
        from models import StudyPlan
        
        plan = StudyPlan.query.filter_by(id=plan_id, user_id=user_id).first()
        
        if not plan:
            return jsonify({'error': 'Study plan not found'}), 404
        
        data = request.get_json()
        progress = data.get('progress_percentage', 0)
        
        if not isinstance(progress, (int, float)) or progress < 0 or progress > 100:
            return jsonify({'error': 'Progress must be between 0 and 100'}), 400
        
        plan.progress_percentage = progress
        if progress >= 100:
            plan.is_active = False
        
        db.session.commit()
        
        return jsonify({
            'message': 'Progress updated',
            'plan': plan.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to update progress', 'message': str(e)}), 500

@ai_bp.route('/practice-problems', methods=['POST'])
@jwt_required()
def generate_practice_problems():
    """Generate practice problems for a topic"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data or 'topic' not in data:
            return jsonify({'error': 'Topic is required'}), 400
        
        topic = data.get('topic', '').strip()
        difficulty = data.get('difficulty', 'medium')
        num_problems = data.get('num_problems', 5)
        
        if not topic or len(topic) < 2:
            return jsonify({'error': 'Topic too short'}), 400
        
        if difficulty not in ['easy', 'medium', 'hard']:
            return jsonify({'error': 'Invalid difficulty level'}), 400
        
        if num_problems < 1 or num_problems > 20:
            return jsonify({'error': 'Number of problems must be between 1 and 20'}), 400
        
        # Generate problems using AI
        problems = ai_service.generate_practice_problems(topic, difficulty, num_problems)
        
        if not problems:
            return jsonify({'error': 'Failed to generate problems'}), 500
        
        return jsonify({
            'message': 'Practice problems generated',
            'topic': topic,
            'difficulty': difficulty,
            'problems': problems
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to generate problems', 'message': str(e)}), 500

@ai_bp.route('/summarize-batch', methods=['POST'])
@jwt_required()
def summarize_batch_notes():
    """Summarize multiple notes at once"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data or 'note_ids' not in data:
            return jsonify({'error': 'note_ids required'}), 400
        
        note_ids = data.get('note_ids', [])
        
        if not isinstance(note_ids, list) or len(note_ids) == 0:
            return jsonify({'error': 'At least one note required'}), 400
        
        if len(note_ids) > 10:
            return jsonify({'error': 'Maximum 10 notes per batch'}), 400
        
        notes = Note.query.filter(
            Note.id.in_(note_ids),
            Note.user_id == user_id
        ).all()
        
        if not notes:
            return jsonify({'error': 'Notes not found'}), 404
        
        summaries = []
        for note in notes:
            summary = ai_service.generate_summary(note.content)
            if summary:
                note.summary = summary
                summaries.append({
                    'note_id': note.id,
                    'title': note.title,
                    'summary': summary
                })
        
        db.session.commit()
        
        return jsonify({
            'message': f'{len(summaries)} summaries generated',
            'summaries': summaries
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to summarize', 'message': str(e)}), 500

@ai_bp.route('/organize-batch', methods=['POST'])
@jwt_required()
def organize_batch_notes():
    """Organize multiple notes at once"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data or 'note_ids' not in data:
            return jsonify({'error': 'note_ids required'}), 400
        
        note_ids = data.get('note_ids', [])
        
        if not isinstance(note_ids, list) or len(note_ids) == 0:
            return jsonify({'error': 'At least one note required'}), 400
        
        if len(note_ids) > 5:
            return jsonify({'error': 'Maximum 5 notes per batch'}), 400
        
        notes = Note.query.filter(
            Note.id.in_(note_ids),
            Note.user_id == user_id
        ).all()
        
        if not notes:
            return jsonify({'error': 'Notes not found'}), 404
        
        organized = []
        for note in notes:
            organized_content = ai_service.organize_content(note.content)
            concepts = ai_service.extract_key_concepts(note.content)
            
            if organized_content:
                note.content = organized_content
                note.key_concepts = concepts
                note.auto_organized = True
                
                organized.append({
                    'note_id': note.id,
                    'title': note.title,
                    'key_concepts': concepts
                })
        
        db.session.commit()
        
        return jsonify({
            'message': f'{len(organized)} notes organized',
            'organized_notes': organized
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to organize', 'message': str(e)}), 500


# backend/routes.py (Part 6 - Collaboration Routes)
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
import uuid

from models import db, User, Note, Collaboration, FlashcardSet

collaborate_bp = Blueprint('collaborate', __name__, url_prefix='/api/collaborate')

@collaborate_bp.route('/share-note', methods=['POST'])
@jwt_required()
def share_note():
    """Share note with other users"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data or 'note_id' not in data or 'share_with_email' not in data:
            return jsonify({'error': 'Missing required fields'}), 400
        
        note_id = data.get('note_id')
        share_with_email = data.get('share_with_email', '').strip().lower()
        permission_level = data.get('permission_level', 'view')
        
        # Validate note ownership
        note = Note.query.filter_by(id=note_id, user_id=user_id).first()
        if not note:
            return jsonify({'error': 'Note not found'}), 404
        
        # Find recipient user
        recipient = User.query.filter_by(email=share_with_email).first()
        if not recipient:
            return jsonify({'error': 'User not found'}), 404
        
        if recipient.id == user_id:
            return jsonify({'error': 'Cannot share with yourself'}), 400
        
        # Check if already shared
        existing = Collaboration.query.filter_by(
            note_id=note_id,
            owner_id=user_id,
            shared_with_id=recipient.id
        ).first()
        
        if existing:
            return jsonify({'error': 'Already shared with this user'}), 409
        
        # Create collaboration
        collaboration = Collaboration(
            id=str(uuid.uuid4()),
            note_id=note_id,
            owner_id=user_id,
            shared_with_id=recipient.id,
            permission_level=permission_level
        )
        
        db.session.add(collaboration)
        db.session.commit()
        
        return jsonify({
            'message': f'Note shared with {recipient.name}',
            'collaboration': collaboration.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to share note', 'message': str(e)}), 500

@collaborate_bp.route('/shared-with-me', methods=['GET'])
@jwt_required()
def get_shared_notes():
    """Get notes shared with current user"""
    try:
        user_id = get_jwt_identity()
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        collaborations = Collaboration.query.filter_by(
            shared_with_id=user_id
        ).order_by(Collaboration.created_at.desc()).paginate(
            page=page,
            per_page=per_page
        )
        
        shared_notes = []
        for collab in collaborations.items:
            note_dict = collab.note.to_dict()
            note_dict['shared_by'] = collab.owner.name
            note_dict['permission_level'] = collab.permission_level
            shared_notes.append(note_dict)
        
        return jsonify({
            'notes': shared_notes,
            'pagination': {
                'total': collaborations.total,
                'pages': collaborations.pages,
                'current_page': page
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to fetch shared notes', 'message': str(e)}), 500

@collaborate_bp.route('/my-shares', methods=['GET'])
@jwt_required()
def get_my_shares():
    """Get notes shared by current user"""
    try:
        user_id = get_jwt_identity()
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        collaborations = Collaboration.query.filter_by(
            owner_id=user_id
        ).order_by(Collaboration.created_at.desc()).paginate(
            page=page,
            per_page=per_page
        )
        
        shares = []
        for collab in collaborations.items:
            note_dict = collab.note.to_dict()
            note_dict['shared_with'] = collab.shared_with.name
            note_dict['shared_with_email'] = collab.shared_with.email
            note_dict['permission_level'] = collab.permission_level
            note_dict['created_at'] = collab.created_at.isoformat()
            shares.append(note_dict)
        
        return jsonify({
            'shares': shares,
            'pagination': {
                'total': collaborations.total,
                'pages': collaborations.pages,
                'current_page': page
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to fetch shares', 'message': str(e)}), 500

@collaborate_bp.route('/revoke-share/<collab_id>', methods=['DELETE'])
@jwt_required()
def revoke_share(collab_id):
    """Revoke note sharing"""
    try:
        user_id = get_jwt_identity()
        
        collab = Collaboration.query.filter_by(id=collab_id, owner_id=user_id).first()
        if not collab:
            return jsonify({'error': 'Share not found'}), 404
        
        note_title = collab.note.title
        shared_with_name = collab.shared_with.name
        
        db.session.delete(collab)
        db.session.commit()
        
        return jsonify({
            'message': f'Share revoked: {note_title} from {shared_with_name}'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to revoke share', 'message': str(e)}), 500

@collaborate_bp.route('/update-permission/<collab_id>', methods=['PUT'])
@jwt_required()
def update_permission(collab_id):
    """Update collaboration permission level"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data or 'permission_level' not in data:
            return jsonify({'error': 'permission_level required'}), 400
        
        permission_level = data.get('permission_level')
        
        if permission_level not in ['view', 'edit', 'admin']:
            return jsonify({'error': 'Invalid permission level'}), 400
        
        collab = Collaboration.query.filter_by(id=collab_id, owner_id=user_id).first()
        if not collab:
            return jsonify({'error': 'Share not found'}), 404
        
        collab.permission_level = permission_level
        db.session.commit()
        
        return jsonify({
            'message': 'Permission updated',
            'collaboration': collab.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to update permission', 'message': str(e)}), 500

@collaborate_bp.route('/share-flashcards', methods=['POST'])
@jwt_required()
def share_flashcards():
    """Share flashcard set with other users"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data or 'set_id' not in data or 'share_with_email' not in data:
            return jsonify({'error': 'Missing required fields'}), 400
        
        set_id = data.get('set_id')
        share_with_email = data.get('share_with_email', '').strip().lower()
        
        # Validate set ownership
        fset = FlashcardSet.query.filter_by(id=set_id, user_id=user_id).first()
        if not fset:
            return jsonify({'error': 'Flashcard set not found'}), 404
        
        # Find recipient
        recipient = User.query.filter_by(email=share_with_email).first()
        if not recipient:
            return jsonify({'error': 'User not found'}), 404
        
        if recipient.id == user_id:
            return jsonify({'error': 'Cannot share with yourself'}), 400
        
        # Add to shared_with list
        if not fset.shared_with:
            fset.shared_with = []
        
        if recipient.id in fset.shared_with:
            return jsonify({'error': 'Already shared with this user'}), 409
        
        fset.shared_with.append(recipient.id)
        db.session.commit()
        
        return jsonify({
            'message': f'Flashcard set shared with {recipient.name}',
            'shared_with': recipient.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to share flashcards', 'message': str(e)}), 500

@collaborate_bp.route('/study-groups', methods=['GET'])
@jwt_required()
def get_study_groups():
    """Get user's study groups"""
    try:
        user_id = get_jwt_identity()
        
        # Get all collaborations
        shared_with_me = Collaboration.query.filter_by(shared_with_id=user_id).all()
        my_shares = Collaboration.query.filter_by(owner_id=user_id).all()
        
        # Extract unique collaborators
        collaborators = {}
        
        for collab in shared_with_me:
            owner_id = collab.owner_id
            if owner_id not in collaborators:
                collaborators[owner_id] = {
                    'user': collab.owner.to_dict(),
                    'shared_notes': 0,
                    'shared_sets': 0
                }
            collaborators[owner_id]['shared_notes'] += 1
        
        for collab in my_shares:
            shared_id = collab.shared_with_id
            if shared_id not in collaborators:
                collaborators[shared_id] = {
                    'user': collab.shared_with.to_dict(),
                    'shared_notes': 0,
                    'shared_sets': 0
                }
            collaborators[shared_id]['shared_notes'] += 1
        
        return jsonify({
            'study_groups': list(collaborators.values()),
            'total_collaborators': len(collaborators)
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to fetch study groups', 'message': str(e)}), 500

@collaborate_bp.route('/public-notes', methods=['GET'])
def get_public_notes():
    """Get publicly available notes (for discovery)"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        topic = request.args.get('topic')
        
        query = Note.query.filter_by(is_shared=True)
        
        if topic:
            query = query.filter(Note.tags.astext.ilike(f'%{topic}%'))
        
        paginated = query.order_by(Note.updated_at.desc()).paginate(
            page=page,
            per_page=per_page
        )
        
        notes_data = []
        for note in paginated.items:
            note_dict = note.to_dict()
            note_dict['author'] = note.author.name
            notes_data.append(note_dict)
        
        return jsonify({
            'notes': notes_data,
            'pagination': {
                'total': paginated.total,
                'pages': paginated.pages,
                'current_page': page
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to fetch public notes', 'message': str(e)}), 500


# backend/routes.py (Part 7 - Dashboard Routes)
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta

from models import db, User, Note, FlashcardSet, StudySession
from services import AnalyticsService

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api/dashboard')

@dashboard_bp.route('', methods=['GET'])
@jwt_required()
def get_dashboard():
    """Get comprehensive dashboard data"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Count statistics
        notes_count = Note.query.filter_by(user_id=user_id).count()
        flashcard_sets = FlashcardSet.query.filter_by(user_id=user_id).all()
        total_cards = sum(fs.total_cards for fs in flashcard_sets)
        
        # Study time this week
        week_ago = datetime.utcnow() - timedelta(days=7)
        sessions = StudySession.query.filter(
            StudySession.user_id == user_id,
            StudySession.started_at >= week_ago
        ).all()
        
        total_study_time = sum(s.duration_minutes for s in sessions if s.duration_minutes) or 0
        
        # Recent activity
        recent_notes = Note.query.filter_by(user_id=user_id).order_by(
            Note.updated_at.desc()
        ).limit(5).all()
        
        recent_activity = []
        for note in recent_notes:
            recent_activity.append({
                'icon': '📝',
                'title': f'Updated: {note.title}',
                'time': note.updated_at.isoformat()
            })
        
        # Performance metrics
        performance = AnalyticsService.get_performance_metrics(user_id, days=7)
        
        return jsonify({
            'user': {
                'name': user.name,
                'email': user.email,
                'avatar_url': user.avatar_url
            },
            'statistics': {
                'notes_count': notes_count,
                'flashcard_sets': len(flashcard_sets),
                'total_flashcards': total_cards,
                'study_time_hours': round(total_study_time / 60, 1),
                'study_streak': user.study_streak,
                'total_points': user.total_points
            },
            'recent_activity': recent_activity,
            'performance': performance,
            'week_study_time': round(total_study_time, 0)
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to fetch dashboard', 'message': str(e)}), 500

@dashboard_bp.route('/quick-stats', methods=['GET'])
@jwt_required()
def get_quick_stats():
    """Get quick statistics for dashboard cards"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        notes = Note.query.filter_by(user_id=user_id).count()
        
        sessions = StudySession.query.filter(
            StudySession.user_id == user_id,
            StudySession.started_at >= datetime.utcnow() - timedelta(days=7)
        ).all()
        
        study_time = sum(s.duration_minutes for s in sessions if s.duration_minutes) or 0
        
        accuracy = 0
        if sessions:
            total_correct = sum(s.correct_answers for s in sessions)
            total_attempted = sum(s.cards_studied for s in sessions)
            if total_attempted > 0:
                accuracy = (total_correct / total_attempted) * 100
        
        return jsonify({
            'notes_count': notes,
            'study_time': f"{round(study_time / 60, 1)}h",
            'accuracy': f"{round(accuracy, 0)}%",
            'streak': user.study_streak
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to fetch quick stats', 'message': str(e)}), 500

