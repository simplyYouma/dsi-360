/** Liste des pays, en français, pour les champs de localisation (ex. où sont hébergées les données
 *  d'une application). Une liste fermée plutôt qu'un texte libre : « Côte d'Ivoire », « Cote
 *  d'ivoire » et « CI » désignaient la même chose et ne se regroupaient jamais à l'analyse.
 *
 *  Les pays de la zone UEMOA et les partenaires habituels de la banque ouvrent la liste — on les
 *  saisit dix fois plus souvent que les autres, et les faire descendre en bas d'un alphabet de
 *  deux cents entrées n'aurait servi personne. Le reste suit, par ordre alphabétique. */

/** Les plus fréquents, en tête de liste. */
export const PAYS_FREQUENTS: string[] = [
  'Mali',
  'Bénin',
  'Burkina Faso',
  "Côte d'Ivoire",
  'Guinée-Bissau',
  'Niger',
  'Sénégal',
  'Togo',
  'France',
  'Maroc',
  'Tunisie',
];

/** Tous les autres, par ordre alphabétique. */
const AUTRES: string[] = [
  'Afrique du Sud', 'Albanie', 'Algérie', 'Allemagne', 'Andorre', 'Angola', 'Arabie saoudite',
  'Argentine', 'Arménie', 'Australie', 'Autriche', 'Azerbaïdjan', 'Bahreïn', 'Bangladesh',
  'Belgique', 'Biélorussie', 'Bolivie', 'Bosnie-Herzégovine', 'Botswana', 'Brésil', 'Bulgarie',
  'Burundi', 'Cambodge', 'Cameroun', 'Canada', 'Cap-Vert', 'Chili', 'Chine', 'Chypre', 'Colombie',
  'Comores', 'Congo', 'Corée du Sud', 'Costa Rica', 'Croatie', 'Cuba', 'Danemark', 'Djibouti',
  'Égypte', 'Émirats arabes unis', 'Équateur', 'Érythrée', 'Espagne', 'Estonie', 'Eswatini',
  'États-Unis', 'Éthiopie', 'Finlande', 'Gabon', 'Gambie', 'Géorgie', 'Ghana', 'Grèce', 'Guatemala',
  'Guinée', 'Guinée équatoriale', 'Haïti', 'Honduras', 'Hongrie', 'Île Maurice', 'Inde',
  'Indonésie', 'Irak', 'Iran', 'Irlande', 'Islande', 'Israël', 'Italie', 'Jamaïque', 'Japon',
  'Jordanie', 'Kazakhstan', 'Kenya', 'Koweït', 'Lettonie', 'Liban', 'Liberia', 'Libye',
  'Lituanie', 'Luxembourg', 'Macédoine du Nord', 'Madagascar', 'Malaisie', 'Malawi', 'Maldives',
  'Malte', 'Mauritanie', 'Mexique', 'Moldavie', 'Monaco', 'Mongolie', 'Monténégro', 'Mozambique',
  'Myanmar', 'Namibie', 'Népal', 'Nicaragua', 'Nigeria', 'Norvège', 'Nouvelle-Zélande', 'Oman',
  'Ouganda', 'Ouzbékistan', 'Pakistan', 'Panama', 'Paraguay', 'Pays-Bas', 'Pérou', 'Philippines',
  'Pologne', 'Portugal', 'Qatar', 'République centrafricaine',
  'République démocratique du Congo', 'République dominicaine', 'République tchèque', 'Roumanie',
  'Royaume-Uni', 'Russie', 'Rwanda', 'Salvador', 'Sao Tomé-et-Principe', 'Serbie', 'Seychelles',
  'Sierra Leone', 'Singapour', 'Slovaquie', 'Slovénie', 'Somalie', 'Soudan', 'Sri Lanka', 'Suède',
  'Suisse', 'Syrie', 'Tanzanie', 'Tchad', 'Thaïlande', 'Turquie', 'Ukraine', 'Uruguay',
  'Venezuela', 'Viêt Nam', 'Yémen', 'Zambie', 'Zimbabwe',
];

/** La liste complète, dans l'ordre d'affichage : les habituels d'abord, puis l'alphabet. */
export const PAYS: string[] = [...PAYS_FREQUENTS, ...AUTRES];

/** Options prêtes pour `SelecteurListe`. */
export const OPTIONS_PAYS = PAYS.map((p) => ({ valeur: p, libelle: p }));
