## Validation rose et ré-export — 10 septembre 2026

27 tests Python et 5 tests JavaScript réussis. Tests ajoutés : remplacement sur disque à session constante, retrait d’une tuile obsolète, conservation de l’ancienne session lors d’un nouveau lien, conservation des anciennes tuiles sur erreur, rejet des identifiants invalides, en-têtes anti-cache exacts et Expires 0.

Le test Edge `tests/validate_reexport.cjs` couvre les événements tactiles émulés, clic et clavier sur la rose, la conservation des coordonnées et du même objet rectangle après modification du slider, et les deux ré-exports via l’interface. Pas de test sur téléphone physique ni de pilotage de Maps Viewer.

# Validation de la refonte — 10 septembre 2026

- 26 tests Python et 5 tests JavaScript réussis : calcul SIG, filtres, découpe, couleurs, MBTiles TMS, égalité exacte des PNG XYZ/MBTiles, CORS, MIME, 404, annulation et absence de publication sur erreur.
- Export réel vérifié sur 4 tuiles alpines : 5 226 pixels sélectionnés, résultat comparé aux calculs du DEM, zéro téléchargement en mode hors ligne. Les PNG reçus via HTTP sont identiques aux blobs MBTiles.
- Navigateur Edge automatisé : 390 × 844, 320 × 568, 844 × 390 et 1440 × 900, sans débordement horizontal. À 390 pixels : carte de 756 pixels tiroir replié, 473 pixels tiroir ouvert ; en-tête absent, recherche absente, puces fonctionnelles et génération réelle XYZ/MBTiles. Validation sur émulation tactile, pas sur un téléphone physique.
- Leaflet fourni sans extension de rotation/inclinaison : aucun gestionnaire bearing/pitch/rotation tactile. Le zoom tactile est conservé.
- Benchmark sur 96 tuiles DEM réelles en cache, trois passages, sans réseau. Avant optimisation du décodage/compression : séquentiel 6,573 / 6,422 / 6,361 s. Pipeline final à quatre travailleurs : 1,518 / 1,517 / 1,492 s, soit environ **4,28× plus rapide (−77 %)**. Sur le pipeline final seul, un travailleur prend 2,603 / 2,443 / 2,526 s : la parallélisation apporte environ 1,67×, le reste vient du cache DEM décodé et de la compression PNG niveau 1. Benchmark MBTiles ; la copie sur disque XYZ ajoute un coût. Le téléchargement initial reste tributaire du réseau.
- Pas de déploiement public ni de pilotage de Maps Viewer : contrat XYZ HTTP testé. Un lecteur distant exige une adresse accessible ; un lecteur HTTPS exige des tuiles HTTPS.

Les scripts reproductibles sont dans tests/. Les PNG de contrôle sont mobile-validation.png et export-validation.png.

---

## Documentation de validation antérieure (formats historiques remplacés)

# Validation de Fat Tiles

Vérification effectuée le **10 septembre 2026** sur Windows, Python 3.12.2, NumPy 2.3.5, Pillow 12.0.0 et Node.js 24.19.0.

## Résultats exécutés

| Vérification | Résultat |
| --- | --- |
| Tests Python (`python -m unittest discover -s tests -v`) | **23 / 23 réussis** |
| Tests JavaScript (`node --test tests/test_filters.cjs`) | **4 / 4 réussis**, dont 2 000 pixels float32 comparés à Python |
| Analyse de syntaxe JavaScript (`node --check static/app.js`) | Réussie |
| Lancement Windows répété sur le même port | Réouverture du serveur existant, sans seconde instance concurrente |
| Source réelle AWS Terrarium, région de Chamonix | Tuiles téléchargées et décodées |
| Interface de bureau, navigateur intégré, 1 280 × 720 | Relief, sélection, valeurs numériques, orientations N + SE et rectangle vérifiés |
| Interface mobile, fenêtre de 390 × 844 | Mise en page, navigation, bascule hors ligne et export vérifiés |
| Export MBTiles par l’interface en mode hors ligne | **8 tuiles**, fichier de 65 536 octets ; téléchargement proposé |
| Nouvelle instance du serveur, cache mémoire vide, cache disque conservé, mode hors ligne | Trois formats exportés, **0 téléchargement réseau** |
| Comparaison de tous les pixels exportés au prédicat attendu et à la découpe | **5 226 pixels sélectionnés**, identiques pour chacun des trois formats sur la zone test de 4 tuiles |
| Fichiers SQLite | `PRAGMA integrity_check = ok`, coordonnées et métadonnées vérifiées |
| Archive XYZ | Contrôle ZIP réussi, arborescence et PNG vérifiés |

