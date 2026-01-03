// Game state
let currentMatchId = null;
let currentGameState = null;
let currentPlayerIndex = 1; // Which player YOU are (set at match start, never changes)
let matchMode = "PVE"; // "PVE" or "PVP"
let selectedCard = null; // Selected card from hand
let selectedBoardMonster = null; // Selected monster on board for attacking
let selectedZone = null;
let selectedTributes = [];
let pendingTrapTrigger = null;
let selectedTarget = null; // Selected target for spells/attacks

// API base URL
const API_BASE = 'http://127.0.0.1:8000';

// Image configuration
const CARD_IMAGE_BASE = '/images/cards'; // Change this to your image path/URL
const USE_CARD_IMAGES = false; // Set to false to use text-only cards

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    console.log('Game initialized');
    
    // Read URL parameters and auto-fill form
    const urlParams = new URLSearchParams(window.location.search);
    const deckId = urlParams.get('deck_id');
    const playerId = urlParams.get('player_id');
    
    if (deckId) {
        const deckInput = document.getElementById('deckId');
        if (deckInput) {
            deckInput.value = deckId;
        }
    }
    
    if (playerId) {
        const playerInput = document.getElementById('playerId');
        if (playerInput) {
            playerInput.value = playerId;
        }
    }
    
    // If both are provided, auto-start the match (optional - comment out if you want manual start)
    // if (deckId && playerId) {
    //     startMatch();
    // }
});

// API calls
async function apiCall(endpoint, method = 'GET', body = null) {
    showLoading(true);
    try {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json',
            },
        };
        if (body) {
            options.body = JSON.stringify(body);
        }
        const response = await fetch(`${API_BASE}${endpoint}`, options);
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'API error');
        }
        return data;
    } catch (error) {
        console.error('API error:', error);
        alert(`Error: ${error.message}`);
        throw error;
    } finally {
        showLoading(false);
    }
}

// Toggle match mode
function toggleMatchMode() {
    const mode = document.getElementById('matchMode').value;
    matchMode = mode;
    const player2Group = document.getElementById('player2Group');
    const player2DeckGroup = document.getElementById('player2DeckGroup');
    
    if (mode === 'PVP') {
        player2Group.style.display = 'block';
        player2DeckGroup.style.display = 'block';
    } else {
        player2Group.style.display = 'none';
        player2DeckGroup.style.display = 'none';
    }
}

// Start match
async function startMatch() {
    const playerId = document.getElementById('playerId').value.trim();
    const deckId = document.getElementById('deckId').value.trim();
    const mode = document.getElementById('matchMode').value;
    matchMode = mode;
    
    if (!playerId || !deckId) {
        alert('Please enter both Player ID and Deck ID');
        return;
    }
    
    const payload = {
        player_id: playerId,
        deck_id: deckId,
        mode: mode,
    };
    
    if (mode === 'PVP') {
        const player2Id = document.getElementById('player2Id').value.trim();
        const player2DeckId = document.getElementById('player2DeckId').value.trim();
        
        if (!player2Id || !player2DeckId) {
            alert('PVP mode requires Player 2 ID and Deck ID');
            return;
        }
        
        payload.player2_id = player2Id;
        payload.player2_deck_id = player2DeckId;
    }
    
    try {
        const response = await apiCall('/battle/start', 'POST', payload);
        
        currentMatchId = response.match_id;
        currentGameState = response.game_state;
        // currentPlayerIndex stays as 1 (you are always player 1)
        // Don't change it based on current_player - that's just whose turn it is
        
        document.getElementById('setupPanel').style.display = 'none';
        document.getElementById('gameBoard').style.display = 'block';
        
        updateGameBoard();
        
        // If it's AI's turn, process it automatically
        if (matchMode === 'PVE' && currentGameState.current_player === 2) {
            await processAITurn();
        }
    } catch (error) {
        console.error('Failed to start match:', error);
    }
}

// Process AI turn
async function processAITurn() {
    if (matchMode !== 'PVE') {
        console.log('Not PVE mode, skipping AI turn');
        return;
    }
    
    // Double-check it's actually the AI's turn
    if (currentGameState && currentGameState.current_player !== 2) {
        console.log('Not AI turn, current player is:', currentGameState.current_player);
        return;
    }
    
    // Don't process if there's a pending trap trigger waiting for player decision
    if (pendingTrapTrigger) {
        console.log('Trap trigger pending, waiting for player decision');
        return;
    }
    
    showLoading(true);
    try {
        console.log('Processing AI turn...');
        const response = await apiCall('/battle/ai-turn', 'POST', {
            match_id: currentMatchId,
            ai_player_index: 2,
        });
        
        currentGameState = response.game_state;
        // Don't change currentPlayerIndex - you stay as player 1
        
        updateGameBoard();
        
        // Check if a player trap was triggered (requires player decision)
        if (response.trap_triggers_available && response.trap_triggers_available.length > 0) {
            // Only show trap trigger if it's YOUR trap (player 1)
            const triggerPlayerIndex = response.trigger_player_index || 1;
            if (triggerPlayerIndex === currentPlayerIndex) {
                pendingTrapTrigger = response;
                showTrapTriggerModal(response.trap_triggers_available[0], response);
                // STOP processing AI turn - wait for player to respond to trap
                return;
            }
        }
        
        // Log AI actions
        if (response.ai_actions_taken && response.ai_actions_taken.length > 0) {
            console.log('AI took actions:', response.ai_actions_taken);
        }
        
        // If AI ended turn and it's back to player 1, we're done
        // Otherwise, if there's still an ai_turn flag, process again
        if (response.ai_turn && currentGameState.current_player === 2) {
            console.log('AI turn still active, processing again...');
            setTimeout(() => processAITurn(), 500);
        }
    } catch (error) {
        console.error('AI turn failed:', error);
        // Show user-friendly error message
        if (error.message) {
            alert(`AI turn error: ${error.message}`);
        } else {
            alert(`AI turn error: ${JSON.stringify(error)}`);
        }
    } finally {
        showLoading(false);
    }
}

// Send action
async function sendAction(action, payload = {}) {
    if (!currentMatchId) {
        alert('No active match');
        return;
    }
    
    try {
        const response = await apiCall('/battle/action', 'POST', {
            match_id: currentMatchId,
            player_index: currentPlayerIndex,
            action: action,
            ...payload,
        });
        
        currentGameState = response.game_state;
        // Don't change currentPlayerIndex - you stay as player 1
        
        // Check for trap triggers
        if (response.trap_triggers_available && response.trap_triggers_available.length > 0) {
            // Only show trap trigger if it's YOUR trap
            const triggerPlayerIndex = response.trigger_player_index;
            if (triggerPlayerIndex === currentPlayerIndex) {
                pendingTrapTrigger = response;
                showTrapTriggerModal(response.trap_triggers_available[0], response);
                return;
            } else {
                // Opponent's trap - don't show to us, just continue with action
                // The server will handle opponent trap activation automatically in PVE
                // In PVP, the opponent will see it on their side
            }
        }
        
        // Force update game board to refresh monster states
        updateGameBoard();
        
        // If PVE and it's now AI's turn, process it automatically
        // Check both response.ai_turn flag and current_player to be safe
        const isAITurn = matchMode === 'PVE' && 
                         currentPlayerIndex === 1 && // Only auto-process if we're player 1
                         (response.ai_turn === true || currentGameState.current_player === 2);
        
        if (isAITurn) {
            console.log('AI turn detected, processing...', {
                matchMode,
                currentPlayerIndex,
                ai_turn: response.ai_turn,
                current_player: currentGameState.current_player
            });
            setTimeout(() => processAITurn(), 500); // Small delay for UX
        } else {
            console.log('Not AI turn:', {
                matchMode,
                currentPlayerIndex,
                ai_turn: response.ai_turn,
                current_player: currentGameState.current_player
            });
        }
    } catch (error) {
        console.error('Action failed:', error);
    }
}

