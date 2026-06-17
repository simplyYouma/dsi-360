-- Matrice d'accès paramétrable : quel profil accède à quels modules (cf. docs/04-SECURITY §2).
-- Les actions sensibles restent gardées en dur côté API ; ceci ne pilote que l'accès aux modules.

CREATE TABLE core.acces_role (
    profil_code text NOT NULL REFERENCES core.profil(code) ON DELETE CASCADE,
    acces       text NOT NULL,  -- clé de module : tableau-de-bord, incidents, demandes, ...
    PRIMARY KEY (profil_code, acces)
);

COMMENT ON TABLE core.acces_role IS 'Accès profil -> modules (paramétrable depuis l''administration).';