Le script `tests/smoke_real.py` reproduit le test réel et écrit les résultats dans `test-results/real-data.json`. La zone utilisée est `[6.84,45.90,6.90,45.94]`, zooms 11 et 12. Les fichiers générés sont conservés dans `exports`.

La vérification mobile est une **validation du navigateur à la taille d’un téléphone**, pas un essai sur un téléphone physique. QGIS, OsmAnd et les applications « Maps Viewer » n’ont pas été ouverts : la validation porte sur les formats produits et les conventions de leurs spécifications. Le Dockerfile est fourni pour le déploiement ultérieur, mais Docker n’étant pas installé ici, sa construction n’a pas été exécutée.

## Formules vérifiées

### Décodage de l’altitude

```text
h = 256 R + G + B / 256 − 32768, en mètres
```

Les canaux sont convertis en flottants **avant** l’arithmétique, évitant tout dépassement sur des entiers 8 bits. Les fractions multiples de 1/256 sont préservées. `RGB(128,0,0)` signifie bien zéro mètre. Un alpha nul et les valeurs hors de l’intervalle physique conservateur [−12 000, 10 000] deviennent `NaN` ; un pixel noir, à −32 768 m, est donc exclu. Une altitude négative plausible reste une donnée valide.

### Projection et échelle réelle

Pour une tuile XYZ `(z,x,y)`, une ligne `j`, une largeur de tuile de 256 pixels et le rayon Web Mercator `R = 6 378 137 m` :

```text
u   = (256 y + j + 0,5) / (256 × 2^z)
φ   = atan(sinh(π (1 − 2u)))
d   = 2π R / (256 × 2^z) × cos(φ)
```

`d` est l’espacement local au sol, en mètres, recalculé **pour chaque ligne**. À 60° de latitude, cet espacement est la moitié de celui de l’équateur au même zoom. Omettre ce facteur sous-estimerait les gradients loin de l’équateur. Les distances ici sont celles du modèle sphérique de Web Mercator ; ce n’est pas une correction géodésique ellipsoïdale de haute précision.

### Gradient de Horn

Avec le voisinage orienté nord en haut :

```text
a b c
d e f
g h i

p = ((c + 2f + i) − (a + 2d + g)) / (8 × espacement)
q = ((g + 2h + i) − (a + 2b + c)) / (8 × espacement)

pente = atan(sqrt(p² + q²)) × 180 / π
exposition = (atan2(−p, q) × 180 / π) modulo 360
```

`p` est la dérivée vers l’Est et `q` la dérivée vers le Sud. Le vecteur de descente a donc pour coordonnées `(Est, Nord) = (−p, q)`, ce qui justifie l’ordre et les signes de `atan2`. Les azimuts sont horaires : Nord 0°, Est 90°, Sud 180°, Ouest 270°.

Les tests construisent des plans analytiques à **37° de pente** dans les huit directions cardinales et intermédiaires et contrôlent l’azimut et la pente. Un second test utilise une pente linéaire dans le plan projeté à 0°, 45°, 75° et −60° de latitude, puis la compare à l’inclinaison physique attendue ligne par ligne. Les calculs sont effectués en float64 avant un stockage float32 commun à l’aperçu et à l’export.

### Expositions et limites

```text
secteur = floor(((azimut + 22,5) modulo 360) / 45)
```

Les secteurs sont des intervalles demi-ouverts pour éviter les ambiguïtés aux frontières. Le Nord correspond à `[337,5°,360°) ∪ [0°,22,5°)` ; exactement 22,5° appartient au Nord-Est. Les valeurs arrondies à 360° lors de la conversion float32 sont ramenées à zéro. Altitude et pente ont des bornes **incluses**.