// Trigger trap
async function triggerTrap(activate) {
    if (!pendingTrapTrigger) return;
    
    closeModal('trapTriggerModal');
    
    const wasPendingTrap = pendingTrapTrigger;
    pendingTrapTrigger = null; // Clear immediately to allow AI turn to continue
    
    if (activate) {
        try {
            const trigger = wasPendingTrap.trap_triggers_available[0];
            const response = await apiCall('/battle/trigger-trap', 'POST', {
                match_id: currentMatchId,
                player_index: wasPendingTrap.trigger_player_index || currentPlayerIndex,
                trap_instance_id: trigger.trap_instance_id,
                trigger_type: wasPendingTrap.trigger_type,
                trigger_event: wasPendingTrap.trigger_event,
                pending_action: wasPendingTrap.pending_action,
            });
            
            currentGameState = response.game_state;
            updateGameBoard();
            
            // If trap cancelled the action, we're done
            // If attack was completed by trap (prevent-destruction), we're done
            // Otherwise, continue with pending action if it exists
            if (!response.cancelled_action && !response.attack_completed && wasPendingTrap.pending_action) {
                const pending = wasPendingTrap.pending_action;
                // Re-send the original action with correct structure
                const actionPayload = {
                    match_id: currentMatchId,
                    player_index: pending.player_index || currentPlayerIndex,
                    action: pending.action,
                };
                
                // Add the specific action payload
                if (pending.play_monster) actionPayload.play_monster = pending.play_monster;
                if (pending.play_spell) actionPayload.play_spell = pending.play_spell;
                if (pending.play_trap) actionPayload.play_trap = pending.play_trap;
                if (pending.activate_trap) actionPayload.activate_trap = pending.activate_trap;
                if (pending.activate_hero_ability) actionPayload.activate_hero_ability = pending.activate_hero_ability;
                if (pending.attack_monster) actionPayload.attack_monster = pending.attack_monster;
                if (pending.attack_player) actionPayload.attack_player = pending.attack_player;
                
                await sendAction(pending.action, actionPayload);
            }
        } catch (error) {
            console.error('Trap trigger failed:', error);
        }
    } else {
        // Continue with pending action if it exists (trap declined)
        if (wasPendingTrap.pending_action) {
            const pending = wasPendingTrap.pending_action;
            // Re-send the original action with correct structure
            const actionPayload = {
                match_id: currentMatchId,
                player_index: pending.player_index || currentPlayerIndex,
                action: pending.action,
            };
            
            // Add the specific action payload
            if (pending.play_monster) actionPayload.play_monster = pending.play_monster;
            if (pending.play_spell) actionPayload.play_spell = pending.play_spell;
            if (pending.play_trap) actionPayload.play_trap = pending.play_trap;
            if (pending.activate_trap) actionPayload.activate_trap = pending.activate_trap;
            if (pending.activate_hero_ability) actionPayload.activate_hero_ability = pending.activate_hero_ability;
            if (pending.attack_monster) actionPayload.attack_monster = pending.attack_monster;
            if (pending.attack_player) actionPayload.attack_player = pending.attack_player;
            
            await sendAction(pending.action, actionPayload);
        }
    }
    
    // After trap is resolved, if it's still AI's turn, continue processing
    if (matchMode === 'PVE' && currentGameState && currentGameState.current_player === 2) {
        setTimeout(() => processAITurn(), 500);
    }
}

// Update game board
function updateGameBoard() {
    if (!currentGameState) return;
    
    const player = currentGameState.players[currentPlayerIndex];
    const opponent = currentGameState.players[currentPlayerIndex === 1 ? 2 : 1];
    
    // Update headers
    const isMyTurn = currentPlayerIndex === currentGameState.current_player;
    const turnIndicator = isMyTurn ? ' (Your Turn)' : ' (Opponent\'s Turn)';
    document.getElementById('turnInfo').textContent = `Turn: ${currentGameState.turn}${turnIndicator}`;
    document.getElementById('phaseInfo').textContent = `Phase: ${currentGameState.phase}`;
    document.getElementById('phaseDisplay').textContent = `Phase: ${currentGameState.phase}`;
    document.getElementById('playerName').textContent = player.name;
    document.getElementById('playerHp').textContent = `${player.hp} HP`;
    document.getElementById('opponentName').textContent = opponent.name;
    document.getElementById('opponentHp').textContent = `${opponent.hp} HP`;
    
    // Update action buttons state
    updateActionButtons();
    
    // Don't disable buttons here - let updateActionButtons() handle it
    // This was causing buttons to be enabled when they shouldn't be
    
    // Update player zones
    updateZones('player', player);
    updateZones('opponent', opponent);
    
    // Update hand
    updateHand(player.hand);
    
    // Update hero
    updateHero('player', player.hero);
    updateHero('opponent', opponent.hero);
    
    // Update log
    updateLog(currentGameState.log);
    
    // Check for match end
    checkMatchEnd();
    
    // Update action buttons
    updateActionButtons();
    
    // Clear selections (but preserve if still valid)
    if (selectedCard) {
        // Check if selected card is still in hand
        const stillInHand = player.hand.some(c => c.instance_id === selectedCard.instance_id);
        if (!stillInHand) {
            selectedCard = null;
        }
    }
    if (selectedBoardMonster) {
        // Check if selected monster is still on board and update its zone_index
        const currentMonster = player.monster_zones.find(m => m && m.instance_id === selectedBoardMonster.instance_id);
        if (!currentMonster) {
            // Monster destroyed - clear selection
            selectedBoardMonster = null;
        } else {
            // Monster still exists - update zone_index and monster data to match current state
            const currentZoneIndex = player.monster_zones.findIndex(m => m && m.instance_id === selectedBoardMonster.instance_id);
            if (currentZoneIndex !== -1) {
                selectedBoardMonster = { ...currentMonster, zone_index: currentZoneIndex };
            } else {
                selectedBoardMonster = null;
            }
        }
    }
    selectedTarget = null;
}

