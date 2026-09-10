# Ouvrir et partager Fat Tiles

## Windows : application autonome

Dans l’archive **Fat-Tiles-Windows-x64.zip** :

1. Faites **Extraire tout** vers un dossier normal, par exemple sur le Bureau.
2. Double-cliquez sur **Fat-Tiles.exe**.
3. La carte s’ouvre dans votre navigateur. Gardez la petite fenêtre du serveur ouverte ; fermez-la pour arrêter l’application.

**Aucune commande à saisir et aucun Python à installer.** Le premier démarrage peut prendre quelques secondes pendant l’ouverture du paquet. L’application cible Windows 10/11 64 bits. Elle n’est pas signée numériquement ; les réglages de sécurité du destinataire peuvent en empêcher le lancement.

Vous pouvez envoyer simplement l’exécutable à un autre PC Windows compatible. Les dépendances et l’interface sont incorporées. Le cache est créé dans `data`, et les fichiers cartographiques dans `exports`, **à côté de l’exécutable** : utilisez un dossier dans lequel vous pouvez écrire. Les archives livrées n’incluent aucune de vos zones ou sélections personnelles.

Pour transmettre également vos cartes déjà préparées, fermez Fat Tiles puis copiez son dossier `data` avec l’exécutable. Pour transmettre uniquement une carte exportée, envoyez son fichier MBTiles, SQLiteDB ou ZIP.

## macOS et Linux : paquet du projet

Le paquet **Fat-Tiles-Multiplateforme** contient l’application complète et trois lanceurs :

| Système | Fichier à ouvrir |
| --- | --- |
| Windows avec Python | `demarrer.cmd` |
| macOS avec Python | `demarrer.command` |
| Linux avec Python | `demarrer-linux.sh` → Exécuter comme un programme |

Python **3.10 ou plus récent** doit être présent. À la première utilisation, les deux bibliothèques manquantes sont installées automatiquement ; Internet est alors nécessaire. Sur Linux, Python doit inclure `venv` et `pip`.

Le paquet `.tar.gz` préserve les permissions d’exécution des lanceurs macOS/Linux. Le `.zip` contient les mêmes fichiers, mais certains extracteurs perdent ces permissions : utilisez alors Propriétés → Permissions → Autoriser l’exécution. Selon le bureau Linux, le gestionnaire de fichiers peut proposer « Exécuter dans un terminal » au lieu de lancer le script directement.

Il n’existe pas de fichier exécutable unique natif pour Windows, macOS, Linux, Android et iOS. Le programme Windows autonome a été construit et testé sur ce PC. Les lanceurs macOS/Linux sont fournis, mais n’ont pas été exécutés sur ces systèmes. Le script de construction `build_release.py` permet de fabriquer une application autonome sur chaque ordinateur cible équipé de Python et PyInstaller ; ces autres binaires ne sont pas inclus ici.

## Téléphone et usage sans Internet

Android et iOS utilisent la carte dans leur navigateur, via l’adresse Wi-Fi indiquée par le serveur PC. Les exécutables d’ordinateur ne s’installent pas sur un téléphone. Les zones doivent être téléchargées avant de couper Internet ; le PC reste nécessaire pour l’interface. Sans PC, utilisez le fichier cartographique exporté dans votre lecteur hors ligne.

## Version incluse

- Altitude : de 0 à 8 848,86 mètres (Everest).
- Expositions combinables sur une rose des vents tactile et utilisable au clavier.
- Couleur du masque libre, bleue par défaut, identique dans la légende et les exports.
- OpenTopoMap comme fond initial ; Relief local pour les zones hors ligne.

La couleur choisie est mémorisée dans le navigateur. « Réinitialiser » rétablit le bleu.
