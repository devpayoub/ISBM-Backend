# 🏭 Plan Backend Django — Système d'Alertes & Suivi de Production ISBM

## Projet : Plateforme de Supervision Industrielle PET/ISBM

**Document d'architecture technique — Backend Django**

| | |
|---|---|
| **Client** | Unité de production PET ISBM (Tunisie) |
| **Périmètre** | Backend API + Temps réel + Supervision |
| **Stack principale** | Django 5.x · Django REST Framework · Django Channels · PostgreSQL · Redis · Celery |
| **Version** | v1.0 — Juillet 2026 |

---

## 📌 Résumé Exécutif

Ce document définit l'architecture complète du backend Django pour une **plateforme de supervision industrielle** couvrant :

1. **🚨 Système d'alertes machines en temps réel** (fonctionnalité cœur) — Le contrôleur déclare un incident depuis son dashboard → l'alerte s'affiche instantanément sur les écrans d'atelier (problème / machine / heure / opérateur) → l'équipe maintenance est notifiée.
2. **📊 Suivi de production horaire** — Saisie par machine (ISBM110, ISBM88, Injection Bouchons) avec rebuts, arrêts, consommation PET/énergie/air.
3. **📈 Calcul TRS/OEE automatique** — Disponibilité × Performance × Qualité.
4. **💰 Analyse des coûts** — Coût matière, énergie, main-d'œuvre, coût unitaire par bouteille.
5. **📉 Pareto des pannes** — Analyse des causes d'incidents pour amélioration continue.
6. **📅 Planning de production** — Objectifs vs réalisé par machine/produit/jour.
7. **🖥️ Dashboard temps réel** — KPIs affichés sur écrans d'atelier via WebSocket.

---

## 1. 📋 Analyse du Fichier Excel — Suivi_Production_ISBM_V5.xlsx

Le fichier Excel fourni contient **7 feuilles** qui révèlent un système complet de suivi de production :

### 1.1 Feuille Saisie — Saisie Horaire de Production

| Colonne | Type | Description |
|---|---|---|
| Heure | Time | Créneau horaire (1:00 → 24:00, soit 24 lignes/jour) |
| ISBM110 | Integer | Nombre de bouteilles produites par la machine ISBM 110 (750 ml) |
| ISBM88 | Integer | Nombre de bouteilles produites par la machine ISBM 88 (250 ml) |
| Bouchons | Integer | Nombre de bouchons produits par la presse à injection |
| Rebut_% | Float | Taux de rebut (bouteilles défectueuses) en % |
| Arret_min | Integer | Durée d'arrêt machine en minutes |
| PET_kg | Float | Consommation de matière PET en kg |
| Energie_kWh | Float | Consommation électrique en kWh |
| Air_m3 | Float | Consommation d'air comprimé en m³ |

> **→ Module Django : production** — Saisie horaire par machine, avec validation et calculs automatiques.

### 1.2 Feuille Parametres — Paramètres Machine & Coûts

| Paramètre | Valeur | Description |
|---|---|---|
| Cadence ISBM110 | 720 BPH | Cadence nominale (bouteilles/heure) — 750 ml, 6 cavités |
| Cadence ISBM88 | 1 100 BPH | Cadence nominale — 250 ml, 6 cavités |
| Cadence bouchons | 1 600 CPH | Cadence nominale (bouchons/heure) — moule 8 cavités |
| Temps shift | 1 440 min | Durée d'un shift (24h) |
| Seuil TRS | 70 % | Objectif minimum de TRS |
| Coût PET/kg | à définir | Prix matière première |
| Coût énergie/kWh | à définir | Prix électricité (STEG) |
| Coût MO/h | à définir | Coût main-d'œuvre horaire |
| Coût air/m³ | à définir | Coût air comprimé |

> **→ Module Django : machines + parametres** — Référentiel machines et paramètres configurables par l'admin.

### 1.3 Feuille TRS — Calcul OEE