// Update zones
function updateZones(prefix, player) {
    const isOpponent = prefix === 'opponent';
    const isMyPlayer = prefix === 'player';
    
    const renderStatusTags = (monster) => {
        const rawStatuses = monster.statuses || [];
        if (!rawStatuses.length) return '';

        const statuses = rawStatuses.map(s => typeof s === 'string' ? { code: s } : s).filter(s => s && s.code);
        if (!statuses.length) return '';

        const labelMap = {
            FROZEN: 'Frozen',
            STATUS_IMMUNE: 'Status Immune',
            HASTE: 'Haste',
            BURN: 'Burn',
        };
        const classMap = {
            FROZEN: 'status-frozen',
            STATUS_IMMUNE: 'status-immune',
            HASTE: 'status-haste',
            BURN: 'status-burn',
        };

        const tags = statuses.map(s => {
            const code = (s.code || '').toUpperCase();
            const label = labelMap[code] || code;
            const cls = classMap[code] || 'status-generic';
            return `<span class="status-tag ${cls}">${label}</span>`;
        });

        return `<div class="zone-card-status-tags">${tags.join('')}</div>`;
    };

    // Monster zones
    const monsterContainer = document.getElementById(`${prefix}Monsters`);
    player.monster_zones.forEach((monster, idx) => {
        const slot = monsterContainer.querySelector(`[data-zone="${idx}"]`);
        // Check if monster exists and has valid data (not null, not undefined, has instance_id)
        if (monster && monster.instance_id && monster.name) {
            const imageUrl = getCardImageUrl(monster);
            const isFaceDown = monster.face_down;
            
            // Show details to owner, hide from opponent if face-down
            const canAttack = monster.can_attack || false;
            const attackStatus = canAttack ? 'Can Attack' : 'Can\'t Attack';
            const attackStatusClass = canAttack ? 'status-can-attack' : 'status-cant-attack';
            
            if (isFaceDown && isOpponent) {
                // Opponent's face-down card - show nothing
                slot.innerHTML = '<div class="face-down-card">Face Down</div>';
            } else if (isFaceDown && isMyPlayer) {
                // My face-down card - show details to me
                slot.innerHTML = `
                    <div class="zone-card-content">
                        <div class="zone-card-name">${monster.name}</div>
                        <div class="zone-card-stats">⭐${monster.stars} | ${monster.atk}/${monster.hp}</div>
                        <div class="zone-card-status">Face Down</div>
                        <div class="zone-card-status ${attackStatusClass}">${attackStatus}</div>
                        ${renderStatusTags(monster)}
                    </div>
                `;
            } else {
                // Face-up card - show full details
                // Check for active buffs (we'll track this via log events, but for now show base stats)
                const buffEffects = currentGameState.log
                    .filter(e => e.type === 'PLAY_SPELL' && e.effects)
                    .flatMap(e => e.effects.filter(ef => ef.type === 'EFFECT_BUFF_MONSTER' && ef.card_instance_id === monster.instance_id))
                    .reduce((acc, ef) => {
                        acc.atk = (acc.atk || 0) + (ef.atk_after - ef.atk_before);
                        acc.hp = (acc.hp || 0) + (ef.hp_after - ef.hp_before);
                        return acc;
                    }, {atk: 0, hp: 0});
                
                const buffDisplay = (buffEffects.atk !== 0 || buffEffects.hp !== 0) 
                    ? `<div class="zone-card-buff">+${buffEffects.atk} ATK, +${buffEffects.hp} HP</div>` 
                    : '';
                
                if (imageUrl) {
                    slot.innerHTML = `
                        <img src="${imageUrl}" alt="${monster.name}" class="zone-card-image" 
                             onerror="this.style.display='none'; this.nextElementSibling.style.display='block';">
                        <div class="zone-card-content" style="display: none;">
                            <div class="zone-card-name">${monster.name}</div>
                            <div class="zone-card-stats">⭐${monster.stars} | ${monster.atk}/${monster.hp}</div>
                            ${buffDisplay}
                            ${monster.hp < monster.max_hp ? `<div class="zone-card-damage">-${monster.max_hp - monster.hp}</div>` : ''}
                            <div class="zone-card-status ${attackStatusClass}">${attackStatus}</div>
                            ${renderStatusTags(monster)}
                        </div>
                    `;
                } else {
                    slot.innerHTML = `
                        <div class="zone-card-content">
                            <div class="zone-card-name">${monster.name}</div>
                            <div class="zone-card-stats">⭐${monster.stars} | ${monster.atk}/${monster.hp}</div>
                            ${buffDisplay}
                            ${monster.hp < monster.max_hp ? `<div class="zone-card-damage">-${monster.max_hp - monster.hp}</div>` : ''}
                            <div class="zone-card-status ${attackStatusClass}">${attackStatus}</div>
                            ${renderStatusTags(monster)}
                        </div>
                    `;
                }
            }
            slot.className = 'zone-slot occupied';
            slot.setAttribute('data-instance-id', monster.instance_id);
            
            // Make player's monsters selectable for attacking
            if (isMyPlayer && canAttack) {
                slot.style.cursor = 'pointer';
                slot.onclick = () => selectBoardMonster(monster, idx);
                if (selectedBoardMonster && selectedBoardMonster.instance_id === monster.instance_id) {
                    slot.classList.add('selected');
                } else {
                    slot.classList.remove('selected');
                }
            } else if (isMyPlayer && isFaceDown) {
                // Face-down monsters can also be selected (for targeting)
                slot.style.cursor = 'pointer';
                slot.onclick = () => selectBoardMonster(monster, idx);
                if (selectedBoardMonster && selectedBoardMonster.instance_id === monster.instance_id) {
                    slot.classList.add('selected');
                } else {
                    slot.classList.remove('selected');
                }
            } else {
                slot.onclick = null;
                slot.style.cursor = 'default';
            }
        } else {
            // Clear the slot completely (monster destroyed or invalid)
            slot.innerHTML = '';
            slot.textContent = '-';
            slot.className = 'zone-slot';
            slot.removeAttribute('data-instance-id');
            slot.onclick = null;
            slot.style.cursor = 'default';
            slot.classList.remove('selected', 'occupied');
        }
    });
    
    // Spell/Trap zones
    const spellTrapContainer = document.getElementById(`${prefix}SpellTraps`);
    player.spell_trap_zones.forEach((card, idx) => {
        const slot = spellTrapContainer.querySelector(`[data-zone="${idx}"]`);
        if (card) {
            const imageUrl = getCardImageUrl(card);
            const isFaceDown = card.face_down;
            
            const description = card.description || card.rules_text || '';
            const effectParams = card.effect_params || {};
            const effects = effectParams.effects || [];
            const triggerKeywords = effects.map(e => e.keyword || '').filter(k => k.startsWith('TRAP_') || k.startsWith('SPELL_COUNTER'));
            const triggerInfo = triggerKeywords.length > 0 ? `Triggers: ${triggerKeywords.join(', ')}` : '';
            
            // Always show "Set" for opponent traps (traps are always hidden from opponent until triggered)
            if (isOpponent && card.card_type === 'trap') {
                slot.innerHTML = '<div class="face-down-card">Set</div>';
            } else if (isFaceDown && isOpponent) {
                slot.innerHTML = '<div class="face-down-card">Set</div>';
            } else if (isFaceDown && isMyPlayer) {
                slot.innerHTML = `
                    <div class="zone-card-content">
                        <div class="zone-card-name">${card.name}</div>
                        <div class="zone-card-type">${card.card_type}</div>
                        ${description ? `<div class="zone-card-description" title="${description}">${description.substring(0, 40)}${description.length > 40 ? '...' : ''}</div>` : ''}
                        ${triggerInfo ? `<div class="zone-card-trigger" title="${triggerInfo}">${triggerInfo.substring(0, 30)}${triggerInfo.length > 30 ? '...' : ''}</div>` : ''}
                    </div>
                `;
            } else {
                if (imageUrl) {
                    slot.innerHTML = `<img src="${imageUrl}" alt="${card.name}" class="zone-card-image" 
                                   onerror="this.parentElement.innerHTML='${card.name}';">`;
                } else {
                    slot.innerHTML = `
                        <div class="zone-card-content">
                            <div class="zone-card-name">${card.name}</div>
                            ${description ? `<div class="zone-card-description" title="${description}">${description.substring(0, 40)}${description.length > 40 ? '...' : ''}</div>` : ''}
                        </div>
                    `;
                }
            }
            slot.className = 'zone-slot occupied';
            slot.setAttribute('data-instance-id', card.instance_id);
        } else {
            slot.textContent = '-';
            slot.className = 'zone-slot';
            slot.removeAttribute('data-instance-id');
        }
    });
}

// Get card image URL
function getCardImageUrl(card) {
    if (!USE_CARD_IMAGES) return null;
    
    // Try multiple patterns:
    // 1. By card_code: /images/cards/CORE-SUMMON-001.png
    // 2. By card_code + element: /images/cards/CORE-SUMMON-001-fire.png
    // 3. By name (sanitized): /images/cards/goblin-squad.png
    
    const code = card.card_code || '';
    const elementId = card.element_id;
    const name = (card.name || '').toLowerCase().replace(/[^a-z0-9]/g, '-');
    
    // Element names mapping (from your element table)
    const elementNames = {
        1: 'neutral',
        2: 'fire',
        3: 'ice',
        4: 'nature',
        5: 'void',
        6: 'dark',
        7: 'holy'
    };
    
    const elementName = elementNames[elementId] || 'neutral';
    
    // Try card_code with element first (for element variants)
    if (code && elementId && elementId !== 1) {
        return `${CARD_IMAGE_BASE}/${code}-${elementName}.png`;
    }
    
    // Try card_code
    if (code) {
        return `${CARD_IMAGE_BASE}/${code}.png`;
    }
    
    // Fallback to name
    if (name) {
        return `${CARD_IMAGE_BASE}/${name}.png`;
    }
    
    return null;
}

// Update hand
function updateHand(hand) {
    const handContainer = document.getElementById('handCards');
    const handCount = document.getElementById('handCount');
    
    handCount.textContent = hand.length;
    handContainer.innerHTML = '';
    
    hand.forEach(card => {
        const cardEl = document.createElement('div');
        cardEl.className = 'card';
        cardEl.setAttribute('data-instance-id', card.instance_id);
        cardEl.onclick = () => selectCard(card);
        
        const imageUrl = getCardImageUrl(card);
        
        const description = card.description || '';
        cardEl.innerHTML = `
            ${imageUrl ? `
                <img src="${imageUrl}" alt="${card.name}" class="card-image" 
                     onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
            ` : ''}
            <div class="card-content" ${imageUrl ? 'style="display: none;"' : ''}>
                <div class="card-name">${card.name}</div>
                <div class="card-type">${card.card_type}</div>
                ${card.card_type === 'monster' || card.card_type === 'hero' ? `
                    <div class="card-stats">
                        <span>⭐${card.stars}</span>
                        <span>${card.atk}/${card.hp}</span>
                    </div>
                ` : ''}
                ${description ? `<div class="card-description" title="${description}">${description.substring(0, 50)}${description.length > 50 ? '...' : ''}</div>` : ''}
            </div>
        `;
        
        if (selectedCard && selectedCard.instance_id === card.instance_id) {
            cardEl.classList.add('selected');
        }
        
        handContainer.appendChild(cardEl);
    });
    
    updateActionButtons();
}

