# API Python de SlayBot

Cette page documente l'API Python complète de SlayBot, générée automatiquement à partir du code source via **mkdocstrings**.

## À propos de cette documentation

La documentation API est générée dynamiquement des docstrings du code Python. Elle couvre :

- **Signatures de fonctions** : paramètres, types de retour, valeurs par défaut.
- **Docstrings** : descriptions détaillées des comportements et des cas d'usage.
- **Annotations de type** : indicateurs clairs des types attendus et retournés.
- **Constantes publiques** : variables exposées par chaque module.

> Le dossier racine du projet est ajouté automatiquement au `PYTHONPATH` dans `mkdocs.yml`, permettant à mkdocstrings d'importer tous les modules sans installation supplémentaire.

Modules documentés

Chaque module correspond à un composant du système SlayBot.


Application Android principale.

:::slaybot_apk

Système de vision par ordinateur pour navigation autonome.

:::slaybot_camera

Gestion du serveur central et des communications réseau.

:::slaybot_hotspot

:::slaybot_hotspot.templates.app

Gestion de l'affichage et de l'interface visuelle.

:::slaybot_screen

Logique embarquée pour la table (ESP32).

:::slaybot_table

Outils de simulation et de développement.

:::slaybot_utilitaire_dev

site de comande du restaurant 

:::site_commande.restaurant_site.app

Utilisation
Lancer le serveur de documentation en local
.\.venv\Scripts\mkdocs.exe serve

Le site sera accessible à l’adresse suivante :
http://127.0.0.1:8000

Générer le site statique
.\.venv\Scripts\mkdocs.exe build --clean

Les fichiers générés seront disponibles dans le dossier site/.

Dépannage

Si certains modules ne s’affichent pas correctement :

vérifier que le PYTHONPATH est bien configuré dans mkdocs.yml,
s’assurer que toutes les dépendances sont installées,
consulter les erreurs affichées dans la console lors de mkdocs serve.