| Indicateur | Formule |
|---|---|
| Production théorique | Cadence × Temps shift = 43 680 bouteilles |
| Disponibilité % | (Temps shift − Arrêts) / Temps shift × 100 |
| Performance % | Production réelle / Production théorique × 100 |
| Qualité % | (Production − Rebuts) / Production × 100 |
| TRS % | Disponibilité × Performance × Qualité / 10 000 |
| kWh / bouteille | Énergie totale / Production |
| Air / bouteille | Air total / Production |

> **→ Module Django : oee** — Calcul automatique du TRS par machine et par shift.

### 1.4 Feuille Cout — Analyse des Coûts

| Poste | Calcul |
|---|---|
| Coût PET | PET_kg × Coût PET/kg |
| Coût énergie | Energie_kWh × Coût énergie/kWh |
| Coût air | Air_m³ × Coût air/m³ |
| Coût MO | Heures × Coût MO/h |
| Coût total | Σ des 4 postes |
| Coût / bouteille | Coût total / Production |

> **→ Module Django : costs** — Calcul des coûts par shift/jour/mois.

### 1.5 Feuille Pareto_Pannes — Analyse Pareto des Incidents

| Colonne | Description |
|---|---|
| Cause | Cause de la panne (catégorisée) |
| Nb incidents | Nombre d'occurrences |

> **→ Module Django : alerts** — Chaque alerte/incident est catégorisé → génération automatique du Pareto.

### 1.6 Feuille Planning — Planning de Production

| Colonne | Description |
|---|---|
| Jour | Date du jour |
| Machine | Machine concernée |
| Produit | Type de produit (750 ml / 250 ml / Bouchon) |
| Objectif BPH | Objectif de production |
| Réel | Production réelle |
| Ecart | Écart = Réel − Objectif |

> **→ Module Django : planning** — Planification quotidienne avec suivi des écarts.

### 1.7 Feuille Dashboard — Tableau de Bord KPIs

| KPI | Source |
|---|---|
| TRS | Calcul OEE |
| Production | Somme ISBM110 + ISBM88 |
| kWh / bouteille | TRS |
| Air / bouteille | TRS |
| Coût / bouteille | Cout |

> **→ Module Django : dashboard** — Agrégation temps réel des KPIs.

### 🔑 Conclusion de l'analyse

Le fichier Excel est le **cahier des charges fonctionnel** d'un système MES complet. Le backend Django couvre **7 modules métier** interconnectés, avec le **système d'alertes en temps réel** comme fonctionnalité centrale.

---

## 2. 🏗️ Architecture Technique

### 2.1 Stack Technologique

| Composant | Technologie | Justification |
|---|---|---|
| Framework | Django 5.x + DRF 3.15 | API REST robuste, ORM puissant |
| Temps réel | Django Channels 4 + WebSocket | Alertes instantanées sur écrans |
| Base de données | PostgreSQL 16 | Fiabilité industrielle |
| Cache / Broker | Redis 7 | Cache + broker Celery + channel layer |
| Tâches async | Celery 5 | Notifications, rapports, recalculs OEE |
| Auth | Django Auth + JWT (SimpleJWT) | Authentification stateless |
| Notifications | Email (SMTP) + WebSocket + SMS | Alertes multi-canal |
| Frontend | React.js / Vue.js + écrans TV | Dashboard + écrans atelier |
| Déploiement | Docker + Nginx + Daphne | ASGI pour WebSocket |

### 2.2 Structure du Projet Django

    isbm_backend/
    ├── config/                          # Configuration principale
    │   ├── settings/ (base, dev, prod)
    │   ├── urls.py
    │   ├── asgi.py                      # ASGI (Channels + WebSocket)
    │   ├── wsgi.py
    │   └── celery.py
    │
    ├── apps/
    │   ├── accounts/                    # 👤 Utilisateurs & Rôles
    │   ├── machines/                    # 🏭 Référentiel Machines
    │   ├── production/                  # 📊 Saisie Horaire Production
    │   ├── alerts/                      # 🚨 Alertes & Incidents (CŒUR)
    │   │   ├── consumers.py             # WebSocket consumer
    │   │   ├── routing.py               # WebSocket URLs
    │   │   ├── notifications.py         # Multi-canal
    │   │   └── tasks.py                 # Celery (escalade)
    │   ├── maintenance/                 # 🔧 Interventions Maintenance
    │   ├── oee/                         # 📈 Calcul TRS/OEE
    │   ├── costs/                       # 💰 Analyse des Coûts
    │   ├── planning/                    # 📅 Planning Production
    │   └── dashboard/                   # 🖥️ Dashboard & KPIs
    │
    ├── common/                          # Utilitaires partagés
    ├── requirements/ (base, dev, prod)
    ├── docker-compose.yml
    ├── Dockerfile
    └── manage.py

