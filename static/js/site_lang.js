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
    auth_passwords_mismatch: 'Les mots de passe ne correspondent pas.' },
  en: { back_home: '← Back to home', games_title: '🎮 MONTENOIR GAMES', coming_soon: 'Coming soon.', login_title: '👤 Login', register_title: '📝 Register',
    field_username: 'Username', field_password: 'Password', field_email: 'Email', field_confirm_password: 'Confirm password', field_gender: 'Gender',
    gender_male: 'Male', gender_female: 'Female', gender_other: 'Other', gender_prefer_not: 'Prefer not to say',
    btn_submit_login: 'Log in', btn_submit_register: 'Sign up',
    link_no_account: "No account? Sign up", link_have_account: 'Already have an account? Log in',
    auth_success_login: '✅ Logged in! Redirecting...', auth_success_register: '✅ Account created! Redirecting...',
    auth_passwords_mismatch: 'Passwords do not match.' },
  es: { back_home: '← Volver al inicio', games_title: '🎮 JUEGOS MONTENOIR', coming_soon: 'Próximamente.', login_title: '👤 Iniciar sesión', register_title: '📝 Registro',
    field_username: 'Nombre de usuario', field_password: 'Contraseña', field_email: 'Correo electrónico', field_confirm_password: 'Confirmar contraseña', field_gender: 'Género',
    gender_male: 'Hombre', gender_female: 'Mujer', gender_other: 'Otro', gender_prefer_not: 'Prefiero no decirlo',
    btn_submit_login: 'Iniciar sesión', btn_submit_register: 'Registrarse',
    link_no_account: '¿Sin cuenta? Regístrate', link_have_account: '¿Ya tienes cuenta? Inicia sesión',
    auth_success_login: '✅ ¡Conectado! Redirigiendo...', auth_success_register: '✅ ¡Cuenta creada! Redirigiendo...',
    auth_passwords_mismatch: 'Las contraseñas no coinciden.' },
  de: { back_home: '← Zurück zur Startseite', games_title: '🎮 MONTENOIR SPIELE', coming_soon: 'Demnächst verfügbar.', login_title: '👤 Anmelden', register_title: '📝 Registrierung',
    field_username: 'Benutzername', field_password: 'Passwort', field_email: 'E-Mail', field_confirm_password: 'Passwort bestätigen', field_gender: 'Geschlecht',
    gender_male: 'Männlich', gender_female: 'Weiblich', gender_other: 'Andere', gender_prefer_not: 'Keine Angabe',
    btn_submit_login: 'Anmelden', btn_submit_register: 'Registrieren',
    link_no_account: 'Kein Konto? Registrieren', link_have_account: 'Bereits ein Konto? Anmelden',
    auth_success_login: '✅ Angemeldet! Weiterleitung...', auth_success_register: '✅ Konto erstellt! Weiterleitung...',
    auth_passwords_mismatch: 'Die Passwörter stimmen nicht überein.' },
  it: { back_home: '← Torna alla home', games_title: '🎮 GIOCHI MONTENOIR', coming_soon: 'Prossimamente.', login_title: '👤 Accedi', register_title: '📝 Registrazione',
    field_username: 'Nome utente', field_password: 'Password', field_email: 'Email', field_confirm_password: 'Conferma password', field_gender: 'Genere',
    gender_male: 'Uomo', gender_female: 'Donna', gender_other: 'Altro', gender_prefer_not: 'Preferisco non dirlo',
    btn_submit_login: 'Accedi', btn_submit_register: 'Registrati',
    link_no_account: 'Nessun account? Registrati', link_have_account: 'Hai già un account? Accedi',
    auth_success_login: '✅ Connesso! Reindirizzamento...', auth_success_register: '✅ Account creato! Reindirizzamento...',
    auth_passwords_mismatch: 'Le password non coincidono.' },
  nl: { back_home: '← Terug naar home', games_title: '🎮 MONTENOIR SPELLEN', coming_soon: 'Binnenkort beschikbaar.', login_title: '👤 Inloggen', register_title: '📝 Registreren',
    field_username: 'Gebruikersnaam', field_password: 'Wachtwoord', field_email: 'E-mail', field_confirm_password: 'Bevestig wachtwoord', field_gender: 'Geslacht',
    gender_male: 'Man', gender_female: 'Vrouw', gender_other: 'Anders', gender_prefer_not: 'Zeg ik liever niet',
    btn_submit_login: 'Inloggen', btn_submit_register: 'Registreren',
    link_no_account: 'Geen account? Registreer', link_have_account: 'Al een account? Inloggen',
    auth_success_login: '✅ Ingelogd! Doorverwijzen...', auth_success_register: '✅ Account aangemaakt! Doorverwijzen...',
    auth_passwords_mismatch: 'Wachtwoorden komen niet overeen.' },
  ru: { back_home: '← На главную', games_title: '🎮 ИГРЫ MONTENOIR', coming_soon: 'Скоро.', login_title: '👤 Вход', register_title: '📝 Регистрация',
    field_username: 'Имя пользователя', field_password: 'Пароль', field_email: 'Email', field_confirm_password: 'Подтвердите пароль', field_gender: 'Пол',
    gender_male: 'Мужской', gender_female: 'Женский', gender_other: 'Другое', gender_prefer_not: 'Не указывать',
    btn_submit_login: 'Войти', btn_submit_register: 'Зарегистрироваться',
    link_no_account: 'Нет аккаунта? Зарегистрироваться', link_have_account: 'Уже есть аккаунт? Войти',
    auth_success_login: '✅ Вход выполнен! Перенаправление...', auth_success_register: '✅ Аккаунт создан! Перенаправление...',
    auth_passwords_mismatch: 'Пароли не совпадают.' },
  ar: { back_home: '→ العودة للرئيسية', games_title: '🎮 ألعاب مونتينوار', coming_soon: 'قريبًا.', login_title: '👤 تسجيل الدخول', register_title: '📝 تسجيل',
    field_username: 'اسم المستخدم', field_password: 'كلمة المرور', field_email: 'البريد الإلكتروني', field_confirm_password: 'تأكيد كلمة المرور', field_gender: 'الجنس',
    gender_male: 'ذكر', gender_female: 'أنثى', gender_other: 'آخر', gender_prefer_not: 'أفضل عدم القول',
    btn_submit_login: 'دخول', btn_submit_register: 'تسجيل',
    link_no_account: 'ليس لديك حساب؟ سجّل', link_have_account: 'لديك حساب؟ سجّل الدخول',
    auth_success_login: '✅ تم تسجيل الدخول! جارٍ التحويل...', auth_success_register: '✅ تم إنشاء الحساب! جارٍ التحويل...',
    auth_passwords_mismatch: 'كلمتا المرور غير متطابقتين.' },
  pt: { back_home: '← Voltar ao início', games_title: '🎮 JOGOS MONTENOIR', coming_soon: 'Em breve.', login_title: '👤 Entrar', register_title: '📝 Registrar',
    field_username: 'Nome de usuário', field_password: 'Senha', field_email: 'Email', field_confirm_password: 'Confirmar senha', field_gender: 'Gênero',
    gender_male: 'Masculino', gender_female: 'Feminino', gender_other: 'Outro', gender_prefer_not: 'Prefiro não dizer',
    btn_submit_login: 'Entrar', btn_submit_register: 'Registrar',
    link_no_account: 'Sem conta? Registre-se', link_have_account: 'Já tem conta? Entrar',
    auth_success_login: '✅ Conectado! Redirecionando...', auth_success_register: '✅ Conta criada! Redirecionando...',
    auth_passwords_mismatch: 'As senhas não coincidem.' },
  pl: { back_home: '← Powrót do strony głównej', games_title: '🎮 GRY MONTENOIR', coming_soon: 'Wkrótce dostępne.', login_title: '👤 Zaloguj się', register_title: '📝 Rejestracja',
    field_username: 'Nazwa użytkownika', field_password: 'Hasło', field_email: 'Email', field_confirm_password: 'Potwierdź hasło', field_gender: 'Płeć',
    gender_male: 'Mężczyzna', gender_female: 'Kobieta', gender_other: 'Inne', gender_prefer_not: 'Wolę nie podawać',
    btn_submit_login: 'Zaloguj się', btn_submit_register: 'Zarejestruj się',
    link_no_account: 'Brak konta? Zarejestruj się', link_have_account: 'Masz już konto? Zaloguj się',
    auth_success_login: '✅ Zalogowano! Przekierowanie...', auth_success_register: '✅ Konto utworzone! Przekierowanie...',
    auth_passwords_mismatch: 'Hasła się nie zgadzają.' },
  tr: { back_home: '← Ana sayfaya dön', games_title: '🎮 MONTENOIR OYUNLARI', coming_soon: 'Yakında.', login_title: '👤 Giriş Yap', register_title: '📝 Kayıt Ol',
    field_username: 'Kullanıcı adı', field_password: 'Şifre', field_email: 'Email', field_confirm_password: 'Şifreyi onayla', field_gender: 'Cinsiyet',
    gender_male: 'Erkek', gender_female: 'Kadın', gender_other: 'Diğer', gender_prefer_not: 'Belirtmek istemiyorum',
    btn_submit_login: 'Giriş Yap', btn_submit_register: 'Kayıt Ol',
    link_no_account: 'Hesabın yok mu? Kayıt ol', link_have_account: 'Zaten hesabın var mı? Giriş yap',
    auth_success_login: '✅ Giriş yapıldı! Yönlendiriliyor...', auth_success_register: '✅ Hesap oluşturuldu! Yönlendiriliyor...',
    auth_passwords_mismatch: 'Şifreler eşleşmiyor.' },
  ja: { back_home: '← ホームに戻る', games_title: '🎮 MONTENOIR ゲーム', coming_soon: '近日公開。', login_title: '👤 ログイン', register_title: '📝 登録',
    field_username: 'ユーザー名', field_password: 'パスワード', field_email: 'メール', field_confirm_password: 'パスワード確認', field_gender: '性別',
    gender_male: '男性', gender_female: '女性', gender_other: 'その他', gender_prefer_not: '回答しない',
    btn_submit_login: 'ログイン', btn_submit_register: '登録',
    link_no_account: 'アカウントがない場合は登録', link_have_account: 'アカウントをお持ちの方はログイン',
    auth_success_login: '✅ ログインしました！リダイレクト中...', auth_success_register: '✅ アカウントが作成されました！リダイレクト中...',
    auth_passwords_mismatch: 'パスワードが一致しません。' },
  zh: { back_home: '← 返回首页', games_title: '🎮 MONTENOIR 游戏', coming_soon: '即将推出。', login_title: '👤 登录', register_title: '📝 注册',
    field_username: '用户名', field_password: '密码', field_email: '邮箱', field_confirm_password: '确认密码', field_gender: '性别',
    gender_male: '男', gender_female: '女', gender_other: '其他', gender_prefer_not: '不愿透露',
    btn_submit_login: '登录', btn_submit_register: '注册',
    link_no_account: '没有账号？注册', link_have_account: '已有账号？登录',
    auth_success_login: '✅ 已登录！正在跳转...', auth_success_register: '✅ 账号已创建！正在跳转...',
    auth_passwords_mismatch: '两次密码不一致。' },
  ko: { back_home: '← 홈으로', games_title: '🎮 MONTENOIR 게임', coming_soon: '곧 제공됩니다.', login_title: '👤 로그인', register_title: '📝 등록',
    field_username: '사용자 이름', field_password: '비밀번호', field_email: '이메일', field_confirm_password: '비밀번호 확인', field_gender: '성별',
    gender_male: '남성', gender_female: '여성', gender_other: '기타', gender_prefer_not: '밝히지 않음',
    btn_submit_login: '로그인', btn_submit_register: '가입하기',
    link_no_account: '계정이 없으신가요? 가입하기', link_have_account: '이미 계정이 있으신가요? 로그인',
    auth_success_login: '✅ 로그인되었습니다! 이동 중...', auth_success_register: '✅ 계정이 생성되었습니다! 이동 중...',
    auth_passwords_mismatch: '비밀번호가 일치하지 않습니다.' }
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
