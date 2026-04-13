-- =============================================
-- CRÉATION DE LA TABLE data_stations
-- =============================================

CREATE TABLE data_stations (
    id SERIAL PRIMARY KEY,
    code_station VARCHAR(50),
    nom_station_fr VARCHAR(255),
    nom_station_ar VARCHAR(255),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    ville VARCHAR(100),
    address_fr TEXT,
    address_ar TEXT
);

-- =============================================
-- INSERTION DES DONNÉES (DUMMY DATA)
-- =============================================

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('957', 'AL AMAL', 'محطة الأمل', 34.219719, -6.589476, 'Kénitra', 'Avenue Mohammed V KM 6, Kénitra', 'شارع Mohammed V كم 3، Kénitra');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('702', 'AL BARAKA', 'محطة البركة', 29.67791, -9.729433, 'Tiznit', 'CT 7873 PK 270+678 Douar Bni Said, Province Casablanca', 'بوليفارد Yacoub El Mansour، حي Hay Hassani، Tiznit');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('1544', 'AL FIRDAOUS', 'محطة الفردوس', 33.535632, -5.159617, 'Ifrane', 'Zone Industrielle Sapino, Lot 40, Ifrane', 'طث 2025 نك 6+237 دوار Ait Hammou، إقليم Fès-Meknès');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('1554', 'AL MASSIRA', 'محطة المسيرة', 31.62282, -8.030244, 'Marrakech', 'Angle Rue Al Quds et Rue Oqba Ibn Nafii, Marrakech', 'بوليفارد Massira، حي Hay Nahda، Marrakech');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('2832', 'AL MOUKHTAR', 'محطة المختار', 31.51743, -9.766282, 'Essaouira', 'Boulevard Zerktouni, Quartier Hay Nahda, Essaouira', 'طريق Tanger كم 29، مخرج Essaouira');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('9350', 'AL WAFA', 'محطة الوفاء', 34.63991, -1.926897, 'Oujda', 'Zone Industrielle Ouled Saleh, Lot 102, Oujda', 'طو رقم 16 نك 176+812 جماعة Ait Ourir، إقليم Casablanca');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('3253', 'ATLAS', 'محطة الأطلس', 33.572506, -5.122663, 'Ifrane', 'RN N° 14 PK 193+612 Commune Oulad Ayad, Province de Marrakech-Safi', 'شارع Ibn Tachfine كم 9، Ifrane');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('899', 'BAB DOUKKALA', 'محطة باب دكالة', 30.390134, -9.605288, 'Agadir', 'CT 5730 PK 245+647 Douar Ait Hammou, Province Béni Mellal-Khénifra', 'زاوية شارع Liberté وشارع Imam Malik، Agadir');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('2818', 'BOULEVARD ZERKTOUNI', 'محطة شارع الزرقطوني', 29.721062, -9.728477, 'Tiznit', 'Route de Essaouira KM 4, Sortie Tiznit', 'طث 4410 نك 31+683 دوار Oulad Brahim، إقليم Oriental');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('279', 'CHAMS', 'محطة الشمس', 32.352921, -6.345107, 'Béni Mellal', 'RN N° 8 PK 224+815 Commune Oulad Ayad, Province de Marrakech-Safi', 'طريق Meknès كم 29، مخرج Béni Mellal');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('5881', 'DAR SALAM', 'محطة دار السلام', 33.276861, -7.586097, 'Berrechid', 'Zone Industrielle Lissasfa, Lot 47, Berrechid', 'طو رقم 6 نك 45+438 جماعة Ouled Moussa، إقليم Rabat-Salé');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('2300', 'EL FATH', 'محطة الفتح', 30.873018, -6.899653, 'Ouarzazate', 'Route de Agadir KM 22, Sortie Ouarzazate', 'طريق Marrakech كم 18، مخرج Ouarzazate');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('153', 'EL WAHDA', 'محطة الوحدة', 31.493554, -9.733615, 'Essaouira', 'RP 8849 PK 194+836 Centre Sidi Bennour', 'المنطقة الصناعية Sapino، القطعة 26، Essaouira');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('2086', 'HASSAN II', 'محطة الحسن الثاني', 32.721528, -4.747889, 'Midelt', 'RP 2081 PK 67+358 Centre Beni Yakhlef', 'شارع Abdelkrim Khattabi كم 22، Midelt');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('1473', 'HAY MOHAMMADI', 'محطة حي المحمدي', 30.431413, -9.60597, 'Agadir', 'Angle Rue Al Quds et Rue Oqba Ibn Nafii, Agadir', 'بوليفارد Ghandi، حي Hay Salam، Agadir');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('6665', 'IBN SINA', 'محطة ابن سينا', 33.707934, -7.346823, 'Mohammedia', 'Zone Industrielle Bouskoura, Lot 13, Mohammedia', 'المنطقة الصناعية Ouled Saleh، القطعة 131، Mohammedia');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('3115', 'JARDINS', 'محطة الجنان', 33.268314, -7.564518, 'Berrechid', 'Avenue Ibn Tachfine KM 30, Berrechid', 'طو 1686 نك 289+700 مركز Skhirat');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('1293', 'KASBAH', 'محطة القصبة', 34.688782, -1.86107, 'Oujda', 'Avenue Abdelkrim Khattabi KM 11, Oujda', 'طو رقم 17 نك 74+477 جماعة Ouled Moussa، إقليم Marrakech-Safi');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('185', 'LAYMOUNE', 'محطة الليمون', 32.967277, -7.631582, 'Settat', 'CT 1237 PK 35+537 Douar Oulad Brahim, Province Oriental', 'المنطقة الصناعية Sapino، القطعة 174، Settat');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('333', 'MAARIF', 'محطة المعاريف', 33.276206, -8.457786, 'El Jadida', 'RP 2205 PK 279+418 Centre Ouled Moussa', 'طث 9350 نك 97+287 دوار Oulad Ziane، إقليم Fès-Meknès');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('4313', 'NAKHIL', 'محطة النخيل', 31.648742, -7.994281, 'Marrakech', 'Route de Casablanca KM 23, Sortie Marrakech', 'شارع Bir Anzarane كم 17، Marrakech');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('6009', 'OASIS', 'محطة الواحة', 34.684839, -1.872033, 'Oujda', 'CT 8322 PK 107+438 Douar Oulad Ziane, Province Béni Mellal-Khénifra', 'زاوية شارع Oqba Ibn Nafii وشارع Ibn Rochd، Oujda');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('8443', 'PLACE JAMAA', 'محطة ساحة الجامع', 34.231008, -4.033029, 'Taza', 'Route de Rabat KM 19, Sortie Taza', 'بوليفارد Yacoub El Mansour، حي Hay Nahda، Taza');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('7429', 'RAHMA', 'محطة الرحمة', 33.541191, -7.562631, 'Casablanca', 'Boulevard Zerktouni, Quartier Hay Nahda, Casablanca', 'طريق Agadir كم 15، مخرج Casablanca');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('9947', 'RIAD', 'محطة الرياض', 30.469243, -9.633729, 'Agadir', 'Route de Oujda KM 17, Sortie Agadir', 'زاوية شارع Al Quds وشارع Oqba Ibn Nafii، Agadir');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('1583', 'SALAM', 'محطة السلام', 32.338594, -6.302088, 'Béni Mellal', 'Avenue Moulay Ismail KM 4, Béni Mellal', 'شارع Allal Ben Abdellah كم 12، Béni Mellal');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('7430', 'TARIK', 'محطة طارق', 35.133858, -2.954673, 'Nador', 'Zone Industrielle Lissasfa, Lot 137, Nador', 'طث 4890 نك 118+258 دوار Oulad Brahim، إقليم Béni Mellal-Khénifra');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('4537', 'YASMINE', 'محطة الياسمين', 30.426953, -9.581128, 'Agadir', 'Boulevard Ghandi, Quartier Hay Salam, Agadir', 'طث 8607 نك 48+475 دوار Oulad Ziane، إقليم Oriental');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('8580', 'ZAHRA', 'محطة الزهراء', 32.955772, -7.580771, 'Settat', 'Zone Industrielle Ouled Saleh, Lot 164, Settat', 'طريق Marrakech كم 9، مخرج Settat');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('3911', 'ZITOUN', 'محطة الزيتون', 33.192236, -8.506898, 'El Jadida', 'RN N° 1 PK 190+728 Commune Ouled Moussa, Province de Oriental', 'طو 7591 نك 299+818 مركز Skhirat');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('910', 'AIN SEBAA', 'محطة عين السبع', 30.904962, -6.87557, 'Ouarzazate', 'Route de Meknès KM 28, Sortie Ouarzazate', 'طريق Agadir كم 2، مخرج Ouarzazate');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('6330', 'ANFA', 'محطة أنفا', 30.440813, -8.867191, 'Taroudant', 'Boulevard Massira, Quartier Hay Hassani, Taroudant', 'شارع Allal Ben Abdellah كم 7، Taroudant');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('2799', 'BOURGOGNE', 'محطة بورغون', 29.02866, -10.033012, 'Guelmim', 'Route de Marrakech KM 28, Sortie Guelmim', 'شارع Mohammed V كم 22، Guelmim');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('4681', 'CIL', 'محطة سيل', 31.65671, -7.961928, 'Marrakech', 'Angle Rue Moulay Youssef et Rue Oqba Ibn Nafii, Marrakech', 'طو رقم 18 نك 105+455 جماعة Tameslouht، إقليم Marrakech-Safi');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('1365', 'DERB SULTAN', 'محطة درب السلطان', 34.252099, -6.557303, 'Kénitra', 'CT 4673 PK 63+229 Douar Oulad Ziane, Province Marrakech-Safi', 'شارع Bir Anzarane كم 10، Kénitra');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('2374', 'ENNASR', 'محطة النصر', 33.040305, -7.652724, 'Settat', 'CT 5844 PK 141+243 Douar Oulad Brahim, Province Rabat-Salé', 'طو رقم 17 نك 202+479 جماعة Ain Atiq، إقليم Casablanca');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('2860', 'FADL', 'محطة الفضل', 33.860471, -6.086341, 'Khémisset', 'Zone Industrielle Ahl Loghlam, Lot 159, Khémisset', 'بوليفارد Zerktouni، حي Hay Salam، Khémisset');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('2858', 'GHANDI', 'محطة غاندي', 33.604393, -7.625023, 'Casablanca', 'Boulevard Ghandi, Quartier Hay Hassani, Casablanca', 'طو 8284 نك 197+714 مركز Ouled Moussa');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('8900', 'HILAL', 'محطة الهلال', 34.235242, -3.976591, 'Taza', 'Avenue Allal Ben Abdellah KM 12, Taza', 'طث 9698 نك 114+311 دوار Ait Lahcen، إقليم Rabat-Salé');

INSERT INTO data_stations (code_station, nom_station_fr, nom_station_ar, latitude, longitude, ville, address_fr, address_ar)
VALUES ('6856', 'INBIAAT', 'محطة الانبعاث', 35.603941, -5.343682, 'Tétouan', 'Boulevard Zerktouni, Quartier Hay Salam, Tétouan', 'طث 2653 نك 79+858 دوار Ait Lahcen، إقليم Rabat-Salé');