---

## 3. 🗄️ Modèle de Données

### 3.1 Modèles Principaux

#### accounts.CustomUser
- role: ADMIN | MANAGER | CONTROLLER | MAINTENANCE | OPERATOR
- shift: MORNING | AFTERNOON | NIGHT
- phone, machine_assignment, is_on_duty

#### machines.Machine
- name, code, type (ISBM | INJECTION | COMPRESSOR | CHILLER)
- status (RUNNING | STOPPED | MAINTENANCE | BREAKDOWN)
- nominal_bph, nominal_cph, cavities, product_format, location

#### alerts.AlertCategory
- name, code, severity_default, color, requires_maintenance

#### alerts.Alert (MODÈLE CENTRAL)
- machine (FK), category (FK), title, description
- severity: CRITICAL | MAJOR | MINOR | INFO
- status: OPEN → ACKNOWLEDGED → IN_PROGRESS → RESOLVED → CLOSED
- reported_by (FK), worker_name, shift
- acknowledged_at/by, resolved_at/by, closed_at
- downtime_min, bottles_lost, photo, priority_score

#### production.ProductionEntry
- date, hour (1-24), machine (FK), shift
- bottles_produced, caps_produced, reject_count, reject_pct
- downtime_min, downtime_reason
- pet_kg, energy_kwh, air_m3
- recorded_by (FK)
- unique_together: [date, hour, machine]

#### oee.OEERecord
- machine (FK), date, shift
- theoretical_production, actual_production, total_downtime_min
- availability_pct, performance_pct, quality_pct, trs_pct
- kwh_per_bottle, air_per_bottle, pet_per_bottle

#### costs.CostParameter
- name, value, unit, effective_from, is_active

#### costs.CostRecord
- machine (FK), date, shift
- pet_cost, energy_cost, air_cost, labor_cost
- total_cost, production_count, cost_per_bottle

#### planning.ProductionPlan
- date, machine (FK), product
- target_bph, actual_bph, variance, variance_pct

#### maintenance.Intervention
- alert (OneToOne), technician (FK)
- action_taken, parts_used, started_at, finished_at, duration_min

---

## 4. 🔌 API REST — Endpoints

### 4.1 Authentification (/api/v1/auth/)
- POST /login/ — Connexion JWT
- POST /refresh/ — Rafraîchir token
- POST /logout/ — Déconnexion
- GET /me/ — Profil utilisateur

### 4.2 Machines (/api/v1/machines/)
- GET / — Liste machines
- POST / — Créer machine
- GET /{id}/ — Détail + paramètres
- PATCH /{id}/status/ — Changer statut

### 4.3 🚨 Alertes (/api/v1/alerts/) — API CENTRALE
- GET / — Liste alertes (filtres: status, severity, machine, date)
- POST / — **Créer une alerte** (déclenche WebSocket + notifs)
- GET /{id}/ — Détail + commentaires + intervention
- PATCH /{id}/acknowledge/ — Acquitter (maintenance)
- PATCH /{id}/resolve/ — Résoudre (maintenance)
- PATCH /{id}/close/ — Clôturer (manager)
- PATCH /{id}/escalate/ — Escalader
- POST /{id}/comments/ — Commentaire
- GET /active/ — Alertes actives
- GET /pareto/ — Données Pareto
- GET /stats/ — MTTR, MTBF, taux par machine

