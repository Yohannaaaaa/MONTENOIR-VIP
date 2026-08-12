# Tarot Cards Image Organization Guide

This directory contains tarot card images for the Montenoir VIP application.

## Directory Structure

```
/static/tarot_cards/
├── card_mapping.json          # JSON mapping of card names to filenames
├── Major Arcana (0-21)
│   ├── 00_joker.jpg
│   ├── 01_sihirbaz.jpg
│   ├── ...
│   └── 21_dunya.jpg
│
├── Minor Arcana - Wands (Değnek)
│   ├── wands_01_ace.jpg
│   ├── wands_02_two.jpg
│   ├── ...
│   └── wands_14_king.jpg
│
├── Minor Arcana - Cups (Kupa)
│   ├── cups_01_ace.jpg
│   ├── cups_02_two.jpg
│   ├── ...
│   └── cups_14_king.jpg
│
├── Minor Arcana - Swords (Kılıç)
│   ├── swords_01_ace.jpg
│   ├── swords_02_two.jpg
│   ├── ...
│   └── swords_14_king.jpg
│
└── Minor Arcana - Pentacles (Tılsım)
    ├── pentacles_01_ace.jpg
    ├── pentacles_02_two.jpg
    ├── ...
    └── pentacles_14_king.jpg
```

## File Naming Convention

All card images follow a consistent naming pattern:

- **Major Arcana**: `{number:02d}_{turkish_name}.jpg`
  - Example: `00_joker.jpg`, `01_sihirbaz.jpg`, `21_dunya.jpg`

- **Minor Arcana**: `{suit}_{number:02d}_{english_name}.jpg`
  - Suits: `wands`, `cups`, `swords`, `pentacles`
  - Numbers: 01-10 (Ace-Ten), 11 (Page), 12 (Knight), 13 (Queen), 14 (King)
  - Example: `wands_01_ace.jpg`, `cups_14_king.jpg`

## Supported Card Suits

### Wands (Değnek)
- Ace, Two, Three, Four, Five, Six, Seven, Eight, Nine, Ten, Page, Knight, Queen, King

### Cups (Kupa)
- Ace, Two, Three, Four, Five, Six, Seven, Eight, Nine, Ten, Page, Knight, Queen, King

### Swords (Kılıç)
- Ace, Two, Three, Four, Five, Six, Seven, Eight, Nine, Ten, Page, Knight, Queen, King

### Pentacles (Tılsım)
- Ace, Two, Three, Four, Five, Six, Seven, Eight, Nine, Ten, Page, Knight, Queen, King

## Total Cards: 78

- Major Arcana: 22 cards (0-21)
- Minor Arcana: 56 cards (4 suits × 14 cards)

## Integration with app.py

The `instantTarot()` function in `app.py` now references card images using the `card.image` property from the `TAROT_DECK` array. When a card is drawn, it attempts to load the image from:

```
/static/tarot_cards/{card.image}
```

If an image is not found (404 error), the function falls back to displaying an emoji symbol.

## How to Add Card Images

1. Collect all 78 tarot card images
2. Name each file according to the convention above
3. Place files in the appropriate location in this directory
4. The images will automatically be used by the instant reading feature

## Image Requirements

- **Format**: JPG, PNG, or WebP
- **Recommended Size**: 300x450px (standard tarot card aspect ratio)
- **Color**: Full color (supporting the traditional tarot card appearance)
