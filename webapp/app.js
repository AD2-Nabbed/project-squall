// Web App JavaScript
const API_BASE = 'http://localhost:8000';

// Session management
let currentSession = null;
let currentUser = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Check if already logged in
    const savedSession = localStorage.getItem('session_token');
    if (savedSession) {
        currentSession = savedSession;
        checkAuth();
    }
});

// Auth functions
function switchTab(tab) {
    if (tab === 'login') {
        document.getElementById('loginForm').style.display = 'block';
        document.getElementById('registerForm').style.display = 'none';
        document.querySelectorAll('.tab-btn')[0].classList.add('active');
        document.querySelectorAll('.tab-btn')[1].classList.remove('active');
    } else {
        document.getElementById('loginForm').style.display = 'none';
        document.getElementById('registerForm').style.display = 'block';
        document.querySelectorAll('.tab-btn')[0].classList.remove('active');
        document.querySelectorAll('.tab-btn')[1].classList.add('active');
    }
}

async function handleLogin() {
    const username = document.getElementById('loginUsername').value;
    const password = document.getElementById('loginPassword').value;
    const errorDiv = document.getElementById('loginError');
    
    errorDiv.textContent = '';
    
    try {
        const response = await fetch(`${API_BASE}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password }),
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || 'Login failed');
        }
        
        currentSession = data.session_token;
        currentUser = data;
        localStorage.setItem('session_token', currentSession);
        
        showDashboard();
    } catch (error) {
        errorDiv.textContent = error.message;
    }
}

async function handleRegister() {
    const username = document.getElementById('registerUsername').value;
    const password = document.getElementById('registerPassword').value;
    const gamerTag = document.getElementById('registerGamerTag').value;
    const errorDiv = document.getElementById('registerError');
    
    errorDiv.textContent = '';
    
    try {
        const response = await fetch(`${API_BASE}/api/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password, gamer_tag: gamerTag }),
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || 'Registration failed');
        }
        
        currentSession = data.session_token;
        currentUser = data;
        localStorage.setItem('session_token', currentSession);
        
        showDashboard();
    } catch (error) {
        errorDiv.textContent = error.message;
    }
}

async function checkAuth() {
    if (!currentSession) return false;
    
    try {
        const response = await fetch(`${API_BASE}/api/auth/me?session_token=${currentSession}`);
        const data = await response.json();
        
        if (response.ok) {
            currentUser = data;
            showDashboard();
            return true;
        }
    } catch (error) {
        console.error('Auth check failed:', error);
    }
    
    return false;
}

function logout() {
    if (currentSession) {
        fetch(`${API_BASE}/api/auth/logout?session_token=${currentSession}`);
    }
    currentSession = null;
    currentUser = null;
    localStorage.removeItem('session_token');
    showLogin();
}

// Navigation
function showLogin() {
    hideAllPages();
    document.getElementById('loginPage').style.display = 'block';
    document.getElementById('navbar').style.display = 'none';
}

function showDashboard() {
    hideAllPages();
    document.getElementById('dashboardPage').style.display = 'block';
    document.getElementById('navbar').style.display = 'flex';
    
    if (currentUser) {
        document.getElementById('playerGamerTag').textContent = currentUser.gamer_tag || '-';
        document.getElementById('playerId').textContent = currentUser.player_id || '-';
    }
}

function showCardCatalog() {
    hideAllPages();
    document.getElementById('catalogPage').style.display = 'block';
    document.getElementById('navbar').style.display = 'flex';
    loadCardCatalog();
}

function showMyDecks() {
    hideAllPages();
    document.getElementById('decksPage').style.display = 'block';
    document.getElementById('navbar').style.display = 'flex';
    loadDecks();
}