// Update hero
function updateHero(prefix, hero) {
    const heroEl = document.getElementById(`${prefix}Hero`);
    if (hero) {
        const imageUrl = getCardImageUrl(hero);
        if (imageUrl) {
            heroEl.innerHTML = `<img src="${imageUrl}" alt="${hero.name}" class="hero-card-image" 
                                   onerror="this.parentElement.textContent='${hero.name}';">`;
        } else {
            heroEl.textContent = hero.name;
        }
        heroEl.className = 'hero-card occupied';
    } else {
        heroEl.textContent = '-';
        heroEl.className = 'hero-card';
    }
}

// Update log
function updateLog(log) {
    const logContainer = document.getElementById('logContent');
    logContainer.innerHTML = '';
    
    log.slice(-20).forEach(entry => {
        const logEl = document.createElement('div');
        logEl.className = 'log-entry';
        logEl.textContent = formatLogEntry(entry);
        logContainer.appendChild(logEl);
    });
    
    // Auto-scroll to bottom
    logContainer.scrollTop = logContainer.scrollHeight;
}

// Check for match end and show win screen
function checkMatchEnd() {
    if (!currentGameState) return;
    
    // Check if match has ended
    if (currentGameState.status === 'completed' || currentGameState.winner !== null) {
        const winner = currentGameState.winner;
        const isPlayerWin = winner === currentPlayerIndex;
        const isDraw = winner === null;
        
        showWinScreen(isPlayerWin, isDraw);
    }
    
    // Also check log for MATCH_END entries
    const matchEndEntry = currentGameState.log.find(e => e.type === 'MATCH_END');
    if (matchEndEntry && currentGameState.status !== 'completed') {
        const winner = matchEndEntry.winner;
        const isPlayerWin = winner === currentPlayerIndex;
        const isDraw = winner === null;
        
        showWinScreen(isPlayerWin, isDraw);
    }
}

// Show win screen modal
function showWinScreen(isWin, isDraw) {
    // Don't show multiple times
    if (document.getElementById('winScreenModal')) {
        return;
    }
    
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.id = 'winScreenModal';
    modal.style.display = 'flex';
    
    let title, message;
    if (isDraw) {
        title = 'Draw!';
        message = 'The match ended in a draw.';
    } else if (isWin) {
        title = 'Victory!';
        message = 'You won the match!';
    } else {
        title = 'Defeat';
        message = 'You lost the match.';
    }
    
    modal.innerHTML = `
        <div class="modal-content" style="max-width: 400px; text-align: center;">
            <h2 style="font-size: 2rem; margin-bottom: 1rem; color: ${isWin ? 'var(--success-color)' : isDraw ? 'var(--warning-color)' : 'var(--danger-color)'};">${title}</h2>
            <p style="font-size: 1.2rem; margin-bottom: 2rem;">${message}</p>
            <button class="btn btn-primary" onclick="resetToStartScreen()" style="font-size: 1.1rem; padding: 0.75rem 2rem;">New Match</button>
        </div>
    `;
    
    document.body.appendChild(modal);
}

// Reset to start screen
function resetToStartScreen() {
    // Remove win screen modal
    const modal = document.getElementById('winScreenModal');
    if (modal) {
        modal.remove();
    }
    
    // Reset game state
    currentMatchId = null;
    currentGameState = null;
    selectedCard = null;
    selectedBoardMonster = null;
    selectedTarget = null;
    pendingTrapTrigger = null;
    
    // Hide game board, show setup panel
    document.getElementById('gameBoard').style.display = 'none';
    document.getElementById('setupPanel').style.display = 'block';
    
    // Clear any modals
    document.querySelectorAll('.modal').forEach(m => {
        if (m.id !== 'winScreenModal') {
            m.style.display = 'none';
        }
    });
}

