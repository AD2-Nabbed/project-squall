# TODO: Image Path Configuration

**Reminder:** User needs to provide the image path pattern for `art_asset_id` field.

Once provided, update:
- `frontend/game.js` - `getCardImageUrl()` function
- Use `art_asset_id` instead of `card_code` for image lookup
- Update `CARD_IMAGE_BASE` path if needed

Current placeholder: `/images/cards/{card_code}.png`
Future: `/images/cards/{art_asset_id}.png` (or whatever pattern user provides)