function showDeckEditor(deckId) {
    hideAllPages();
    document.getElementById('deckEditorPage').style.display = 'block';
    document.getElementById('navbar').style.display = 'flex';
    
    if (deckId) {
        document.getElementById('deckEditorTitle').textContent = 'Edit Deck';
        loadDeck(deckId);
    } else {
        document.getElementById('deckEditorTitle').textContent = 'Create Deck';
        document.getElementById('deckName').value = '';
        document.getElementById('deckIsPublic').checked = false;
        document.getElementById('deckCardsList').innerHTML = '<p>No cards in deck yet.</p>';
        document.getElementById('deckValidation').innerHTML = '';
        updateDeckStats([]);
        currentDeckId = null;
    }
    
    loadOwnedCards();
}

function showGame() {
    hideAllPages();
    document.getElementById('gamePage').style.display = 'block';
    document.getElementById('navbar').style.display = 'flex';
    loadDecksForGame();
}

function hideAllPages() {
    document.querySelectorAll('.page').forEach(page => {
        page.style.display = 'none';
    });
}

// API calls
async function apiCall(endpoint, method = 'GET', body = null) {
    const options = {
        method,
        headers: { 'Content-Type': 'application/json' },
    };
    
    if (body) {
        options.body = JSON.stringify(body);
    }
    
    // Add session token to query params
    if (currentSession) {
        endpoint += (endpoint.includes('?') ? '&' : '?') + `session_token=${currentSession}`;
    }
    
    const fullUrl = `${API_BASE}${endpoint}`;
    console.log(`API Call: ${method} ${fullUrl}`, body ? 'with body' : 'no body');
    
    try {
        const response = await fetch(fullUrl, options);
        console.log(`Response status: ${response.status} ${response.statusText}`);
        
        // Check if response is ok before parsing JSON
        let data;
        try {
            data = await response.json();
        } catch (e) {
            // If JSON parsing fails, get text instead
            const text = await response.text();
            throw new Error(`Server error (${response.status}): ${text || response.statusText}`);
        }
        
        if (!response.ok) {
            throw new Error(data.detail || data.message || `API error: ${response.status} ${response.statusText}`);
        }
        
        return data;
    } catch (error) {
        console.error('Fetch error details:', error);
        // Re-throw with more context if it's a network error
        if (error.name === 'TypeError' && (error.message.includes('fetch') || error.message.includes('Failed to fetch'))) {
            throw new Error(`Network error: Could not connect to server at ${API_BASE}. Is the backend running? Original error: ${error.message}`);
        }
        throw error;
    }
}

// Card Catalog
let allCards = [];
let ownedCards = [];

async function loadCardCatalog() {
    try {
        allCards = await apiCall('/api/cards/catalog');
        ownedCards = await apiCall('/api/cards/owned');
        
        displayCards(allCards);
    } catch (error) {
        console.error('Failed to load catalog:', error);
        alert('Failed to load card catalog');
    }
}

function displayCards(cards) {
    const grid = document.getElementById('catalogGrid');
    grid.innerHTML = '';
    
    cards.forEach(card => {
        const owned = ownedCards.find(oc => oc.card_code === card.card_code);
        const quantity = owned ? owned.quantity : 0;
        
        const cardDiv = document.createElement('div');
        cardDiv.className = 'card-item';
        cardDiv.innerHTML = `
            <h3>${card.name}</h3>
            <div class="card-stats">
                <p>Code: ${card.card_code}</p>
                ${card.stars ? `<p>⭐${card.stars}</p>` : ''}
                ${card.atk ? `<p>ATK: ${card.atk}</p>` : ''}
                ${card.hp ? `<p>HP: ${card.hp}</p>` : ''}
                <p><strong>Owned: ${quantity}</strong></p>
            </div>
        `;
        cardDiv.onclick = () => showCardDetails(card);
        grid.appendChild(cardDiv);
    });
}

function filterCards() {
    const search = document.getElementById('cardSearch').value.toLowerCase();
    const typeFilter = document.getElementById('cardTypeFilter').value;
    
    let filtered = allCards.filter(card => {
        const matchesSearch = card.name.toLowerCase().includes(search);
        const matchesType = !typeFilter || card.card_type === typeFilter;
        return matchesSearch && matchesType;
    });
    
    displayCards(filtered);
}

