#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import random
from pathlib import Path

SPREAD_COST = 200  # Jeton maliyeti

def load_tarot_cards():
    """Load all tarot cards from JSON"""
    try:
        with open('/home/user/MONTENOIR-VIP/static/tarot_cards/cards.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading tarot cards: {e}")
        return []

def select_random_cards(count=3):
    """Select random cards from the deck"""
    cards = load_tarot_cards()
    selected = random.sample(cards, min(count, len(cards)))
    return selected

def format_card_interpretation(card, position='Düz'):
    """Format a single card's interpretation"""
    if position not in card.get('positions', {}):
        position = 'Düz'

    pos_data = card['positions'].get(position, {})

    return {
        'number': card.get('number'),
        'name': card.get('name'),
        'position': position,
        'image': card.get('image'),
        'intro': pos_data.get('intro', ''),
        'life_areas': pos_data.get('life_areas', {}),
        'symbols': pos_data.get('symbols', ''),
        'questions': pos_data.get('questions', ''),
        'weekly': pos_data.get('weekly', ''),
        'hidden': pos_data.get('hidden', '')
    }

def three_card_spread(question=''):
    """3-Card Spread: Past, Present, Future"""
    cards = select_random_cards(3)
    interpretations = [
        format_card_interpretation(cards[i], random.choice(['Düz', 'Ters']))
        for i in range(3)
    ]

    return {
        'type': '3-card',
        'name': '3-Kart Açılımı',
        'question': question,
        'cost': SPREAD_COST,
        'spread': [
            {'position': 'Geçmiş', 'card': interpretations[0]},
            {'position': 'Şimdiki', 'card': interpretations[1]},
            {'position': 'Gelecek', 'card': interpretations[2]}
        ]
    }

def seven_card_spread(question=''):
    """7-Card Spread: Situation, Challenge, Support, etc"""
    cards = select_random_cards(7)
    positions = ['Durum', 'Zorluk', 'Destek', 'Yakın Gelecek', 'Uzak Gelecek', 'Tavsiye', 'Sonuç']
    interpretations = [
        format_card_interpretation(cards[i], random.choice(['Düz', 'Ters']))
        for i in range(7)
    ]

    return {
        'type': '7-card',
        'name': '7-Kart Açılımı',
        'question': question,
        'cost': SPREAD_COST,
        'spread': [
            {'position': positions[i], 'card': interpretations[i]}
            for i in range(7)
        ]
    }

def yes_no_spread(question=''):
    """Yes/No Spread: Single card for yes/no/maybe"""
    cards = select_random_cards(1)
    position = random.choice(['Düz', 'Ters'])
    interpretation = format_card_interpretation(cards[0], position)

    is_upright = position == 'Düz'
    positive_cards = ['JOKER', 'BÜYÜCÜ', 'AŞ', 'IMPARATOR', 'AŞIKLAR', 'SAVAŞ ARABASI',
                      'GÜÇ', 'KADER ÇARKI', 'ADALET', 'YILDIZ', 'GÜNEŞ', 'DÜNYA']
    negative_cards = ['ÖLÜM', 'İBLİS', 'KULE', 'AY', 'YARGI']

    card_name = interpretation['name'].upper()

    if any(pname in card_name for pname in positive_cards) and is_upright:
        answer = 'Evet ✨'
    elif any(nname in card_name for nname in negative_cards) and not is_upright:
        answer = 'Hayır ❌'
    elif is_upright:
        answer = 'Evet ✨'
    else:
        answer = 'Hayır ❌'

    return {
        'type': 'yes-no',
        'name': 'Evet/Hayır Okuyuşu',
        'question': question,
        'cost': SPREAD_COST,
        'answer': answer,
        'card': interpretation
    }

def love_spread(question=''):
    """Love/Relationship 5-Card Spread"""
    cards = select_random_cards(5)
    positions = ['Mevcut Durum', 'Partneriniz', 'Sizin Hisleriniz', 'İlişkinin Yönü', 'Tavsiye']
    interpretations = [
        format_card_interpretation(cards[i], random.choice(['Düz', 'Ters']))
        for i in range(5)
    ]

    return {
        'type': 'love',
        'name': '💕 Aşk Açılımı',
        'question': question,
        'cost': SPREAD_COST,
        'spread': [
            {'position': positions[i], 'card': interpretations[i]}
            for i in range(5)
        ]
    }

def work_spread(question=''):
    """Career/Work 5-Card Spread"""
    cards = select_random_cards(5)
    positions = ['Mevcut Kariyer', 'Zorluklar', 'Fırsatlar', 'Yakın Gelecek', 'Tavsiye']
    interpretations = [
        format_card_interpretation(cards[i], random.choice(['Düz', 'Ters']))
        for i in range(5)
    ]

    return {
        'type': 'work',
        'name': '💼 İş Açılımı',
        'question': question,
        'cost': SPREAD_COST,
        'spread': [
            {'position': positions[i], 'card': interpretations[i]}
            for i in range(5)
        ]
    }

def general_spread(question=''):
    """General 6-Card Spread"""
    cards = select_random_cards(6)
    positions = ['Geçmiş', 'Şimdiki', 'Yakın Gelecek', 'Tavsiye', 'Dış Etkenler', 'Sonuç']
    interpretations = [
        format_card_interpretation(cards[i], random.choice(['Düz', 'Ters']))
        for i in range(6)
    ]

    return {
        'type': 'general',
        'name': '✨ Genel Okuyuş',
        'question': question,
        'cost': SPREAD_COST,
        'spread': [
            {'position': positions[i], 'card': interpretations[i]}
            for i in range(6)
        ]
    }

if __name__ == '__main__':
    print("Test Okuyuşları:")
    print(json.dumps(three_card_spread("Test?"), ensure_ascii=False, indent=2)[:300])
