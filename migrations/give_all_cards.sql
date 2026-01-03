-- Clear all owned cards for player d4ac398c-12a6-4cf3-836e-8ede11835029 (Nabbed)
-- Then add 2 copies of every card from the cards table

-- Step 1: Clear existing owned cards
DELETE FROM owned_cards
WHERE owner_id = 'd4ac398c-12a6-4cf3-836e-8ede11835029';

-- Step 2: Insert 2 copies of every card
INSERT INTO owned_cards (owner_id, card_code, quantity)
SELECT 
    'd4ac398c-12a6-4cf3-836e-8ede11835029' as owner_id,
    card_code,
    2 as quantity
FROM cards;

-- Verify the results
SELECT 
    COUNT(*) as total_card_types,
    SUM(quantity) as total_cards
FROM owned_cards
WHERE owner_id = 'd4ac398c-12a6-4cf3-836e-8ede11835029';

