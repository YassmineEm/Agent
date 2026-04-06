"""
Base SQLite - AlloCarburant
Domaine : Stations, Stocks, Approvisionnements, Cuves, Alertes, Ventes
Chemin  : C:/Users/dell/Agent-Conversationnel-Omnicanal/sql_agent/database/commandes.db
"""

import sqlite3, random
from datetime import datetime, timedelta

DB_PATH = r"C:\Users\dell\Agent-Conversationnel-Omnicanal\sql_agent\database\commandes.db"
DB_LOCAL = DB_PATH  # change this line if running locally
# Pour génération locale (CI)


con = sqlite3.connect(DB_PATH)
cur = con.cursor()

# ═══════════════════════════════════════════════════
# SCHÉMA
# ═══════════════════════════════════════════════════
cur.executescript("""
DROP TABLE IF EXISTS stations;
DROP TABLE IF EXISTS carburants;
DROP TABLE IF EXISTS cuves;
DROP TABLE IF EXISTS stocks;
DROP TABLE IF EXISTS approvisionnements;
DROP TABLE IF EXISTS ventes_journalieres;
DROP TABLE IF EXISTS alertes_stock;
DROP TABLE IF EXISTS maintenances;
DROP TABLE IF EXISTS fournisseurs;
DROP TABLE IF EXISTS prix_historique;

-- Stations service
CREATE TABLE stations (
    id              INTEGER PRIMARY KEY,
    nom             TEXT NOT NULL,
    code            TEXT UNIQUE,
    ville           TEXT,
    region          TEXT,
    adresse         TEXT,
    telephone       TEXT,
    responsable     TEXT,
    nb_pistolets    INTEGER,
    superficie_m2   INTEGER,
    statut          TEXT DEFAULT 'active',  -- active / maintenance / fermée
    date_ouverture  TEXT,
    latitude        REAL,
    longitude       REAL
);

-- Types de carburant
CREATE TABLE carburants (
    id          INTEGER PRIMARY KEY,
    code        TEXT UNIQUE,
    nom         TEXT,
    prix_achat  REAL,
    prix_vente  REAL,
    unite       TEXT DEFAULT 'litre'
);

-- Cuves par station (une station peut avoir plusieurs cuves par carburant)
CREATE TABLE cuves (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id      INTEGER,
    carburant_id    INTEGER,
    numero_cuve     TEXT,
    capacite_max_L  REAL,
    seuil_alerte_L  REAL,
    date_installation TEXT,
    statut          TEXT DEFAULT 'opérationnelle',
    FOREIGN KEY (station_id) REFERENCES stations(id),
    FOREIGN KEY (carburant_id) REFERENCES carburants(id)
);

-- Stock actuel par cuve
CREATE TABLE stocks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    cuve_id         INTEGER UNIQUE,
    station_id      INTEGER,
    carburant_id    INTEGER,
    volume_actuel_L REAL,
    derniere_maj    TEXT,
    FOREIGN KEY (cuve_id) REFERENCES cuves(id),
    FOREIGN KEY (station_id) REFERENCES stations(id),
    FOREIGN KEY (carburant_id) REFERENCES carburants(id)
);

-- Fournisseurs
CREATE TABLE fournisseurs (
    id      INTEGER PRIMARY KEY,
    nom     TEXT,
    contact TEXT,
    region  TEXT,
    delai_livraison_h INTEGER
);

-- Approvisionnements (livraisons de carburant aux stations)
CREATE TABLE approvisionnements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    numero          TEXT UNIQUE,
    station_id      INTEGER,
    carburant_id    INTEGER,
    fournisseur_id  INTEGER,
    volume_commande_L REAL,
    volume_livre_L  REAL,
    prix_unitaire   REAL,
    montant_total   REAL,
    statut          TEXT,  -- commandé / livré / partiel / annulé
    date_commande   TEXT,
    date_livraison_prevue TEXT,
    date_livraison_reelle TEXT,
    FOREIGN KEY (station_id) REFERENCES stations(id),
    FOREIGN KEY (carburant_id) REFERENCES carburants(id),
    FOREIGN KEY (fournisseur_id) REFERENCES fournisseurs(id)
);

-- Ventes journalières par station et carburant
CREATE TABLE ventes_journalieres (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id      INTEGER,
    carburant_id    INTEGER,
    date_vente      TEXT,
    volume_vendu_L  REAL,
    montant_MAD     REAL,
    nb_transactions INTEGER,
    FOREIGN KEY (station_id) REFERENCES stations(id),
    FOREIGN KEY (carburant_id) REFERENCES carburants(id)
);

-- Alertes stock (générées automatiquement quand stock < seuil)
CREATE TABLE alertes_stock (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id      INTEGER,
    cuve_id         INTEGER,
    carburant_id    INTEGER,
    type_alerte     TEXT,  -- critique / faible / normal
    volume_au_moment_L REAL,
    seuil_L         REAL,
    message         TEXT,
    statut          TEXT DEFAULT 'active',  -- active / résolue
    date_alerte     TEXT,
    date_resolution TEXT,
    FOREIGN KEY (station_id) REFERENCES stations(id),
    FOREIGN KEY (cuve_id) REFERENCES cuves(id)
);

-- Maintenances cuves / stations
CREATE TABLE maintenances (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id      INTEGER,
    cuve_id         INTEGER,
    type_maintenance TEXT,  -- nettoyage / inspection / réparation / calibration
    description     TEXT,
    statut          TEXT,   -- planifiée / en_cours / terminée
    date_planifiee  TEXT,
    date_debut      TEXT,
    date_fin        TEXT,
    cout_MAD        REAL,
    technicien      TEXT,
    FOREIGN KEY (station_id) REFERENCES stations(id),
    FOREIGN KEY (cuve_id) REFERENCES cuves(id)
);

-- Historique prix carburant
CREATE TABLE prix_historique (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    carburant_id    INTEGER,
    prix_achat      REAL,
    prix_vente      REAL,
    date_application TEXT,
    FOREIGN KEY (carburant_id) REFERENCES carburants(id)
);
""")

