#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tarot kartlarını metinlerle eşleştirmek için script
Kart görüntülerini düzenleme ve adlandırma
"""

import json
import os
from pathlib import Path

# Majör Arkana kartları (0-21)
MAJOR_ARCANA = {
    0: {'tr': 'Joker', 'en': 'The Fool', 'file': '00_joker'},
    1: {'tr': 'Sihirbaz', 'en': 'The Magician', 'file': '01_sihirbaz'},
    2: {'tr': 'Bakireyiz', 'en': 'The High Priestess', 'file': '02_bakireyiz'},
    3: {'tr': 'İmparatoriçe', 'en': 'The Empress', 'file': '03_imparatorice'},
    4: {'tr': 'İmparator', 'en': 'The Emperor', 'file': '04_imparator'},
    5: {'tr': 'Başrahip', 'en': 'The Hierophant', 'file': '05_basrahip'},
    6: {'tr': 'Aşıklar', 'en': 'The Lovers', 'file': '06_asiklar'},
    7: {'tr': 'Savaş Arabası', 'en': 'The Chariot', 'file': '07_savas_arabasi'},
    8: {'tr': 'Güç', 'en': 'Strength', 'file': '08_guc'},
    9: {'tr': 'Münzevi', 'en': 'The Hermit', 'file': '09_munzevi'},
    10: {'tr': 'Kader Çarkı', 'en': 'Wheel of Fortune', 'file': '10_kader_carki'},
    11: {'tr': 'Adalet', 'en': 'Justice', 'file': '11_adalet'},
    12: {'tr': 'Asılı Adam', 'en': 'The Hanged Man', 'file': '12_asili_adam'},
    13: {'tr': 'Ölüm', 'en': 'Death', 'file': '13_olum'},
    14: {'tr': 'İtidal', 'en': 'Temperance', 'file': '14_itidal'},
    15: {'tr': 'İblis', 'en': 'The Devil', 'file': '15_iblis'},
    16: {'tr': 'Kule', 'en': 'The Tower', 'file': '16_kule'},
    17: {'tr': 'Yıldız', 'en': 'The Star', 'file': '17_yildiz'},
    18: {'tr': 'Ay', 'en': 'The Moon', 'file': '18_ay'},
    19: {'tr': 'Güneş', 'en': 'The Sun', 'file': '19_gunes'},
    20: {'tr': 'Yargi', 'en': 'Judgement', 'file': '20_yargi'},
    21: {'tr': 'Dünya', 'en': 'The World', 'file': '21_dunya'},
}

# Minör Arkana - Numaralar
MINOR_NUMBERS = {
    1: {'en': 'Ace', 'file': '01_ace'},
    2: {'en': 'Two', 'file': '02_two'},
    3: {'en': 'Three', 'file': '03_three'},
    4: {'en': 'Four', 'file': '04_four'},
    5: {'en': 'Five', 'file': '05_five'},
    6: {'en': 'Six', 'file': '06_six'},
    7: {'en': 'Seven', 'file': '07_seven'},
    8: {'en': 'Eight', 'file': '08_eight'},
    9: {'en': 'Nine', 'file': '09_nine'},
    10: {'en': 'Ten', 'file': '10_ten'},
    11: {'en': 'Page', 'file': '11_page'},
    12: {'en': 'Knight', 'file': '12_knight'},
    13: {'en': 'Queen', 'file': '13_queen'},
    14: {'en': 'King', 'file': '14_king'},
}

# Minör Arkana - Takımlar
MINOR_SUITS = {
    'wands': {'tr': 'Değnek', 'file': 'wands'},
    'cups': {'tr': 'Kupa', 'file': 'cups'},
    'swords': {'tr': 'Kılıç', 'file': 'swords'},
    'pentacles': {'tr': 'Tılsım', 'file': 'pentacles'},
}

def create_card_database():
    """Tüm 78 kartın veritabanını oluştur"""
    cards = []

    # Majör Arkana
    for num, info in MAJOR_ARCANA.items():
        cards.append({
            'id': f'major_{num}',
            'number': num,
            'type': 'major',
            'turkish_name': info['tr'],
            'english_name': info['en'],
            'filename': f"{info['file']}.jpg",
        })

    # Minör Arkana
    for suit_en, suit_info in MINOR_SUITS.items():
        for num, num_info in MINOR_NUMBERS.items():
            card_id = f"{suit_en}_{num}"
            cards.append({
                'id': card_id,
                'suit': suit_en,
                'suit_turkish': suit_info['tr'],
                'number': num,
                'type': 'minor',
                'english_name': f"{num_info['en']} of {suit_en.capitalize()}",
                'turkish_name': f"{suit_info['tr']} {num_info['en']}",
                'filename': f"{suit_info['file']}_{num_info['file']}.jpg",
            })

    return cards

def save_card_database(cards, output_file='card_database.json'):
    """Kart veritabanını JSON dosyasına kaydet"""
    script_dir = Path(__file__).parent
    output_path = script_dir / output_file

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(cards, f, ensure_ascii=False, indent=2)

    print(f"✓ Kart veritabanı kaydedildi: {output_path}")
    print(f"✓ Toplam kartlar: {len(cards)}")

def verify_images(cards, image_dir=None):
    """Eksik kartları kontrol et"""
    if image_dir is None:
        image_dir = Path(__file__).parent

    missing = []
    found = []

    for card in cards:
        card_path = image_dir / card['filename']
        if card_path.exists():
            found.append(card['filename'])
        else:
            missing.append(card)

    print(f"\n📊 Görüntü Kontrol Sonuçları:")
    print(f"✓ Bulunan: {len(found)} kart")
    print(f"✗ Eksik: {len(missing)} kart")

    if missing:
        print(f"\n Eksik Kartlar:")
        for card in missing[:10]:  # İlk 10'u göster
            print(f"  - {card['filename']} ({card['turkish_name']})")
        if len(missing) > 10:
            print(f"  ... ve {len(missing) - 10} daha")

    return found, missing

def generate_upload_guide():
    """Kartları yüklemek için rehber oluştur"""
    cards = create_card_database()

    guide = "# Tarot Kartları Yükleme Rehberi\n\n"
    guide += "## Majör Arkana (22 kart)\n\n"

    for card in cards[:22]:
        guide += f"- {card['number']:2d}. {card['turkish_name']:<20} → `{card['filename']}`\n"

    guide += "\n## Minör Arkana - Değnek (14 kart)\n\n"
    for card in cards[22:36]:
        guide += f"- {card['number']:2d}. {card['turkish_name']:<20} → `{card['filename']}`\n"

    guide += "\n## Minör Arkana - Kupa (14 kart)\n\n"
    for card in cards[36:50]:
        guide += f"- {card['number']:2d}. {card['turkish_name']:<20} → `{card['filename']}`\n"

    guide += "\n## Minör Arkana - Kılıç (14 kart)\n\n"
    for card in cards[50:64]:
        guide += f"- {card['number']:2d}. {card['turkish_name']:<20} → `{card['filename']}`\n"

    guide += "\n## Minör Arkana - Tılsım (14 kart)\n\n"
    for card in cards[64:78]:
        guide += f"- {card['number']:2d}. {card['turkish_name']:<20} → `{card['filename']}`\n"

    script_dir = Path(__file__).parent
    guide_path = script_dir / 'UPLOAD_GUIDE.md'
    with open(guide_path, 'w', encoding='utf-8') as f:
        f.write(guide)

    print(f"✓ Yükleme rehberi oluşturuldu: {guide_path}")

if __name__ == '__main__':
    print("🎴 Tarot Kartları Veritabanı Oluşturucu\n")

    # Kart veritabanını oluştur
    cards = create_card_database()
    save_card_database(cards)

    # Görüntüleri kontrol et
    verify_images(cards)

    # Yükleme rehberi oluştur
    generate_upload_guide()

    print("\n✓ Tamamlandı!")
