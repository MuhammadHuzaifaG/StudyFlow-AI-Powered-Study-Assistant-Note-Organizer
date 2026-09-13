# backend/routes.py - CONTINUATION (Parts 2-6)
# This is a continuation - append to the existing routes.py file

# ============================================
# PART 3: FLASHCARDS ROUTES - NO AUTH REQUIRED
# ============================================
flashcards_bp = Blueprint('flashcards', __name__, url_prefix='/api/flashcards')
sr_service = SpacedRepetitionService()

@flashcards_bp.route('/sets', methods=['GET'])
def get_flashcard_sets():
    """Get all flashcard sets for current user"""
    try:
        user = get_current_user()
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        sort_by = request.args.get('sort', 'updated')
        
        query = FlashcardSet.query.filter_by(user_id=user.id)
        
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
def create_flashcard_set():
    """Create new flashcard set"""
    try:
        user = get_current_user()
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
            user_id=user.id,
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
def get_flashcard_set(set_id):
    """Get flashcard set with all cards"""
    try:
        user = get_current_user()
        fset = FlashcardSet.query.filter_by(id=set_id, user_id=user.id).first()
        
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
def update_flashcard_set(set_id):
    """Update flashcard set"""
    try:
        user = get_current_user()
        fset = FlashcardSet.query.filter_by(id=set_id, user_id=user.id).first()
        
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
def delete_flashcard_set(set_id):
    """Delete flashcard set"""
    try:
        user = get_current_user()
        fset = FlashcardSet.query.filter_by(id=set_id, user_id=user.id).first()
        
        if not fset:
            return jsonify({'error': 'Flashcard set not found'}), 404
        
        db.session.delete(fset)
        db.session.commit()
        
        return jsonify({'message': 'Flashcard set deleted'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to delete flashcard set', 'message': str(e)}), 500

@flashcards_bp.route('/<set_id>/add', methods=['POST'])
def add_flashcard(set_id):
    """Add flashcard to set"""
    try:
        user = get_current_user()
        fset = FlashcardSet.query.filter_by(id=set_id, user_id=user.id).first()
        
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
def update_flashcard(card_id):
    """Update flashcard"""
    try:
        user = get_current_user()
        card = Flashcard.query.join(FlashcardSet).filter(
            Flashcard.id == card_id,
            FlashcardSet.user_id == user.id
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
def delete_flashcard(card_id):
    """Delete flashcard"""
    try:
        user = get_current_user()
        card = Flashcard.query.join(FlashcardSet).filter(
            Flashcard.id == card_id,
            FlashcardSet.user_id == user.id
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
def generate_flashcards_from_note(set_id):
    """Generate flashcards from a note using AI"""
    try:
        user = get_current_user()
        
        fset = FlashcardSet.query.filter_by(id=set_id, user_id=user.id).first()
        if not fset:
            return jsonify({'error': 'Flashcard set not found'}), 404
        
        data = request.get_json()
        note_id = data.get('note_id')
        num_cards = data.get('num_cards', 10)
        
        if not note_id:
            return jsonify({'error': 'note_id is required'}), 400
        
        note = Note.query.filter_by(id=note_id, user_id=user.id).first()
        if not note:
            return jsonify({'error': 'Note not found'}), 404
        
        generated_cards = ai_service.generate_flashcards(note.content, num_cards)
        
        if not generated_cards:
            return jsonify({'error': 'Failed to generate flashcards'}), 500
        
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
def get_study_cards(set_id):
    """Get cards due for review (spaced repetition)"""
    try:
        user = get_current_user()
        fset = FlashcardSet.query.filter_by(id=set_id, user_id=user.id).first()
        
        if not fset:
            return jsonify({'error': 'Flashcard set not found'}), 404
        
        cards_due = Flashcard.query.filter(
            Flashcard.set_id == set_id,
            Flashcard.next_review <= datetime.utcnow()
        ).all()
        
        if not cards_due:
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
def review_flashcard(card_id):
    """Record flashcard review and apply spaced repetition algorithm"""
    try:
        user = get_current_user()
        
        card = Flashcard.query.join(FlashcardSet).filter(
            Flashcard.id == card_id,
            FlashcardSet.user_id == user.id
        ).first()
        
        if not card:
            return jsonify({'error': 'Flashcard not found'}), 404
        
        data = request.get_json()
        
        if 'quality' not in data:
            return jsonify({'error': 'Quality rating is required'}), 400
        
        quality = data.get('quality')
        
        if not isinstance(quality, int) or quality < 0 or quality > 5:
            return jsonify({'error': 'Quality must be between 0 and 5'}), 400
        
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
def bulk_add_flashcards(set_id):
    """Add multiple flashcards at once"""
    try:
        user = get_current_user()
        fset = FlashcardSet.query.filter_by(id=set_id, user_id=user.id).first()
        
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
def get_set_statistics(set_id):
    """Get detailed statistics for a flashcard set"""
    try:
        user = get_current_user()
        fset = FlashcardSet.query.filter_by(id=set_id, user_id=user.id).first()
        
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
def export_flashcards(set_id):
    """Export flashcard set"""
    try:
        user = get_current_user()
        fset = FlashcardSet.query.filter_by(id=set_id, user_id=user.id).first()
        
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

# ============================================
# PART 4: ANALYTICS ROUTES - NO AUTH REQUIRED
# ============================================
analytics_bp = Blueprint('analytics', __name__, url_prefix='/api/analytics')

@analytics_bp.route('/dashboard', methods=['GET'])
def get_dashboard_stats():
    """Get dashboard statistics"""
    try:
        user = get_current_user()
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        stats = AnalyticsService.get_user_study_stats(user.id, days=30)
        weekly_time = AnalyticsService.get_weekly_study_time(user.id)
        performance = AnalyticsService.get_performance_metrics(user.id)
        topic_dist = AnalyticsService.get_topic_distribution(user.id)
        
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
def get_study_sessions():
    """Get user's study sessions"""
    try:
        user = get_current_user()
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        session_type = request.args.get('type')
        
        query = StudySession.query.filter_by(user_id=user.id)
        
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
def create_study_session():
    """Create new study session"""
    try:
        user = get_current_user()
        data = request.get_json()
        
        session_type = data.get('session_type', 'general')
        duration_minutes = data.get('duration_minutes', 0)
        cards_studied = data.get('cards_studied', 0)
        correct_answers = data.get('correct_answers', 0)
        note_id = data.get('note_id')
        
        session = StudySession(
            user_id=user.id,
            note_id=note_id,
            session_type=session_type,
            duration_minutes=duration_minutes,
            cards_studied=cards_studied,
            correct_answers=correct_answers
        )
        
        session.accuracy_percentage = session.calculate_accuracy()
        
        db.session.add(session)
        
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
def get_learning_goals():
    """Get user's learning goals"""
    try:
        user = get_current_user()
        
        goals = LearningGoal.query.filter_by(user_id=user.id).order_by(
            LearningGoal.target_date.asc()
        ).all()
        
        return jsonify({
            'goals': [g.to_dict() for g in goals]
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to fetch goals', 'message': str(e)}), 500

@analytics_bp.route('/learning-goals', methods=['POST'])
def create_learning_goal():
    """Create new learning goal"""
    try:
        user = get_current_user()
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
            user_id=user.id,
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
def update_learning_goal(goal_id):
    """Update learning goal progress"""
    try:
        user = get_current_user()
        goal = LearningGoal.query.filter_by(id=goal_id, user_id=user.id).first()
        
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
def delete_learning_goal(goal_id):
    """Delete learning goal"""
    try:
        user = get_current_user()
        goal = LearningGoal.query.filter_by(id=goal_id, user_id=user.id).first()
        
        if not goal:
            return jsonify({'error': 'Goal not found'}), 404
        
        db.session.delete(goal)
        db.session.commit()
        
        return jsonify({'message': 'Goal deleted'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to delete goal', 'message': str(e)}), 500

@analytics_bp.route('/progress', methods=['GET'])
def get_progress_report():
    """Get comprehensive progress report"""
    try:
        user = get_current_user()
        
        days = request.args.get('days', 30, type=int)
        start_date = datetime.utcnow() - timedelta(days=days)
        
        stats = AnalyticsService.get_user_study_stats(user.id, days=days)
        performance = AnalyticsService.get_performance_metrics(user.id, days=days)
        
        goals = LearningGoal.query.filter_by(user_id=user.id).all()
        
        return jsonify({
            'period_days': days,
            'stats': stats,
            'performance': performance,
            'goals': [g.to_dict() for g in goals],
            'report_generated_at': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to generate report', 'message': str(e)}), 500