# ═══════════════════════════════════════════════════
# DONNÉES DE RÉFÉRENCE
# ═══════════════════════════════════════════════════

STATIONS_DATA = [
    (1,"Station Ain Sebaa",    "STA-001","Casablanca","Grand Casablanca","Bd Zerktouni, Ain Sebaa",      "0522-111-001","Khalid Mansouri",8,1200,"active","2015-03-10",33.6038,-7.5241),
    (2,"Station Hay Hassani",  "STA-002","Casablanca","Grand Casablanca","Route de Médiouna, Hay Hassani","0522-111-002","Samira Tazi",    6, 900,"active","2017-06-15",33.5522,-7.6631),
    (3,"Station Agdal",        "STA-003","Rabat",     "Rabat-Salé-Kénitra","Av. Fal Ould Oumeir, Agdal",   "0537-222-001","Omar Benali",   10,1500,"active","2012-01-20",33.9988,-6.8529),
    (4,"Station Salé Médina",  "STA-004","Salé",      "Rabat-Salé-Kénitra","Bd Hassan II, Salé",            "0537-222-002","Nadia Chraibi",  6, 800,"active","2018-09-05",34.0377,-6.8084),
    (5,"Station Guéliz",       "STA-005","Marrakech", "Marrakech-Safi",   "Av. Mohammed VI, Guéliz",       "0524-333-001","Rachid Ouali",   8,1100,"active","2014-04-12",31.6340,-8.0106),
    (6,"Station Route Fès",    "STA-006","Marrakech", "Marrakech-Safi",   "Route de Fès km 5",             "0524-333-002","Hassan Idrissi", 4, 600,"maintenance","2016-07-30",31.6920,-7.9810),
    (7,"Station Ville Nouvelle","STA-007","Fès",      "Fès-Meknès",       "Bd Allal El Fassi, Ville Nouvelle","0535-444-001","Fatima Amrani",6, 850,"active","2013-11-18",34.0346,-5.0010),
    (8,"Station Tanger Port",  "STA-008","Tanger",    "Tanger-Tétouan-Al Hoceima","Av. du Port, Tanger",  "0539-555-001","Youssef Zouine",10,1400,"active","2011-05-25",35.7595,-5.8340),
    (9,"Station Agadir Talborjt","STA-009","Agadir",  "Souss-Massa",      "Av. du Prince Héritier, Talborjt","0528-666-001","Aziz Berrada",8,1000,"active","2016-02-14",30.4278,-9.5981),
    (10,"Station Meknès Centre","STA-010","Meknès",   "Fès-Meknès",       "Av. Hassan II, Centre Ville",   "0535-777-001","Leila Hajji",    6, 750,"active","2019-03-08",33.8935,-5.5473),
    (11,"Station Oujda Est",   "STA-011","Oujda",     "Oriental",         "Route de Nador, Oujda",         "0536-888-001","Karim Filali",   4, 550,"active","2020-01-15",34.6867,-1.8990),
    (12,"Station Kénitra",     "STA-012","Kénitra",   "Rabat-Salé-Kénitra","Bd Mohammed V, Kénitra",       "0537-999-001","Sara Alaoui",    6, 700,"fermée","2010-08-20",34.2610,-6.5802),
]

