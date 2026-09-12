# backend/services.py (Part 1 - AI Service)
import openai
import os
import logging
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class AIService:
    """Service for AI-powered features"""
    
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.model = 'gpt-3.5-turbo'
        if self.api_key:
            openai.api_key = self.api_key
    
    def generate_summary(self, content: str, max_length: int = 200) -> Optional[str]:
        """Generate concise summary of content"""
        try:
            if not content or len(content) < 50:
                return None
            
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful study assistant. Provide concise summaries in bullet points."},
                    {"role": "user", "content": f"Summarize this in {max_length} words or less:\n\n{content[:3000]}"}
                ],
                max_tokens=150,
                temperature=0.7
            )
            
            summary = response.choices[0].message.content.strip()
            return summary
            
        except Exception as e:
            logger.error(f"Summary generation failed: {str(e)}")
            return None
    
    def organize_content(self, content: str) -> Optional[str]:
        """Organize and structure note content"""
        try:
            if not content or len(content) < 50:
                return None
            
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a study note organization expert. Structure notes with clear headings and bullet points."},
                    {"role": "user", "content": f"Organize and structure this note content better:\n\n{content[:3000]}"}
                ],
                max_tokens=2000,
                temperature=0.7
            )
            
            organized = response.choices[0].message.content.strip()
            return organized
            
        except Exception as e:
            logger.error(f"Content organization failed: {str(e)}")
            return None
    
    def extract_key_concepts(self, content: str, max_concepts: int = 10) -> List[str]:
        """Extract key concepts from content"""
        try:
            if not content or len(content) < 50:
                return []
            
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Extract key concepts and terms from study material. Return as comma-separated list."},
                    {"role": "user", "content": f"Extract up to {max_concepts} key concepts from:\n\n{content[:2000]}"}
                ],
                max_tokens=200,
                temperature=0.5
            )
            
            concepts_text = response.choices[0].message.content.strip()
            concepts = [c.strip() for c in concepts_text.split(',')][:max_concepts]
            return concepts
            
        except Exception as e:
            logger.error(f"Key concepts extraction failed: {str(e)}")
            return []
    
    def generate_flashcards(self, content: str, num_cards: int = 10) -> List[Dict[str, str]]:
        """Generate flashcards from content"""
        try:
            if not content or len(content) < 50:
                return []
            
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Create study flashcards with questions and answers. Format: Q: ... | A: ..."},
                    {"role": "user", "content": f"Create {num_cards} flashcards from:\n\n{content[:2000]}"}
                ],
                max_tokens=1500,
                temperature=0.7
            )
            
            response_text = response.choices[0].message.content.strip()
            flashcards = []
            
            for line in response_text.split('\n'):
                if 'Q:' in line and 'A:' in line:
                    parts = line.split('|')
                    if len(parts) == 2:
                        question = parts[0].replace('Q:', '').strip()
                        answer = parts[1].replace('A:', '').strip()
                        if question and answer:
                            flashcards.append({
                                'front': question,
                                'back': answer
                            })
            
            return flashcards[:num_cards]
            
        except Exception as e:
            logger.error(f"Flashcard generation failed: {str(e)}")
            return []
    
    def answer_question(self, question: str, context: Optional[str] = None) -> Optional[str]:
        """AI tutor - Answer student questions"""
        try:
            if not question or len(question) < 3:
                return None
            
            context_msg = f"Context from notes: {context}" if context else "Use general knowledge."
            
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful study tutor. Provide clear, educational answers. Encourage learning."},
                    {"role": "user", "content": f"{context_msg}\n\nQuestion: {question}"}
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            answer = response.choices[0].message.content.strip()
            return answer
            
        except Exception as e:
            logger.error(f"Question answering failed: {str(e)}")
            return None
    
    def generate_study_plan(self, notes_content: List[str], duration_days: int = 7) -> Optional[Dict]:
        """Generate personalized study plan"""
        try:
            if not notes_content:
                return None
            
            combined_content = "\n".join(notes_content)[:3000]
            
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Create a structured {}-day study plan. Include daily topics, time allocation, and practice activities.".format(duration_days)},
                    {"role": "user", "content": f"Create a study plan for: {combined_content}"}
                ],
                max_tokens=1500,
                temperature=0.7
            )
            
            plan_text = response.choices[0].message.content.strip()
            
            return {
                'plan': plan_text,
                'duration_days': duration_days,
                'created_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Study plan generation failed: {str(e)}")
            return None
    
    def generate_practice_problems(self, topic: str, difficulty: str = 'medium', num_problems: int = 5) -> List[Dict]:
        """Generate practice problems for a topic"""
        try:
            if not topic or len(topic) < 2:
                return []
            
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": f"Generate {difficulty} level practice problems with solutions."},
                    {"role": "user", "content": f"Create {num_problems} practice problems about: {topic}"}
                ],
                max_tokens=1500,
                temperature=0.8
            )
            
            response_text = response.choices[0].message.content.strip()
            problems = []
            
            # Parse response into problems
            current_problem = {}
            for line in response_text.split('\n'):
                if line.strip():
                    problems.append({'problem': line})
            
            return problems[:num_problems]
            
        except Exception as e:
            logger.error(f"Problem generation failed: {str(e)}")
            return []


