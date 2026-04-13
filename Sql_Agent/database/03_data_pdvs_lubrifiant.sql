-- =============================================
-- CRÉATION DE LA TABLE data_pdvs_lubrifiant
-- =============================================

CREATE TABLE data_pdvs_lubrifiant (
    id SERIAL PRIMARY KEY,
    nom_fr VARCHAR(255),
    nom_ar VARCHAR(255),
    telephone VARCHAR(20),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8)
);

-- Index pour améliorer les performances
CREATE INDEX idx_pdvs_lubrifiant_nom_fr ON data_pdvs_lubrifiant(nom_fr);

-- =============================================
-- INSERTION DES DONNÉES (DUMMY DATA)
-- =============================================

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Accessoire auto Benani', NULL, '212786645113', 33.2455211, -7.5819866);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Pièce auto Toufik', NULL, '212748560568', 33.5823155, -7.5873744);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Accessoire auto Samir', NULL, '212644859792', 33.2484436, -7.578644);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Centre auto Reda', NULL, '212627093896', 32.6702523, -4.7390746);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Pneumatique El Amrani', NULL, '212638853210', 34.2418544, -4.025546);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Pneumatique Bouazza', NULL, '212765761841', 34.0499045, -6.8545197);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Pièce auto Lahlou', NULL, '212674543320', 31.9233377, -4.4374436);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Accessoire auto Moussaoui', NULL, '212790312996', 33.9978515, -6.83122);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Pneumatique Benjelloun', NULL, '212744143438', 30.46279, -8.8647946);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Lubrifiant Chraibi', NULL, '212748330934', 29.71897, -9.7088611);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Lubrifiant Fassi', NULL, '212776183984', 33.2533722, -8.5052368);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Accessoire auto Berrada', NULL, '212775583236', 33.6930652, -7.4069235);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Espace auto Alaoui', NULL, '212681443959', 35.2180135, -6.1821809);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Vidange Tahiri', NULL, '212626670490', 32.9931376, -7.5889335);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Accessoire auto Ziani', NULL, '212694655500', 33.4170859, -5.2467642);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Garage Haddad', NULL, '212717339794', 30.4531464, -8.8501994);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Lubrifiant Naciri', NULL, '212638691437', 30.4005781, -9.5867435);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Pneumatique Kettani', NULL, '212642970015', 33.2791169, -7.556518);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Centre auto Slaoui', NULL, '212756300714', 33.9992768, -6.8160087);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Garage Benhima', NULL, '212792018825', 29.7054525, -9.7294442);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Pièce auto Idrissi', NULL, '212657067680', 32.6953436, -4.7376537);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Espace auto El Ouafi', NULL, NULL, 31.6372582, -8.0100254);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Espace auto Bouzidi', NULL, '212638087753', 33.4529866, -5.1984216);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Pièce auto Chakir', NULL, '212772866294', 32.6776668, -4.7453068);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Garage El Mouden', NULL, '212666481577', 34.6580535, -1.8835448);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Accessoire auto Rahmani', NULL, '212661064381', 35.7507369, -5.8255661);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Espace auto Kabbaj', NULL, '212672602845', 33.2577331, -7.5673634);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Garage Sefrioui', NULL, '212714101408', 32.351608, -6.3572554);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Centre auto Tazi', NULL, '212751406405', 33.2565002, -8.5001415);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Lubrifiant Ouazzani', NULL, '212755105908', 31.6160646, -7.9968389);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Garage Filali', NULL, '212684094398', 35.2156453, -6.1441968);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Espace auto Bakkali', NULL, '212674095520', 34.2388817, -4.0365793);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Centre auto El Harti', NULL, '212651304140', 33.802162, -6.0853501);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Vidange Bennani', NULL, '212698409376', 29.0069997, -10.0325904);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Garage Sqalli', NULL, '212754396088', 33.9000746, -5.5619648);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Centre auto Guessous', NULL, '212738531320', 35.5992803, -5.38998);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Espace auto Bargach', NULL, '212787602946', 30.8918191, -6.9162439);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Centre auto Cherkaoui', NULL, '212640959815', 31.9572287, -4.4216897);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Accessoire auto Benkirane', NULL, '212725793729', 33.5985729, -7.586951);

INSERT INTO data_pdvs_lubrifiant (nom_fr, nom_ar, telephone, latitude, longitude)
VALUES ('Pneumatique El Khattabi', NULL, '212799247901', 34.2743662, -6.5888339);