function formatLogEntry(entry) {
    if (typeof entry === 'string') return entry;
    if (entry.type === 'GAME_INIT') {
        return `Game started: ${entry.player1} vs ${entry.player2}`;
    }
    if (entry.type === 'PLAY_MONSTER') {
        // Try to get monster stats from game state
        let statsText = '';
        if (currentGameState && currentGameState.players) {
            const player = currentGameState.players[entry.player];
            if (player && player.monster_zones) {
                const monster = player.monster_zones.find(m => m && m.instance_id === entry.card_instance_id);
                if (monster) {
                    statsText = ` (⭐${monster.stars} | ${monster.atk}/${monster.hp})`;
                }
            }
        }
        return `Player ${entry.player} played ${entry.card_name || 'a monster'}${statsText}`;
    }
    if (entry.type === 'PLAY_SPELL') {
        let msg = `Player ${entry.player} played ${entry.card_name || 'a spell'}`;
        
        // Add target monster info if available
        if (entry.target_monster) {
            const target = entry.target_monster;
            const targetName = target.name || 'Unknown';
            const targetStats = ` (⭐${target.stars || '?'} | ${target.atk || 0}/${target.hp_before || target.hp || 0})`;
            msg += ` → Target: ${targetName}${targetStats}`;
        }
        
        if (entry.effects && entry.effects.length > 0) {
            const effectMsgs = [];
            entry.effects.forEach(eff => {
                if (eff.type === 'EFFECT_BUFF_MONSTER') {
                    const atkChange = eff.atk_after - eff.atk_before;
                    const hpChange = eff.hp_after - eff.hp_before;
                    effectMsgs.push(`Buff: +${atkChange} ATK, +${hpChange} HP`);
                } else if (eff.type === 'EFFECT_DAMAGE_MONSTER') {
                    const hpAfter = eff.hp_after !== undefined ? ` (${eff.hp_after}/${eff.hp_before} HP)` : '';
                    effectMsgs.push(`Dealt ${eff.amount} damage${hpAfter}`);
                } else if (eff.type === 'EFFECT_DAMAGE_PLAYER') {
                    effectMsgs.push(`Dealt ${eff.amount} damage to Player ${eff.player_index}`);
                } else if (eff.type === 'EFFECT_HEAL_MONSTER') {
                    effectMsgs.push(`Healed ${eff.amount} HP`);
                } else if (eff.type === 'EFFECT_HEAL_PLAYER') {
                    effectMsgs.push(`Healed Player ${eff.player_index} for ${eff.amount} HP`);
                } else if (eff.type === 'EFFECT_DRAW_CARDS') {
                    effectMsgs.push(`Drew ${eff.amount || eff.count || 0} cards`);
                } else if (eff.type === 'EFFECT_PREVENT_DESTRUCTION') {
                    effectMsgs.push(`Prevented destruction (HP: ${eff.hp_before} → ${eff.hp_after})`);
                } else if (eff.type === 'EFFECT_HASTE') {
                    effectMsgs.push(`Granted haste to ${eff.monster_name || 'monster'}`);
                } else if (eff.type === 'EFFECT_FREEZE_MONSTER') {
                    effectMsgs.push(`Froze ${eff.monster_name || 'monster'}`);
                }
            });
            if (effectMsgs.length > 0) {
                msg += ` → ${effectMsgs.join(', ')}`;
            }
        }
        return msg;
    }
    if (entry.type === 'ATTACK_MONSTER') {
        // Try to get monster names and stats from game state
        let attackerName = 'monster';
        let defenderName = 'monster';
        let attackerStats = '';
        let defenderStats = '';
        
        if (currentGameState && currentGameState.players) {
            const atkPlayer = currentGameState.players[entry.attacking_player];
            const defPlayer = currentGameState.players[entry.defending_player];
            
            if (atkPlayer && atkPlayer.monster_zones && entry.attacker_instance_id) {
                const attacker = atkPlayer.monster_zones.find(m => m && m.instance_id === entry.attacker_instance_id);
                if (attacker) {
                    attackerName = attacker.name;
                    attackerStats = ` (⭐${attacker.stars} | ${attacker.atk}/${attacker.hp})`;
                }
            }
            
            if (defPlayer && defPlayer.monster_zones && entry.defender_instance_id) {
                const defender = defPlayer.monster_zones.find(m => m && m.instance_id === entry.defender_instance_id);
                if (defender) {
                    defenderName = defender.name;
                    defenderStats = ` (⭐${defender.stars} | ${defender.atk}/${defender.hp})`;
                }
            }
        }
        
        let msg = `Player ${entry.attacking_player}'s ${attackerName}${attackerStats} attacked Player ${entry.defending_player}'s ${defenderName}${defenderStats}`;
        if (entry.attacker_atk !== undefined) {
            msg += ` → ${entry.attacker_atk} ATK vs ${entry.defender_atk || 0} ATK`;
        }
        if (entry.attacker_hp_after !== undefined && entry.defender_hp_after !== undefined) {
            msg += ` | Attacker: ${entry.attacker_hp_after}/${entry.attacker_hp_before} HP, Defender: ${entry.defender_hp_after}/${entry.defender_hp_before} HP`;
        }
        if (entry.overflow_to_attacker_player > 0 || entry.overflow_to_defender_player > 0) {
            msg += ` | Overflow: ${entry.overflow_to_defender_player} to Player ${entry.defending_player}, ${entry.overflow_to_attacker_player} to Player ${entry.attacking_player}`;
        }
        if (entry.attacker_player_hp_after !== undefined) {
            msg += ` | Player ${entry.attacking_player}: ${entry.attacker_player_hp_after} HP, Player ${entry.defending_player}: ${entry.defender_player_hp_after} HP`;
        }
        return msg;
    }
    if (entry.type === 'ATTACK_PLAYER') {
        let msg = `Player ${entry.attacking_player} attacked Player ${entry.defending_player} directly`;
        if (entry.attacker_atk !== undefined) {
            msg += ` (${entry.attacker_atk} damage)`;
        }
        if (entry.defender_hp_after !== undefined) {
            msg += ` → Player ${entry.defending_player}: ${entry.defender_hp_after}/${entry.defender_hp_before} HP`;
        }
        return msg;
    }
    if (entry.type === 'END_TURN') {
        return `Player ${entry.from_player} ended turn → Player ${entry.to_player}'s turn (Turn ${entry.turn})`;
    }
    if (entry.type === 'ACTIVATE_HERO_ABILITY') {
        let msg = `Player ${entry.player} activated ${entry.card_name || 'hero'} ability`;
        if (entry.effects && entry.effects.length > 0) {
            const effectMsgs = [];
            entry.effects.forEach(eff => {
                if (eff.type === 'EFFECT_BUFF_MONSTER') {
                    const atkChange = eff.atk_after - eff.atk_before;
                    const hpChange = eff.hp_after - eff.hp_before;
                    effectMsgs.push(`Buff: +${atkChange} ATK, +${hpChange} HP`);
                } else if (eff.type === 'EFFECT_DAMAGE_MONSTER') {
                    effectMsgs.push(`Dealt ${eff.amount} damage`);
                } else if (eff.type === 'EFFECT_DAMAGE_PLAYER') {
                    effectMsgs.push(`Dealt ${eff.amount} damage to Player ${eff.player_index}`);
                } else if (eff.type === 'EFFECT_HEAL_MONSTER') {
                    effectMsgs.push(`Healed ${eff.amount} HP`);
                } else if (eff.type === 'EFFECT_HEAL_PLAYER') {
                    effectMsgs.push(`Healed Player ${eff.player_index} for ${eff.amount} HP`);
                } else if (eff.type === 'EFFECT_DRAW_CARDS') {
                    effectMsgs.push(`Drew ${eff.amount || eff.count || 0} cards`);
                } else if (eff.type === 'EFFECT_PREVENT_DESTRUCTION') {
                    effectMsgs.push(`Prevented destruction (HP: ${eff.hp_before} → ${eff.hp_after})`);
                } else if (eff.type === 'EFFECT_HASTE') {
                    effectMsgs.push(`Granted haste to ${eff.monster_name || 'monster'}`);
                } else if (eff.type === 'EFFECT_FREEZE_MONSTER') {
                    effectMsgs.push(`Froze ${eff.monster_name || 'monster'}`);
                }
            });
            if (effectMsgs.length > 0) {
                msg += ` → ${effectMsgs.join(', ')}`;
            }
        }
        return msg;
    }
    if (entry.type === 'HERO_PASSIVE_AURA') {
        const atkChange = entry.atk_after - entry.atk_before;
        const hpChange = entry.hp_after - entry.hp_before;
        return `Hero ${entry.hero_name} aura: ${entry.monster_name} gained +${atkChange} ATK, +${hpChange} HP`;
    }
    if (entry.type === 'PLAY_HERO') {
        // Try to get hero stats from game state
        let statsText = '';
        if (currentGameState && currentGameState.players) {
            const player = currentGameState.players[entry.player];
            if (player && player.hero && player.hero.instance_id === entry.card_instance_id) {
                const hero = player.hero;
                statsText = ` (⭐${hero.stars} | ${hero.atk}/${hero.hp})`;
            }
        }
        return `Player ${entry.player} summoned ${entry.card_name || 'a hero'}${statsText}`;
    }
    if (entry.type === 'ACTION_CANCELLED') {
        if (entry.original_action && entry.original_action.action === 'PLAY_SPELL') {
            const spellName = entry.original_action.play_spell?.card_name || 'a spell';
            return `Spell ${spellName} was countered and negated`;
        }
        return `Action was cancelled: ${entry.reason || 'unknown'}`;
    }
    if (entry.type === 'SPELL_REFLECTED') {
        let msg = `Spell ${entry.spell_name || 'a spell'} was reflected by Player ${entry.reflected_by}`;
        if (entry.target_monster) {
            msg += ` → Hit ${entry.target_monster}`;
        }
        if (entry.effects && entry.effects.length > 0) {
            const effectMsgs = [];
            entry.effects.forEach(eff => {
                if (eff.type === 'EFFECT_DAMAGE_MONSTER') {
                    effectMsgs.push(`Dealt ${eff.amount} damage`);
                } else if (eff.type === 'EFFECT_DAMAGE_PLAYER') {
                    effectMsgs.push(`Dealt ${eff.amount} damage to Player ${eff.player_index}`);
                }
            });
            if (effectMsgs.length > 0) {
                msg += ` → ${effectMsgs.join(', ')}`;
            }
        }
        return msg;
    }
    if (entry.type === 'TRAP_TRIGGERED') {
        let msg = `Player ${entry.player} triggered ${entry.card_name || 'a trap'}`;
        if (entry.cancelled_action) {
            msg += ' → Countered and negated the action';
        }
        if (entry.effects && entry.effects.length > 0) {
            const effectMsgs = [];
            entry.effects.forEach(eff => {
                if (eff.type === 'EFFECT_COUNTER_SPELL' || eff.type === 'EFFECT_COUNTER_AND_REFLECT_SPELL') {
                    if (eff.reflect_spell) {
                        effectMsgs.push('Countered and reflected spell');
                    } else {
                        effectMsgs.push('Countered spell');
                    }
                }
            });
            if (effectMsgs.length > 0) {
                msg += ` → ${effectMsgs.join(', ')}`;
            }
        }
        return msg;
    }
    return JSON.stringify(entry);
}

// Card selection
function selectCard(card) {
    // Toggle selection
    if (selectedCard && selectedCard.instance_id === card.instance_id) {
        selectedCard = null;
    } else {
        selectedCard = card;
        // Clear board monster selection when selecting hand card
        selectedBoardMonster = null;
    }
    updateHand(currentGameState.players[currentPlayerIndex].hand);
    updateZones('player', currentGameState.players[currentPlayerIndex]);
    updateActionButtons();
}

// Board monster selection (for attacking)
function selectBoardMonster(monster, zoneIndex) {
    // Toggle selection
    if (selectedBoardMonster && selectedBoardMonster.instance_id === monster.instance_id) {
        selectedBoardMonster = null;
    } else {
        // Always find the current zone index from game state to ensure accuracy
        const player = currentGameState.players[currentPlayerIndex];
        const currentZoneIndex = player.monster_zones.findIndex(m => m && m.instance_id === monster.instance_id);
        if (currentZoneIndex === -1) {
            // Monster not found - don't select
            return;
        }
        selectedBoardMonster = { ...monster, zone_index: currentZoneIndex };
        // Clear hand card selection when selecting board monster
        selectedCard = null;
    }
    updateHand(currentGameState.players[currentPlayerIndex].hand);
    updateZones('player', currentGameState.players[currentPlayerIndex]);
    updateActionButtons();
}