function showCardDetails(card) {
    // Simple modal or detailed view
    alert(`Card: ${card.name}\nCode: ${card.card_code}\nType: ${card.card_type}\nStars: ${card.stars || 'N/A'}\nATK: ${card.atk || 'N/A'}\nHP: ${card.hp || 'N/A'}`);
}

// Deck Management
let currentDeckId = null;

async function loadDecks() {
    try {
        const decks = await apiCall('/api/decks');
        displayDecks(decks);
    } catch (error) {
        console.error('Failed to load decks:', error);
        alert('Failed to load decks');
    }
}

function displayDecks(decks) {
    const list = document.getElementById('decksList');
    list.innerHTML = '';
    
    if (decks.length === 0) {
        list.innerHTML = '<p>No decks yet. Create one to get started!</p>';
        return;
    }
    
    decks.forEach(deck => {
        const deckDiv = document.createElement('div');
        deckDiv.className = 'deck-item';
        deckDiv.innerHTML = `
            <h3>${deck.name}</h3>
            <p>${deck.is_public ? 'Public' : 'Private'}</p>
            <div class="deck-item-actions">
                <button class="btn btn-primary" onclick="showDeckEditor('${deck.id}')">Edit</button>
                <button class="btn btn-secondary" onclick="deleteDeck('${deck.id}')">Delete</button>
            </div>
        `;
        list.appendChild(deckDiv);
    });
}

async function loadDeck(deckId) {
    try {
        const deck = await apiCall(`/api/decks/${deckId}`);
        currentDeckId = deckId;
        document.getElementById('deckName').value = deck.name;
        document.getElementById('deckIsPublic').checked = deck.is_public;
        
        const cards = deck.cards || [];
        displayDeckCards(cards);
        
        // Display validation errors if any
        if (deck.validation) {
            displayDeckValidation(deck.validation);
        }
    } catch (error) {
        console.error('Failed to load deck:', error);
        alert('Failed to load deck');
    }
}

async function loadOwnedCards() {
    try {
        ownedCards = await apiCall('/api/cards/owned');
        // Debug: Log the structure of the first card to see what we're getting
        if (ownedCards.length > 0) {
            console.log('First owned card structure:', JSON.stringify(ownedCards[0], null, 2));
            const firstCard = ownedCards[0]?.cards;
            if (firstCard) {
                console.log('First card has card_type:', firstCard.card_type);
                console.log('First card has card_type_id:', firstCard.card_type_id);
            }
        }
        displayOwnedCards();
    } catch (error) {
        console.error('Failed to load owned cards:', error);
    }
}

// Card ordering function - returns a sort key for ordering
function getCardSortKey(card) {
    const cardType = (card.card_type || 'unknown').toLowerCase();
    const stars = card.stars || 0;
    
    // Order: Heroes (1000), Monsters 4-star (900), 3-star (800), 2-star (700), 1-star (600), Spells (500), Traps (400)
    if (cardType === 'hero') {
        return 1000;
    } else if (cardType === 'monster') {
        // Higher stars = higher priority: 4-star = 900, 3-star = 800, 2-star = 700, 1-star = 600
        return 1000 - ((5 - stars) * 100);
    } else if (cardType === 'spell') {
        return 500;
    } else if (cardType === 'trap') {
        return 400;
    }
    return 0; // Unknown types go last
}

