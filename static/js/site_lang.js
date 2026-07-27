// Choix de langue partagé entre toutes les pages de Montenoir VIP.
// La langue choisie est mémorisée dans localStorage ("site_lang") et relue sur chaque page.
const SITE_LANGS = [
  {code: 'fr', flag: '🇫🇷'},
  {code: 'en', flag: '🇬🇧'},
  {code: 'es', flag: '🇪🇸'},
  {code: 'de', flag: '🇩🇪'},
  {code: 'it', flag: '🇮🇹'},
  {code: 'nl', flag: '🇳🇱'},
  {code: 'ru', flag: '🇷🇺'},
  {code: 'ar', flag: '🇸🇦'},
  {code: 'pt', flag: '🇵🇹'},
  {code: 'pl', flag: '🇵🇱'},
  {code: 'tr', flag: '🇹🇷'},
  {code: 'ja', flag: '🇯🇵'},
  {code: 'zh', flag: '🇨🇳'},
  {code: 'ko', flag: '🇰🇷'}
];

function getSiteLang() {
  return localStorage.getItem('site_lang') || 'fr';
}

function setSiteLang(code) {
  localStorage.setItem('site_lang', code);
  document.documentElement.dir = (code === 'ar') ? 'rtl' : 'ltr';
}

// Construit les boutons drapeaux dans `container` (parmi `allowed`, ou tous si omis).
// `onChange(code)` est appelé au clic, après mise à jour de setSiteLang().
function buildLangSelector(container, onChange, allowed) {
  const list = allowed ? SITE_LANGS.filter(l => allowed.includes(l.code)) : SITE_LANGS;
  const current = getSiteLang();
  container.innerHTML = '';
  list.forEach(l => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'lang-btn' + (l.code === current ? ' active selected' : '');
    btn.textContent = l.flag;
    btn.title = l.code.toUpperCase();
    btn.dataset.lang = l.code;
    btn.addEventListener('click', () => {
      setSiteLang(l.code);
      container.querySelectorAll('.lang-btn').forEach(b => b.classList.remove('active', 'selected'));
      btn.classList.add('active', 'selected');
      onChange(l.code);
    });
    container.appendChild(btn);
  });
  document.documentElement.dir = (current === 'ar') ? 'rtl' : 'ltr';
}