CARBURANTS_DATA = [
    (1,"GO",   "Gasoil",              8.30, 9.50, "litre"),
    (2,"SP95", "Super Sans Plomb 95",12.80,13.90, "litre"),
    (3,"SP98", "Super Sans Plomb 98",13.50,14.80, "litre"),
    (4,"FD",   "Fuel Domestique",     9.10,10.20, "litre"),
    (5,"HFO",  "Fuel Industriel",     7.60, 8.40, "litre"),
    (6,"GOP",  "Gasoil Pêche",        7.00, 7.80, "litre"),
]

FOURNISSEURS_DATA = [
    (1,"AFRIQUIA SMDC",   "0522-400-000","National",     36),
    (2,"TOTAL MAROC",     "0522-500-000","National",     48),
    (3,"SHELL MAROC",     "0522-600-000","National",     48),
    (4,"PETROM",          "0522-700-000","Casablanca",   24),
    (5,"ZINE PETROLEUM",  "0522-800-000","Casablanca",   30),
]

cur.executemany("INSERT INTO stations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", STATIONS_DATA)
cur.executemany("INSERT INTO carburants VALUES (?,?,?,?,?,?)", CARBURANTS_DATA)
cur.executemany("INSERT INTO fournisseurs VALUES (?,?,?,?,?)", FOURNISSEURS_DATA)

# ═══════════════════════════════════════════════════
# CUVES (2-3 cuves par station par carburant principal)
# ═══════════════════════════════════════════════════
cuve_id = 0
cuve_map = {}  # (station_id, carburant_id) -> [cuve_ids]

# Chaque station active a GO + SP95 obligatoire, et selon taille d'autres carburants
carbs_par_station = {
    1:[1,2,3,4],2:[1,2,4],3:[1,2,3,4,5],4:[1,2],
    5:[1,2,3,4],6:[1,2],  7:[1,2,3],    8:[1,2,3,5],
    9:[1,2,3,4],10:[1,2,3],11:[1,2],    12:[1,2],
}

CAPACITES = [10000, 15000, 20000, 30000]
for s_id, carb_list in carbs_par_station.items():
    for c_id in carb_list:
        n_cuves = 2 if s_id in [4,6,11,12] else (3 if c_id==1 else 2)
        for n in range(1, n_cuves+1):
            cuve_id += 1
            cap = random.choice(CAPACITES)
            seuil = cap * 0.15
            statut_cuve = "opérationnelle"
            if s_id == 6:  statut_cuve = "en maintenance"
            if s_id == 12: statut_cuve = "hors service"
            cur.execute("INSERT INTO cuves VALUES (?,?,?,?,?,?,?,?)", (
                cuve_id, s_id, c_id,
                f"C{s_id:02d}-{c_id:02d}-{n:02d}",
                cap, seuil,
                f"20{random.randint(10,22):02d}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
                statut_cuve
            ))
            cuve_map.setdefault((s_id, c_id), []).append((cuve_id, cap, seuil))

# ═══════════════════════════════════════════════════
# STOCKS ACTUELS
# ═══════════════════════════════════════════════════
now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
alerte_id = 0

