// frontend/js/api.js
const API_BASE = 'http://localhost:5000/api';

async function fetchAPI(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    
    const headers = {
        'Content-Type': 'application/json'
        // Token requirement removed - no authentication needed
    };

    try {
        const response = await fetch(url, {
            ...options,
            headers: { ...headers, ...options.headers }
        });

        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error('Fetch error:', error);
        throw error;
    }
}

// Auth functions removed - no longer needed

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
