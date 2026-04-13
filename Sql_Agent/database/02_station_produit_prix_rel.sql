-- =============================================
-- CRÉATION DE LA TABLE station_produit_prix_rel
-- =============================================

CREATE TABLE station_produit_prix_rel (
    id SERIAL PRIMARY KEY,
    code_station VARCHAR(50) NOT NULL,
    code_produit VARCHAR(50) NOT NULL,
    prix DECIMAL(10, 2),
    unite VARCHAR(10) DEFAULT 'L',
    date_du DATE,
    date_au DATE
);

-- Index pour améliorer les performances
CREATE INDEX idx_station_produit_prix_code_station ON station_produit_prix_rel(code_station);
CREATE INDEX idx_station_produit_prix_code_produit ON station_produit_prix_rel(code_produit);
CREATE INDEX idx_station_produit_prix_dates ON station_produit_prix_rel(date_du, date_au);

-- =============================================
-- INSERTION DES DONNÉES (DUMMY DATA) - CORRIGÉE AVEC VRAIS CODES STATION
-- =============================================

-- Station 957 (AL AMAL)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('957', 11054001, 11.01, 'L', '2025-09-01', '2025-06-30');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('957', 11191001, 15.07, 'L', '2025-06-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('957', 11011001, 12.64, 'L', '2025-09-01', '2025-06-30');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('957', 11052001, 10.62, 'L', '2025-06-01', NULL);

-- Station 702 (AL BARAKA)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('702', 11054001, 11.18, 'L', '2025-06-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('702', 15011001, 13.6, 'L', '2025-03-01', '2025-09-30');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('702', 11191001, 15.08, 'L', '2025-03-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('702', 11011001, 12.72, 'L', '2025-03-01', NULL);

-- Station 1544 (AL FIRDAOUS)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('1544', 11011001, 12.9, 'L', '2025-03-01', '2025-12-31');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('1544', 11191001, 14.5, 'L', '2025-11-01', '2025-12-31');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('1544', 11052001, 11.17, 'L', '2025-03-01', '2025-06-30');

-- Station 1554 (AL MASSIRA)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('1554', 11191001, 14.85, 'L', '2025-01-15', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('1554', 11011001, 12.73, 'L', '2025-06-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('1554', 15011001, 13.78, 'L', '2025-01-15', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('1554', 11052001, 11.03, 'L', '2025-09-01', NULL);

-- Station 2832 (AL MOUKHTAR)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('2832', 11052001, 10.89, 'L', '2025-09-01', '2025-09-30');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('2832', 11191001, 15.1, 'L', '2025-11-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('2832', 15011001, 13.37, 'L', '2025-01-15', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('2832', 11054001, 11.17, 'L', '2025-06-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('2832', 11011001, 12.99, 'L', '2025-01-15', NULL);

-- Station 9350 (AL WAFA)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('9350', 11011001, 12.73, 'L', '2025-09-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('9350', 11054001, 11.68, 'L', '2025-03-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('9350', 11052001, 11.03, 'L', '2025-11-01', NULL);

-- Station 3253 (ATLAS)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('3253', 11191001, 15.22, 'L', '2025-06-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('3253', 11054001, 11.21, 'L', '2025-11-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('3253', 15011001, 13.48, 'L', '2025-11-01', '2025-12-31');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('3253', 11011001, 12.67, 'L', '2025-03-01', NULL);

-- Station 899 (BAB DOUKKALA)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('899', 11191001, 15.48, 'L', '2025-06-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('899', 11052001, 11.04, 'L', '2025-09-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('899', 15011001, 13.8, 'L', '2025-01-15', '2025-12-31');

-- Station 2818 (BOULEVARD ZERKTOUNI)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('2818', 15011001, 13.3, 'L', '2025-06-01', '2025-09-30');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('2818', 11011001, 13.09, 'L', '2025-11-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('2818', 11191001, 14.66, 'L', '2025-09-01', NULL);

-- Station 279 (CHAMS)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('279', 11191001, 14.31, 'L', '2025-11-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('279', 11054001, 11.19, 'L', '2025-03-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('279', 15011001, 13.8, 'L', '2025-09-01', '2025-09-30');

-- Station 5881 (DAR SALAM)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('5881', 11052001, 10.73, 'L', '2025-01-15', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('5881', 11054001, 11.42, 'L', '2025-06-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('5881', 15011001, 13.33, 'L', '2025-06-01', NULL);

-- Station 2300 (EL FATH)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('2300', 11054001, 11.07, 'L', '2025-11-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('2300', 11011001, 12.59, 'L', '2025-06-01', '2025-06-30');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('2300', 11191001, 14.37, 'L', '2025-01-15', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('2300', 11052001, 10.6, 'L', '2025-01-15', NULL);

-- Station 153 (EL WAHDA)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('153', 11054001, 11.5, 'L', '2025-03-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('153', 11052001, 10.76, 'L', '2025-01-15', '2025-12-31');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('153', 15011001, 13.3, 'L', '2025-09-01', '2025-06-30');

-- Station 2086 (HASSAN II)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('2086', 11054001, 11.69, 'L', '2025-09-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('2086', 11191001, 15.21, 'L', '2025-06-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('2086', 15011001, 13.15, 'L', '2025-09-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('2086', 11011001, 12.55, 'L', '2025-09-01', NULL);

-- Station 1473 (HAY MOHAMMADI)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('1473', 11191001, 14.8, 'L', '2025-11-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('1473', 11054001, 11.34, 'L', '2025-11-01', '2025-09-30');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('1473', 11011001, 12.45, 'L', '2025-11-01', '2025-06-30');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('1473', 11052001, 10.52, 'L', '2025-01-15', NULL);

-- Station 6665 (IBN SINA)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('6665', 11191001, 14.99, 'L', '2025-11-01', '2025-06-30');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('6665', 11052001, 11.01, 'L', '2025-01-15', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('6665', 11054001, 11.61, 'L', '2025-01-15', NULL);

-- Station 3115 (JARDINS)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('3115', 11011001, 13.03, 'L', '2025-01-15', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('3115', 11052001, 11.02, 'L', '2025-01-15', '2025-06-30');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('3115', 11054001, 11.13, 'L', '2025-01-15', '2025-06-30');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('3115', 15011001, 13.18, 'L', '2025-11-01', NULL);

-- Station 1293 (KASBAH)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('1293', 11054001, 11.55, 'L', '2025-06-01', '2025-06-30');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('1293', 11191001, 14.99, 'L', '2025-06-01', '2025-12-31');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('1293', 15011001, 13.7, 'L', '2025-09-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('1293', 11011001, 12.94, 'L', '2025-03-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('1293', 11052001, 10.76, 'L', '2025-11-01', NULL);

-- Station 185 (LAYMOUNE)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('185', 11054001, 11.53, 'L', '2025-09-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('185', 11011001, 13.09, 'L', '2025-01-15', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('185', 11191001, 14.68, 'L', '2025-11-01', '2025-09-30');

-- Station 333 (MAARIF)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('333', 11191001, 15.32, 'L', '2025-01-15', '2025-06-30');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('333', 11011001, 12.52, 'L', '2025-06-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('333', 11052001, 10.84, 'L', '2025-06-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('333', 15011001, 13.26, 'L', '2025-09-01', NULL);

-- Station 4313 (NAKHIL)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('4313', 11054001, 11.46, 'L', '2025-03-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('4313', 11052001, 10.66, 'L', '2025-11-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('4313', 11011001, 13.05, 'L', '2025-03-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('4313', 11191001, 14.3, 'L', '2025-09-01', '2025-12-31');

-- Station 6009 (OASIS)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('6009', 11054001, 11.5, 'L', '2025-06-01', '2025-12-31');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('6009', 15011001, 13.1, 'L', '2025-06-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('6009', 11052001, 10.76, 'L', '2025-09-01', '2025-09-30');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('6009', 11011001, 12.99, 'L', '2025-03-01', '2025-06-30');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('6009', 11191001, 14.34, 'L', '2025-09-01', NULL);

-- Station 8443 (PLACE JAMAA)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('8443', 11191001, 15.03, 'L', '2025-09-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('8443', 15011001, 13.62, 'L', '2025-11-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('8443', 11052001, 11.17, 'L', '2025-03-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('8443', 11054001, 11.3, 'L', '2025-06-01', '2025-09-30');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('8443', 11011001, 12.45, 'L', '2025-06-01', '2025-12-31');

-- Station 7429 (RAHMA)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('7429', 11191001, 15.5, 'L', '2025-03-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('7429', 15011001, 13.27, 'L', '2025-01-15', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('7429', 11011001, 12.62, 'L', '2025-01-15', '2025-09-30');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('7429', 11052001, 11.11, 'L', '2025-11-01', '2025-06-30');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('7429', 11054001, 11.44, 'L', '2025-03-01', NULL);

-- Station 9947 (RIAD)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('9947', 11011001, 13.05, 'L', '2025-06-01', '2025-12-31');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('9947', 11054001, 11.38, 'L', '2025-01-15', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('9947', 11191001, 15.05, 'L', '2025-03-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('9947', 11052001, 10.51, 'L', '2025-09-01', NULL);

-- Station 1583 (SALAM)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('1583', 11011001, 12.55, 'L', '2025-03-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('1583', 11052001, 11.18, 'L', '2025-11-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('1583', 11191001, 15.0, 'L', '2025-09-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('1583', 15011001, 13.49, 'L', '2025-01-15', NULL);

-- Station 7430 (TARIK)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('7430', 11052001, 11.03, 'L', '2025-03-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('7430', 11054001, 11.27, 'L', '2025-11-01', '2025-09-30');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('7430', 11191001, 14.78, 'L', '2025-03-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('7430', 11011001, 12.58, 'L', '2025-06-01', NULL);

-- Station 4537 (YASMINE)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('4537', 11011001, 12.47, 'L', '2025-03-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('4537', 15011001, 13.17, 'L', '2025-06-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('4537', 11052001, 10.8, 'L', '2025-03-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('4537', 11054001, 11.45, 'L', '2025-03-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('4537', 11191001, 15.25, 'L', '2025-01-15', NULL);

-- Station 8580 (ZAHRA)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('8580', 11011001, 12.56, 'L', '2025-11-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('8580', 11191001, 14.3, 'L', '2025-11-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('8580', 11052001, 10.54, 'L', '2025-03-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('8580', 15011001, 13.59, 'L', '2025-01-15', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('8580', 11054001, 11.69, 'L', '2025-03-01', '2025-06-30');

-- Station 3911 (ZITOUN)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('3911', 11054001, 11.15, 'L', '2025-01-15', '2025-12-31');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('3911', 11191001, 14.68, 'L', '2025-11-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('3911', 11011001, 12.96, 'L', '2025-01-15', '2025-12-31');

-- Station 910 (AIN SEBAA)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('910', 11191001, 14.52, 'L', '2025-03-01', '2025-06-30');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('910', 11052001, 11.05, 'L', '2025-09-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('910', 11011001, 12.61, 'L', '2025-01-15', '2025-09-30');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('910', 11054001, 11.32, 'L', '2025-03-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('910', 15011001, 13.32, 'L', '2025-03-01', '2025-06-30');

-- Station 6330 (ANFA)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('6330', 15011001, 13.47, 'L', '2025-01-15', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('6330', 11054001, 11.5, 'L', '2025-11-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('6330', 11191001, 15.46, 'L', '2025-01-15', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('6330', 11052001, 10.51, 'L', '2025-01-15', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('6330', 11011001, 12.49, 'L', '2025-09-01', '2025-12-31');

-- Station 2799 (BOURGOGNE)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('2799', 11052001, 10.6, 'L', '2025-11-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('2799', 11011001, 12.49, 'L', '2025-11-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('2799', 15011001, 13.39, 'L', '2025-03-01', '2025-12-31');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('2799', 11191001, 14.51, 'L', '2025-11-01', NULL);

-- Station 4681 (CIL)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('4681', 11191001, 14.47, 'L', '2025-03-01', '2025-06-30');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('4681', 11011001, 12.71, 'L', '2025-03-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('4681', 11052001, 10.79, 'L', '2025-11-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('4681', 15011001, 13.65, 'L', '2025-09-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('4681', 11054001, 11.64, 'L', '2025-01-15', '2025-06-30');

-- Station 1365 (DERB SULTAN)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('1365', 15011001, 13.62, 'L', '2025-03-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('1365', 11054001, 11.38, 'L', '2025-03-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('1365', 11052001, 10.61, 'L', '2025-09-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('1365', 11191001, 15.42, 'L', '2025-06-01', NULL);

-- Station 2374 (ENNASR)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('2374', 11191001, 14.69, 'L', '2025-06-01', '2025-09-30');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('2374', 11052001, 11.11, 'L', '2025-01-15', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('2374', 11054001, 11.15, 'L', '2025-06-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('2374', 15011001, 13.65, 'L', '2025-11-01', NULL);

-- Station 2860 (FADL)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('2860', 11052001, 11.0, 'L', '2025-11-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('2860', 11191001, 14.31, 'L', '2025-11-01', '2025-06-30');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('2860', 15011001, 13.2, 'L', '2025-06-01', '2025-06-30');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('2860', 11054001, 11.33, 'L', '2025-03-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('2860', 11011001, 12.99, 'L', '2025-09-01', '2025-09-30');

-- Station 2858 (GHANDI)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('2858', 11054001, 11.28, 'L', '2025-11-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('2858', 11011001, 12.51, 'L', '2025-06-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('2858', 11052001, 10.87, 'L', '2025-09-01', '2025-06-30');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('2858', 15011001, 13.52, 'L', '2025-06-01', NULL);

-- Station 8900 (HILAL)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('8900', 11011001, 12.95, 'L', '2025-01-15', '2025-09-30');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('8900', 11191001, 15.33, 'L', '2025-09-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('8900', 11054001, 11.42, 'L', '2025-09-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('8900', 15011001, 13.38, 'L', '2025-11-01', '2025-12-31');

-- Station 6856 (INBIAAT)
INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('6856', 11052001, 11.17, 'L', '2025-06-01', '2025-09-30');

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('6856', 11191001, 14.82, 'L', '2025-09-01', NULL);

INSERT INTO station_produit_prix_rel (code_station, code_produit, prix, unite, date_du, date_au)
VALUES ('6856', 11054001, 11.19, 'L', '2025-11-01', NULL);