Le plat numérique correspond à une norme du gradient ≤ `10⁻⁷`, soit une pente d’environ `0,00000573°`. Son azimut est indéfini (`NaN`) et la case « terrains plats » contrôle sa sélection indépendamment des directions. Un azimut absent sur un pixel non plat n’est pas sélectionné.

## Bords, absences et cohérence des fichiers

- Chaque tuile reçoit une bordure réelle d’un pixel provenant des **8 tuiles voisines**. Les bords ne sont pas répétés artificiellement.
- Les coordonnées X bouclent à l’antiméridien. Au nord et au sud de Web Mercator, une bordure sans voisin reste absente. Les zones traversant l’antiméridien doivent être exportées en deux rectangles.
- Si une des neuf altitudes nécessaires au calcul manque, le résultat est exclu. Un téléchargement en échec provoque une erreur explicite et aucune publication d’export incomplet.
- Le test de raccord compare les colonnes adjacentes de deux tuiles d’un même plan et vérifie l’absence de rupture artificielle.
- Les tuiles s’intersectant avec le rectangle sont comptées avant de démarrer. Une tolérance de `10⁻¹⁰` unité de tuile évite de compter une rangée fantôme aux coordonnées correspondant exactement à un bord. La transparence est découpée selon le centre du pixel ; une zone plus petite qu’un pixel peut donc produire un fichier transparent.
- MBTiles utilise des lignes TMS : `tile_row = 2^z − 1 − yXYZ`. XYZ et OsmAnd conservent `yXYZ`. OsmAnd déclare `tilenumbering = simple`, `inverted_y = 0`, `ellipsoid = 0` et les zooms directs, conformément à son implémentation.
- Les exports sont écrits progressivement dans un fichier `.part`, fermé, vérifié, puis renommé. Un échec ou une annulation supprime uniquement ce fichier provisoire. Les données source téléchargées restent disponibles.
- L’aperçu charge une fois les altitudes, pentes, expositions et le relief. Les changements de filtres repeignent le Canvas sans solliciter à nouveau la source. Le prédicat JavaScript est testé contre le prédicat Python avec des seuils, valeurs absentes et échantillons aléatoires déterministes.

## Limites de précision et de fonctionnement

La précision dépend du DEM source et du zoom d’analyse. Les tuiles à un zoom inférieur sont des représentations plus lissées du terrain : la sélection n’est donc pas nécessairement identique entre deux niveaux de zoom. Une carte calculée avec un DEM n’est pas une mesure terrain et ne permet pas de conclure, à elle seule, qu’un itinéraire est praticable.

L’utilisation hors ligne de l’interface mobile nécessite l’accès Wi-Fi au serveur PC. Les fichiers exportés fonctionnent indépendamment du PC dans un lecteur compatible. Les ressources OpenTopoMap non déjà consultées ne sont pas garanties hors ligne ; le relief généré depuis le DEM est le fond garanti pour les zones préparées.

Le service local ne fournit ni authentification, ni gestion multi-utilisateurs. Une seule opération lourde est admise à la fois ; 4 requêtes de source et 4 calculs au maximum s’exécutent simultanément. Le cache mémoire du serveur contient au plus 32 tuiles de mesures, et celui du navigateur 40 buffers, en plus des tuiles affichées. La taille du cache disque est plafonnée à 10 Go et un minimum d’espace libre est contrôlé.

## Références

- [Terrarium : encodage et projection](https://github.com/tilezen/joerd/blob/master/docs/formats.md)
- [GDAL : calcul de pente, algorithme de Horn](https://gdal.org/en/stable/programs/gdal_raster_slope.html)
- [GDAL : convention des expositions](https://gdal.org/en/stable/api/python/utilities.html)
- [Spécification MBTiles 1.3](https://github.com/mapbox/mbtiles-spec/blob/master/1.3/spec.md)
- [Format SQLite OsmAnd](https://osmand.net/docs/technical/osmand-file-formats/osmand-sqlite/)
- [Implémentation SQLiteTileSource d’OsmAnd](https://github.com/osmandapp/OsmAnd/blob/master/OsmAnd/src/net/osmand/plus/resources/SQLiteTileSource.java)
