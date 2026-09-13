# backend/routes.py - SIMPLIFIED NO-LOGIN VERSION
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
import uuid
import secrets
import math

from models import db, User, Note, FlashcardSet, Flashcard, StudySession, AIMeeting, Collaboration, LearningGoal, StudyPlan
from services import AIService, NoteService, SpacedRepetitionService, AnalyticsService
from config import Config

# ============================================
# PART 1: AUTH ROUTES - SIMPLIFIED, NO LOGIN
# ============================================
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

DEFAULT_USER_ID = "demo-user-001"

def get_default_user():
    """Get or create default user for no-auth mode"""
    user = User.query.get(DEFAULT_USER_ID)
    if not user:
        user = User(id=DEFAULT_USER_ID, name="Demo User", email="demo@studyflow.local")
        user.set_password("demo_password")
        db.session.add(user)
        db.session.commit()
    return user

def get_current_user():
    """Get default user (no authentication)"""
    return User.query.get(DEFAULT_USER_ID) or get_default_user()

@auth_bp.route('/profile', methods=['GET'])
def get_profile():
    """Get current user profile (default user)"""
    try:
        user = get_default_user()
        
        return jsonify({
            'user': user.to_dict(),
            'stats': {
                'notes_count': Note.query.filter_by(user_id=user.id).count(),
                'study_streak': user.study_streak,
                'total_points': user.total_points
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to fetch profile', 'message': str(e)}), 500

@auth_bp.route('/profile', methods=['PUT'])
def update_profile():
    """Update user profile"""
    try:
        user = get_default_user()
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

# ============================================
# PART 2: NOTES ROUTES - NO AUTH REQUIRED
# ============================================
notes_bp = Blueprint('notes', __name__, url_prefix='/api/notes')
ai_service = AIService()
note_service = NoteService()

@notes_bp.route('', methods=['GET'])
def get_notes():
    """Get all notes with filtering"""
    try:
        user = get_current_user()
        user_id = user.id
        
        filter_type = request.args.get('filter', 'all')
        sort_by = request.args.get('sort', 'updated')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        query = Note.query.filter_by(user_id=user_id)
        
        if filter_type == 'flagged':
            query = query.filter_by(is_flagged=True)
        elif filter_type == 'shared':
            query = query.filter_by(is_shared=True)
        elif filter_type == 'recent':
            query = query.filter(Note.last_accessed >= datetime.utcnow() - timedelta(days=7))
        
        if sort_by == 'created':
            query = query.order_by(Note.created_at.desc())
        elif sort_by == 'title':
            query = query.order_by(Note.title.asc())
        else:
            query = query.order_by(Note.updated_at.desc())
        
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
def get_note(note_id):
    """Get single note by ID"""
    try:
        user = get_current_user()
        note = Note.query.filter_by(id=note_id, user_id=user.id).first()
        
        if not note:
            return jsonify({'error': 'Note not found'}), 404
        
        note.last_accessed = datetime.utcnow()
        db.session.commit()
        
        return jsonify(note.to_dict()), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to fetch note', 'message': str(e)}), 500

@notes_bp.route('', methods=['POST'])
def create_note():
    """Create new note"""
    try:
        user = get_current_user()
        data = request.get_json()
        
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
        
        if not isinstance(tags, list):
            tags = []
        tags = [tag.strip() for tag in tags if isinstance(tag, str) and tag.strip()][:10]
        
        note = Note(
            id=str(uuid.uuid4()),
            user_id=user.id,
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
def update_note(note_id):
    """Update existing note"""
    try:
        user = get_current_user()
        note = Note.query.filter_by(id=note_id, user_id=user.id).first()
        
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
def delete_note(note_id):
    """Delete note"""
    try:
        user = get_current_user()
        note = Note.query.filter_by(id=note_id, user_id=user.id).first()
        
        if not note:
            return jsonify({'error': 'Note not found'}), 404
        
        db.session.delete(note)
        db.session.commit()
        
        return jsonify({'message': 'Note deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to delete note', 'message': str(e)}), 500

@notes_bp.route('/<note_id>/flag', methods=['POST'])
def flag_note(note_id):
    """Flag/unflag note as important"""
    try:
        user = get_current_user()
        note = Note.query.filter_by(id=note_id, user_id=user.id).first()
        
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
def summarize_note(note_id):
    """Generate AI summary of note"""
    try:
        user = get_current_user()
        note = Note.query.filter_by(id=note_id, user_id=user.id).first()
        
        if not note:
            return jsonify({'error': 'Note not found'}), 404
        
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
def organize_note(note_id):
    """AI-powered note organization"""
    try:
        user = get_current_user()
        note = Note.query.filter_by(id=note_id, user_id=user.id).first()
        
        if not note:
            return jsonify({'error': 'Note not found'}), 404
        
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
def share_note(note_id):
    """Generate share link for note"""
    try:
        user = get_current_user()
        note = Note.query.filter_by(id=note_id, user_id=user.id).first()
        
        if not note:
            return jsonify({'error': 'Note not found'}), 404
        
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
def search_notes():
    """Search notes by query"""
    try:
        user = get_current_user()
        query = request.args.get('q', '').strip()
        
        if not query or len(query) < 2:
            return jsonify({'error': 'Search query too short (min 2 characters)'}), 400
        
        notes = Note.query.filter_by(user_id=user.id).filter(
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
def export_note(note_id):
    """Export note as text or markdown"""
    try:
        user = get_current_user()
        note = Note.query.filter_by(id=note_id, user_id=user.id).first()
        
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
def get_key_concepts(note_id):
    """Get AI-extracted key concepts from note"""
    try:
        user = get_current_user()
        note = Note.query.filter_by(id=note_id, user_id=user.id).first()
        
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
def bulk_delete_notes():
    """Delete multiple notes at once"""
    try:
        user = get_current_user()
        data = request.get_json()
        
        if not data or 'note_ids' not in data:
            return jsonify({'error': 'Missing note_ids'}), 400
        
        note_ids = data.get('note_ids', [])
        
        if not isinstance(note_ids, list) or len(note_ids) == 0:
            return jsonify({'error': 'Invalid note_ids'}), 400
        
        deleted_count = Note.query.filter(
            Note.id.in_(note_ids),
            Note.user_id == user.id
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
def duplicate_note(note_id):
    """Create a duplicate of a note"""
    try:
        user = get_current_user()
        original_note = Note.query.filter_by(id=note_id, user_id=user.id).first()
        
        if not original_note:
            return jsonify({'error': 'Note not found'}), 404
        
        duplicated_note = Note(
            id=str(uuid.uuid4()),
            user_id=user.id,
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
def batch_tag_notes():
    """Add tags to multiple notes"""
    try:
        user = get_current_user()
        data = request.get_json()
        
        if not data or 'note_ids' not in data or 'tags' not in data:
            return jsonify({'error': 'Missing note_ids or tags'}), 400
        
        note_ids = data.get('note_ids', [])
        new_tags = data.get('tags', [])
        
        notes = Note.query.filter(
            Note.id.in_(note_ids),
            Note.user_id == user.id
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