// Update action buttons based on current selection
function updateActionButtons() {
    const playButton = document.getElementById('playButton');
    const attackButton = document.getElementById('attackButton');
    const isMyTurn = currentGameState && currentPlayerIndex === currentGameState.current_player;
    
    if (!isMyTurn) {
        playButton.disabled = true;
        attackButton.disabled = true;
        return;
    }
    
    // Enable Play button if a card is selected from hand
    if (selectedCard) {
        const cardType = selectedCard.card_type;
        if (cardType === 'monster' || cardType === 'hero' || cardType === 'spell' || cardType === 'trap') {
            playButton.disabled = false;
        } else {
            playButton.disabled = true;
        }
    } else {
        playButton.disabled = true;
    }
    
    // Enable Attack button if a can-attack monster is selected
    if (selectedBoardMonster && selectedBoardMonster.can_attack) {
        attackButton.disabled = false;
    } else {
        attackButton.disabled = true;
    }
}

// Play selected card from hand
async function playSelectedCard() {
    if (!selectedCard) {
        alert('Please select a card from your hand');
        return;
    }
    
    const cardType = selectedCard.card_type;
    
    if (cardType === 'monster' || cardType === 'hero') {
        await playMonster(selectedCard);
    } else if (cardType === 'spell') {
        await playSpell(selectedCard);
    } else if (cardType === 'trap') {
        await playTrap(selectedCard);
    } else {
        alert('Cannot play this card type');
    }
    
    // Clear selection after playing
    selectedCard = null;
    updateHand(currentGameState.players[currentPlayerIndex].hand);
    updateActionButtons();
}

// Attack with selected monster
async function attackWithSelected() {
    console.log('attackWithSelected called', { selectedBoardMonster, currentPlayerIndex });
    
    if (!selectedBoardMonster) {
        alert('Please select a monster on the board that can attack');
        return;
    }
    
    // Re-fetch the monster from current game state to ensure we have the latest can_attack status
    const player = currentGameState.players[currentPlayerIndex];
    if (!player) {
        console.error('Player not found', currentPlayerIndex);
        return;
    }
    
    const currentMonster = player.monster_zones.find(m => m && m.instance_id === selectedBoardMonster.instance_id);
    
    if (!currentMonster) {
        alert('Monster not found on board');
        selectedBoardMonster = null;
        updateActionButtons();
        return;
    }
    
    console.log('Current monster:', { 
        name: currentMonster.name, 
        can_attack: currentMonster.can_attack,
        instance_id: currentMonster.instance_id 
    });
    
    if (!currentMonster.can_attack) {
        alert('This monster cannot attack');
        selectedBoardMonster = null;
        updateActionButtons();
        return;
    }
    
    // Update selectedBoardMonster with latest data - find the correct zone_index from current game state
    const currentZoneIndex = player.monster_zones.findIndex(m => m && m.instance_id === currentMonster.instance_id);
    if (currentZoneIndex === -1) {
        // Monster not found - clear selection
        selectedBoardMonster = null;
        updateActionButtons();
        updateZones('player', player);
        return;
    }
    selectedBoardMonster = { ...currentMonster, zone_index: currentZoneIndex };
    
    const opponent = currentGameState.players[currentPlayerIndex === 1 ? 2 : 1];
    const opponentMonsters = opponent.monster_zones.filter(m => m !== null);
    
    console.log('Opponent monsters:', opponentMonsters.length);
    
    if (opponentMonsters.length === 0) {
        // Direct attack
        console.log('Direct attack on player');
        await sendAction('ATTACK_PLAYER', {
            attack_player: {
                attacker_instance_id: selectedBoardMonster.instance_id,
            },
        });
    } else if (opponentMonsters.length === 1) {
        // Auto-attack the only monster
        console.log('Attacking single monster:', opponentMonsters[0].name);
        await sendAction('ATTACK_MONSTER', {
            attack_monster: {
                attacker_instance_id: selectedBoardMonster.instance_id,
                defender_instance_id: opponentMonsters[0].instance_id,
            },
        });
    } else {
        // Show target selection
        console.log('Showing target selection modal');
        showAttackTargetModal(opponentMonsters);
    }
    
    // Clear selection after attacking
    selectedBoardMonster = null;
    updateZones('player', currentGameState.players[currentPlayerIndex]);
    updateActionButtons();
}

// Show attack target selection modal
function showAttackTargetModal(opponentMonsters) {
    const modal = document.getElementById('attackModal');
    const content = document.getElementById('attackContent');
    
    content.innerHTML = '<p>Select target:</p>';
    
    // Store the attacker instance ID before closing modal
    const attackerId = selectedBoardMonster ? selectedBoardMonster.instance_id : null;
    
    if (!attackerId) {
        console.error('No attacker selected');
        return;
    }
    
    // Don't show "Attack Player Directly" if opponent has monsters - you must attack monsters first
    // (The game logic already handles direct attack automatically when no monsters exist)
    
    // Add monster targets with ATK/HP display
    opponentMonsters.forEach(monster => {
        const btn = document.createElement('button');
        btn.className = 'btn btn-action';
        const displayName = monster.face_down ? 'Face-Down Monster' : monster.name;
        const statsText = monster.face_down ? '' : ` (⭐${monster.stars} | ${monster.atk}/${monster.hp})`;
        btn.textContent = `${displayName}${statsText}`;
        btn.onclick = async () => {
            closeModal('attackModal');
            await sendAction('ATTACK_MONSTER', {
                attack_monster: {
                    attacker_instance_id: attackerId,
                    defender_instance_id: monster.instance_id,
                },
            });
            selectedBoardMonster = null;
            updateZones('player', currentGameState.players[currentPlayerIndex]);
            updateActionButtons();
        };
        content.appendChild(btn);
    });
    
    modal.style.display = 'flex';
}

// Zone selection
function selectMonsterZone(zoneIndex) {
    selectedZone = zoneIndex;
    document.querySelectorAll('#playerMonsters .zone-slot').forEach((slot, idx) => {
        slot.classList.toggle('selected', idx === zoneIndex);
    });
}

function selectSpellTrapZone(zoneIndex) {
    selectedZone = zoneIndex;
    document.querySelectorAll('#playerSpellTraps .zone-slot').forEach((slot, idx) => {
        slot.classList.toggle('selected', idx === zoneIndex);
    });
}

// Modals
function showPlayMonsterModal() {
    const player = currentGameState.players[currentPlayerIndex];
    const monsters = player.hand.filter(c => c.card_type === 'monster' || c.card_type === 'hero');
    
    const content = document.getElementById('playMonsterContent');
    content.innerHTML = '<p>Select a monster or hero from your hand:</p>';
    
    monsters.forEach(monster => {
        const btn = document.createElement('button');
        btn.className = 'btn btn-action';
        const cardTypeLabel = monster.card_type === 'hero' ? 'Hero' : 'Monster';
        btn.textContent = `${monster.name} (${cardTypeLabel} ⭐${monster.stars})`;
        btn.onclick = () => playMonster(monster);
        btn.style.margin = '0.5rem';
        content.appendChild(btn);
    });
    
    document.getElementById('playMonsterModal').style.display = 'flex';
}

async function playMonster(monster) {
    if (typeof closeModal === 'function') {
        closeModal('playMonsterModal');
    }
    
    if (!monster) {
        if (!selectedCard || (selectedCard.card_type !== 'monster' && selectedCard.card_type !== 'hero')) {
            alert('Please select a monster or hero from your hand');
            return;
        }
        monster = selectedCard;
    }
    
    // Check if tribute needed
    const needsTribute = monster.stars >= 4;
    const needsHeroTribute = monster.stars === 6;
    
    const requiredTributes = needsHeroTribute ? 2 : (needsTribute ? 1 : 0);
    
    if (requiredTributes > 0 && selectedTributes.length < requiredTributes) {
        // Show tribute selection modal
        showTributeSelectionModal(monster, requiredTributes);
        return;
    }
    
    // Always find first empty zone (don't trust selectedZone if it's occupied)
    const player = currentGameState.players[currentPlayerIndex];
    const emptyZone = player.monster_zones.findIndex(m => m === null);
    if (emptyZone === -1) {
        alert('No empty monster zones');
        return;
    }
    selectedZone = emptyZone;
    
    sendAction('PLAY_MONSTER', {
        play_monster: {
            card_instance_id: monster.instance_id,
            zone_index: selectedZone,
            tribute_instance_ids: selectedTributes,
        },
    });
}

