# Traductions françaises complètes pour les 56 cartes mineures du Tarot

def _get_minor_translation_template(suit_name, suit_fr, rank_name, rank_fr, rank_meaning):
    """Generate French translations for a minor card using a template"""
    return {
        f'{suit_fr} ({rank_fr})': {
            'Düz': {
                'intro': f'Le {rank_fr} de {suit_fr} représente {rank_meaning}. C\'est une période liée à {suit_name} et énergie constructive. Une force positive s\'exprime à travers cette carte.',
                'life_areas': {
                    'Relation': f'En amour, le {rank_fr} de {suit_fr} apporte {rank_meaning} dans vos connexions émotionnelles.',
                    'Carrière': f'Au travail, cela manifeste {rank_meaning} dans votre parcours professionnel.',
                    'Finances': f'Financièrement, ce {rank_fr} indique {rank_meaning} dans vos ressources.',
                    'Santé': f'Pour la santé, {rank_meaning} affecte votre bien-être général positivement.',
                    'Famille': f'En famille, {rank_meaning} influence les dynamiques relationnelles harmonieusement.'
                },
                'symbols': f'- Le {rank_fr} de {suit_fr}: {rank_meaning}\n- Les éléments du {suit_name}: Représentent les énergies positives.',
                'questions': f'- "Comment {rank_meaning} affecte-t-il ma vie?"\n- "Que puis-je apprendre de cette énergie?"\n- "Comment puis-je utiliser cette force?"',
                'weekly': f'Cette semaine, {rank_meaning} est au centre de votre expérience. Acceptez cette énergie positive.',
                'hidden': f'"L\'essence du {rank_fr} de {suit_fr} est {rank_meaning} qui transforme."'
            },
            'Ters': {
                'intro': f'Le {rank_fr} de {suit_fr} inversé montre le blocage de {rank_meaning}. L\'énergie est stagnante ou négative. Vous devez reconnaître ce blocage.',
                'life_areas': {
                    'Relation': f'En amour, l\'absence de {rank_meaning} crée de la distance.',
                    'Carrière': f'Au travail, le manque de {rank_meaning} bloque la progression.',
                    'Finances': f'Financièrement, le refus de {rank_meaning} peut créer des défis.',
                    'Santé': f'Pour la santé, le blocage de {rank_meaning} affecte négativement.',
                    'Famille': f'En famille, l\'inverse de {rank_meaning} cause des tensions.'
                },
                'symbols': f'- Le {rank_fr} inversé: Énergie bloquée.\n- L\'absence: Manque de {rank_meaning}.',
                'questions': f'- "Qu\'est-ce qui bloque {rank_meaning}?"\n- "Comment puis-je libérer cette énergie?"\n- "Que refuse-je d\'accepter?"',
                'weekly': f'Cette semaine, vous pouvez sentir le manque de {rank_meaning}. Cherchez à restaurer l\'équilibre.',
                'hidden': f'"L\'inversion du {rank_fr} de {suit_fr} invite à transformer le blocage en flux."'
            }
        }
    }

# Coupes (Emotions, Relationships, Feelings)
def build_coupes_translations():
    coupes = {}
    coupes_ranks = [
        ('As', 'As', 'l\'amour authentique et la connexion émotionnelle'),
        ('2', '2', 'l\'harmonie et l\'équilibre dans les relations'),
        ('3', '3', 'la célébration et la joie partagée'),
        ('4', '4', 'la stabilité émotionnelle et la satisfaction'),
        ('5', '5', 'la tristesse et la déception émotionnelle'),
        ('6', '6', 'la nostalgie et les beaux souvenirs'),
        ('7', '7', 'les rêves et les possibilités émotionnelles'),
        ('8', '8', 'l\'abandon et la transition émotionnelle'),
        ('9', '9', 'l\'accomplissement émotionnel et la satisfaction'),
        ('10', '10', 'l\'harmonie familiale et l\'amour complet'),
        ('Valet', 'Valet', 'la sensibilité et l\'intuition'),
        ('Cavalier', 'Cavalier', 'l\'arrivée d\'une personne emotionnelle'),
        ('Reine', 'Reine', 'l\'intuition et la sagesse émotionnelle'),
        ('Roi', 'Roi', 'la maîtrise émotionnelle et la bienveillance'),
    ]

    for rank, rank_fr, meaning in coupes_ranks:
        trans = _get_minor_translation_template('émotions et relations', 'Coupes', rank, rank_fr, meaning)
        coupes.update(trans)

    return coupes