// Filter and sort owned cards
function filterAndDisplayOwnedCards() {
    const filterValue = document.getElementById('deckCardTypeFilter')?.value || '';
    const list = document.getElementById('ownedCardsList');
    if (!list) {
        return;
    }
    list.innerHTML = '';
    
    if (ownedCards.length === 0) {
        list.innerHTML = '<p>No cards in your collection.</p>';
        return;
    }
    
    // Filter cards
    let filteredCards = ownedCards;
    if (filterValue) {
        filteredCards = ownedCards.filter(owned => {
            const card = owned.cards;
            if (!card) {
                console.log('Card missing for owned item:', owned);
                return false;
            }
            
            const cardType = (card.card_type || 'unknown').toLowerCase();
            const stars = card.stars || 0;
            
            // Debug: log first few cards to see their structure
            if (ownedCards.indexOf(owned) < 3) {
                console.log(`Card: ${card.name}, card_type: ${card.card_type}, card_type_id: ${card.card_type_id}, type (lowercase): ${cardType}`);
            }
            
            if (filterValue === 'hero') {
                return cardType === 'hero';
            } else if (filterValue.startsWith('monster-')) {
                const targetStars = parseInt(filterValue.split('-')[1]);
                return cardType === 'monster' && stars === targetStars;
            } else if (filterValue === 'spell') {
                const matches = cardType === 'spell';
                if (ownedCards.indexOf(owned) < 3) {
                    console.log(`  Spell filter check: ${card.name} -> ${matches} (cardType: ${cardType})`);
                }
                return matches;
            } else if (filterValue === 'trap') {
                return cardType === 'trap';
            }
            return true;
        });
        console.log('Filtered cards count:', filteredCards.length);
    }
    
    // Sort cards by type/stars, then by name
    filteredCards.sort((a, b) => {
        const cardA = a.cards || {};
        const cardB = b.cards || {};
        
        const sortKeyA = getCardSortKey(cardA);
        const sortKeyB = getCardSortKey(cardB);
        
        if (sortKeyA !== sortKeyB) {
            return sortKeyB - sortKeyA; // Higher sort key first
        }
        
        // If same type/star, sort by name
        const nameA = cardA.name || '';
        const nameB = cardB.name || '';
        return nameA.localeCompare(nameB);
    });
    
    // Display filtered and sorted cards
    filteredCards.forEach(owned => {
        const card = owned.cards;
        if (!card) return;
        
        const cardDiv = document.createElement('div');
        cardDiv.className = 'owned-card-item';
        
        const cardType = (card.card_type || 'unknown').toLowerCase();
        const maxCopies = getMaxCopies(cardType);
        const copyLimitText = `Max: ${maxCopies}${cardType === 'hero' ? ' (locked)' : ''}`;
        
        // Build card info HTML
        let cardInfo = `<div class="card-header"><h4>${card.name}</h4> <span class="card-quantity-badge">x${owned.quantity}</span></div>`;
        cardInfo += `<div class="card-code">Code: ${owned.card_code}</div>`;
        cardInfo += `<div class="card-copy-limit">${copyLimitText}</div>`;
        
        // Card type
        const cardTypeDisplay = card.card_type || 'Unknown';
        cardInfo += `<div class="card-type">Type: <strong>${cardTypeDisplay.charAt(0).toUpperCase() + cardTypeDisplay.slice(1)}</strong></div>`;
        
        // Monster stats
        if (card.stars) {
            cardInfo += `<div class="card-stars">⭐ ${card.stars} Star${card.stars !== 1 ? 's' : ''}</div>`;
        }
        if (card.atk !== null && card.atk !== undefined) {
            cardInfo += `<div class="card-stats">ATK: ${card.atk} | HP: ${card.hp || 'N/A'}</div>`;
        }
        
        // Element
        if (card.element_id) {
            cardInfo += `<div class="card-element">Element ID: ${card.element_id}</div>`;
        }
        
        // Rules text / description
        if (card.rules_text) {
            cardInfo += `<div class="card-description">${card.rules_text}</div>`;
        }
        
        // Effect tags
        if (card.effect_tags && card.effect_tags.length > 0) {
            cardInfo += `<div class="card-effects">Effects: ${card.effect_tags.join(', ')}</div>`;
        }
        
        cardDiv.innerHTML = `
            <div class="owned-card-content">
                ${cardInfo}
            </div>
            <button class="btn btn-primary" onclick="addCardToDeck('${owned.card_code}')">Add to Deck</button>
        `;
        list.appendChild(cardDiv);
    });
}

// Keep the old function name for compatibility, but it now uses the filtered/sorted version
function displayOwnedCards() {
    filterAndDisplayOwnedCards();
}

