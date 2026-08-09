# CLAUDE.md

Guidance for Claude Code (and other AI assistants) working in this repository.

## What this is

**Montenoir VIP** is a French-flavored "VIP casino/games club" web app: a single Flask
server that renders server-side HTML templates and drives real-time multiplayer
gameplay over Socket.IO. There is no build step and no frontend framework — pages are
Jinja templates with plain JS/CSS in `static/`.

Games implemented: Codenames, Metropoly (a Monopoly-style board game with a 3D
Three.js board), Poker, Okey, Ludo, 101 (Turkish rummy), Tavla (backgammon), Bowling,
and a "Magic"/tarot-adjacent mini-game. There's also an account system, a virtual
chip economy, Stripe-based real-money purchases, an admin/"owner" panel, and a
tarot request feature.

## Architecture

- **`app.py`** — the entire backend (~9,900 lines). Everything lives in this one
  file: Flask routes, Socket.IO event handlers, game logic/state machines for every
  game, the user/auth system, Stripe integration, email sending, and the owner admin
  panel. There is no package/blueprint split — when working here, search by section
  rather than expecting a directory-per-feature layout.
- **`templates/`** — Jinja2 templates, roughly one per game/page (`index.html` is the
  landing/lobby, `metropoly.html`, `poker.html`, `okey.html`, `ludo.html`, `101.html`,
  `tavla.html`, `bowling.html`, `magic.html`, `codenames.html`).
- **`static/`** — per-game JS (`static/js/`), CSS (`static/css/`), images, and 3D
  assets (`static/models/*.glb` for the board/dice used by Metropoly's Three.js
  scene). `static/js/vendor/` holds vendored third-party JS.
- **State/data**: no ORM. User accounts and small persistent records are stored as
  JSON files (e.g. `users.json`, `tarot_requests.json`, `site_settings.json`,
  `stripe_processed_sessions.json`) under `DATA_DIR` (defaults to the working
  directory). An optional Postgres connection (`DATABASE_URL`, via `psycopg2`) backs
  a subset of features when configured — treat it as optional/best-effort, not the
  primary store.
- **In-memory game state**: live rooms/tables (`rooms = {}` and similar dicts near the
  top of `app.py`) live only in process memory. Since `Flask-SocketIO` runs with
  `async_mode='threading'`, concurrent Socket.IO event handlers execute on separate
  OS threads against this shared state — mutations to shared room/user dicts must go
  through `_state_lock` (an `RLock`). Follow the existing pattern (see
  `seat_sid_ok`/the comment block near the top of `app.py`) when adding new handlers
  that touch shared state.
- **Auth model**: sessions are tracked by a `sid -> username` map
  (`authenticated_sids`) plus a `token -> username` map for `resume_session`, rather
  than Flask's built-in session/cookie auth. Actions on a seated player go through
  `seat_sid_ok(room, username, sid)` to confirm the calling socket actually owns that
  seat — always use this check (or add an equivalent one) before letting a socket
  event mutate another player's state.
- **Payments**: Stripe Checkout is used for buying virtual chips (`/api/chips/*`,
  `/webhook/stripe`) and is gated by `stripe_configured()` — the app must keep
  working with Stripe fully unconfigured (local/dev), so don't remove those guards.

## Routing conventions worth knowing

- Many routes have "old" and "new" pairs, e.g. `/turnuvalar_old_disabled_236840` vs
  `/turnuvalar`. The `_old_disabled_<digits>` routes are intentionally dead/parked
  endpoints kept for reference — don't wire new features to them, and don't delete
  them without checking why they were parked.
- Several routes register multiple URL aliases for the same view function (e.g.
  `/games`, `/oyunlar`, and `/jeux` all forcing users to Metropoly; `/metropoly` and
  `/monopoly` as aliases). This is deliberate (French/Turkish/English URL variants
  and marketing redirects) — preserve existing aliases when refactoring a route.