for (s_id, c_id), cuves in cuve_map.items():
    for (cv_id, cap, seuil) in cuves:
        # stations en maintenance/fermée ont stocks bas ou nuls
        if s_id == 12:
            vol = 0.0
        elif s_id == 6:
            vol = round(random.uniform(0, seuil * 0.5), 0)
        else:
            # 80% du temps stock normal, 15% faible, 5% critique
            r = random.random()
            if r < 0.05:
                vol = round(random.uniform(0, seuil * 0.5), 0)       # critique
            elif r < 0.20:
                vol = round(random.uniform(seuil * 0.5, seuil), 0)   # faible
            else:
                vol = round(random.uniform(seuil, cap * 0.9), 0)     # normal

        cur.execute("INSERT INTO stocks VALUES (NULL,?,?,?,?,?)",
                    (cv_id, s_id, c_id, vol, now_str))

        # Générer alerte si stock bas
        if vol <= seuil:
            type_a = "critique" if vol <= seuil * 0.5 else "faible"
            date_a = (datetime.now() - timedelta(hours=random.randint(1,48))).strftime("%Y-%m-%d %H:%M")
            statut_a = "active" if vol < seuil * 0.3 else random.choice(["active","résolue"])
            date_r = None
            if statut_a == "résolue":
                date_r = (datetime.now() - timedelta(hours=random.randint(0,24))).strftime("%Y-%m-%d %H:%M")
            cur.execute("INSERT INTO alertes_stock VALUES (NULL,?,?,?,?,?,?,?,?,?,?)", (
                s_id, cv_id, c_id, type_a, vol, seuil,
                f"Stock {type_a} : {vol:.0f}L / seuil {seuil:.0f}L",
                statut_a, date_a, date_r
            ))

# ═══════════════════════════════════════════════════
# APPROVISIONNEMENTS (300 livraisons sur 12 mois)
# ═══════════════════════════════════════════════════
def rand_date(days_back=365):
    return datetime.now() - timedelta(
        days=random.randint(0, days_back),
        hours=random.randint(0, 23)
    )

statuts_appro = ["livré","livré","livré","livré","commandé","partiel","annulé"]