// Copy limits (matching backend validation)
const COPY_LIMITS = {
    monster: 2,
    spell: 1,
    trap: 1,
    hero: 1
};

function getMaxCopies(cardType) {
    return COPY_LIMITS[cardType?.toLowerCase()] || 99;
}

function displayDeckCards(cards) {
    const list = document.getElementById('deckCardsList');
    list.innerHTML = '';
    
    if (cards.length === 0) {
        list.innerHTML = '<p>No cards in deck yet.</p>';
        updateDeckStats(cards);
        return;
    }
    
    cards.forEach(dc => {
        const card = dc.cards;
        if (!card) return;
        
        const cardType = card.card_type?.toLowerCase() || 'unknown';
        const quantity = dc.quantity || 0;
        const maxCopies = getMaxCopies(cardType);
        const copyIndicator = `${quantity}/${maxCopies}`;
        
        const cardDiv = document.createElement('div');
        cardDiv.className = 'deck-card-item';
        
        // Highlight if at max copies
        const atMaxClass = quantity >= maxCopies ? ' at-max-copies' : '';
        
        cardDiv.innerHTML = `
            <div class="card-name-info">
                <div class="card-name">${card.name}</div>
                <div class="copy-indicator${atMaxClass}">${copyIndicator}</div>
            </div>
            <div class="card-quantity">
                <input type="number" value="${quantity}" min="0" max="${maxCopies}" 
                       onchange="updateCardQuantity('${dc.card_code}', this.value)">
                <button class="btn btn-secondary" onclick="removeCardFromDeck('${dc.card_code}')">Remove</button>
            </div>
        `;
        list.appendChild(cardDiv);
    });
    
    updateDeckStats(cards);
}

function updateDeckStats(cards) {
    const statsDiv = document.getElementById('deckStats');
    if (!statsDiv) return;
    
    let total = 0;
    let heroes = 0;
    let monsters = 0;
    let spells = 0;
    let traps = 0;
    
    cards.forEach(dc => {
        const card = dc.cards;
        if (!card) return;
        
        const quantity = dc.quantity || 0;
        const cardType = card.card_type?.toLowerCase() || '';
        
        total += quantity;
        
        if (cardType === 'hero') {
            heroes += quantity;
        } else if (cardType === 'monster') {
            monsters += quantity;
        } else if (cardType === 'spell') {
            spells += quantity;
        } else if (cardType === 'trap') {
            traps += quantity;
        }
    });
    
    statsDiv.innerHTML = `
        <div class="deck-stats-header">Deck Statistics</div>
        <div class="deck-stats-grid">
            <div class="stat-item">
                <span class="stat-label">Total Cards:</span>
                <span class="stat-value">${total}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Heroes:</span>
                <span class="stat-value">${heroes}/1</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Monsters:</span>
                <span class="stat-value">${monsters}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Spells:</span>
                <span class="stat-value">${spells}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Traps:</span>
                <span class="stat-value">${traps}</span>
            </div>
        </div>
    `;
}

async function saveDeck() {
    const name = document.getElementById('deckName').value;
    const isPublic = document.getElementById('deckIsPublic').checked;
    
    if (!name) {
        alert('Please enter a deck name');
        return;
    }
    
    try {
        if (currentDeckId) {
            await apiCall(`/api/decks/${currentDeckId}`, 'PUT', {
                name,
                is_public: isPublic,
            });
            
            // Validate deck after saving
            const deck = await apiCall(`/api/decks/${currentDeckId}`);
            if (deck.validation && !deck.validation.is_valid) {
                const errorMsg = deck.validation.errors.join('\n');
                const confirmSave = confirm(`Deck saved, but has validation errors:\n\n${errorMsg}\n\nDo you want to continue?`);
                if (!confirmSave) {
                    return;
                }
            }
        } else {
            const deck = await apiCall('/api/decks', 'POST', {
                name,
                is_public: isPublic,
            });
            currentDeckId = deck.id;
        }
        
        alert('Deck saved!');
        showMyDecks();
    } catch (error) {
        console.error('Failed to save deck:', error);
        alert('Failed to save deck: ' + error.message);
    }
}