- `/` is defined more than once in the file; the **last** `@app.route('/', ...)`
  registration wins with Flask. Check line order in `app.py` before assuming which
  handler actually serves a given path.

## Conventions

- **Language mix**: UI copy and many route names are French/Turkish (this is a
  French-market product with Turkish-speaking maintainers); code identifiers,
  comments, and commit messages are English. Match whichever is already used in the
  section you're editing.
- **Comments**: the codebase leans on comments to explain non-obvious concurrency and
  security invariants (see `seat_sid_ok`, `_state_lock`). Preserve/update these when
  touching the code they describe — they document real bugs that were fixed, not
  boilerplate.
- **Socket.IO event naming**: events are prefixed by game, e.g. `poker_*`,
  `okey_*`, `ludo_*`, `tavla_*`, `bowling_*`, `r101_*`, `magic_solo_*`,
  `magic_duel_*`, `monopoly_*` (Metropoly's events kept the `monopoly_` prefix).
  Follow the existing prefix when adding events for one of these games.
- No type hints, no linked style guide beyond `flake8` in CI (see below) — keep new
  code consistent with the surrounding function rather than introducing a new style.

## Environment variables

Read via `os.environ.get(...)` in `app.py`; nothing here has a `.env.example`, so
treat this list as the source of truth:

| Variable | Purpose |
| --- | --- |
| `DATA_DIR` | Directory for JSON data files (users, tarot requests, site settings, processed Stripe sessions). Tests set this to `/tmp`. |
| `DATABASE_URL` | Optional Postgres connection string; DB features are best-effort/optional. |
| `PORT` | Server port for `python app.py`. |
| `PUBLIC_BASE_URL` | Base URL used when building absolute links (e.g. password reset emails). |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Bootstrap credentials for the default admin/owner account. |
| `OWNER_SECRET` | Secret gate for the owner/admin panel endpoints. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Outbound email (password reset, etc.) via `smtplib`. |
| `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET` | Stripe integration; app must degrade gracefully when unset. |

## Development workflow

- **Runtime**: Python 3.11 (`runtime.txt`); CI pins 3.10 (`.github/workflows/python-app.yml`) — keep code compatible with both.
- **Install deps**: `pip install -r requirements.txt`
- **Run locally**: `python app.py` (reads `PORT`/`DATA_DIR`/etc. from the environment; set `DATA_DIR` to a writable scratch dir for local testing so you don't touch real data files).
- **Run the app in production**: `gunicorn` via the `Procfile` (`web: python app.py` is actually what's configured — check `Procfile` before assuming gunicorn is invoked directly).
- **Tests**: `pytest` (see `tests/test_smoke.py` and `conftest.py`). Tests are a
  minimal smoke suite — they import `app.py` (after setting `DATA_DIR=/tmp`) and
  assert key routes are registered. Add to this suite when you touch route
  registration or app import behavior; don't expect deep coverage of game logic.
- **Lint**: CI runs `flake8` twice — once strict (`--select=E9,F63,F7,F82`, fails the
  build on syntax errors/undefined names) and once advisory
  (`--exit-zero --max-complexity=10 --max-line-length=127`). Run
  `flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics` before
  pushing to catch what CI treats as a hard failure.
- **CI**: `.github/workflows/python-app.yml` runs on push/PR to `main` — installs
  `requirements.txt`, lints, then runs `pytest`.

## Working in this file

`app.py` is large; when making changes:
- Use search (route path, Socket.IO event name, or function name) rather than
  reading the whole file.
- Game logic for each game is grouped together but not modularized — expect to find
  room-creation, gameplay, and chat/voice handlers for a given game close together
  in the file, in that rough order.
- When adding a new mutating Socket.IO handler, check whether it needs
  `_state_lock` and a `seat_sid_ok`-style ownership check — most gameplay-mutation
  bugs historically fixed here were concurrency/authorization issues (see recent
  git log), not gameplay logic bugs.
