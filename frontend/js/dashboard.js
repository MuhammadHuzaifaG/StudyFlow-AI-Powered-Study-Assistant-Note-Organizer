// frontend/js/dashboard.js
let currentUser = null;
let pomodoroInterval = null;
let pomodoroTime = 25 * 60;
let pomodoroMode = 'work';
let sessionsCompleted = 0;

document.addEventListener('DOMContentLoaded', function() {
    checkAuth();
    loadUserData();
    setupEventListeners();
    displayCurrentDate();
    loadDashboardData();
    generateCalendar();
    setupNavigation();
});

function checkAuth() {
    const token = localStorage.getItem('token');
    if (!token) {
        window.location.href = '/';
    }
    const user = JSON.parse(localStorage.getItem('user') || '{}');
    currentUser = user;
    document.getElementById('userName').textContent = user.name || 'User';
}

function setupEventListeners() {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const section = item.getAttribute('data-section');
            switchSection(section);
        });
    });

    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            loadNotes(btn.getAttribute('data-filter'));
        });
    });

    document.getElementById('searchInput').addEventListener('input', (e) => {
        searchNotes(e.target.value);
    });
}

function switchSection(section) {
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.getElementById(section).classList.add('active');

    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
        if (item.getAttribute('data-section') === section) {
            item.classList.add('active');
        }
    });

    if (section === 'notes') {
        loadNotes('all');
    } else if (section === 'flashcards') {
        loadFlashcards();
    } else if (section === 'study-plan') {
        loadStudyPlan();
    } else if (section === 'analytics') {
        loadAnalytics();
    } else if (section === 'collaborate') {
        loadCollaborationData();
    }
}

async function loadDashboardData() {
    try {
        const response = await fetchAPI('/dashboard');
        document.getElementById('notesCount').textContent = response.notesCount;
        document.getElementById('studyTime').textContent = (response.studyTime / 60).toFixed(1) + 'h';
        document.getElementById('accuracy').textContent = response.accuracy + '%';
        document.getElementById('streak').textContent = response.streak;

        loadRecentActivity(response.recentActivity);
    } catch (error) {
        console.error('Failed to load dashboard data:', error);
    }
}

function loadRecentActivity(activities) {
    const list = document.getElementById('recentList');
    if (!activities || activities.length === 0) {
        list.innerHTML = '<p class="empty-state">No recent activity</p>';
        return;
    }

    list.innerHTML = activities.map(activity => `
        <div class="activity-item">
            <span class="activity-icon">${activity.icon}</span>
            <div class="activity-content">
                <h4>${activity.title}</h4>
                <p class="activity-time">${activity.time}</p>
            </div>
        </div>
    `).join('');
}

function generateCalendar() {
    const grid = document.getElementById('calendarGrid');
    const today = new Date();
    const startDate = new Date(today.getFullYear(), today.getMonth(), 1);
    const endDate = new Date(today.getFullYear(), today.getMonth() + 1, 0);

    grid.innerHTML = '';
    for (let d = new Date(startDate); d <= endDate; d.setDate(d.getDate() + 1)) {
        const dayElement = document.createElement('div');
        dayElement.className = 'calendar-day';
        if (d.getDate() === today.getDate() && d.getMonth() === today.getMonth()) {
            dayElement.classList.add('today');
        }
        if (Math.random() > 0.5) dayElement.classList.add('active');
        dayElement.textContent = d.getDate();
        grid.appendChild(dayElement);
    }
}

function displayCurrentDate() {
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    const date = new Date().toLocaleDateString('en-US', options);
    document.getElementById('dateDisplay').textContent = date;
}

function openNoteEditor() {
    document.getElementById('noteEditorModal').style.display = 'block';
}

function closeNoteEditor() {
    document.getElementById('noteEditorModal').style.display = 'none';
    document.getElementById('noteTitle').value = '';
    document.getElementById('noteContent').value = '';
    document.getElementById('noteTags').value = '';
}

async function saveNote() {
    const title = document.getElementById('noteTitle').value;
    const content = document.getElementById('noteContent').value;
    const tags = document.getElementById('noteTags').value.split(',').map(t => t.trim());

    if (!title || !content) {
        alert('Please fill in both title and content');
        return;
    }

    try {
        await createNote(title, content);
        closeNoteEditor();
        loadNotes('all');
        alert('Note saved successfully!');
    } catch (error) {
        alert('Failed to save note: ' + error.message);
    }
}

async function autoOrganizeNote() {
    const content = document.getElementById('noteContent').value;
    if (!content) {
        alert('Please write some content first');
        return;
    }

    try {
        const response = await fetchAPI('/ai/organize', {
            method: 'POST',
            body: JSON.stringify({ content })
        });
        document.getElementById('noteContent').value = response.organizedContent;
    } catch (error) {
        alert('Failed to organize note: ' + error.message);
    }
}

