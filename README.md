# Fat Tiles

Une application locale en français pour sélectionner le terrain selon **l’altitude, la pente et l’exposition**, puis l’emporter hors ligne. Aucune clé API, aucun abonnement. Carte tactile sur smartphone et ordinateur.

## Démarrer sur ce PC

1. Ouvrez le dossier **Fat Tiles** dans l’Explorateur de fichiers.
2. Faites un clic droit dans le dossier, puis **Ouvrir dans le Terminal**.
3. Collez cette unique commande et appuyez sur Entrée :

   ```powershell
   python launch.py
   ```

Le navigateur s’ouvre automatiquement à **http://localhost:8765**. Gardez le terminal ouvert. **Ctrl+C** arrête le serveur. Vous pouvez aussi double-cliquer sur **demarrer.cmd**. Si Fat Tiles fonctionne déjà, la même commande rouvre simplement l’interface et conserve le serveur existant.

Python est déjà installé sur ce PC. Sur un autre ordinateur, Python 3.10 ou plus récent doit être installé au préalable. Le lanceur installe automatiquement NumPy et Pillow dans un environnement local si ces bibliothèques sont absentes ; cette première installation nécessite Internet. La bibliothèque de carte Leaflet est livrée dans le projet, sans CDN.

Si le port est déjà occupé : `python launch.py --port 8766`.

## Utiliser la carte

1. Déplacez la carte, zoomez avec la molette, les boutons +/− ou le geste tactile.
2. Le champ de lieu propose quelques destinations et accepte partout **latitude, longitude**, par exemple `45.92, 6.87`. Il ne s’agit pas d’un moteur de recherche d’adresses mondial.
3. Ajustez les deux poignées de l’altitude et de la pente. Les champs numériques et les poignées sont synchronisés. Les limites sont incluses ; le minimum ne dépasse jamais le maximum.
4. Activez autant d’expositions que souhaité. **N + SE** sélectionne les versants nord **ou** sud-est, qui respectent aussi les intervalles d’altitude **et** de pente.
5. Les surfaces plates n’ont pas d’exposition : leur case est indépendante, et leur pente doit également entrer dans l’intervalle choisi. Aucune direction cochée et case des plats désactivée donnent une sélection vide.
6. Ajustez l’opacité ou masquez temporairement la sélection avec l’interrupteur de la légende. Touchez un point sur la carte pour lire ses mesures.

**Relief local** est calculé à partir du même DEM et fonctionne sans Internet sur les zones téléchargées. **OpenTopoMap** ajoute une carte topographique avec noms de lieux ; les tuiles consultées sont conservées sur disque. Le téléchargement préalable d’une zone et les exports utilisent le relief local, sans téléchargement massif du fond OpenTopoMap.

## Exporter

1. Ouvrez **Exporter → Dessiner un rectangle**.
2. Cliquez ou touchez un premier coin, puis le coin opposé. Vous pouvez déplacer la carte entre les deux. **Annuler** ou Échap abandonne le dessin. **Utiliser la vue actuelle** et la saisie des quatre coordonnées sont également disponibles.
3. Choisissez les zooms, par exemple **11 à 14**. L’estimation indique les tuiles exportées, le DEM à télécharger avec ses bordures et un volume approximatif. Un maximum de **2 000 tuiles par export** évite les opérations démesurées.
4. Choisissez le format et le contenu :

   | Format | Utilisation |
   | --- | --- |
   | **MBTiles** | Base SQLite standard, tuiles PNG RGBA, pour QGIS et les lecteurs qui acceptent le MBTiles raster. |
   | **SQLiteDB** | Format raster propre à OsmAnd, avec numérotation des zooms explicitement déclarée. |
   | **ZIP XYZ** | Images `z/x/y.png`, métadonnées et attributions ; utilisable dans un serveur de tuiles ou un outil acceptant cette arborescence. |

   **Masque transparent** s’ajoute à votre fond de carte habituel. **Relief local + masque** embarque également une image du terrain. OpenTopoMap n’est pas incorporé à ces exports.

5. Cliquez sur **Générer et télécharger**. Le téléchargement démarre à la fin, avec un lien de secours si le navigateur le bloque. Une copie est conservée dans le dossier **exports** du projet.

Le fichier contient les filtres au moment du lancement. La découpe respecte le rectangle au centre des pixels : les pixels extérieurs sont transparents. Les tuiles entièrement vides sont conservées, ce qui préserve la pyramide de zooms et le nombre annoncé. L’export est une **image de sélection**, pas un DEM permettant de recalculer les critères dans une autre application.

Dans **QGIS**, ajoutez le fichier `.mbtiles` comme couche raster, ou glissez-le sur la carte. Dans **OsmAnd**, importez le `.sqlitedb` comme carte raster locale et choisissez-le comme source ou superposition ; l’emplacement du menu dépend d’Android/iOS et de la version. Les applications portant le nom « Maps Viewer » ne partagent pas toutes les mêmes formats : choisissez MBTiles seulement si votre lecteur annonce le support du **MBTiles raster PNG avec transparence**. Ces applications externes n’ont pas été pilotées lors de la validation ; les fichiers et leurs conventions ont été vérifiés directement.