// Petites chaînes réutilisées sur les pages simples (jeux, connexion, inscription...).
const COMMON_I18N = {
  fr: { back_home: '← Retour accueil', games_title: '🎮 JEUX MONTENOIR', coming_soon: 'Bientôt disponible.', login_title: '👤 Connexion', register_title: '📝 Inscription',
    field_username: 'Nom d\'utilisateur', field_password: 'Mot de passe', field_email: 'Email', field_confirm_password: 'Confirmer le mot de passe', field_gender: 'Genre',
    gender_male: 'Homme', gender_female: 'Femme', gender_other: 'Autre', gender_prefer_not: 'Je préfère ne pas dire',
    btn_submit_login: 'Se connecter', btn_submit_register: "S'inscrire",
    link_no_account: "Pas de compte ? S'inscrire", link_have_account: 'Déjà un compte ? Se connecter',
    auth_success_login: '✅ Connecté ! Redirection...', auth_success_register: '✅ Compte créé ! Redirection...',
    auth_passwords_mismatch: 'Les mots de passe ne correspondent pas.' ,
    coming_soon_game_desc: 'Ce jeu sera codé séparément plus tard selon ses propres règles.' ,
    premium_title: '💎 Adhésion Premium', premium_desc: 'Le système d\'adhésion premium sera bientôt actif.', kasa_title: '🪙 Caisse Montenoir', kasa_desc: 'Les packs de jetons et le système de paiement seront bientôt ici.', tournaments_title: '🏆 Tournois', tournaments_desc: 'Tournoi Codenames hebdomadaire — Entrée : 100 jetons — Récompense : 5000 jetons.', friends_title: '👥 Amis', friends_desc: 'Ajout d\'amis, messages privés et statut en ligne bientôt disponibles.', rules_title: '📜 Règles du jeu', rules_desc: 'Jeu respectueux, triche interdite, comportement inapproprié interdit.', chests_title: '🎁 Système de coffres', chests_desc: 'Coffres Bronze, Argent, Or et Diamant bientôt disponibles.', profile_shop_title: '🎨 Personnalisation du profil', profile_shop_desc: 'Cadre doré, cadre diamant, cadre baroque, couleurs de nom et profil animé bientôt disponibles.', ai_tarot_title: '🤖 IA Tarot Premium', ai_tarot_desc: 'Consultation premium : 1500 jetons.' , ai_tarot_desc2: 'Consultation personnalisée avec date de naissance, question et photo, bientôt disponible.' },
  en: { back_home: '← Back to home', games_title: '🎮 MONTENOIR GAMES', coming_soon: 'Coming soon.', login_title: '👤 Login', register_title: '📝 Register',
    field_username: 'Username', field_password: 'Password', field_email: 'Email', field_confirm_password: 'Confirm password', field_gender: 'Gender',
    gender_male: 'Male', gender_female: 'Female', gender_other: 'Other', gender_prefer_not: 'Prefer not to say',
    btn_submit_login: 'Log in', btn_submit_register: 'Sign up',
    link_no_account: "No account? Sign up", link_have_account: 'Already have an account? Log in',
    auth_success_login: '✅ Logged in! Redirecting...', auth_success_register: '✅ Account created! Redirecting...',
    auth_passwords_mismatch: 'Passwords do not match.' ,
    coming_soon_game_desc: 'This game will be built separately later, following its own rules.' ,
    premium_title: '💎 Premium Membership', premium_desc: 'The premium membership system will be active soon.', kasa_title: '🪙 Montenoir Cashier', kasa_desc: 'Chip packs and the payment system will be here soon.', tournaments_title: '🏆 Tournaments', tournaments_desc: 'Weekly Codenames Tournament — Entry: 100 chips — Prize: 5000 chips.', friends_title: '👥 Friends', friends_desc: 'Adding friends, private messages and online status coming soon.', rules_title: '📜 Game Rules', rules_desc: 'Respectful play, cheating forbidden, inappropriate behavior forbidden.', chests_title: '🎁 Chest System', chests_desc: 'Bronze, Silver, Gold and Diamond chests coming soon.', profile_shop_title: '🎨 Profile Customization', profile_shop_desc: 'Gold frame, diamond frame, baroque frame, name colors and animated profile coming soon.', ai_tarot_title: '🤖 AI Tarot Premium', ai_tarot_desc: 'Premium reading: 1500 chips.' , ai_tarot_desc2: 'Personalized reading with birth date, question and photo coming soon.' },
  es: { back_home: '← Volver al inicio', games_title: '🎮 JUEGOS MONTENOIR', coming_soon: 'Próximamente.', login_title: '👤 Iniciar sesión', register_title: '📝 Registro',
    field_username: 'Nombre de usuario', field_password: 'Contraseña', field_email: 'Correo electrónico', field_confirm_password: 'Confirmar contraseña', field_gender: 'Género',
    gender_male: 'Hombre', gender_female: 'Mujer', gender_other: 'Otro', gender_prefer_not: 'Prefiero no decirlo',
    btn_submit_login: 'Iniciar sesión', btn_submit_register: 'Registrarse',
    link_no_account: '¿Sin cuenta? Regístrate', link_have_account: '¿Ya tienes cuenta? Inicia sesión',
    auth_success_login: '✅ ¡Conectado! Redirigiendo...', auth_success_register: '✅ ¡Cuenta creada! Redirigiendo...',
    auth_passwords_mismatch: 'Las contraseñas no coinciden.' ,
    coming_soon_game_desc: 'Este juego se programará por separado más adelante, según sus propias reglas.' ,
    premium_title: '💎 Membresía Premium', premium_desc: 'El sistema de membresía premium estará activo pronto.', kasa_title: '🪙 Caja Montenoir', kasa_desc: 'Los paquetes de fichas y el sistema de pago estarán aquí pronto.', tournaments_title: '🏆 Torneos', tournaments_desc: 'Torneo Semanal de Codenames — Entrada: 100 fichas — Premio: 5000 fichas.', friends_title: '👥 Amigos', friends_desc: 'Agregar amigos, mensajes privados y estado en línea próximamente.', rules_title: '📜 Reglas del juego', rules_desc: 'Juego respetuoso, trampas prohibidas, comportamiento inapropiado prohibido.', chests_title: '🎁 Sistema de cofres', chests_desc: 'Cofres de Bronce, Plata, Oro y Diamante próximamente.', profile_shop_title: '🎨 Personalización de perfil', profile_shop_desc: 'Marco dorado, marco de diamante, marco barroco, colores de nombre y perfil animado próximamente.', ai_tarot_title: '🤖 IA Tarot Premium', ai_tarot_desc: 'Lectura premium: 1500 fichas.' , ai_tarot_desc2: 'Lectura personalizada con fecha de nacimiento, pregunta y foto próximamente.' },
  de: { back_home: '← Zurück zur Startseite', games_title: '🎮 MONTENOIR SPIELE', coming_soon: 'Demnächst verfügbar.', login_title: '👤 Anmelden', register_title: '📝 Registrierung',
    field_username: 'Benutzername', field_password: 'Passwort', field_email: 'E-Mail', field_confirm_password: 'Passwort bestätigen', field_gender: 'Geschlecht',
    gender_male: 'Männlich', gender_female: 'Weiblich', gender_other: 'Andere', gender_prefer_not: 'Keine Angabe',
    btn_submit_login: 'Anmelden', btn_submit_register: 'Registrieren',
    link_no_account: 'Kein Konto? Registrieren', link_have_account: 'Bereits ein Konto? Anmelden',
    auth_success_login: '✅ Angemeldet! Weiterleitung...', auth_success_register: '✅ Konto erstellt! Weiterleitung...',
    auth_passwords_mismatch: 'Die Passwörter stimmen nicht überein.' ,
    coming_soon_game_desc: 'Dieses Spiel wird später separat nach seinen eigenen Regeln entwickelt.' ,
    premium_title: '💎 Premium-Mitgliedschaft', premium_desc: 'Das Premium-Mitgliedschaftssystem wird bald aktiv sein.', kasa_title: '🪙 Montenoir Kasse', kasa_desc: 'Chip-Pakete und das Zahlungssystem werden bald hier sein.', tournaments_title: '🏆 Turniere', tournaments_desc: 'Wöchentliches Codenames-Turnier — Eintritt: 100 Chips — Preis: 5000 Chips.', friends_title: '👥 Freunde', friends_desc: 'Freunde hinzufügen, private Nachrichten und Online-Status demnächst verfügbar.', rules_title: '📜 Spielregeln', rules_desc: 'Respektvolles Spiel, Betrug verboten, unangemessenes Verhalten verboten.', chests_title: '🎁 Truhensystem', chests_desc: 'Bronze-, Silber-, Gold- und Diamant-Truhen demnächst verfügbar.', profile_shop_title: '🎨 Profilanpassung', profile_shop_desc: 'Goldrahmen, Diamantrahmen, Barockrahmen, Namensfarben und animiertes Profil demnächst verfügbar.', ai_tarot_title: '🤖 KI Tarot Premium', ai_tarot_desc: 'Premium-Lesung: 1500 Chips.' , ai_tarot_desc2: 'Personalisierte Lesung mit Geburtsdatum, Frage und Foto demnächst verfügbar.' },
  it: { back_home: '← Torna alla home', games_title: '🎮 GIOCHI MONTENOIR', coming_soon: 'Prossimamente.', login_title: '👤 Accedi', register_title: '📝 Registrazione',
    field_username: 'Nome utente', field_password: 'Password', field_email: 'Email', field_confirm_password: 'Conferma password', field_gender: 'Genere',
    gender_male: 'Uomo', gender_female: 'Donna', gender_other: 'Altro', gender_prefer_not: 'Preferisco non dirlo',
    btn_submit_login: 'Accedi', btn_submit_register: 'Registrati',
    link_no_account: 'Nessun account? Registrati', link_have_account: 'Hai già un account? Accedi',
    auth_success_login: '✅ Connesso! Reindirizzamento...', auth_success_register: '✅ Account creato! Reindirizzamento...',
    auth_passwords_mismatch: 'Le password non coincidono.' ,
    coming_soon_game_desc: 'Questo gioco verrà sviluppato separatamente in seguito, secondo le proprie regole.' ,
    premium_title: '💎 Abbonamento Premium', premium_desc: 'Il sistema di abbonamento premium sarà presto attivo.', kasa_title: '🪙 Cassa Montenoir', kasa_desc: 'I pacchetti di fiches e il sistema di pagamento saranno presto qui.', tournaments_title: '🏆 Tornei', tournaments_desc: 'Torneo Settimanale di Codenames — Ingresso: 100 fiches — Premio: 5000 fiches.', friends_title: '👥 Amici', friends_desc: 'Aggiungere amici, messaggi privati e stato online in arrivo.', rules_title: '📜 Regole del gioco', rules_desc: 'Gioco rispettoso, imbrogli vietati, comportamento inappropriato vietato.', chests_title: '🎁 Sistema di forzieri', chests_desc: 'Forzieri Bronzo, Argento, Oro e Diamante in arrivo.', profile_shop_title: '🎨 Personalizzazione profilo', profile_shop_desc: 'Cornice dorata, cornice di diamante, cornice barocca, colori del nome e profilo animato in arrivo.', ai_tarot_title: '🤖 IA Tarocchi Premium', ai_tarot_desc: 'Lettura premium: 1500 fiches.' , ai_tarot_desc2: 'Lettura personalizzata con data di nascita, domanda e foto in arrivo.' },
  nl: { back_home: '← Terug naar home', games_title: '🎮 MONTENOIR SPELLEN', coming_soon: 'Binnenkort beschikbaar.', login_title: '👤 Inloggen', register_title: '📝 Registreren',
    field_username: 'Gebruikersnaam', field_password: 'Wachtwoord', field_email: 'E-mail', field_confirm_password: 'Bevestig wachtwoord', field_gender: 'Geslacht',
    gender_male: 'Man', gender_female: 'Vrouw', gender_other: 'Anders', gender_prefer_not: 'Zeg ik liever niet',
    btn_submit_login: 'Inloggen', btn_submit_register: 'Registreren',
    link_no_account: 'Geen account? Registreer', link_have_account: 'Al een account? Inloggen',
    auth_success_login: '✅ Ingelogd! Doorverwijzen...', auth_success_register: '✅ Account aangemaakt! Doorverwijzen...',
    auth_passwords_mismatch: 'Wachtwoorden komen niet overeen.' ,
    coming_soon_game_desc: 'Dit spel wordt later apart ontwikkeld, volgens zijn eigen regels.' ,
    premium_title: '💎 Premium Lidmaatschap', premium_desc: 'Het premium lidmaatschapssysteem is binnenkort actief.', kasa_title: '🪙 Montenoir Kassa', kasa_desc: 'Chippakketten en het betaalsysteem komen hier binnenkort.', tournaments_title: '🏆 Toernooien', tournaments_desc: 'Wekelijks Codenames Toernooi — Inleg: 100 chips — Prijs: 5000 chips.', friends_title: '👥 Vrienden', friends_desc: 'Vrienden toevoegen, privéberichten en online status binnenkort beschikbaar.', rules_title: '📜 Spelregels', rules_desc: 'Respectvol spel, valsspelen verboden, ongepast gedrag verboden.', chests_title: '🎁 Kistsysteem', chests_desc: 'Bronzen, zilveren, gouden en diamanten kisten binnenkort beschikbaar.', profile_shop_title: '🎨 Profielaanpassing', profile_shop_desc: 'Gouden lijst, diamanten lijst, barokke lijst, naamkleuren en geanimeerd profiel binnenkort beschikbaar.', ai_tarot_title: '🤖 AI Tarot Premium', ai_tarot_desc: 'Premium lezing: 1500 chips.' , ai_tarot_desc2: 'Gepersonaliseerde lezing met geboortedatum, vraag en foto binnenkort beschikbaar.' },
  ru: { back_home: '← На главную', games_title: '🎮 ИГРЫ MONTENOIR', coming_soon: 'Скоро.', login_title: '👤 Вход', register_title: '📝 Регистрация',
    field_username: 'Имя пользователя', field_password: 'Пароль', field_email: 'Email', field_confirm_password: 'Подтвердите пароль', field_gender: 'Пол',
    gender_male: 'Мужской', gender_female: 'Женский', gender_other: 'Другое', gender_prefer_not: 'Не указывать',
    btn_submit_login: 'Войти', btn_submit_register: 'Зарегистрироваться',
    link_no_account: 'Нет аккаунта? Зарегистрироваться', link_have_account: 'Уже есть аккаунт? Войти',
    auth_success_login: '✅ Вход выполнен! Перенаправление...', auth_success_register: '✅ Аккаунт создан! Перенаправление...',
    auth_passwords_mismatch: 'Пароли не совпадают.' ,
    coming_soon_game_desc: 'Эта игра будет разработана отдельно позже, по своим собственным правилам.' ,
    premium_title: '💎 Премиум-членство', premium_desc: 'Система премиум-членства скоро заработает.', kasa_title: '🪙 Касса Montenoir', kasa_desc: 'Наборы фишек и система оплаты скоро появятся здесь.', tournaments_title: '🏆 Турниры', tournaments_desc: 'Еженедельный турнир Codenames — Взнос: 100 фишек — Приз: 5000 фишек.', friends_title: '👥 Друзья', friends_desc: 'Добавление друзей, личные сообщения и статус онлайн скоро появятся.', rules_title: '📜 Правила игры', rules_desc: 'Уважительная игра, читерство запрещено, неподобающее поведение запрещено.', chests_title: '🎁 Система сундуков', chests_desc: 'Бронзовые, серебряные, золотые и алмазные сундуки скоро появятся.', profile_shop_title: '🎨 Настройка профиля', profile_shop_desc: 'Золотая рамка, алмазная рамка, барочная рамка, цвета имени и анимированный профиль скоро появятся.', ai_tarot_title: '🤖 ИИ Таро Премиум', ai_tarot_desc: 'Премиум-расклад: 1500 фишек.' , ai_tarot_desc2: 'Персонализированный расклад с датой рождения, вопросом и фото скоро появится.' },
  ar: { back_home: '→ العودة للرئيسية', games_title: '🎮 ألعاب مونتينوار', coming_soon: 'قريبًا.', login_title: '👤 تسجيل الدخول', register_title: '📝 تسجيل',
    field_username: 'اسم المستخدم', field_password: 'كلمة المرور', field_email: 'البريد الإلكتروني', field_confirm_password: 'تأكيد كلمة المرور', field_gender: 'الجنس',
    gender_male: 'ذكر', gender_female: 'أنثى', gender_other: 'آخر', gender_prefer_not: 'أفضل عدم القول',
    btn_submit_login: 'دخول', btn_submit_register: 'تسجيل',
    link_no_account: 'ليس لديك حساب؟ سجّل', link_have_account: 'لديك حساب؟ سجّل الدخول',
    auth_success_login: '✅ تم تسجيل الدخول! جارٍ التحويل...', auth_success_register: '✅ تم إنشاء الحساب! جارٍ التحويل...',
    auth_passwords_mismatch: 'كلمتا المرور غير متطابقتين.' ,
    coming_soon_game_desc: 'ستتم برمجة هذه اللعبة بشكل منفصل لاحقًا وفقًا لقواعدها الخاصة.' ,
    premium_title: '💎 عضوية بريميوم', premium_desc: 'سيتم تفعيل نظام العضوية المميزة قريبًا.', kasa_title: '🪙 خزينة Montenoir', kasa_desc: 'ستكون حزم الرقاقات ونظام الدفع هنا قريبًا.', tournaments_title: '🏆 البطولات', tournaments_desc: 'بطولة Codenames الأسبوعية — الدخول: 100 رقاقة — الجائزة: 5000 رقاقة.', friends_title: '👥 الأصدقاء', friends_desc: 'إضافة الأصدقاء والرسائل الخاصة وحالة الاتصال قريبًا.', rules_title: '📜 قواعد اللعبة', rules_desc: 'لعب محترم، الغش ممنوع، السلوك غير اللائق ممنوع.', chests_title: '🎁 نظام الصناديق', chests_desc: 'صناديق برونزية وفضية وذهبية وماسية قريبًا.', profile_shop_title: '🎨 تخصيص الملف الشخصي', profile_shop_desc: 'إطار ذهبي وإطار ماسي وإطار باروكي وألوان الاسم والملف الشخصي المتحرك قريبًا.', ai_tarot_title: '🤖 تارو الذكاء الاصطناعي المميز', ai_tarot_desc: 'قراءة مميزة: 1500 رقاقة.' , ai_tarot_desc2: 'قراءة مخصصة مع تاريخ الميلاد والسؤال والصورة قريبًا.' },
  pt: { back_home: '← Voltar ao início', games_title: '🎮 JOGOS MONTENOIR', coming_soon: 'Em breve.', login_title: '👤 Entrar', register_title: '📝 Registrar',
    field_username: 'Nome de usuário', field_password: 'Senha', field_email: 'Email', field_confirm_password: 'Confirmar senha', field_gender: 'Gênero',
    gender_male: 'Masculino', gender_female: 'Feminino', gender_other: 'Outro', gender_prefer_not: 'Prefiro não dizer',
    btn_submit_login: 'Entrar', btn_submit_register: 'Registrar',
    link_no_account: 'Sem conta? Registre-se', link_have_account: 'Já tem conta? Entrar',
    auth_success_login: '✅ Conectado! Redirecionando...', auth_success_register: '✅ Conta criada! Redirecionando...',
    auth_passwords_mismatch: 'As senhas não coincidem.' ,
    coming_soon_game_desc: 'Este jogo será desenvolvido separadamente mais tarde, seguindo suas próprias regras.' ,
    premium_title: '💎 Assinatura Premium', premium_desc: 'O sistema de assinatura premium estará ativo em breve.', kasa_title: '🪙 Caixa Montenoir', kasa_desc: 'Os pacotes de fichas e o sistema de pagamento estarão aqui em breve.', tournaments_title: '🏆 Torneios', tournaments_desc: 'Torneio Semanal de Codenames — Entrada: 100 fichas — Prêmio: 5000 fichas.', friends_title: '👥 Amigos', friends_desc: 'Adicionar amigos, mensagens privadas e status online em breve.', rules_title: '📜 Regras do jogo', rules_desc: 'Jogo respeitoso, trapaça proibida, comportamento inadequado proibido.', chests_title: '🎁 Sistema de baús', chests_desc: 'Baús de Bronze, Prata, Ouro e Diamante em breve.', profile_shop_title: '🎨 Personalização de perfil', profile_shop_desc: 'Moldura dourada, moldura de diamante, moldura barroca, cores de nome e perfil animado em breve.', ai_tarot_title: '🤖 IA Tarô Premium', ai_tarot_desc: 'Leitura premium: 1500 fichas.' , ai_tarot_desc2: 'Leitura personalizada com data de nascimento, pergunta e foto em breve.' },
  pl: { back_home: '← Powrót do strony głównej', games_title: '🎮 GRY MONTENOIR', coming_soon: 'Wkrótce dostępne.', login_title: '👤 Zaloguj się', register_title: '📝 Rejestracja',
    field_username: 'Nazwa użytkownika', field_password: 'Hasło', field_email: 'Email', field_confirm_password: 'Potwierdź hasło', field_gender: 'Płeć',
    gender_male: 'Mężczyzna', gender_female: 'Kobieta', gender_other: 'Inne', gender_prefer_not: 'Wolę nie podawać',
    btn_submit_login: 'Zaloguj się', btn_submit_register: 'Zarejestruj się',
    link_no_account: 'Brak konta? Zarejestruj się', link_have_account: 'Masz już konto? Zaloguj się',
    auth_success_login: '✅ Zalogowano! Przekierowanie...', auth_success_register: '✅ Konto utworzone! Przekierowanie...',
    auth_passwords_mismatch: 'Hasła się nie zgadzają.' ,
    coming_soon_game_desc: 'Ta gra zostanie stworzona osobno później, zgodnie z własnymi zasadami.' ,
    premium_title: '💎 Członkostwo Premium', premium_desc: 'System członkostwa premium będzie wkrótce aktywny.', kasa_title: '🪙 Kasa Montenoir', kasa_desc: 'Pakiety żetonów i system płatności pojawią się tutaj wkrótce.', tournaments_title: '🏆 Turnieje', tournaments_desc: 'Cotygodniowy Turniej Codenames — Wpisowe: 100 żetonów — Nagroda: 5000 żetonów.', friends_title: '👥 Znajomi', friends_desc: 'Dodawanie znajomych, wiadomości prywatne i status online wkrótce.', rules_title: '📜 Zasady gry', rules_desc: 'Gra fair play, oszustwa zabronione, niewłaściwe zachowanie zabronione.', chests_title: '🎁 System skrzynek', chests_desc: 'Skrzynki Brązowa, Srebrna, Złota i Diamentowa wkrótce.', profile_shop_title: '🎨 Personalizacja profilu', profile_shop_desc: 'Złota ramka, diamentowa ramka, barokowa ramka, kolory nazwy i animowany profil wkrótce.', ai_tarot_title: '🤖 AI Tarot Premium', ai_tarot_desc: 'Premium odczyt: 1500 żetonów.' , ai_tarot_desc2: 'Spersonalizowany odczyt z datą urodzenia, pytaniem i zdjęciem wkrótce.' },
  tr: { back_home: '← Ana sayfaya dön', games_title: '🎮 MONTENOIR OYUNLARI', coming_soon: 'Yakında.', login_title: '👤 Giriş Yap', register_title: '📝 Kayıt Ol',
    field_username: 'Kullanıcı adı', field_password: 'Şifre', field_email: 'Email', field_confirm_password: 'Şifreyi onayla', field_gender: 'Cinsiyet',
    gender_male: 'Erkek', gender_female: 'Kadın', gender_other: 'Diğer', gender_prefer_not: 'Belirtmek istemiyorum',
    btn_submit_login: 'Giriş Yap', btn_submit_register: 'Kayıt Ol',
    link_no_account: 'Hesabın yok mu? Kayıt ol', link_have_account: 'Zaten hesabın var mı? Giriş yap',
    auth_success_login: '✅ Giriş yapıldı! Yönlendiriliyor...', auth_success_register: '✅ Hesap oluşturuldu! Yönlendiriliyor...',
    auth_passwords_mismatch: 'Şifreler eşleşmiyor.' ,
    coming_soon_game_desc: 'Bu oyun daha sonra kurallarına göre ayrı ayrı kodlanacak.' ,
    premium_title: '💎 Premium Üyelik', premium_desc: 'Premium üyelik sistemi yakında aktif olacak.', kasa_title: '🪙 Montenoir Kasası', kasa_desc: 'Jeton paketleri ve ödeme sistemi burada olacak.', tournaments_title: '🏆 Turnuvalar', tournaments_desc: 'Haftalık Codenames Turnuvası — Giriş: 100 jeton — Ödül: 5000 jeton.', friends_title: '👥 Arkadaşlar', friends_desc: 'Arkadaş ekleme, özel mesaj ve çevrimiçi durumu yakında.', rules_title: '📜 Oyun Kuralları', rules_desc: 'Saygılı oyun, hile yasak, uygunsuz davranış yasak.', chests_title: '🎁 Sandık Sistemi', chests_desc: 'Bronz, Gümüş, Altın ve Elmas sandıklar yakında.', profile_shop_title: '🎨 Profil Özelleştirme', profile_shop_desc: 'Altın çerçeve, elmas çerçeve, barok çerçeve, isim renkleri ve animasyonlu profil yakında.', ai_tarot_title: '🤖 AI Tarot Premium', ai_tarot_desc: 'Premium yorum: 1500 jeton.' , ai_tarot_desc2: 'Doğum tarihi, soru ve fotoğraf ile kişiselleştirilmiş yorum yakında.' },
  ja: { back_home: '← ホームに戻る', games_title: '🎮 MONTENOIR ゲーム', coming_soon: '近日公開。', login_title: '👤 ログイン', register_title: '📝 登録',
    field_username: 'ユーザー名', field_password: 'パスワード', field_email: 'メール', field_confirm_password: 'パスワード確認', field_gender: '性別',
    gender_male: '男性', gender_female: '女性', gender_other: 'その他', gender_prefer_not: '回答しない',
    btn_submit_login: 'ログイン', btn_submit_register: '登録',
    link_no_account: 'アカウントがない場合は登録', link_have_account: 'アカウントをお持ちの方はログイン',
    auth_success_login: '✅ ログインしました！リダイレクト中...', auth_success_register: '✅ アカウントが作成されました！リダイレクト中...',
    auth_passwords_mismatch: 'パスワードが一致しません。' ,
    coming_soon_game_desc: 'このゲームは後で独自のルールに従って別途開発されます。' ,
    premium_title: '💎 プレミアム会員', premium_desc: 'プレミアム会員制度は近日中に有効になります。', kasa_title: '🪙 Montenoirキャッシャー', kasa_desc: 'チップパックと決済システムは近日公開予定です。', tournaments_title: '🏆 トーナメント', tournaments_desc: '週間コードネームトーナメント — 参加費：チップ100枚 — 賞品：チップ5000枚。', friends_title: '👥 フレンド', friends_desc: 'フレンド追加、プライベートメッセージ、オンライン状態は近日公開。', rules_title: '📜 ゲームルール', rules_desc: '敬意ある対戦、不正行為禁止、不適切な行動禁止。', chests_title: '🎁 チェストシステム', chests_desc: 'ブロンズ、シルバー、ゴールド、ダイヤモンドチェストは近日公開。', profile_shop_title: '🎨 プロフィールカスタマイズ', profile_shop_desc: 'ゴールドフレーム、ダイヤモンドフレーム、バロックフレーム、名前の色、アニメーションプロフィールは近日公開。', ai_tarot_title: '🤖 AIタロットプレミアム', ai_tarot_desc: 'プレミアム鑑定：チップ1500枚。' , ai_tarot_desc2: '生年月日、質問、写真によるパーソナライズされた鑑定は近日公開。' },
  zh: { back_home: '← 返回首页', games_title: '🎮 MONTENOIR 游戏', coming_soon: '即将推出。', login_title: '👤 登录', register_title: '📝 注册',
    field_username: '用户名', field_password: '密码', field_email: '邮箱', field_confirm_password: '确认密码', field_gender: '性别',
    gender_male: '男', gender_female: '女', gender_other: '其他', gender_prefer_not: '不愿透露',
    btn_submit_login: '登录', btn_submit_register: '注册',
    link_no_account: '没有账号？注册', link_have_account: '已有账号？登录',
    auth_success_login: '✅ 已登录！正在跳转...', auth_success_register: '✅ 账号已创建！正在跳转...',
    auth_passwords_mismatch: '两次密码不一致。' ,
    coming_soon_game_desc: '这款游戏将根据其自身规则在稍后单独开发。' ,
    premium_title: '💎 高级会员', premium_desc: '高级会员系统即将上线。', kasa_title: '🪙 Montenoir收银台', kasa_desc: '筹码套餐和支付系统即将上线。', tournaments_title: '🏆 锦标赛', tournaments_desc: '每周codenames锦标赛 — 入场：100筹码 — 奖励：5000筹码。', friends_title: '👥 好友', friends_desc: '添加好友、私信和在线状态即将推出。', rules_title: '📜 游戏规则', rules_desc: '尊重比赛，禁止作弊，禁止不当行为。', chests_title: '🎁 宝箱系统', chests_desc: '青铜、白银、黄金和钻石宝箱即将推出。', profile_shop_title: '🎨 个人资料自定义', profile_shop_desc: '金色边框、钻石边框、巴洛克边框、名称颜色和动态资料即将推出。', ai_tarot_title: '🤖 AI塔罗高级版', ai_tarot_desc: '高级解读：1500筹码。' , ai_tarot_desc2: '根据出生日期、问题和照片提供的个性化解读即将推出。' },
  ko: { back_home: '← 홈으로', games_title: '🎮 MONTENOIR 게임', coming_soon: '곧 제공됩니다.', login_title: '👤 로그인', register_title: '📝 등록',
    field_username: '사용자 이름', field_password: '비밀번호', field_email: '이메일', field_confirm_password: '비밀번호 확인', field_gender: '성별',
    gender_male: '남성', gender_female: '여성', gender_other: '기타', gender_prefer_not: '밝히지 않음',
    btn_submit_login: '로그인', btn_submit_register: '가입하기',
    link_no_account: '계정이 없으신가요? 가입하기', link_have_account: '이미 계정이 있으신가요? 로그인',
    auth_success_login: '✅ 로그인되었습니다! 이동 중...', auth_success_register: '✅ 계정이 생성되었습니다! 이동 중...',
    auth_passwords_mismatch: '비밀번호가 일치하지 않습니다.' ,
    coming_soon_game_desc: '이 게임은 나중에 고유한 규칙에 따라 별도로 개발됩니다.' ,
    premium_title: '💎 프리미엄 멤버십', premium_desc: '프리미엄 멤버십 시스템이 곧 활성화됩니다.', kasa_title: '🪙 Montenoir 캐셔', kasa_desc: '칩 패키지와 결제 시스템이 곧 제공됩니다.', tournaments_title: '🏆 토너먼트', tournaments_desc: '주간 코드네임 토너먼트 — 참가비: 칩 100개 — 상금: 칩 5000개.', friends_title: '👥 친구', friends_desc: '친구 추가, 개인 메시지 및 온라인 상태가 곧 제공됩니다.', rules_title: '📜 게임 규칙', rules_desc: '존중하는 플레이, 부정행위 금지, 부적절한 행동 금지.', chests_title: '🎁 상자 시스템', chests_desc: '브론즈, 실버, 골드, 다이아몬드 상자가 곧 제공됩니다.', profile_shop_title: '🎨 프로필 커스터마이징', profile_shop_desc: '골드 프레임, 다이아몬드 프레임, 바로크 프레임, 이름 색상 및 애니메이션 프로필이 곧 제공됩니다.', ai_tarot_title: '🤖 AI 타로 프리미엄', ai_tarot_desc: '프리미엄 리딩: 칩 1500개.' , ai_tarot_desc2: '생년월일, 질문, 사진을 활용한 맞춤형 리딩이 곧 제공됩니다.' }
};