### 4.4 Production (/api/v1/production/)
- GET / — Liste saisies
- POST / — Saisie horaire
- POST /bulk/ — Saisie en lot
- GET /daily-summary/ — Résumé journalier
- GET /shift-summary/ — Résumé par shift

### 4.5 TRS/OEE (/api/v1/oee/)
- GET / — Historique TRS
- GET /current/ — TRS en cours
- GET /{machine_id}/detail/ — Détail par machine
- GET /trends/ — Tendances

### 4.6 Coûts (/api/v1/costs/)
- GET /parameters/ — Paramètres actifs
- PUT /parameters/ — Modifier paramètres
- GET /daily/ — Coût du jour
- GET /monthly-report/ — Rapport mensuel

### 4.7 Planning (/api/v1/planning/)
- GET / — Planning
- POST / — Créer entrée
- GET /today/ — Planning du jour + écarts
- GET /variance-report/ — Rapport écarts

### 4.8 Dashboard (/api/v1/dashboard/)
- GET /kpis/ — KPIs agrégés
- GET /machines-status/ — Statut temps réel machines
- GET /shift-report/ — Rapport de shift
- GET /pareto/ — Pareto pannes

### 4.9 Maintenance (/api/v1/maintenance/)
- GET /interventions/ — Liste interventions
- POST /interventions/ — Créer intervention
- PATCH /interventions/{id}/finish/ — Terminer
- GET /my-tasks/ — Mes interventions
- GET /mttr/ — MTTR par machine

---

## 5. 🚨 Système d'Alertes Temps Réel

### 5.1 Cycle de vie d'une alerte

1. **DÉCLARATION** — Le contrôleur détecte un problème et crée l'alerte
2. **BROADCAST** — L'alerte s'affiche INSTANTANÉMENT sur tous les écrans (WebSocket)
3. **ACQUITTEMENT** — Le technicien maintenance acquitte ("Je m'en occupe")
4. **RÉSOLUTION** — Le technicien résout et documente l'intervention
5. **CLÔTURE** — Le manager clôture après vérification
6. **ANALYSE** — L'alerte alimente le Pareto + statistiques MTTR

### 5.2 WebSocket (Django Channels)

- Endpoint: ws/alerts/
- Consumer: AlertConsumer (AsyncJsonWebsocketConsumer)
- Group: "alerts" (tous les écrans connectés)
- Actions: alert.create, alert.acknowledge, alert.resolve
- Broadcast: alert.created, alert.acknowledged, alert.resolved

### 5.3 Écran d'atelier

Affichage permanent :
- Alerte active en grand (rouge/orange/jaune selon sévérité)
- Machine / Problème / Opérateur / Heure / Durée
- Statut machines (ISBM110, ISBM88, Bouchons)
- TRS global
- Historique alertes récentes

### 5.4 Notifications multi-canal

1. WebSocket (instantané — écrans + app mobile)
2. Email SMTP (vers maintenance en service)
3. SMS (optionnel — si alerte CRITIQUE)

### 5.5 Escalade automatique (Celery Beat)

- Toutes les 2 min : vérifier alertes OPEN non acquittées
- > 5 min sans acquittement → rappel manager
- > 15 min → escalade CRITIQUE

### 5.6 Permissions par rôle

| Action | Admin | Manager | Contrôleur | Maintenance | Opérateur |
|---|---|---|---|---|---|
| Créer alerte | ✅ | ✅ | ✅ | ✅ | ❌ |
| Acquitter | ✅ | ✅ | ❌ | ✅ | ❌ |
| Résoudre | ✅ | ✅ | ❌ | ✅ | ❌ |
| Clôturer | ✅ | ✅ | ❌ | ❌ | ❌ |
| Escalader | ✅ | ✅ | ✅ | ❌ | ❌ |
| Saisie production | ✅ | ✅ | ✅ | ❌ | ❌ |
| Modifier paramètres | ✅ | ✅ | ❌ | ❌ | ❌ |
| Voir dashboard | ✅ | ✅ | ✅ | ✅ | ✅ |
| Voir coûts | ✅ | ✅ | ❌ | ❌ | ❌ |
| Gérer utilisateurs | ✅ | ❌ | ❌ | ❌ | ❌ |