class NoteService:
    """Service for note management"""
    
    @staticmethod
    def calculate_reading_time(content: str) -> int:
        """Calculate estimated reading time in minutes"""
        words = len(content.split())
        return max(1, words // 200)  # Average 200 words per minute
    
    @staticmethod
    def get_content_stats(content: str) -> Dict:
        """Get statistics about note content"""
        words = len(content.split())
        characters = len(content)
        sentences = len(content.split('.'))
        paragraphs = len(content.split('\n\n'))
        
        return {
            'word_count': words,
            'character_count': characters,
            'sentence_count': sentences,
            'paragraph_count': paragraphs,
            'reading_time_minutes': NoteService.calculate_reading_time(content)
        }

# backend/services.py (Part 2 - Spaced Repetition Service)
from datetime import datetime, timedelta
import math

class SpacedRepetitionService:
    """Implements SM-2 (SuperMemo 2) algorithm for spaced repetition"""
    
    @staticmethod
    def apply_sm2(card, quality: int):
        """
        Apply SM-2 algorithm to update card's learning parameters
        
        Quality scale (0-5):
        0 = Complete blackout, wrong on all attempts
        1 = Incorrect response, serious difficulty
        2 = Incorrect response, but on the verge of correct
        3 = Correct response after serious difficulty
        4 = Correct response after some difficulty
        5 = Perfect response
        """
        
        if quality < 0 or quality > 5:
            quality = 3
        
        # First review
        if card.repetitions == 0:
            if quality < 3:
                card.repetitions = 0
                card.interval = 1
            else:
                card.repetitions = 1
                card.interval = 1
        
        # Second review
        elif card.repetitions == 1:
            if quality < 3:
                card.repetitions = 0
                card.interval = 1
            else:
                card.repetitions = 2
                card.interval = 3
        
        # Subsequent reviews
        else:
            if quality < 3:
                card.repetitions = 0
                card.interval = 1
            else:
                card.repetitions += 1
                card.interval = round(card.interval * card.ease_factor)
        
        # Update ease factor using SM-2 formula
        card.ease_factor = max(1.3, card.ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
        
        # Calculate next review date
        card.next_review = datetime.utcnow() + timedelta(days=card.interval)
        
        return card
    
    @staticmethod
    def get_recommended_reviews_today(cards: list) -> list:
        """Get cards recommended for review today"""
        return [c for c in cards if c.next_review <= datetime.utcnow()]
    
    @staticmethod
    def calculate_retention_rate(cards: list) -> float:
        """Calculate retention rate (percentage of mastered cards)"""
        if not cards:
            return 0.0
        
        mastered = sum(1 for c in cards if c.ease_factor >= 2.5)
        return (mastered / len(cards)) * 100


class AnalyticsService:
    """Service for learning analytics"""
    
    @staticmethod
    def get_user_study_stats(user_id: str, days: int = 30):
        """Get comprehensive study statistics"""
        from models import StudySession, Note, FlashcardSet
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Study sessions
        sessions = StudySession.query.filter(
            StudySession.user_id == user_id,
            StudySession.started_at >= start_date
        ).all()
        
        total_study_time = sum(s.duration_minutes for s in sessions if s.duration_minutes)
        total_sessions = len(sessions)
        
        # Flashcard stats
        flashcard_sets = FlashcardSet.query.filter_by(user_id=user_id).all()
        total_cards = sum(fs.total_cards for fs in flashcard_sets)
        
        # Notes
        total_notes = Note.query.filter_by(user_id=user_id).count()
        
        # Daily breakdown
        daily_stats = {}
        for session in sessions:
            date_key = session.started_at.date().isoformat()
            if date_key not in daily_stats:
                daily_stats[date_key] = {
                    'study_time': 0,
                    'sessions': 0,
                    'accuracy': 0
                }
            daily_stats[date_key]['study_time'] += session.duration_minutes or 0
            daily_stats[date_key]['sessions'] += 1
            if session.accuracy_percentage:
                daily_stats[date_key]['accuracy'] = session.accuracy_percentage
        
        return {
            'total_study_time_minutes': total_study_time,
            'total_sessions': total_sessions,
            'average_session_minutes': total_study_time / total_sessions if total_sessions > 0 else 0,
            'total_flashcard_sets': len(flashcard_sets),
            'total_flashcards': total_cards,
            'total_notes': total_notes,
            'daily_breakdown': daily_stats
        }
    
    @staticmethod
    def get_weekly_study_time(user_id: str) -> dict:
        """Get study time for each day of current week"""
        from models import StudySession
        
        today = datetime.utcnow()
        week_start = today - timedelta(days=today.weekday())
        
        daily_minutes = {}
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        for i in range(7):
            date = week_start + timedelta(days=i)
            date_key = date.date().isoformat()
            daily_minutes[day_names[i]] = 0
        
        sessions = StudySession.query.filter(
            StudySession.user_id == user_id,
            StudySession.started_at >= week_start
        ).all()
        
        for session in sessions:
            date_key = session.started_at.date().isoformat()
            day_index = session.started_at.weekday()
            day_name = day_names[day_index]
            daily_minutes[day_name] += session.duration_minutes or 0
        
        return daily_minutes
    
    @staticmethod
    def get_performance_metrics(user_id: str, days: int = 30) -> dict:
        """Get performance metrics for flashcards"""
        from models import StudySession
        
        start_date = datetime.utcnow() - timedelta(days=days)
        sessions = StudySession.query.filter(
            StudySession.user_id == user_id,
            StudySession.started_at >= start_date,
            StudySession.session_type == 'flashcard'
        ).all()
        
        if not sessions:
            return {
                'average_accuracy': 0,
                'total_correct': 0,
                'total_attempted': 0,
                'improvement_trend': []
            }
        
        total_correct = sum(s.correct_answers for s in sessions)
        total_attempted = sum(s.cards_studied for s in sessions)
        average_accuracy = (total_correct / total_attempted * 100) if total_attempted > 0 else 0
        
        # Improvement trend (last 7 sessions)
        improvement = []
        for session in sorted(sessions, key=lambda s: s.started_at)[-7:]:
            acc = session.calculate_accuracy()
            improvement.append(acc)
        
        return {
            'average_accuracy': round(average_accuracy, 2),
            'total_correct': total_correct,
            'total_attempted': total_attempted,
            'improvement_trend': improvement
        }
    
    @staticmethod
    def get_topic_distribution(user_id: str) -> dict:
        """Get distribution of study by topic/tag"""
        from models import Note
        
        notes = Note.query.filter_by(user_id=user_id).all()
        topic_count = {}
        
        for note in notes:
            if note.tags:
                for tag in note.tags:
                    topic_count[tag] = topic_count.get(tag, 0) + 1
        
        return sorted(
            [{'topic': k, 'count': v} for k, v in topic_count.items()],
            key=lambda x: x['count'],
            reverse=True
        )