function ct(key, lng) {
  const dict = COMMON_I18N[lng || getSiteLang()] || COMMON_I18N.fr;
  return dict[key] !== undefined ? dict[key] : (COMMON_I18N.fr[key] || key);
}

function applyCommonI18n(lang) {
  document.querySelectorAll('[data-common-i18n]').forEach(el => { el.textContent = ct(el.dataset.commonI18n, lang); });
  document.querySelectorAll('[data-common-i18n-placeholder]').forEach(el => { el.placeholder = ct(el.dataset.commonI18nPlaceholder, lang); });
}

// Messages d'erreur fixes renvoyés par /api/auth/login et /api/auth/register (texte turc côté serveur),
// traduits ici par correspondance exacte plutôt que de modifier l'API partagée avec /codenames.
const AUTH_ERR_I18N = {
  "Kullanıcı adı en az 3 karakter olmalı.": { fr:"Le nom d'utilisateur doit faire au moins 3 caractères.", en:'Username must be at least 3 characters.', es:'El nombre de usuario debe tener al menos 3 caracteres.', de:'Der Benutzername muss mindestens 3 Zeichen lang sein.', it:'Il nome utente deve avere almeno 3 caratteri.', nl:'Gebruikersnaam moet minstens 3 tekens bevatten.', ru:'Имя пользователя должно содержать не менее 3 символов.', ar:'يجب أن يتكون اسم المستخدم من 3 أحرف على الأقل.', pt:'O nome de usuário deve ter pelo menos 3 caracteres.', pl:'Nazwa użytkownika musi mieć co najmniej 3 znaki.', tr:'Kullanıcı adı en az 3 karakter olmalı.', ja:'ユーザー名は3文字以上必要です。', zh:'用户名至少需要3个字符。', ko:'사용자 이름은 3자 이상이어야 합니다.' },
  "Geçerli bir email yaz.": { fr:'Merci de saisir un email valide.', en:'Please enter a valid email.', es:'Introduce un correo electrónico válido.', de:'Bitte eine gültige E-Mail-Adresse eingeben.', it:'Inserisci un\'email valida.', nl:'Voer een geldig e-mailadres in.', ru:'Введите действительный email.', ar:'يرجى إدخال بريد إلكتروني صالح.', pt:'Digite um email válido.', pl:'Podaj prawidłowy adres email.', tr:'Geçerli bir email yaz.', ja:'有効なメールアドレスを入力してください。', zh:'请输入有效的邮箱地址。', ko:'유효한 이메일을 입력하세요.' },
  "Şifre en az 4 karakter olmalı.": { fr:'Le mot de passe doit faire au moins 4 caractères.', en:'Password must be at least 4 characters.', es:'La contraseña debe tener al menos 4 caracteres.', de:'Das Passwort muss mindestens 4 Zeichen lang sein.', it:'La password deve avere almeno 4 caratteri.', nl:'Wachtwoord moet minstens 4 tekens bevatten.', ru:'Пароль должен содержать не менее 4 символов.', ar:'يجب أن تتكون كلمة المرور من 4 أحرف على الأقل.', pt:'A senha deve ter pelo menos 4 caracteres.', pl:'Hasło musi mieć co najmniej 4 znaki.', tr:'Şifre en az 4 karakter olmalı.', ja:'パスワードは4文字以上必要です。', zh:'密码至少需要4个字符。', ko:'비밀번호는 4자 이상이어야 합니다.' },
  "Bu kullanıcı adı zaten var.": { fr:"Ce nom d'utilisateur existe déjà.", en:'This username already exists.', es:'Este nombre de usuario ya existe.', de:'Dieser Benutzername existiert bereits.', it:'Questo nome utente esiste già.', nl:'Deze gebruikersnaam bestaat al.', ru:'Это имя пользователя уже занято.', ar:'اسم المستخدم هذا موجود بالفعل.', pt:'Este nome de usuário já existe.', pl:'Ta nazwa użytkownika już istnieje.', tr:'Bu kullanıcı adı zaten var.', ja:'このユーザー名は既に使用されています。', zh:'该用户名已存在。', ko:'이미 존재하는 사용자 이름입니다.' },
  "Bu email zaten kayıtlı.": { fr:'Cet email est déjà enregistré.', en:'This email is already registered.', es:'Este correo ya está registrado.', de:'Diese E-Mail ist bereits registriert.', it:'Questa email è già registrata.', nl:'Dit e-mailadres is al geregistreerd.', ru:'Этот email уже зарегистрирован.', ar:'هذا البريد الإلكتروني مسجل بالفعل.', pt:'Este email já está registrado.', pl:'Ten adres email jest już zarejestrowany.', tr:'Bu email zaten kayıtlı.', ja:'このメールアドレスは既に登録されています。', zh:'该邮箱已被注册。', ko:'이미 등록된 이메일입니다.' },
  "Kullanıcı bulunamadı.": { fr:'Utilisateur introuvable.', en:'User not found.', es:'Usuario no encontrado.', de:'Benutzer nicht gefunden.', it:'Utente non trovato.', nl:'Gebruiker niet gevonden.', ru:'Пользователь не найден.', ar:'لم يتم العثور على المستخدم.', pt:'Usuário não encontrado.', pl:'Nie znaleziono użytkownika.', tr:'Kullanıcı bulunamadı.', ja:'ユーザーが見つかりません。', zh:'未找到用户。', ko:'사용자를 찾을 수 없습니다.' },
  "Şifre yanlış.": { fr:'Mot de passe incorrect.', en:'Incorrect password.', es:'Contraseña incorrecta.', de:'Falsches Passwort.', it:'Password errata.', nl:'Onjuist wachtwoord.', ru:'Неверный пароль.', ar:'كلمة المرور غير صحيحة.', pt:'Senha incorreta.', pl:'Nieprawidłowe hasło.', tr:'Şifre yanlış.', ja:'パスワードが間違っています。', zh:'密码错误。', ko:'비밀번호가 올바르지 않습니다.' },
  "Şifreler aynı değil.": { fr:'Les mots de passe ne correspondent pas.', en:'Passwords do not match.', es:'Las contraseñas no coinciden.', de:'Die Passwörter stimmen nicht überein.', it:'Le password non coincidono.', nl:'Wachtwoorden komen niet overeen.', ru:'Пароли не совпадают.', ar:'كلمتا المرور غير متطابقتين.', pt:'As senhas não coincidem.', pl:'Hasła się nie zgadzają.', tr:'Şifreler aynı değil.', ja:'パスワードが一致しません。', zh:'两次密码不一致。', ko:'비밀번호가 일치하지 않습니다.' }
};

function translateAuthMsg(msg, lng) {
  const entry = AUTH_ERR_I18N[msg];
  if (!entry) return msg;
  return entry[lng || getSiteLang()] || entry.fr || msg;
}
