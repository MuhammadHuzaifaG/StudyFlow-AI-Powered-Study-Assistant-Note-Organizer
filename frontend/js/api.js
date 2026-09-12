// frontend/js/api.js
const API_BASE = 'http://localhost:5000/api';

async function fetchAPI(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const token = localStorage.getItem('token');
    
    const headers = {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` })
    };

    try {
        const response = await fetch(url, {
            ...options,
            headers: { ...headers, ...options.headers }
        });

        if (!response.ok) {
            if (response.status === 401) {
                localStorage.removeItem('token');
                window.location.href = '/';
            }
            throw new Error(`API error: ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error('Fetch error:', error);
        throw error;
    }
}

async function signup(name, email, password) {
    return fetchAPI('/auth/signup', {
        method: 'POST',
        body: JSON.stringify({ name, email, password })
    });
}

async function login(email, password) {
    return fetchAPI('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password })
    });
}

async function getNotes() {
    return fetchAPI('/notes');
}

async function createNote(title, content) {
    return fetchAPI('/notes', {
        method: 'POST',
        body: JSON.stringify({ title, content })
    });
}

async function generateSummary(noteId) {
    return fetchAPI(`/notes/${noteId}/summarize`, {
        method: 'POST'
    });
}

async function generateFlashcards(noteId) {
    return fetchAPI(`/notes/${noteId}/flashcards`, {
        method: 'POST'
    });
}