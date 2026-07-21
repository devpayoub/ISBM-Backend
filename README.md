# ISBM Backend — Plateforme de Supervision Industrielle PET/ISBM

Backend **Django 5.1** pour la supervision d'une unité de production PET ISBM (Tunisie) :
système d'alertes temps réel (cœur fonctionnel), suivi de production, calcul TRS/OEE,
analyse des coûts, Pareto pannes, planning et dashboard temps réel (WebSocket).

## Stack

| Composant | Technologie |
|---|---|
| Framework | Django 5.1 + DRF 3.15 |
| Temps réel | Django Channels 4.1 + Daphne (ASGI) |
| DB | PostgreSQL 16 |
| Cache / Broker | Redis 7 |
| Async | Celery 5.4 + django-celery-beat |
| Auth | SimpleJWT (access 15min / refresh 7j) |
| Docs API | drf-spectacular (Swagger) |

## Modules

```
apps/
  accounts/    Utilisateurs, rôles RBAC, JWT
  machines/    Référentiel machines + paramètres
  alerts/      🚨 Alertes temps réel (CŒUR) — CRUD + actions + WebSocket + notifications + escalation
  maintenance/ Interventions
  production/  Saisie horaire de production
  oee/         Calcul TRS / OEE
  costs/       Analyse des coûts
  planning/    Planning + écarts
  dashboard/   KPIs agrégés temps réel
  common/      Utilitaires (permissions, pagination, audit, broadcast Channels)
```

## Démarrage rapide (Docker)

```bash
cp .env.example .env
docker compose up --build
```

Services exposés :
- `http://localhost:8000/`        — écran d'atelier (WebSocket floor screen)
- `http://localhost:8000/api/docs/` — Swagger UI
- `http://localhost:8000/admin/`  — back-office Django
- WebSocket : `ws://localhost:8000/ws/alerts/?token=<JWT>`

## Démarrage local (sans Docker)

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements/dev.txt
pip install psycopg2-binary
python manage.py migrate
python manage.py seed
python manage.py runserver
# dans un autre terminal
celery -A config worker -l info
celery -A config beat -l info
```

## Compte admin de seed

| Email | Mot de passe |
|---|---|
| `admin@isbm.local` | `admin12345` |

À changer dès la première connexion.

## Cycle de vie d'une alerte

```
DÉCLARATION ➔ BROADCAST (WS) ➔ ACQUITTEMENT ➔ RÉSOLUTION ➔ CLÔTURE ➔ ANALYSE (Pareto + MTTR)
```

- Le contrôleur crée l'alerte → elle s'affiche **immédiatement** sur tous les écrans connectés (`ws/alerts/`).
- Notifications e-mail (et SMS pour CRITICAL) sont envoyées au personnel maintenance de garde.
- **Escalade Celery Beat** (toutes les 2 min) :
  - `> 5 min` sans acquittement → rappel manager
  - `> 15 min` → escalade CRITIQUE

## Endpoints REST (extraits)

| Méthode | Route | Description |
|---|---|---|
| POST | `/api/v1/auth/login/`  | JWT login |
| POST | `/api/v1/auth/refresh/` | Refresh JWT |
| GET  | `/api/v1/auth/me/`     | Profil courant |
| GET/POST | `/api/v1/machines/`   | CRUD machines |
| PATCH | `/api/v1/machines/{id}/status/` | Changer statut |
| GET/POST | `/api/v1/alerts/`    | CRUD alertes |
| PATCH | `/api/v1/alerts/{id}/acknowledge/` | Acquitter |
| PATCH | `/api/v1/alerts/{id}/resolve/`     | Résoudre |
| PATCH | `/api/v1/alerts/{id}/close/`       | Clôturer |
| PATCH | `/api/v1/alerts/{id}/escalate/`    | Escalader |
| POST | `/api/v1/alerts/{id}/comments/`    | Commenter |
| GET  | `/api/v1/alerts/active/`  | Alertes actives |
| GET  | `/api/v1/alerts/pareto/`  | Pareto des causes |
| GET  | `/api/v1/alerts/stats/`   | MTTR / MTBF / taux |
| GET/POST | `/api/v1/production/` | Saisie horaire |
| POST | `/api/v1/production/bulk/` | Saisie en lot |
| GET  | `/api/v1/oee/current/`    | TRS du jour |
| POST | `/api/v1/oee/recalc/`     | Recalcul OEE |
| GET  | `/api/v1/costs/parameters/` | Paramètres coûts |
| GET  | `/api/v1/costs/monthly-report/` | Rapport mensuel |
| GET  | `/api/v1/dashboard/kpis/` | KPIs agrégés |
| GET  | `/api/v1/maintenance/my-tasks/` | Mes interventions |
| GET  | `/api/v1/maintenance/mttr/` | MTTR par machine |

## Rôles (RBAC)

| Action | Admin | Manager | Contrôleur | Maintenance | Opérateur |
|---|:-:|:-:|:-:|:-:|:-:|
| Créer alerte | ✓ | ✓ | ✓ | ✓ | ✗ |
| Acquitter | ✓ | ✓ | ✗ | ✓ | ✗ |
| Résoudre | ✓ | ✓ | ✗ | ✓ | ✗ |
| Clôturer | ✓ | ✓ | ✗ | ✗ | ✗ |
| Escalader | ✓ | ✓ | ✓ | ✗ | ✗ |
| Saisie production | ✓ | ✓ | ✓ | ✗ | ✗ |
| Modifier paramètres | ✓ | ✓ | ✗ | ✗ | ✗ |
| Voir dashboard | ✓ | ✓ | ✓ | ✓ | ✓ |
| Voir coûts | ✓ | ✓ | ✗ | ✗ | ✗ |
| Gérer utilisateurs | ✓ | ✗ | ✗ | ✗ | ✗ |

## Commandes utiles

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py seed
python manage.py createsuperuser
python manage.py test
```

## Lint / Tests

Tests unitaires :

```bash
pytest
```

Vérification syntaxique rapide du projet :

```bash
python -m compileall apps config
```

## Variables d'environnement

Voir `.env.example` — éléments clés : `SECRET_KEY`, journaux de logs,
identifiants PostgreSQL, URLs Redis/Celery, configuration mail,
Twilio (SMS optionnel), Sentry (prod).

## Mots-clés Excel → module

| Feuille Excel | Module Django | Phase |
|---|---|---|
| Saisie horaire | `production` | 3 |
| Paramètres | `machines` + `costs` | 1 + 4 |
| TRS | `oee` | 4 |
| Coût | `costs` | 4 |
| Pareto pannes | `alerts` | 4 |
| Planning | `planning` | 5 |
| Dashboard KPIs | `dashboard` | 5 |
| **Alertes temps réel** | **`alerts` + Channels** | **2** |
| Interventions maintenance | `maintenance` | 2 |
| Écran atelier (WS) | `alerts/consumers.py` | 2 |
| Notifications (e-mail + SMS) | `alerts/notifications.py` | 2 |
```
