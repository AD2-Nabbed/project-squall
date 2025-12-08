# Card Image Setup Guide

## Current Status

The frontend now supports card images, but **no images are currently configured**. Cards will display as text-only until you add images.

## Image Configuration

### 1. Set Image Path

Edit `frontend/game.js` and configure:

```javascript
const CARD_IMAGE_BASE = '/images/cards'; // Change to your image path
const USE_CARD_IMAGES = true; // Set to false for text-only
```

### 2. Image Naming Convention

The frontend will look for images in this order:

1. **By card_code + element**: `{CARD_IMAGE_BASE}/{card_code}-{element}.png`
   - Example: `/images/cards/CORE-SUMMON-001-fire.png`
   - Used when element_id is set (2-7, not neutral)

2. **By card_code**: `{CARD_IMAGE_BASE}/{card_code}.png`
   - Example: `/images/cards/CORE-SUMMON-001.png`
   - Used for neutral cards or when element variant not found

3. **By name (fallback)**: `{CARD_IMAGE_BASE}/{sanitized-name}.png`
   - Example: `/images/cards/goblin-squad.png`
   - Used if card_code is missing

### 3. Image Organization

Recommended folder structure:

```
frontend/
  images/
    cards/
      CORE-SUMMON-001.png          (neutral)
      CORE-SUMMON-001-fire.png     (fire variant)
      CORE-SUMMON-001-ice.png      (ice variant)
      CORE-SPELL-001.png
      CORE-TRAP-001.png
      CORE-HERO-001.png
```

### 4. Image Requirements

- **Format**: PNG, JPG, or WebP (PNG recommended for transparency)
- **Aspect Ratio**: 3:4 (portrait) recommended
- **Size**: 
  - Hand cards: ~120x160px (desktop), ~80x107px (mobile)
  - Zone cards: Scale to fit zone size
- **Naming**: Must match exactly (case-sensitive on some servers)

### 5. Using External URLs

If hosting images elsewhere (CDN, Supabase Storage, etc.):

```javascript
const CARD_IMAGE_BASE = 'https://your-cdn.com/cards';
// or
const CARD_IMAGE_BASE = 'https://your-project.supabase.co/storage/v1/object/public/card-images';
```

### 6. Fallback Behavior

If an image fails to load:
- The image will hide automatically
- Text content will display instead
- No errors will be shown to the user

## Testing

1. Place a test image: `frontend/images/cards/CORE-SUMMON-001.png`
2. Start a match with a deck containing that card
3. The image should appear in your hand
4. If it doesn't, check browser console for 404 errors

## Unity/Godot Integration

For Unity/Godot, you can:
- Use the same naming convention
- Load images from Resources/StreamingAssets or asset bundles
- Use the `card_code` and `element_id` from game state to construct image paths
- Cache images to avoid repeated loads

Example Unity C#:
```csharp
string imagePath = $"Cards/{card.card_code}";
if (card.element_id > 1) {
    imagePath += $"-{GetElementName(card.element_id)}";
}
Sprite cardSprite = Resources.Load<Sprite>(imagePath);
```