function showPlaySpellModal() {
    const player = currentGameState.players[currentPlayerIndex];
    const spells = player.hand.filter(c => c.card_type === 'spell');
    
    const content = document.getElementById('playSpellContent');
    content.innerHTML = '<p>Select a spell from your hand:</p>';
    
    spells.forEach(spell => {
        const btn = document.createElement('button');
        btn.className = 'btn btn-action';
        btn.textContent = spell.name;
        btn.onclick = () => playSpell(spell);
        btn.style.margin = '0.5rem';
        content.appendChild(btn);
    });
    
    document.getElementById('playSpellModal').style.display = 'flex';
}

async function playSpell(spell) {
    if (typeof closeModal === 'function') {
        closeModal('playSpellModal');
    }
    
    if (!spell) {
        if (!selectedCard || selectedCard.card_type !== 'spell') {
            alert('Please select a spell from your hand');
            return;
        }
        spell = selectedCard;
    }
    
    // Check if spell needs a target
    const effectParams = spell.effect_params || {};
    const effects = effectParams.effects || [];
    const needsTarget = effects.some(e => {
        const keyword = e.keyword || '';
        return keyword.includes('MONSTER') || keyword.includes('PLAYER');
    });
    
    if (needsTarget) {
        // Show target selection modal
        showSpellTargetModal(spell);
    } else {
        // No target needed, play directly
        sendAction('PLAY_SPELL', {
            play_spell: {
                card_instance_id: spell.instance_id,
                target_player_index: null,
                target_monster_instance_id: null,
            },
        });
    }
}

// Show spell target selection modal
function showSpellTargetModal(spell) {
    const modal = document.getElementById('playSpellModal');
    const content = document.getElementById('playSpellContent');
    
    content.innerHTML = `<p>Select target for ${spell.name}:</p>`;
    
    // Get all monsters on board
    const player = currentGameState.players[currentPlayerIndex];
    const opponent = currentGameState.players[currentPlayerIndex === 1 ? 2 : 1];
    
    // Determine spell type from effect_params
    const effectParams = spell.effect_params || {};
    const effects = effectParams.effects || [];
    const isHealSpell = effects.some(eff => eff.keyword && eff.keyword.includes('HEAL'));
    const isBuffSpell = effects.some(eff => eff.keyword && eff.keyword.includes('BUFF'));
    const isDamageSpell = effects.some(eff => eff.keyword && eff.keyword.includes('DAMAGE'));
    
    // For buff/heal spells, only show friendly monsters
    // For heal spells, only show damaged monsters
    // For damage spells, only show enemy monsters
    let playerMonsters = player.monster_zones.filter(m => m !== null);
    const opponentMonsters = opponent.monster_zones.filter(m => m !== null);
    
    if (isHealSpell) {
        // Only show damaged friendly monsters for healing
        playerMonsters = playerMonsters.filter(m => m.hp < m.max_hp);
    }
    
    // Add player monsters as targets (only for buff/heal spells)
    if ((isBuffSpell || isHealSpell) && playerMonsters.length > 0) {
        const playerLabel = document.createElement('div');
        playerLabel.textContent = isHealSpell ? 'Your Damaged Monsters:' : 'Your Monsters:';
        playerLabel.style.fontWeight = 'bold';
        playerLabel.style.marginTop = '0.5rem';
        content.appendChild(playerLabel);
        
        playerMonsters.forEach(monster => {
            const btn = document.createElement('button');
            btn.className = 'btn btn-action';
            const hpInfo = isHealSpell ? ` (${monster.hp}/${monster.max_hp} HP)` : '';
            const statsText = ` (⭐${monster.stars} | ${monster.atk}/${monster.hp})`;
            btn.textContent = `${monster.name}${statsText}${hpInfo}`;
            btn.onclick = () => {
                closeModal('playSpellModal');
                sendAction('PLAY_SPELL', {
                    play_spell: {
                        card_instance_id: spell.instance_id,
                        target_player_index: currentPlayerIndex,
                        target_monster_instance_id: monster.instance_id,
                    },
                });
            };
            content.appendChild(btn);
        });
    }
    
    // Add opponent monsters as targets (only for damage spells)
    if (isDamageSpell && opponentMonsters.length > 0) {
        const opponentLabel = document.createElement('div');
        opponentLabel.textContent = 'Opponent Monsters:';
        opponentLabel.style.fontWeight = 'bold';
        opponentLabel.style.marginTop = '0.5rem';
        content.appendChild(opponentLabel);
        
        opponentMonsters.forEach(monster => {
            const btn = document.createElement('button');
            btn.className = 'btn btn-action';
            const displayName = monster.face_down ? 'Face-Down Monster' : monster.name;
            const statsText = monster.face_down ? '' : ` (⭐${monster.stars} | ${monster.atk}/${monster.hp})`;
            btn.textContent = `${displayName}${statsText}`;
            btn.onclick = () => {
                closeModal('playSpellModal');
                const targetPlayerIndex = currentPlayerIndex === 1 ? 2 : 1;
                sendAction('PLAY_SPELL', {
                    play_spell: {
                        card_instance_id: spell.instance_id,
                        target_player_index: targetPlayerIndex,
                        target_monster_instance_id: monster.instance_id,
                    },
                });
            };
            content.appendChild(btn);
        });
    }
    
    // Auto-target if there's only one valid target
    const allTargets = [];
    if ((isBuffSpell || isHealSpell) && playerMonsters.length > 0) {
        allTargets.push(...playerMonsters.map(m => ({ type: 'friendly', monster: m })));
    }
    if (isDamageSpell && opponentMonsters.length > 0) {
        allTargets.push(...opponentMonsters.map(m => ({ type: 'enemy', monster: m })));
    }
    
    if (allTargets.length === 0) {
        // No valid targets - close modal and show error
        closeModal('playSpellModal');
        alert(`${spell.name} requires a target, but no valid targets are available.`);
        return;
    }
    
    if (allTargets.length === 1) {
        // Auto-target the single valid target
        const target = allTargets[0];
        closeModal('playSpellModal');
        const targetPlayerIndex = target.type === 'friendly' ? currentPlayerIndex : (currentPlayerIndex === 1 ? 2 : 1);
        sendAction('PLAY_SPELL', {
            play_spell: {
                card_instance_id: spell.instance_id,
                target_player_index: targetPlayerIndex,
                target_monster_instance_id: target.monster.instance_id,
            },
        });
        return;
    }
    
    // Multiple targets - show selection modal
    modal.style.display = 'flex';
}

function showPlayTrapModal() {
    const player = currentGameState.players[currentPlayerIndex];
    const traps = player.hand.filter(c => c.card_type === 'trap');
    
    const content = document.getElementById('playTrapContent');
    content.innerHTML = '<p>Select a trap from your hand:</p>';
    
    traps.forEach(trap => {
        const btn = document.createElement('button');
        btn.className = 'btn btn-action';
        btn.textContent = trap.name;
        btn.onclick = () => playTrap(trap);
        btn.style.margin = '0.5rem';
        content.appendChild(btn);
    });
    
    document.getElementById('playTrapModal').style.display = 'flex';
}

async function playTrap(trap) {
    if (typeof closeModal === 'function') {
        closeModal('playTrapModal');
    }
    
    if (!trap) {
        if (!selectedCard || selectedCard.card_type !== 'trap') {
            alert('Please select a trap from your hand');
            return;
        }
        trap = selectedCard;
    }
    
    // Auto-select first available spell/trap zone (furthest left)
    const player = currentGameState.players[currentPlayerIndex];
    const spellTrapZones = player.spell_trap_zones || [];
    let emptyZone = null;
    
    for (let i = 0; i < spellTrapZones.length; i++) {
        if (spellTrapZones[i] === null) {
            emptyZone = i;
            break;
        }
    }
    
    if (emptyZone === null) {
        alert('No empty spell/trap zones available');
        return;
    }
    
    sendAction('PLAY_TRAP', {
        play_trap: {
            card_instance_id: trap.instance_id,
            zone_index: emptyZone,
        },
    });
}

