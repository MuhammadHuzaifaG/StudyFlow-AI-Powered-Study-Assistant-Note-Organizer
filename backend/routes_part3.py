# backend/routes.py - PART 5, 6, 7 (AI, Collaboration, Dashboard)
# ============================================
# PART 5: AI TUTOR ROUTES - NO AUTH REQUIRED
# ============================================
ai_bp = Blueprint('ai', __name__, url_prefix='/api/ai')

@ai_bp.route('/tutor/ask', methods=['POST'])
def ask_tutor():
    """AI Tutor - Answer student questions"""
    try:
        user = get_current_user()
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
        
        context = None
        if note_id:
            note = Note.query.filter_by(id=note_id, user_id=user.id).first()
            if note:
                context = note.content[:1500]
        
        answer = ai_service.answer_question(question, context)
        
        if not answer:
            return jsonify({'error': 'Failed to generate answer'}), 500
        
        meeting = AIMeeting(
            id=str(uuid.uuid4()),
            user_id=user.id,
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
def get_tutor_history():
    """Get AI tutor conversation history"""
    try:
        user = get_current_user()
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        topic = request.args.get('topic')
        
        query = AIMeeting.query.filter_by(user_id=user.id)
        
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
def rate_answer(meeting_id):
    """Rate AI tutor answer helpfulness"""
    try:
        user = get_current_user()
        
        meeting = AIMeeting.query.filter_by(id=meeting_id, user_id=user.id).first()
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
def generate_study_plan():
    """Generate personalized AI study plan"""
    try:
        user = get_current_user()
        data = request.get_json()
        
        duration_days = data.get('duration_days', 7)
        note_ids = data.get('note_ids', [])
        
        if not isinstance(note_ids, list) or len(note_ids) == 0:
            return jsonify({'error': 'At least one note is required'}), 400
        
        if duration_days < 1 or duration_days > 90:
            return jsonify({'error': 'Duration must be between 1 and 90 days'}), 400
        
        notes = Note.query.filter(
            Note.id.in_(note_ids),
            Note.user_id == user.id
        ).all()
        
        if not notes:
            return jsonify({'error': 'Notes not found'}), 404
        
        notes_content = [n.content for n in notes]
        
        plan_data = ai_service.generate_study_plan(notes_content, duration_days)
        
        if not plan_data:
            return jsonify({'error': 'Failed to generate plan'}), 500
        
        study_plan = StudyPlan(
            id=str(uuid.uuid4()),
            user_id=user.id,
            title=f"Study Plan - {', '.join([n.title for n in notes[:2]])}",
            description=f"AI-generated plan for {len(notes)} notes over {duration_days} days",
            content=plan_data,
            duration_days=duration_days,
            target_date=datetime.utcnow() + timedelta(days=duration_days)
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
def get_study_plan(plan_id):
    """Get study plan details"""
    try:
        user = get_current_user()
        
        plan = StudyPlan.query.filter_by(id=plan_id, user_id=user.id).first()
        
        if not plan:
            return jsonify({'error': 'Study plan not found'}), 404
        
        return jsonify({
            'plan': plan.to_dict(),
            'content': plan.content
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to fetch plan', 'message': str(e)}), 500

@ai_bp.route('/study-plan/<plan_id>/update-progress', methods=['POST'])
def update_plan_progress(plan_id):
    """Update study plan progress"""
    try:
        user = get_current_user()
        
        plan = StudyPlan.query.filter_by(id=plan_id, user_id=user.id).first()
        
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
def generate_practice_problems():
    """Generate practice problems for a topic"""
    try:
        user = get_current_user()
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
def summarize_batch_notes():
    """Summarize multiple notes at once"""
    try:
        user = get_current_user()
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
            Note.user_id == user.id
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
def organize_batch_notes():
    """Organize multiple notes at once"""
    try:
        user = get_current_user()
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
            Note.user_id == user.id
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

# ============================================
# PART 6: COLLABORATION ROUTES - NO AUTH
# ============================================
collaborate_bp = Blueprint('collaborate', __name__, url_prefix='/api/collaborate')

@collaborate_bp.route('/share-note', methods=['POST'])
def share_note():
    """Share note with other users"""
    try:
        user = get_current_user()
        data = request.get_json()
        
        if not data or 'note_id' not in data or 'share_with_email' not in data:
            return jsonify({'error': 'Missing required fields'}), 400
        
        note_id = data.get('note_id')
        share_with_email = data.get('share_with_email', '').strip().lower()
        permission_level = data.get('permission_level', 'view')
        
        note = Note.query.filter_by(id=note_id, user_id=user.id).first()
        if not note:
            return jsonify({'error': 'Note not found'}), 404
        
        recipient = User.query.filter_by(email=share_with_email).first()
        if not recipient:
            return jsonify({'error': 'User not found'}), 404
        
        if recipient.id == user.id:
            return jsonify({'error': 'Cannot share with yourself'}), 400
        
        existing = Collaboration.query.filter_by(
            note_id=note_id,
            owner_id=user.id,
            shared_with_id=recipient.id
        ).first()
        
        if existing:
            return jsonify({'error': 'Already shared with this user'}), 409
        
        collaboration = Collaboration(
            id=str(uuid.uuid4()),
            note_id=note_id,
            owner_id=user.id,
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
def get_shared_notes():
    """Get notes shared with current user"""
    try:
        user = get_current_user()
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        collaborations = Collaboration.query.filter_by(
            shared_with_id=user.id
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
def get_my_shares():
    """Get notes shared by current user"""
    try:
        user = get_current_user()
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        collaborations = Collaboration.query.filter_by(
            owner_id=user.id
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
def revoke_share(collab_id):
    """Revoke note sharing"""
    try:
        user = get_current_user()
        
        collab = Collaboration.query.filter_by(id=collab_id, owner_id=user.id).first()
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
def update_permission(collab_id):
    """Update collaboration permission level"""
    try:
        user = get_current_user()
        data = request.get_json()
        
        if not data or 'permission_level' not in data:
            return jsonify({'error': 'permission_level required'}), 400
        
        permission_level = data.get('permission_level')
        
        if permission_level not in ['view', 'edit', 'admin']:
            return jsonify({'error': 'Invalid permission level'}), 400
        
        collab = Collaboration.query.filter_by(id=collab_id, owner_id=user.id).first()
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
def share_flashcards():
    """Share flashcard set with other users"""
    try:
        user = get_current_user()
        data = request.get_json()
        
        if not data or 'set_id' not in data or 'share_with_email' not in data:
            return jsonify({'error': 'Missing required fields'}), 400
        
        set_id = data.get('set_id')
        share_with_email = data.get('share_with_email', '').strip().lower()
        
        fset = FlashcardSet.query.filter_by(id=set_id, user_id=user.id).first()
        if not fset:
            return jsonify({'error': 'Flashcard set not found'}), 404
        
        recipient = User.query.filter_by(email=share_with_email).first()
        if not recipient:
            return jsonify({'error': 'User not found'}), 404
        
        if recipient.id == user.id:
            return jsonify({'error': 'Cannot share with yourself'}), 400
        
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
def get_study_groups():
    """Get user's study groups"""
    try:
        user = get_current_user()
        
        shared_with_me = Collaboration.query.filter_by(shared_with_id=user.id).all()
        my_shares = Collaboration.query.filter_by(owner_id=user.id).all()
        
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

# ============================================
# PART 7: DASHBOARD ROUTES - NO AUTH REQUIRED
# ============================================
dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api/dashboard')

@dashboard_bp.route('', methods=['GET'])
def get_dashboard():
    """Get comprehensive dashboard data"""
    try:
        user = get_current_user()
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        notes_count = Note.query.filter_by(user_id=user.id).count()
        flashcard_sets = FlashcardSet.query.filter_by(user_id=user.id).all()
        total_cards = sum(fs.total_cards for fs in flashcard_sets)
        
        week_ago = datetime.utcnow() - timedelta(days=7)
        sessions = StudySession.query.filter(
            StudySession.user_id == user.id,
            StudySession.started_at >= week_ago
        ).all()
        
        total_study_time = sum(s.duration_minutes for s in sessions if s.duration_minutes) or 0
        
        recent_notes = Note.query.filter_by(user_id=user.id).order_by(
            Note.updated_at.desc()
        ).limit(5).all()
        
        recent_activity = []
        for note in recent_notes:
            recent_activity.append({
                'icon': '📝',
                'title': f'Updated: {note.title}',
                'time': note.updated_at.isoformat()
            })
        
        performance = AnalyticsService.get_performance_metrics(user.id, days=7)
        
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
def get_quick_stats():
    """Get quick statistics for dashboard cards"""
    try:
        user = get_current_user()
        
        notes = Note.query.filter_by(user_id=user.id).count()
        
        sessions = StudySession.query.filter(
            StudySession.user_id == user.id,
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