## Sans Internet, sur PC et smartphone

1. Avec Internet, sélectionnez la zone et les zooms dans **Exporter**.
2. Dans **Hors ligne**, cliquez sur **Télécharger le terrain** et attendez le message de réussite. Les neuf tuiles nécessaires autour de chaque tuile analysée sont mises en cache sans doublons.
3. Activez **Mode sans Internet**. Le serveur cesse de contacter les sources. Le fond bascule sur **Relief local**. Une tuile non téléchargée est signalée comme absente, jamais interprétée comme une altitude nulle.
4. Vous pouvez modifier les critères et exporter à nouveau à l’intérieur de la zone, **aux zooms téléchargés**. Un zoom différent ou une zone voisine peut nécessiter des données supplémentaires. Les zones mémorisées permettent de revenir à leur centre.
5. Connectez le smartphone au **même réseau Wi-Fi que le PC**. Ouvrez l’adresse « Téléphone » affichée dans le terminal, ou dans le bouton **?** de l’application. Le Wi-Fi peut fonctionner sans accès Internet.

**Le PC doit rester allumé pour utiliser cette interface sur le téléphone.** Une page ouverte par HTTP sur le réseau local n’est pas une application installée autonome sur le smartphone. Pour partir sans PC, transférez le fichier exporté et utilisez-le dans votre lecteur cartographique hors ligne. Cette distinction est aussi affichée dans l’interface.

Si Windows affiche une demande du pare-feu au premier lancement, autorisez Python sur le **réseau privé**. Si le téléphone ne rejoint pas le serveur, vérifiez le même Wi-Fi, l’adresse affichée et l’absence d’isolation des appareils sur un réseau invité. L’adresse `localhost` concerne le PC lui-même et ne doit pas être saisie sur le téléphone.

Le cache se trouve dans **data/cache** et les zones dans **data/regions.json**. Le cache est limité à 10 Go ; l’application s’arrête avec un message clair si le disque est presque plein. Les téléchargements interrompus sont réutilisés lors de la prochaine tentative. Aucun effacement automatique des zones préparées. Pour libérer manuellement le cache, arrêtez le serveur puis supprimez `data/cache` et `data/regions.json` ; il faudra télécharger les zones à nouveau. Les fichiers dans `exports` sont indépendants.

## Calcul et précision

Voir [VALIDATION.md](VALIDATION.md) pour les formules, conventions, tests et limites. Le DEM est mondial dans l’emprise Web Mercator (±85,0511°). Les zooms autorisés vont de 0 à 14. Le nombre de pixels du fichier ne garantit pas une résolution terrain équivalente : les sources d’altitude ont des résolutions et qualités variables, et les résultats de pente varient avec le zoom.

Les rectangles traversant ±180° doivent être divisés en deux exports. Les tuiles de part et d’autre de l’antiméridien sont néanmoins raccordées correctement pour le calcul. Les pixels impossibles à calculer à la limite polaire ou autour de valeurs absentes sont exclus.

## Installation ultérieure sur un serveur

Le frontend et l’API utilisent la même origine et des chemins relatifs : aucun changement de code n’est nécessaire. Il suffit de copier le projet et de lancer `python launch.py --no-browser`. Les données et exports sont des dossiers persistants. Le service est prévu pour un utilisateur ou un petit réseau privé : quatre accès simultanés aux sources, un seul export/préchargement à la fois.

Un `Dockerfile` est également fourni :

```sh
docker build -t fat-tiles .
docker run --rm -p 127.0.0.1:8765:8765 -v fat-tiles-data:/app/data -v fat-tiles-exports:/app/exports fat-tiles
```

Pour un hébergement accessible sur Internet, placez un reverse proxy HTTPS avec contrôle d’accès devant le service local, par exemple Caddy ou Nginx. Le serveur Python livré n’implémente pas de comptes utilisateurs ni de quotas par compte. Aucun déploiement public n’a été effectué.

## Vérifier le projet

```powershell
python -m unittest discover -s tests -v
node --test tests/test_filters.cjs
```

Node.js sert uniquement au test de concordance JavaScript/Python ; il n’est pas nécessaire pour lancer l’application. La validation sur données réelles est reproductible avec `python tests/smoke_real.py` pendant que le serveur fonctionne (une connexion Internet est nécessaire si la petite zone test n’est pas déjà téléchargée).

Sources : [Terrain Tiles sur AWS](https://registry.opendata.aws/terrain-tiles/), [encodage Terrarium](https://github.com/tilezen/joerd/blob/master/docs/formats.md), [attributions](https://github.com/tilezen/joerd/blob/master/docs/attribution.md), [MBTiles 1.3](https://github.com/mapbox/mbtiles-spec/blob/master/1.3/spec.md), [format SQLite OsmAnd](https://osmand.net/docs/technical/osmand-file-formats/osmand-sqlite/), [Leaflet](https://leafletjs.com/). Les attributions des sources sont intégrées aux exports.