function displayDeckValidation(validation) {
    const validationDiv = document.getElementById('deckValidation');
    if (!validationDiv) return;
    
    validationDiv.innerHTML = '';
    
    if (validation.is_valid) {
        validationDiv.className = 'deck-validation valid';
        validationDiv.innerHTML = '<div class="validation-success">✓ Deck is valid</div>';
    } else {
        validationDiv.className = 'deck-validation invalid';
        let html = '<div class="validation-header">⚠ Deck Validation Errors:</div><ul class="validation-errors">';
        validation.errors.forEach(error => {
            html += `<li>${error}</li>`;
        });
        html += '</ul>';
        validationDiv.innerHTML = html;
    }
}

// Update validation when cards change
async function updateDeckValidation() {
    if (!currentDeckId) return;
    
    try {
        const deck = await apiCall(`/api/decks/${currentDeckId}`);
        if (deck.validation) {
            displayDeckValidation(deck.validation);
        }
    } catch (error) {
        console.error('Failed to validate deck:', error);
    }
}

async function addCardToDeck(cardCode) {
    if (!currentDeckId) {
        alert('Please save the deck first');
        return;
    }
    
    console.log('Adding card:', cardCode, 'to deck:', currentDeckId);
    console.log('Session token:', currentSession ? 'present' : 'missing');
    
    try {
        const result = await apiCall(`/api/decks/${currentDeckId}/cards`, 'POST', {
            card_code: cardCode,
            quantity: 1,
        });
        console.log('Add card result:', result);
        loadDeck(currentDeckId);
        updateDeckValidation();
    } catch (error) {
        console.error('Failed to add card - full error:', error);
        console.error('Error name:', error.name);
        console.error('Error message:', error.message);
        console.error('Error stack:', error.stack);
        alert('Failed to add card: ' + error.message);
    }
}

async function updateCardQuantity(cardCode, quantity) {
    if (!currentDeckId) return;
    
    try {
        await apiCall(`/api/decks/${currentDeckId}/cards/${cardCode}`, 'PUT', {
            quantity: parseInt(quantity),
        });
        
        loadDeck(currentDeckId);
        updateDeckValidation();
    } catch (error) {
        console.error('Failed to update quantity:', error);
    }
}

async function removeCardFromDeck(cardCode) {
    if (!currentDeckId) return;
    
    try {
        await apiCall(`/api/decks/${currentDeckId}/cards/${cardCode}`, 'DELETE');
        loadDeck(currentDeckId);
        updateDeckValidation();
    } catch (error) {
        console.error('Failed to remove card:', error);
    }
}

async function deleteDeck(deckId) {
    if (!confirm('Are you sure you want to delete this deck?')) return;
    
    try {
        await apiCall(`/api/decks/${deckId}`, 'DELETE');
        loadDecks();
    } catch (error) {
        console.error('Failed to delete deck:', error);
        alert('Failed to delete deck');
    }
}

// Game Integration
async function loadDecksForGame() {
    try {
        const decks = await apiCall('/api/decks');
        const select = document.getElementById('gameDeckSelect');
        select.innerHTML = '<option value="">Select a deck...</option>';
        
        decks.forEach(deck => {
            const option = document.createElement('option');
            option.value = deck.id;
            option.textContent = deck.name;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Failed to load decks for game:', error);
    }
}

async function startGameFromWeb() {
    const deckId = document.getElementById('gameDeckSelect').value;
    if (!deckId) {
        alert('Please select a deck');
        return;
    }
    
    // Redirect to the frontend game (assumes it's running on port 8081 or same origin)
    // If frontend is on a different port, update this URL
    // For now, use absolute URL assuming frontend runs on http://localhost:8081
    window.location.href = `http://localhost:8081/index.html?deck_id=${deckId}&player_id=${currentUser.player_id}`;
}

