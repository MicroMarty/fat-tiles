# Fat Tiles

## Démarrer

Dans le terminal du dossier du projet :

```powershell
python launch.py
```

Ouvrez http://localhost:8765. Gardez le terminal ouvert ; Ctrl+C arrête le service. Si une ancienne version tourne, arrêtez-la avant de relancer cette commande. Le lanceur conserve un serveur déjà actif.

Python 3.10+ est requis. Le lanceur installe NumPy et Pillow si nécessaire. Leaflet est fourni localement.

## Carte et mobile

OpenTopoMap est le seul fond. La recherche et le sélecteur de fond sont supprimés. Leaflet sans extension de rotation ne permet ni bearing ni pitch : le Nord reste en haut, y compris avec deux doigts.

Sur smartphone (760 pixels maximum), l’en-tête disparaît. Le tiroir inférieur démarre replié (88 pixels) ; les onglets ouvrent les réglages et la flèche les replie. Ouvert, il utilise 44 % de la hauteur et laisse la carte visible au-dessus. Son contenu défile indépendamment. Les doubles curseurs altitude/pente et la rose des vents tactile à huit secteurs sont conservés.

## MBTiles et URL XYZ

1. Dans Exporter, dessinez le rectangle avec deux coins ou utilisez la vue actuelle.
2. Choisissez les zooms et le contenu (masque transparent ou relief calculé + masque).
3. Lancez la génération. Le MBTiles se télécharge et le bouton **Copier l’URL XYZ** fournit le modèle complet pour Maps Viewer :

```text
http://localhost:8765/tiles/SESSION/{z}/{x}/{y}.png
```

L’URL utilise l’adresse depuis laquelle vous ouvrez l’application. Pour un téléphone ou un autre ordinateur, ouvrez l’interface avec l’adresse réseau du PC. Localhost désigne toujours l’appareil du lecteur. Un Maps Viewer en HTTPS nécessite un serveur de tuiles accessible en HTTPS ; CORS ne contourne pas le blocage du contenu HTTP. Aucun hébergement public n’est créé automatiquement.

Le serveur répond avec `Access-Control-Allow-Origin: *` et `Content-Type: image/png`. Les tuiles absentes renvoient 404. Les sessions persistent dans `exports/SESSION`, même après redémarrage. Les filtres sont figés au lancement. Les exports ne comprennent pas OpenTopoMap.

Quatre travailleurs calculent et encodent les PNG en parallèle ; huit travaux au maximum sont en attente. Les DEM décodés sont partagés dans un cache borné. Un seul écrivain SQLite produit le MBTiles (lignes TMS), et les mêmes octets PNG sont écrits directement dans l’arborescence XYZ. Pas de ZIP intermédiaire, de recalcul ni d’extraction. La publication intervient après vérification SQLite ; les sorties partielles sont supprimées en cas d’échec ou d’annulation. Seuls MBTiles et URL XYZ sont proposés.

## Hôte et port

```powershell
$env:HOST="0.0.0.0"
$env:PORT="8765"
python launch.py --no-browser
```

`HOST` définit l’interface d’écoute et `PORT` le port. Les arguments `--host` et `--port` ont priorité. Pour un serveur distant, conserver les dossiers data et exports et utiliser un reverse proxy HTTPS. Le service est destiné à un utilisateur ou petit réseau, avec une seule génération active.

## Hors ligne

Préchargez le terrain dans l’onglet Hors ligne. Les filtres et exports fonctionnent ensuite sur les zooms préparés. OpenTopoMap reste visible seulement pour les tuiles déjà consultées et mises en cache ; le préchargement DEM ne télécharge pas ce fond. Le PC doit rester allumé pour servir le téléphone et les URL XYZ. Les MBTiles restent utilisables indépendamment.

## Validation

```powershell
python -m unittest discover -s tests -v
node --test tests/test_filters.cjs
python tests/smoke_real.py
python tests/benchmark_export.py
```

Le smoke test utilise le serveur local : `TEST_URL` permet de changer son adresse. Le benchmark utilise jusqu’à 96 tuiles DEM réelles déjà présentes dans data/cache, sans réseau, trois fois avec un puis quatre travailleurs. Le contrôle navigateur `tests/validate_ui.cjs` nécessite Playwright et Edge et utilise le port 8767.

Les tuiles DEM ont des résolutions variables ; les mesures de pente dépendent du zoom. Limite : 2 000 tuiles par export, zoom 14 maximum. Les attributions sont incluses dans les métadonnées MBTiles et accessibles dans ATTRIBUTION.txt.

## Ré-exporter après modification des filtres

Après le premier export, deux boutons remplacent le bouton initial :

- **Mettre à jour le lien** : conserve exactement l’URL XYZ et remplace le dossier de tuiles après calcul réussi. Le rectangle reste en place lorsque vous ajustez les filtres. Un nouveau MBTiles est également fourni.
- **Nouveau lien** : crée une session indépendante et conserve les anciennes tuiles pour superposer plusieurs calques.

Les réponses XYZ comportent `Cache-Control: no-cache, no-store, must-revalidate` et `Expires: 0`. Ces en-têtes empêchent la réutilisation du cache HTTP ; si un lecteur garde déjà un calque affiché en mémoire sans refaire de requête, rechargez ce calque après la mise à jour.

La rose permet de sélectionner plusieurs directions par clic ou toucher ; au clavier, Tab puis Espace/Entrée active un secteur.

Pour relancer : Ctrl+C dans l’ancien terminal, puis `python launch.py`, et actualisez la page. Le code complet est directement mis à jour dans ce dossier.