function showHeroAbilityModal() {
    const player = currentGameState.players[currentPlayerIndex];
    if (!player.hero) {
        alert('You need to summon your hero first');
        return;
    }
    
    sendAction('ACTIVATE_HERO_ABILITY', {
        activate_hero_ability: {
            target_player_index: null, // TODO: Add target selection
            target_monster_instance_id: null, // TODO: Add target selection
        },
    });
}

function showAttackModal() {
    const player = currentGameState.players[currentPlayerIndex];
    const attackers = player.monster_zones
        .map((m, idx) => m && !m.face_down && m.can_attack ? { monster: m, zone: idx } : null)
        .filter(x => x !== null);
    
    if (attackers.length === 0) {
        alert('No monsters available to attack');
        return;
    }
    
    const content = document.getElementById('attackContent');
    content.innerHTML = '<p>Select an attacker:</p>';
    
    attackers.forEach(({ monster, zone }) => {
        const btn = document.createElement('button');
        btn.className = 'btn btn-action';
        btn.textContent = `${monster.name} (${monster.atk} ATK)`;
        btn.onclick = () => {
            // TODO: Show target selection
            attackMonster(monster.instance_id);
        };
        btn.style.margin = '0.5rem';
        content.appendChild(btn);
    });
    
    document.getElementById('attackModal').style.display = 'flex';
}

function attackMonster(attackerInstanceId) {
    closeModal('attackModal');
    
    // TODO: Add target selection UI
    const opponent = currentGameState.players[currentPlayerIndex === 1 ? 2 : 1];
    const targets = opponent.monster_zones.filter(m => m !== null);
    
    if (targets.length === 0) {
        // Direct attack
        sendAction('ATTACK_PLAYER', {
            attack_player: {
                attacker_instance_id: attackerInstanceId,
            },
        });
    } else {
        // Attack first available monster for now
        sendAction('ATTACK_MONSTER', {
            attack_monster: {
                attacker_instance_id: attackerInstanceId,
                defender_instance_id: targets[0].instance_id,
            },
        });
    }
}

function endTurn() {
    sendAction('END_TURN');
}

// Trap trigger modal
function showTrapTriggerModal(trigger, response) {
    const message = document.getElementById('trapTriggerMessage');
    const trapName = trigger.card_name || 'Trap';
    const trapDescription = trigger.description || trigger.rules_text || '';
    const triggerInfo = trigger.trigger_keyword || '';
    
    let messageText = `Trap Trigger Available: ${trapName}`;
    if (trapDescription) {
        messageText += `\n\n${trapDescription}`;
    }
    if (triggerInfo) {
        messageText += `\n\nTrigger: ${triggerInfo}`;
    }
    messageText += `\n\nActivate this trap?`;
    
    message.textContent = messageText;
    document.getElementById('trapTriggerModal').style.display = 'flex';
}

// Show last turn summary
function showLastTurnSummary() {
    if (!currentGameState || !currentGameState.log) {
        alert('No game log available');
        return;
    }
    
    const log = currentGameState.log;
    const currentTurn = currentGameState.turn || 1;
    const lastTurn = currentTurn - 1;
    
    // Get all log entries from the last turn
    const lastTurnEntries = log.filter(entry => {
        if (entry.type === 'END_TURN' && entry.turn === currentTurn) {
            return true; // This marks the end of last turn
        }
        // Get entries that happened during last turn
        // We'll use END_TURN as a marker
        const endTurnIndex = log.findIndex(e => e.type === 'END_TURN' && e.turn === currentTurn);
        if (endTurnIndex === -1) {
            // No turn end yet, show last 10 entries
            return log.indexOf(entry) >= log.length - 10;
        }
        // Show entries from last END_TURN to current
        const lastEndTurnIndex = log.findIndex(e => e.type === 'END_TURN' && e.turn === lastTurn);
        if (lastEndTurnIndex === -1) {
            return log.indexOf(entry) >= 0 && log.indexOf(entry) < endTurnIndex;
        }
        return log.indexOf(entry) > lastEndTurnIndex && log.indexOf(entry) < endTurnIndex;
    });
    
    if (lastTurnEntries.length === 0) {
        // Fallback: show last 10 entries
        const summary = log.slice(-10).map(e => formatLogEntry(e)).join('\n');
        alert(`Last Turn Summary:\n\n${summary || 'No actions yet'}`);
        return;
    }
    
    const summary = lastTurnEntries.map(e => formatLogEntry(e)).join('\n');
    alert(`Last Turn Summary (Turn ${lastTurn}):\n\n${summary}`);
}

// Show tribute selection modal
function showTributeSelectionModal(monster, requiredCount) {
    const player = currentGameState.players[currentPlayerIndex];
    const availableMonsters = player.monster_zones
        .map((m, idx) => m ? { ...m, zone_index: idx } : null)
        .filter(m => m !== null);
    
    if (availableMonsters.length < requiredCount) {
        alert(`Not enough monsters to tribute. You need ${requiredCount} but only have ${availableMonsters.length}.`);
        return;
    }
    
    // Store the monster we're trying to summon
    window.pendingSummonMonster = monster;
    window.requiredTributeCount = requiredCount;
    selectedTributes = []; // Reset selection
    
    const modal = document.getElementById('tributeModal');
    const message = document.getElementById('tributeMessage');
    const content = document.getElementById('tributeContent');
    
    message.textContent = `Select ${requiredCount} monster(s) to tribute for ${monster.name}:`;
    content.innerHTML = '';
    
    availableMonsters.forEach(mon => {
        const btn = document.createElement('button');
        btn.className = 'btn btn-action';
        btn.textContent = `${mon.name} (⭐${mon.stars} | ${mon.atk}/${mon.hp})`;
        btn.style.margin = '0.5rem';
        btn.style.opacity = '0.5';
        
        // Toggle selection
        btn.onclick = () => {
            const index = selectedTributes.indexOf(mon.instance_id);
            if (index > -1) {
                // Deselect
                selectedTributes.splice(index, 1);
                btn.style.opacity = '0.5';
                btn.style.border = '';
            } else {
                // Select (but limit to required count)
                if (selectedTributes.length < requiredCount) {
                    selectedTributes.push(mon.instance_id);
                    btn.style.opacity = '1';
                    btn.style.border = '2px solid var(--success-color)';
                } else {
                    alert(`You can only select ${requiredCount} tribute(s)`);
                }
            }
            
            // Update confirm button
            const confirmBtn = modal.querySelector('.btn-primary');
            if (confirmBtn) {
                confirmBtn.disabled = selectedTributes.length !== requiredCount;
            }
        };
        
        content.appendChild(btn);
    });
    
    modal.style.display = 'flex';
    
    // Disable confirm button initially
    const confirmBtn = modal.querySelector('.btn-primary');
    if (confirmBtn) {
        confirmBtn.disabled = true;
    }
}

// Confirm tribute selection and proceed with summon
function confirmTributes() {
    if (!window.pendingSummonMonster) {
        closeModal('tributeModal');
        return;
    }
    
    const requiredCount = window.requiredTributeCount || 0;
    if (selectedTributes.length !== requiredCount) {
        alert(`Please select exactly ${requiredCount} tribute(s)`);
        return;
    }
    
    closeModal('tributeModal');
    
    // Now proceed with the summon
    const monster = window.pendingSummonMonster;
    delete window.pendingSummonMonster;
    delete window.requiredTributeCount;
    
    // Always find first empty zone
    const player = currentGameState.players[currentPlayerIndex];
    const emptyZone = player.monster_zones.findIndex(m => m === null);
    if (emptyZone === -1) {
        alert('No empty monster zones');
        return;
    }
    
    sendAction('PLAY_MONSTER', {
        play_monster: {
            card_instance_id: monster.instance_id,
            zone_index: emptyZone,
            tribute_instance_ids: selectedTributes,
        },
    });
    
    // Clear tribute selection
    selectedTributes = [];
}

// Utility functions
function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
}

function showLoading(show) {
    document.getElementById('loadingOverlay').style.display = show ? 'flex' : 'none';
}

function toggleHand() {
    const handCards = document.getElementById('handCards');
    handCards.style.display = handCards.style.display === 'none' ? 'flex' : 'none';
}

function toggleLog() {
    const logContent = document.getElementById('logContent');
    logContent.style.display = logContent.style.display === 'none' ? 'block' : 'none';
}