# Bâtons (Creativity, Passion, Action)
def build_batons_translations():
    batons = {}
    batons_ranks = [
        ('As', 'As', 'l\'inspiration créative et la passion'),
        ('2', '2', 'la planification et la vision de croissance'),
        ('3', '3', 'l\'expansion et les opportunités'),
        ('4', '4', 'la célébration et le succès'),
        ('5', '5', 'la compétition et les défis'),
        ('6', '6', 'la victoire et le succès personnel'),
        ('7', '7', 'la défense de ses convictions'),
        ('8', '8', 'l\'énergie rapide et l\'action dynamique'),
        ('9', '9', 'la résilience et la persévérance'),
        ('10', '10', 'le fardeau et les responsabilités'),
        ('Valet', 'Valet', 'l\'impatience et l\'énergie impulsive'),
        ('Cavalier', 'Cavalier', 'l\'arrivée d\'une personne passionnée'),
        ('Reine', 'Reine', 'la confiance et la force créative'),
        ('Roi', 'Roi', 'le leadership charismatique et l\'autorité'),
    ]

    for rank, rank_fr, meaning in batons_ranks:
        trans = _get_minor_translation_template('créativité et action', 'Bâtons', rank, rank_fr, meaning)
        batons.update(trans)

    return batons

# Épées (Intellect, Communication, Truth)
def build_epees_translations():
    epees = {}
    epees_ranks = [
        ('As', 'As', 'la clarté et la vérité'),
        ('2', '2', 'l\'équilibre précaire et la décision'),
        ('3', '3', 'la douleur et la séparation'),
        ('4', '4', 'le repos et la méditation'),
        ('5', '5', 'le conflit et la défaite'),
        ('6', '6', 'la transition difficile'),
        ('7', '7', 'la stratégie et l\'intellect'),
        ('8', '8', 'la restriction et l\'emprisonnement mental'),
        ('9', '9', 'la désespérance et l\'angoisse'),
        ('10', '10', 'la finition douloureuse'),
        ('Valet', 'Valet', 'la curiosité et la communication'),
        ('Cavalier', 'Cavalier', 'l\'arrivée d\'une personne rationnelle'),
        ('Reine', 'Reine', 'la sagesse et la clarté mentale'),
        ('Roi', 'Roi', 'l\'autorité intellectuelle et la justice'),
    ]

    for rank, rank_fr, meaning in epees_ranks:
        trans = _get_minor_translation_template('intellect et communication', 'Épées', rank, rank_fr, meaning)
        epees.update(trans)

    return epees

# Deniers (Manifestation, Prosperity, Physical)
def build_deniers_translations():
    deniers = {}
    deniers_ranks = [
        ('As', 'As', 'l\'abondance et le nouveau départ matériel'),
        ('2', '2', 'l\'équilibre et la gestion des ressources'),
        ('3', '3', 'le travail d\'équipe et la collaboration'),
        ('4', '4', 'l\'accumulation et la sécurité'),
        ('5', '5', 'la pauvreté et le manque matériel'),
        ('6', '6', 'l\'équité et le partage'),
        ('7', '7', 'la récolte et l\'évaluation du travail'),
        ('8', '8', 'l\'apprentissage et la compétence'),
        ('9', '9', 'l\'indépendance et la prospérité'),
        ('10', '10', 'la richesse et la stabilité familiale'),
        ('Valet', 'Valet', 'l\'étudiant et la diligence'),
        ('Cavalier', 'Cavalier', 'l\'arrivée d\'une personne matérielle'),
        ('Reine', 'Reine', 'la prospérité et la terre'),
        ('Roi', 'Roi', 'l\'abondance et le succès matériel'),
    ]

    for rank, rank_fr, meaning in deniers_ranks:
        trans = _get_minor_translation_template('matérialité et ressources', 'Deniers', rank, rank_fr, meaning)
        deniers.update(trans)

    return deniers

# Build the complete dictionary
MINOR_CARD_TRANSLATIONS_FR = {}
MINOR_CARD_TRANSLATIONS_FR.update(build_coupes_translations())
MINOR_CARD_TRANSLATIONS_FR.update(build_batons_translations())
MINOR_CARD_TRANSLATIONS_FR.update(build_epees_translations())
MINOR_CARD_TRANSLATIONS_FR.update(build_deniers_translations())

# Verify we have all 56 cards
if __name__ == '__main__':
    print(f"Total minor cards translated: {len(MINOR_CARD_TRANSLATIONS_FR)}")
    for card_name in sorted(MINOR_CARD_TRANSLATIONS_FR.keys())[:10]:
        print(f"  - {card_name}")
