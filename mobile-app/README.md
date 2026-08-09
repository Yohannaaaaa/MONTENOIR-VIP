# Montenoir VIP — app mobile (wrapper Capacitor)

Ceci n'est **pas** une réécriture de l'app : c'est une coquille native (Capacitor)
qui ouvre `https://montenoirvip.onrender.com` (voir `capacitor.config.json`) dans
une WebView plein écran. Le site Flask/Socket.IO existant reste la seule source
de vérité — aucun code de `app.py` / `templates/` n'est dupliqué ici.

## Ce qui est déjà fait

- `npm install` (Capacitor core/cli/android) et `npx cap add android` ont été
  exécutés — le dossier `android/` est un projet Gradle/Android Studio complet
  et prêt à ouvrir.
- La permission `INTERNET` et le point d'entrée WebView sont déjà configurés.
- `capacitor.config.json` pointe vers l'URL de prod (`server.url`), donc l'app
  chargera toujours la dernière version déployée du site — pas besoin de
  republier l'app à chaque changement de `app.py`.

## Ce qu'il reste à faire (nécessite un poste avec Android Studio / Xcode)

Cet environnement sandbox n'a pas le SDK Android installé et son proxy réseau
bloque `dl.google.com` (dépôt Maven de Google) — impossible d'aller plus loin
ici. `./gradlew assembleDebug` a été testé et échoue uniquement sur cette
résolution réseau, pas sur la config du projet elle-même.

### Android
1. Installer [Android Studio](https://developer.android.com/studio).
2. `cd mobile-app && npm install && npx cap open android`
3. Dans Android Studio : laisser Gradle se synchroniser, puis
   **Build > Generate Signed Bundle/APK** pour créer un `.aab` signé
   (nécessite de créer un keystore de release — ne pas le committer).
4. Créer un compte [Google Play Console](https://play.google.com/console)
   (25$ à vie), créer la fiche app, uploader le `.aab`.

### iOS (nécessite un Mac)
1. `npm install @capacitor/ios && npx cap add ios`
2. `npx cap open ios`, configurer le signing avec un compte
   [Apple Developer](https://developer.apple.com/programs/) (99$/an).
3. Archiver et soumettre via Xcode / App Store Connect.

## ⚠️ Point de vigilance avant de soumettre

Montenoir VIP a des jetons, du VIP payant et des paiements réels (Stripe).
Les deux stores encadrent strictement ce type de contenu :

- **Apple** interdit ou restreint fortement les apps "casino-like" (jetons,
  roue de la chance, etc.) surtout si de l'argent réel entre en jeu — et peut
  rejeter un wrapper WebView jugé sans valeur ajoutée native.
- **Google Play** exige une licence de jeu d'argent réel dans les pays
  concernés si des paiements réels donnent des jetons/avantages ; sinon il
  faut rester clairement dans le cadre "jeu social / divertissement" (pas de
  gain monétaire réel possible).
- Les deux stores imposent en général leur propre système de paiement in-app
  pour les achats de contenu numérique (jetons, VIP) — Stripe direct dans une
  WebView peut être refusé selon comment c'est présenté.

À vérifier avec les guidelines à jour avant de soumettre, idéalement avant de
payer les comptes développeur.