---

## 6. 📦 Dépendances

- Django 5.1, DRF 3.15, django-cors-headers
- djangorestframework-simplejwt (JWT)
- channels 4.1, channels-redis, daphne (WebSocket)
- psycopg2-binary (PostgreSQL)
- celery 5.4, redis, django-celery-beat
- Pillow (photos), openpyxl (Excel), reportlab (PDF)

---

## 7. 🗓️ Plan d'Implémentation — 6 Phases (12 semaines)

### Phase 1 — Fondations & Auth (Sem. 1-2)
- Projet Django + Docker (PostgreSQL + Redis)
- CustomUser + rôles + JWT
- CRUD machines + paramètres
- Seed data (ISBM110, ISBM88, Bouchons)

### Phase 2 — 🚨 Alertes Temps Réel (Sem. 3-4) — PRIORITÉ MAX
- Modèles Alert + AlertCategory + Intervention
- API CRUD alertes + actions (acknowledge, resolve, close, escalate)
- WebSocket Consumer (Django Channels)
- Écran d'atelier (HTML + JS WebSocket)
- Notifications email + SMS
- Escalade automatique (Celery Beat)

### Phase 3 — Production & Saisie (Sem. 5-6)
- ProductionEntry (saisie horaire)
- API saisie + bulk + résumés
- Import Excel historique

### Phase 4 — TRS, Coûts & Pareto (Sem. 7-8)
- OEERecord + calcul TRS automatique
- CostParameter + CostRecord
- Pareto pannes + MTTR/MTBF

### Phase 5 — Planning & Dashboard (Sem. 9-10)
- ProductionPlan + écarts
- Dashboard KPIs temps réel (WebSocket)
- Export rapports (Excel/PDF)

### Phase 6 — Déploiement & Tests (Sem. 11-12)
- Tests (unitaires, intégration, WebSocket, charge)
- Déploiement Docker production
- Monitoring (Sentry) + Backup
- Documentation API (Swagger) + Guide utilisateur

---

## 8. 🔐 Sécurité

- JWT (access 15 min + refresh 7 jours)
- RBAC (permissions par rôle)
- CORS whitelist
- Rate limiting (100 req/min)
- WebSocket auth (token JWT)
- Secrets en variables d'environnement
- HTTPS (Nginx + Let's Encrypt)
- Audit trail (middleware logging)
- Backup PostgreSQL quotidien (30 jours)

---

## 9. 📊 KPIs du Dashboard

| KPI | Source | Fréquence |
|---|---|---|
| TRS Global | OEE | Temps réel |
| TRS par machine | OEE | Temps réel |
| Production totale | Production | Temps réel |
| Alertes actives | Alerts | Temps réel |
| Coût / bouteille | Costs | Par shift |
| kWh / bouteille | OEE | Par shift |
| Air / bouteille | OEE | Par shift |
| MTTR moyen | Maintenance | Quotidien |
| Taux de rebut | Production | Par shift |
| Écart planning | Planning | Quotidien |
| Pareto pannes | Alerts | Quotidien |

---

## 10. ✅ Couverture Fonctionnelle

| Fonction Excel | Module Django | Phase |
|---|---|---|
| Saisie horaire | production | 3 |
| Paramètres machines & coûts | machines + costs | 1 + 4 |
| Calcul TRS | oee | 4 |
| Analyse des coûts | costs | 4 |
| Pareto des pannes | alerts | 4 |
| Planning de production | planning | 5 |
| Dashboard KPIs | dashboard | 5 |
| **Alertes machines temps réel** | **alerts + Channels** | **2** |
| **Interventions maintenance** | **maintenance** | **2** |
| **Écran d'atelier (WebSocket)** | **alerts/consumers.py** | **2** |
| **Notifications (email + SMS)** | **alerts/notifications.py** | **2** |

> Le système d'alertes temps réel est la fonctionnalité cœur (Phase 2), mais le backend couvre l'intégralité des fonctions identifiées dans le fichier Excel.