async function loadNotes(filter) {
    try {
        const notes = await getNotes();
        const grid = document.getElementById('notesGrid');

        if (!notes || notes.length === 0) {
            grid.innerHTML = '<div class="empty-state">📭 No notes yet</div>';
            return;
        }

        grid.innerHTML = notes.map(note => `
            <div class="note-card">
                <div class="note-header">
                    <div class="note-title">${escapeHtml(note.title)}</div>
                    <div class="note-actions">
                        <button class="note-btn" onclick="viewNote(${note.id})">👁️</button>
                        <button class="note-btn" onclick="editNote(${note.id})">✏️</button>
                        <button class="note-btn" onclick="deleteNote(${note.id})">🗑️</button>
                    </div>
                </div>
                <p class="note-preview">${escapeHtml(note.content.substring(0, 150))}...</p>
                <div class="note-footer">
                    <span>${new Date(note.createdAt).toLocaleDateString()}</span>
                    <div class="note-tags-display">
                        ${(note.tags || []).map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}
                    </div>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Failed to load notes:', error);
    }
}

async function loadFlashcards() {
    try {
        const response = await fetchAPI('/flashcards');
        const list = document.getElementById('flashcardList');

        if (!response || response.length === 0) {
            list.innerHTML = '<div class="empty-state">No flashcard sets yet</div>';
            return;
        }

        list.innerHTML = response.map(set => `
            <div class="flashcard-set">
                <h3>${escapeHtml(set.name)}</h3>
                <p>${set.description || 'Generated from your notes'}</p>
                <span class="flashcard-count">${set.cardCount} cards</span>
                <button class="btn-primary" onclick="studyFlashcards(${set.id})" style="margin-top: 1rem; width: 100%;">Study Now</button>
            </div>
        `).join('');
    } catch (error) {
        console.error('Failed to load flashcards:', error);
    }
}

function openFlashcardGenerator() {
    const noteTitle = prompt('Which note would you like to generate flashcards from?');
    if (noteTitle) {
        generateFlashcards(noteTitle);
    }
}

async function generateStudyPlan() {
    try {
        const response = await fetchAPI('/ai/study-plan', { method: 'POST' });
        const planContent = document.getElementById('studyPlanContent');
        planContent.innerHTML = `
            <div class="plan-container">
                <h3>${response.topic || 'Your AI Study Plan'}</h3>
                <div class="plan-content">${response.plan}</div>
                <div class="plan-actions">
                    <button class="btn-primary" onclick="downloadStudyPlan()">📥 Download</button>
                    <button class="btn-secondary" onclick="generateStudyPlan()">🔄 Generate New</button>
                </div>
            </div>
        `;
    } catch (error) {
        alert('Failed to generate study plan: ' + error.message);
    }
}

async function loadStudyPlan() {
    try {
        const response = await fetchAPI('/study-plans');
        const content = document.getElementById('studyPlanContent');

        if (!response || response.length === 0) {
            content.innerHTML = '<div class="empty-state">No study plans yet</div>';
            return;
        }

        content.innerHTML = response[0].plan;
    } catch (error) {
        console.error('Failed to load study plan:', error);
    }
}

function openAITutor() {
    switchSection('ai-tutor');
}

async function sendTutorMessage() {
    const input = document.getElementById('tutorInput');
    const message = input.value.trim();

    if (!message) return;

    const history = document.getElementById('chatHistory');
    history.innerHTML += `<div class="user-message">${escapeHtml(message)}</div>`;
    input.value = '';

    try {
        const response = await fetchAPI('/ai/tutor', {
            method: 'POST',
            body: JSON.stringify({ question: message })
        });

        history.innerHTML += `<div class="bot-message">${response.answer}</div>`;
        history.scrollTop = history.scrollHeight;
    } catch (error) {
        history.innerHTML += `<div class="bot-message">Sorry, I couldn't process that. Please try again.</div>`;
    }
}

function sendTutorMessageModal() {
    const input = document.getElementById('tutorInputModal');
    const message = input.value.trim();

    if (!message) return;

    const history = document.getElementById('tutorChatHistory');
    history.innerHTML += `<div class="user-message">${escapeHtml(message)}</div>`;
    input.value = '';

    fetchAPI('/ai/tutor', {
        method: 'POST',
        body: JSON.stringify({ question: message })
    }).then(response => {
        history.innerHTML += `<div class="bot-message">${response.answer}</div>`;
        history.scrollTop = history.scrollHeight;
    });
}

function startPomodoroSession() {
    document.getElementById('pomodoroModal').style.display = 'block';
}

function closePomodoroModal() {
    document.getElementById('pomodoroModal').style.display = 'none';
    clearInterval(pomodoroInterval);
}

function startPomodoro() {
    document.getElementById('startBtn').style.display = 'none';
    document.getElementById('pauseBtn').style.display = 'block';

    pomodoroInterval = setInterval(() => {
        pomodoroTime--;

        const minutes = Math.floor(pomodoroTime / 60);
        const seconds = pomodoroTime % 60;

        document.getElementById('timerMinutes').textContent = minutes.toString().padStart(2, '0');
        document.getElementById('timerSeconds').textContent = seconds.toString().padStart(2, '0');

        if (pomodoroTime === 0) {
            clearInterval(pomodoroInterval);
            if (pomodoroMode === 'work') {
                sessionsCompleted++;
                document.getElementById('sessionsCount').textContent = sessionsCompleted;
                alert('Great work! Take a break.');
                pomodoroMode = 'break';
                pomodoroTime = 5 * 60;
            } else {
                pomodoroMode = 'work';
                pomodoroTime = 25 * 60;
            }
            document.getElementById('startBtn').style.display = 'block';
            document.getElementById('pauseBtn').style.display = 'none';
        }
    }, 1000);
}

function pausePomodoro() {
    clearInterval(pomodoroInterval);
    document.getElementById('startBtn').style.display = 'block';
    document.getElementById('pauseBtn').style.display = 'none';
}

function resetPomodoro() {
    clearInterval(pomodoroInterval);
    pomodoroTime = pomodoroMode === 'work' ? 25 * 60 : 5 * 60;
    document.getElementById('timerMinutes').textContent = '25';
    document.getElementById('timerSeconds').textContent = '00';
    document.getElementById('startBtn').style.display = 'block';
    document.getElementById('pauseBtn').style.display = 'none';
}

function changePomodoroMode(mode) {
    pomodoroMode = mode;
    pomodoroTime = mode === 'work' ? 25 * 60 : 5 * 60;
    resetPomodoro();
}

async function loadAnalytics() {
    try {
        const response = await fetchAPI('/analytics');

        // Study Time Chart
        const ctxStudy = document.getElementById('studyTimeChart').getContext('2d');
        new Chart(ctxStudy, {
            type: 'line',
            data: {
                labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                datasets: [{
                    label: 'Study Time (minutes)',
                    data: response.weeklyStudyTime || [60, 90, 75, 120, 85, 45, 30],
                    borderColor: '#6366f1',
                    backgroundColor: 'rgba(99, 102, 241, 0.1)',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } }
            }
        });

        // Performance Chart
        const ctxPerf = document.getElementById('performanceChart').getContext('2d');
        new Chart(ctxPerf, {
            type: 'doughnut',
            data: {
                labels: ['Correct', 'Incorrect'],
                datasets: [{
                    data: [response.correctCards || 85, response.incorrectCards || 15],
                    backgroundColor: ['#10b981', '#ef4444']
                }]
            },
            options: { responsive: true, maintainAspectRatio: false }
        });
    } catch (error) {
        console.error('Failed to load analytics:', error);
    }
}

async function loadCollaborationData() {
    try {
        const response = await fetchAPI('/collaborate');
        // Render shared notes and groups
    } catch (error) {
        console.error('Failed to load collaboration data:', error);
    }
}

function searchNotes(query) {
    const cards = document.querySelectorAll('.note-card');
    cards.forEach(card => {
        const title = card.querySelector('.note-title').textContent.toLowerCase();
        const preview = card.querySelector('.note-preview').textContent.toLowerCase();
        if (title.includes(query.toLowerCase()) || preview.includes(query.toLowerCase())) {
            card.style.display = 'block';
        } else {
            card.style.display = 'none';
        }
    });
}

function handleLogout() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    window.location.href = '/';
}

function setupNavigation() {
    window.onclick = function(event) {
        const modals = document.querySelectorAll('.modal');
        modals.forEach(modal => {
            if (event.target === modal) {
                modal.style.display = 'none';
            }
        });
    };
}

function viewNote(noteId) {
    alert('Note viewer will open here');
}

function editNote(noteId) {
    alert('Note editor will open here');
}

async function deleteNote(noteId) {
    if (confirm('Are you sure you want to delete this note?')) {
        try {
            await fetchAPI(`/notes/${noteId}`, { method: 'DELETE' });
            loadNotes('all');
        } catch (error) {
            alert('Failed to delete note');
        }
    }
}

function formatText(command, value) {
    document.execCommand(command, false, value);
    document.getElementById('noteContent').focus();
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

function downloadStudyPlan() {
    const content = document.querySelector('.plan-content').innerHTML;
    const element = document.createElement('a');
    element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(content));
    element.setAttribute('download', 'study-plan.txt');
    element.style.display = 'none';
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
}