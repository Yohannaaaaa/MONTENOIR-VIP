#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import re
from pathlib import Path
from collections import defaultdict

def extract_sections(text):
    """Extract sections from card text"""
    sections = {}

    # Introduction (first paragraph before any section)
    intro_match = re.search(r'^(.+?)(?:\n\n[A-Z]|\n\nHayat|\Z)', text, re.DOTALL)
    sections['intro'] = intro_match.group(1).strip() if intro_match else ''

    # Life Areas
    life_match = re.search(r'Hayat Alanlarında Etkisi\n\n(.*?)(?:\n\nKarttaki Semboller|\Z)', text, re.DOTALL)
    life_areas = {}
    if life_match:
        life_text = life_match.group(1).strip()
        for area in ['İlişki', 'Kariyer', 'Para', 'Sağlık', 'Aile']:
            area_pattern = f'{area}:\\s*(.+?)(?=\n\n[A-Z]|\n\n{[a.upper() for a in ["İlişki", "Kariyer", "Para", "Sağlık", "Aile"] if a != area][0] if [a.upper() for a in ["İlişki", "Kariyer", "Para", "Sağlık", "Aile"] if a != area] else ""}|\\Z)'
            area_match = re.search(area_pattern, life_text, re.DOTALL)
            if area_match:
                life_areas[area.lower()] = area_match.group(1).strip()

    sections['life_areas'] = life_areas

    # Symbols
    symbols_match = re.search(r'Karttaki Semboller ve Anlamları\n(.*?)(?:\n\nKartın Sana Sorduğu|\Z)', text, re.DOTALL)
    sections['symbols'] = symbols_match.group(1).strip() if symbols_match else ''

    # Questions
    questions_match = re.search(r'Kartın Sana Sorduğu Soru\n(.*?)(?:\n\nHaftalık|\Z)', text, re.DOTALL)
    sections['questions'] = questions_match.group(1).strip() if questions_match else ''

    # Weekly Message
    weekly_match = re.search(r'Haftalık / Dönemsel Mesaj\n(.*?)(?:\n\nGizli Mesaj|\Z)', text, re.DOTALL)
    sections['weekly'] = weekly_match.group(1).strip() if weekly_match else ''

    # Hidden Message
    hidden_match = re.search(r'Gizli Mesaj\n(.*?)(?:\Z)', text, re.DOTALL)
    sections['hidden'] = hidden_match.group(1).strip() if hidden_match else ''

    return sections

def parse_tarot_markdown():
    """Parse kart_metinleri.md and create complete card database"""

    file_path = Path('/tmp/claude-0/-home-user-MONTENOIR-VIP/9e0fefa4-3134-5688-a19f-c4902658f56a/scratchpad/tarot/kart_metinleri.md')

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split by card headers: ## {NUMBER} — {NAME} — {POSITION}
    card_pattern = r'^## (.+?) — (.+?) — (Düz|Ters)\s*$'

    cards_dict = defaultdict(lambda: {'positions': {}})

    current_card_key = None
    current_position = None
    current_lines = []

    for line in content.split('\n'):
        match = re.match(card_pattern, line)
        if match:
            # Save previous card content
            if current_card_key and current_position:
                text = '\n'.join(current_lines).strip()
                sections = extract_sections(text)
                cards_dict[current_card_key]['positions'][current_position] = sections

            # Start new card
            num_str, name, position = match.groups()
            num_str = num_str.strip()
            name = name.strip()
            position = position.strip()

            current_card_key = f"{num_str}_{name}"
            current_position = position
            current_lines = []

            # Set card metadata (only once)
            if not cards_dict[current_card_key].get('number'):
                cards_dict[current_card_key]['number'] = num_str
                cards_dict[current_card_key]['name'] = name

                # Determine type
                try:
                    int(num_str)
                    cards_dict[current_card_key]['type'] = 'major'
                except:
                    cards_dict[current_card_key]['type'] = 'minor'

                # Get image
                cards_dict[current_card_key]['image'] = get_image_filename(name, num_str)
        else:
            # Add to current card text
            if current_card_key:
                current_lines.append(line)

    # Save last card
    if current_card_key and current_position:
        text = '\n'.join(current_lines).strip()
        sections = extract_sections(text)
        cards_dict[current_card_key]['positions'][current_position] = sections

    # Convert to list format
    cards_list = []
    for card in cards_dict.values():
        if card.get('number'):  # Only include valid cards
            cards_list.append(dict(card))

    # Sort by number (major first, then by number)
    def sort_key(card):
        num_str = card['number']
        try:
            num = int(num_str)
            return (0, num)
        except:
            return (1, card['name'])

    cards_list.sort(key=sort_key)
    return cards_list

def get_image_filename(name, num):
    """Generate image filename from card name"""

    name_map = {
        'JOKER (Deli)': '00_joker',
        'BÜYÜCÜ': '01_sihirbaz',
        'AZİZE': '02_bakireyiz',
        'İMPARATORİÇE': '03_imparatorice',
        'İMPARATOR': '04_imparator',
        'AZİZ': '05_basrahip',
        'AŞIKLAR': '06_asiklar',
        'SAVAŞ ARABASI': '07_savas_arabasi',
        'GÜÇ': '08_guc',
        'ERMİŞ': '09_munzevi',
        'KADER ÇARKI': '10_kader_carki',
        'ADALET': '11_adalet',
        'ASILAN ADAM': '12_asili_adam',
        'ÖLÜM': '13_olum',
        'DENGE': '14_itidal',
        'ŞEYTAN': '15_iblis',
        'KULE': '16_kule',
        'YILDIZ': '17_yildiz',
        'AY': '18_ay',
        'GÜNEŞ': '19_gunes',
        'MAHKEME': '20_yargi',
        'DÜNYA': '21_dunya',
    }

    # Try exact match first
    if name in name_map:
        return f"{name_map[name]}.webp"

    # Try uppercase
    name_upper = name.upper()
    for key, val in name_map.items():
        if key.upper() == name_upper:
            return f"{val}.webp"

    return None

if __name__ == '__main__':
    cards = parse_tarot_markdown()

    # Save to static directory
    output_path = Path('/home/user/MONTENOIR-VIP/static/tarot_cards/cards.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(cards, f, ensure_ascii=False, indent=2)

    print(f"✓ {len(cards)} kart parse edildi")
    print(f"✓ JSON kaydedildi: {output_path}")

    # Print card count by type
    major = sum(1 for c in cards if c['type'] == 'major')
    minor = sum(1 for c in cards if c['type'] == 'minor')
    print(f"  - Majör Arkana: {major}")
    print(f"  - Minör Arkana: {minor}")

    # Sample first card
    if cards:
        print(f"\n📌 İlk kart örneği:")
        print(f"  - İsim: {cards[0]['name']}")
        print(f"  - Pozisyonlar: {list(cards[0]['positions'].keys())}")
        print(f"  - Resim: {cards[0]['image']}")