for i in range(1, 301):
    s_id = random.randint(1, 12)
    carbs = list(carbs_par_station.get(s_id, [1,2]))
    c_id = random.choice(carbs)
    carb = CARBURANTS_DATA[c_id-1]
    fourn = random.choice(FOURNISSEURS_DATA)
    vol_cmd = random.choice([5000, 10000, 15000, 20000, 30000])
    statut = random.choice(statuts_appro)
    vol_livre = vol_cmd if statut=="livré" else (
        round(vol_cmd * random.uniform(0.5,0.9),0) if statut=="partiel" else 0)
    prix_u = carb[3] * random.uniform(0.97, 1.02)
    montant = round(vol_livre * prix_u, 2)
    date_cmd = rand_date(365)
    delai = timedelta(hours=fourn[4])
    date_prev = date_cmd + delai
    date_reel = (date_prev + timedelta(hours=random.randint(-4,8))) if statut in ("livré","partiel") else None
    cur.execute("""INSERT INTO approvisionnements
        (numero,station_id,carburant_id,fournisseur_id,volume_commande_L,volume_livre_L,
         prix_unitaire,montant_total,statut,date_commande,date_livraison_prevue,date_livraison_reelle)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", (
        f"APPRO-{i:04d}", s_id, c_id, fourn[0],
        vol_cmd, vol_livre, round(prix_u,2), montant, statut,
        date_cmd.strftime("%Y-%m-%d %H:%M"),
        date_prev.strftime("%Y-%m-%d %H:%M"),
        date_reel.strftime("%Y-%m-%d %H:%M") if date_reel else None
    ))

# ═══════════════════════════════════════════════════
# VENTES JOURNALIÈRES (90 jours × 12 stations × carburants)
# ═══════════════════════════════════════════════════
VENTE_BASE = {1:3000, 2:1500, 3:800, 4:500, 5:2000, 6:400}

for day_offset in range(90):
    date_v = (datetime.now() - timedelta(days=day_offset)).strftime("%Y-%m-%d")
    for s_id, carb_list in carbs_par_station.items():
        if s_id == 12: continue  # fermée
        for c_id in carb_list:
            base = VENTE_BASE.get(c_id, 1000)
            # stations grandes vendent plus
            mult = 1.5 if s_id in [1,3,8] else (0.6 if s_id in [11,4] else 1.0)
            # week-end -20%
            dow = (datetime.now() - timedelta(days=day_offset)).weekday()
            if dow >= 5: mult *= 0.8
            vol = round(base * mult * random.uniform(0.85, 1.15), 0)
            prix = CARBURANTS_DATA[c_id-1][4]
            montant = round(vol * prix, 2)
            nb_tx = random.randint(30, 200)
            cur.execute("INSERT INTO ventes_journalieres VALUES (NULL,?,?,?,?,?,?)",
                        (s_id, c_id, date_v, vol, montant, nb_tx))

# ═══════════════════════════════════════════════════
# MAINTENANCES
# ═══════════════════════════════════════════════════
types_maint = ["nettoyage","inspection","réparation","calibration"]
techniciens = ["Ali Benchekroun","Mustapha Lahlou","Hamid Ouaziz","Yassine Bakkali"]

for i in range(60):
    s_id = random.randint(1, 12)
    cuves_s = [cv for (sid,cid),cvs in cuve_map.items() if sid==s_id for cv in cvs]
    if not cuves_s: continue
    cv_id = random.choice(cuves_s)[0]
    type_m = random.choice(types_maint)
    statut_m = random.choice(["planifiée","en_cours","terminée","terminée","terminée"])
    date_plan = rand_date(180)
    date_deb = date_plan + timedelta(hours=1) if statut_m != "planifiée" else None
    date_fin = (date_deb + timedelta(hours=random.randint(2,24))) if statut_m == "terminée" else None
    cout = round(random.uniform(500, 8000), 2)
    cur.execute("""INSERT INTO maintenances
        (station_id,cuve_id,type_maintenance,description,statut,
         date_planifiee,date_debut,date_fin,cout_MAD,technicien) VALUES (?,?,?,?,?,?,?,?,?,?)""", (
        s_id, cv_id, type_m,
        f"{type_m.capitalize()} programmé{'e' if type_m[-1]=='n' else ''} — cuve {cv_id}",
        statut_m,
        date_plan.strftime("%Y-%m-%d %H:%M"),
        date_deb.strftime("%Y-%m-%d %H:%M") if date_deb else None,
        date_fin.strftime("%Y-%m-%d %H:%M") if date_fin else None,
        cout, random.choice(techniciens)
    ))

# ═══════════════════════════════════════════════════
# HISTORIQUE PRIX (12 mois)
# ═══════════════════════════════════════════════════
for c_id in range(1,7):
    for m in range(12, 0, -1):
        date_app = (datetime.now() - timedelta(days=m*30)).strftime("%Y-%m-%d")
        base_achat = CARBURANTS_DATA[c_id-1][3]
        base_vente = CARBURANTS_DATA[c_id-1][4]
        variation = random.uniform(-0.3, 0.3)
        cur.execute("INSERT INTO prix_historique VALUES (NULL,?,?,?,?)",
                    (c_id, round(base_achat+variation,2), round(base_vente+variation*1.2,2), date_app))

con.commit()

# ═══════════════════════════════════════════════════
# RÉSUMÉ
# ═══════════════════════════════════════════════════
print("=" * 55)
print("  BASE SQLITE ALLOCARBURANT — STATIONS & STOCKS")
print("=" * 55)
tables = ["stations","carburants","cuves","stocks","fournisseurs",
          "approvisionnements","ventes_journalieres","alertes_stock",
          "maintenances","prix_historique"]
total = 0
for t in tables:
    n = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    total += n
    print(f"  {t:<25} {n:>5} enregistrements")
print(f"  {'─'*40}")
print(f"  {'TOTAL':<25} {total:>5} enregistrements")
print("=" * 55)

# Alertes actives
al = cur.execute("SELECT COUNT(*) FROM alertes_stock WHERE statut='active'").fetchone()[0]
print(f"  Alertes stock actives   : {al}")

# CA ventes 30 derniers jours
ca = cur.execute("""
    SELECT SUM(montant_MAD) FROM ventes_journalieres
    WHERE date_vente >= date('now','-30 days')
""").fetchone()[0]
print(f"  CA ventes (30 jours)    : {ca:,.0f} MAD")

con.close()
print(f"\n  Fichier : {DB_PATH}")
print("  → Base prête. Utilisez la connection string dans votre dashboard.")