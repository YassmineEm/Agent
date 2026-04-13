#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
create_db.py - Création de la base de données SQLite AlloCarburant
Version corrigée - Gère correctement les colonnes ID auto-incrémentées
"""

import sqlite3
import os
import re

# =============================================
# CONFIGURATION
# =============================================

DB_PATH = r"C:\Users\dell\Agent-Conversationnel-Omnicanal\carburant.db"

# =============================================
# CRÉATION DE LA BASE
# =============================================

def create_database():
    """Crée la base de données SQLite avec les données des fichiers SQL"""
    
    print("=" * 60)
    print("  CRÉATION DE LA BASE DE DONNÉES ALLOCARBURANT")
    print("=" * 60)
    
    # Supprimer l'ancienne base si elle existe
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"🗑️ Ancienne base supprimée: {DB_PATH}")
    
    # Connexion à SQLite
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print(f"\n📁 Création de: {DB_PATH}\n")
    
    # =========================================
    # 1. CRÉATION DES TABLES
    # =========================================
    print("--- Étape 1: Création des tables ---")
    
    # Table data_stations (sans id auto-incrémenté dans l'insert)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS data_stations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code_station TEXT,
        nom_station_fr TEXT,
        nom_station_ar TEXT,
        latitude REAL,
        longitude REAL,
        ville TEXT,
        address_fr TEXT,
        address_ar TEXT
    )
    """)
    print("  ✅ Table data_stations créée")
    
    # Table station_produit_prix_rel
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS station_produit_prix_rel (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code_station TEXT NOT NULL,
        code_produit TEXT NOT NULL,
        prix REAL,
        unite TEXT DEFAULT 'L',
        date_du TEXT,
        date_au TEXT
    )
    """)
    print("  ✅ Table station_produit_prix_rel créée")
    
    # Table data_pdvs_lubrifiant
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS data_pdvs_lubrifiant (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom_fr TEXT,
        nom_ar TEXT,
        telephone TEXT,
        latitude REAL,
        longitude REAL
    )
    """)
    print("  ✅ Table data_pdvs_lubrifiant créée")
    
    # Création des index
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stations_code ON data_stations(code_station)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_prix_station ON station_produit_prix_rel(code_station)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_prix_produit ON station_produit_prix_rel(code_produit)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pdvs_nom ON data_pdvs_lubrifiant(nom_fr)")
    print("  ✅ Index créés")
    
    conn.commit()
    
    # =========================================
    # 2. INSERTION DES DONNÉES - DATA STATIONS
    # =========================================
    print("\n--- Étape 2: Insertion des données ---")
    
    # Données des stations (40 stations)
    stations_data = [
        ('957', 'AL AMAL', 'محطة الأمل', 34.219719, -6.589476, 'Kénitra', 'Avenue Mohammed V KM 6, Kénitra', 'شارع Mohammed V كم 3، Kénitra'),
        ('702', 'AL BARAKA', 'محطة البركة', 29.67791, -9.729433, 'Tiznit', 'CT 7873 PK 270+678 Douar Bni Said, Province Casablanca', 'بوليفارد Yacoub El Mansour، حي Hay Hassani، Tiznit'),
        ('1544', 'AL FIRDAOUS', 'محطة الفردوس', 33.535632, -5.159617, 'Ifrane', 'Zone Industrielle Sapino, Lot 40, Ifrane', 'طث 2025 نك 6+237 دوار Ait Hammou، إقليم Fès-Meknès'),
        ('1554', 'AL MASSIRA', 'محطة المسيرة', 31.62282, -8.030244, 'Marrakech', 'Angle Rue Al Quds et Rue Oqba Ibn Nafii, Marrakech', 'بوليفارد Massira، حي Hay Nahda، Marrakech'),
        ('2832', 'AL MOUKHTAR', 'محطة المختار', 31.51743, -9.766282, 'Essaouira', 'Boulevard Zerktouni, Quartier Hay Nahda, Essaouira', 'طريق Tanger كم 29، مخرج Essaouira'),
        ('9350', 'AL WAFA', 'محطة الوفاء', 34.63991, -1.926897, 'Oujda', 'Zone Industrielle Ouled Saleh, Lot 102, Oujda', 'طو رقم 16 نك 176+812 جماعة Ait Ourir، إقليم Casablanca'),
        ('3253', 'ATLAS', 'محطة الأطلس', 33.572506, -5.122663, 'Ifrane', 'RN N° 14 PK 193+612 Commune Oulad Ayad, Province de Marrakech-Safi', 'شارع Ibn Tachfine كم 9، Ifrane'),
        ('899', 'BAB DOUKKALA', 'محطة باب دكالة', 30.390134, -9.605288, 'Agadir', 'CT 5730 PK 245+647 Douar Ait Hammou, Province Béni Mellal-Khénifra', 'زاوية شارع Liberté وشارع Imam Malik، Agadir'),
        ('2818', 'BOULEVARD ZERKTOUNI', 'محطة شارع الزرقطوني', 29.721062, -9.728477, 'Tiznit', 'Route de Essaouira KM 4, Sortie Tiznit', 'طث 4410 نك 31+683 دوار Oulad Brahim، إقليم Oriental'),
        ('279', 'CHAMS', 'محطة الشمس', 32.352921, -6.345107, 'Béni Mellal', 'RN N° 8 PK 224+815 Commune Oulad Ayad, Province de Marrakech-Safi', 'طريق Meknès كم 29، مخرج Béni Mellal'),
        ('5881', 'DAR SALAM', 'محطة دار السلام', 33.276861, -7.586097, 'Berrechid', 'Zone Industrielle Lissasfa, Lot 47, Berrechid', 'طو رقم 6 نك 45+438 جماعة Ouled Moussa، إقليم Rabat-Salé'),
        ('2300', 'EL FATH', 'محطة الفتح', 30.873018, -6.899653, 'Ouarzazate', 'Route de Agadir KM 22, Sortie Ouarzazate', 'طريق Marrakech كم 18، مخرج Ouarzazate'),
        ('153', 'EL WAHDA', 'محطة الوحدة', 31.493554, -9.733615, 'Essaouira', 'RP 8849 PK 194+836 Centre Sidi Bennour', 'المنطقة الصناعية Sapino، القطعة 26، Essaouira'),
        ('2086', 'HASSAN II', 'محطة الحسن الثاني', 32.721528, -4.747889, 'Midelt', 'RP 2081 PK 67+358 Centre Beni Yakhlef', 'شارع Abdelkrim Khattabi كم 22، Midelt'),
        ('1473', 'HAY MOHAMMADI', 'محطة حي المحمدي', 30.431413, -9.60597, 'Agadir', 'Angle Rue Al Quds et Rue Oqba Ibn Nafii, Agadir', 'بوليفارد Ghandi، حي Hay Salam، Agadir'),
        ('6665', 'IBN SINA', 'محطة ابن سينا', 33.707934, -7.346823, 'Mohammedia', 'Zone Industrielle Bouskoura, Lot 13, Mohammedia', 'المنطقة الصناعية Ouled Saleh، القطعة 131، Mohammedia'),
        ('3115', 'JARDINS', 'محطة الجنان', 33.268314, -7.564518, 'Berrechid', 'Avenue Ibn Tachfine KM 30, Berrechid', 'طو 1686 نك 289+700 مركز Skhirat'),
        ('1293', 'KASBAH', 'محطة القصبة', 34.688782, -1.86107, 'Oujda', 'Avenue Abdelkrim Khattabi KM 11, Oujda', 'طو رقم 17 نك 74+477 جماعة Ouled Moussa، إقليم Marrakech-Safi'),
        ('185', 'LAYMOUNE', 'محطة الليمون', 32.967277, -7.631582, 'Settat', 'CT 1237 PK 35+537 Douar Oulad Brahim, Province Oriental', 'المنطقة الصناعية Sapino، القطعة 174، Settat'),
        ('333', 'MAARIF', 'محطة المعاريف', 33.276206, -8.457786, 'El Jadida', 'RP 2205 PK 279+418 Centre Ouled Moussa', 'طث 9350 نك 97+287 دوار Oulad Ziane، إقليم Fès-Meknès'),
        ('4313', 'NAKHIL', 'محطة النخيل', 31.648742, -7.994281, 'Marrakech', 'Route de Casablanca KM 23, Sortie Marrakech', 'شارع Bir Anzarane كم 17، Marrakech'),
        ('6009', 'OASIS', 'محطة الواحة', 34.684839, -1.872033, 'Oujda', 'CT 8322 PK 107+438 Douar Oulad Ziane, Province Béni Mellal-Khénifra', 'زاوية شارع Oqba Ibn Nafii وشارع Ibn Rochd، Oujda'),
        ('8443', 'PLACE JAMAA', 'محطة ساحة الجامع', 34.231008, -4.033029, 'Taza', 'Route de Rabat KM 19, Sortie Taza', 'بوليفارد Yacoub El Mansour، حي Hay Nahda، Taza'),
        ('7429', 'RAHMA', 'محطة الرحمة', 33.541191, -7.562631, 'Casablanca', 'Boulevard Zerktouni, Quartier Hay Nahda, Casablanca', 'طريق Agadir كم 15، مخرج Casablanca'),
        ('9947', 'RIAD', 'محطة الرياض', 30.469243, -9.633729, 'Agadir', 'Route de Oujda KM 17, Sortie Agadir', 'زاوية شارع Al Quds وشارع Oqba Ibn Nafii، Agadir'),
        ('1583', 'SALAM', 'محطة السلام', 32.338594, -6.302088, 'Béni Mellal', 'Avenue Moulay Ismail KM 4, Béni Mellal', 'شارع Allal Ben Abdellah كم 12، Béni Mellal'),
        ('7430', 'TARIK', 'محطة طارق', 35.133858, -2.954673, 'Nador', 'Zone Industrielle Lissasfa, Lot 137, Nador', 'طث 4890 نك 118+258 دوار Oulad Brahim، إقليم Béni Mellal-Khénifra'),
        ('4537', 'YASMINE', 'محطة الياسمين', 30.426953, -9.581128, 'Agadir', 'Boulevard Ghandi, Quartier Hay Salam, Agadir', 'طث 8607 نك 48+475 دوار Oulad Ziane، إقليم Oriental'),
        ('8580', 'ZAHRA', 'محطة الزهراء', 32.955772, -7.580771, 'Settat', 'Zone Industrielle Ouled Saleh, Lot 164, Settat', 'طريق Marrakech كم 9، مخرج Settat'),
        ('3911', 'ZITOUN', 'محطة الزيتون', 33.192236, -8.506898, 'El Jadida', 'RN N° 1 PK 190+728 Commune Ouled Moussa, Province de Oriental', 'طو 7591 نك 299+818 مركز Skhirat'),
        ('910', 'AIN SEBAA', 'محطة عين السبع', 30.904962, -6.87557, 'Ouarzazate', 'Route de Meknès KM 28, Sortie Ouarzazate', 'طريق Agadir كم 2، مخرج Ouarzazate'),
        ('6330', 'ANFA', 'محطة أنفا', 30.440813, -8.867191, 'Taroudant', 'Boulevard Massira, Quartier Hay Hassani, Taroudant', 'شارع Allal Ben Abdellah كم 7، Taroudant'),
        ('2799', 'BOURGOGNE', 'محطة بورغون', 29.02866, -10.033012, 'Guelmim', 'Route de Marrakech KM 28, Sortie Guelmim', 'شارع Mohammed V كم 22، Guelmim'),
        ('4681', 'CIL', 'محطة سيل', 31.65671, -7.961928, 'Marrakech', 'Angle Rue Moulay Youssef et Rue Oqba Ibn Nafii, Marrakech', 'طو رقم 18 نك 105+455 جماعة Tameslouht، إقليم Marrakech-Safi'),
        ('1365', 'DERB SULTAN', 'محطة درب السلطان', 34.252099, -6.557303, 'Kénitra', 'CT 4673 PK 63+229 Douar Oulad Ziane, Province Marrakech-Safi', 'شارع Bir Anzarane كم 10، Kénitra'),
        ('2374', 'ENNASR', 'محطة النصر', 33.040305, -7.652724, 'Settat', 'CT 5844 PK 141+243 Douar Oulad Brahim, Province Rabat-Salé', 'طو رقم 17 نك 202+479 جماعة Ain Atiq، إقليم Casablanca'),
        ('2860', 'FADL', 'محطة الفضل', 33.860471, -6.086341, 'Khémisset', 'Zone Industrielle Ahl Loghlam, Lot 159, Khémisset', 'بوليفارد Zerktouni، حي Hay Salam، Khémisset'),
        ('2858', 'GHANDI', 'محطة غاندي', 33.604393, -7.625023, 'Casablanca', 'Boulevard Ghandi, Quartier Hay Hassani, Casablanca', 'طو 8284 نك 197+714 مركز Ouled Moussa'),
        ('8900', 'HILAL', 'محطة الهلال', 34.235242, -3.976591, 'Taza', 'Avenue Allal Ben Abdellah KM 12, Taza', 'طث 9698 نك 114+311 دوار Ait Lahcen، إقليم Rabat-Salé'),
        ('6856', 'INBIAAT', 'محطة الانبعاث', 35.603941, -5.343682, 'Tétouan', 'Boulevard Zerktouni, Quartier Hay Salam, Tétouan', 'طث 2653 نك 79+858 دوار Ait Lahcen، إقليم Rabat-Salé')
    ]
    
    cursor.executemany("""
        INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, stations_data)
    conn.commit()
    print(f"  ✅ data_stations: {len(stations_data)} enregistrements insérés")
    
    # =========================================
    # 3. INSERTION DES DONNÉES - PRIX
    # =========================================
    
    # Extraire les prix depuis le fichier SQL
    prix_file = "02_station_produit_prix_rel.sql"
    prix_file_path = os.path.join(os.path.dirname(DB_PATH), prix_file)
    
    if not os.path.exists(prix_file_path):
        prix_file_path = prix_file
    
    prix_data = []
    
    if os.path.exists(prix_file_path):
        with open(prix_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Pattern pour extraire les INSERT
        pattern = r"VALUES\s*\(\s*'([^']+)'\s*,\s*(\d+)\s*,\s*([\d.]+)\s*,\s*'([^']+)'\s*,\s*'([^']*)'\s*,\s*([^)]+)\)"
        matches = re.findall(pattern, content)
        
        for match in matches:
            code_station = match[0]
            code_produit = match[1]
            prix = float(match[2])
            unite = match[3]
            date_du = match[4] if match[4] != 'NULL' else None
            date_au = match[5].strip().replace("'", "").replace(" ", "")
            if date_au == 'NULL' or date_au == '':
                date_au = None
            
            prix_data.append((code_station, code_produit, prix, unite, date_du, date_au))
        
        cursor.executemany("""
            INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
            VALUES (?, ?, ?, ?, ?, ?)
        """, prix_data)
        conn.commit()
        print(f"  ✅ station_produit_prix_rel: {len(prix_data)} enregistrements insérés")
    else:
        print(f"  ⚠️ Fichier {prix_file} non trouvé")
    
    # =========================================
    # 4. INSERTION DES DONNÉES - POINTS DE VENTE
    # =========================================
    
    pdvs_file = "03_data_pdvs_lubrifiant.sql"
    pdvs_file_path = os.path.join(os.path.dirname(DB_PATH), pdvs_file)
    
    if not os.path.exists(pdvs_file_path):
        pdvs_file_path = pdvs_file
    
    pdvs_data = []
    
    if os.path.exists(pdvs_file_path):
        with open(pdvs_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Pattern pour extraire les INSERT
        pattern = r"VALUES\s*\(\s*'([^']+)'\s*,\s*([^,]+)\s*,\s*'([^']*)'\s*,\s*([\d.-]+)\s*,\s*([\d.-]+)\)"
        matches = re.findall(pattern, content)
        
        for match in matches:
            nom_fr = match[0]
            nom_ar = match[1] if match[1] != 'NULL' else None
            telephone = match[2] if match[2] else None
            latitude = float(match[3]) if match[3] else None
            longitude = float(match[4]) if match[4] else None
            
            pdvs_data.append((nom_fr, nom_ar, telephone, latitude, longitude))
        
        cursor.executemany("""
            INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
            VALUES (?, ?, ?, ?, ?)
        """, pdvs_data)
        conn.commit()
        print(f"  ✅ data_pdvs_lubrifiant: {len(pdvs_data)} enregistrements insérés")
    else:
        print(f"  ⚠️ Fichier {pdvs_file} non trouvé")
    
    # =========================================
    # 5. VÉRIFICATION FINALE
    # =========================================
    print("\n--- Étape 3: Vérification ---")
    
    tables = ["data_stations", "station_produit_prix_rel", "data_pdvs_lubrifiant"]
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  📊 {table}: {count} enregistrements")
    
    # Afficher quelques exemples
    print("\n--- Exemples de données ---")
    
    cursor.execute("SELECT code_station, nom_station_fr, ville FROM data_stations LIMIT 5")
    stations = cursor.fetchall()
    print("\n📌 Stations (5 premiers):")
    for s in stations:
        print(f"    - {s[0]}: {s[1]} ({s[2]})")
    
    cursor.execute("SELECT code_station, code_produit, prix FROM station_produit_prix_rel LIMIT 5")
    prix = cursor.fetchall()
    if prix:
        print("\n💰 Prix (5 premiers):")
        for p in prix:
            print(f"    - Station {p[0]}, produit {p[1]}: {p[2]} MAD/L")
    
    cursor.execute("SELECT nom_fr, telephone FROM data_pdvs_lubrifiant LIMIT 5")
    pdvs = cursor.fetchall()
    if pdvs:
        print("\n🏪 Points de vente (5 premiers):")
        for p in pdvs:
            print(f"    - {p[0]}: {p[1]}")
    
    # Vérifier les jointures
    print("\n--- Vérification des jointures ---")
    
    cursor.execute("""
        SELECT s.nom_station_fr, COUNT(p.id) as nb_prix
        FROM data_stations s
        LEFT JOIN station_produit_prix_rel p ON s.code_station = p.code_station
        GROUP BY s.nom_station_fr
        ORDER BY s.nom_station_fr
        LIMIT 10
    """)
    
    jointures = cursor.fetchall()
    if jointures:
        print("\n🔗 Stations avec leurs prix:")
        for j in jointures:
            print(f"    - {j[0]}: {j[1]} prix")
    
    # Fermer la connexion
    conn.close()
    
    print("\n" + "=" * 60)
    print(f"  ✅ BASE DE DONNÉES CRÉÉE AVEC SUCCÈS !")
    print(f"  📁 Fichier: {DB_PATH}")
    print("=" * 60)
    
    return DB_PATH


# =============================================
# EXÉCUTION
# =============================================

if __name__ == "__main__":
    create_database()