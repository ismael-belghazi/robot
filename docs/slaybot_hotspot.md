# slaybot_hotspot

Le module `slaybot_hotspot` constitue le cerveau central du système SlayBot, gérant le hotspot WiFi, le serveur WebSocket de communication, et l'interface de monitoring système.

## Objectif

Fournir l'infrastructure réseau et de communication pour :
- Créer un réseau WiFi isolé pour tous les composants.
- Orchestrer les communications temps réel via WebSocket.
- Piloter les déplacements du robot via scripts Python.
- Surveiller les métriques système (CPU, RAM, réseau).
- Gérer les arrêts d'urgence et la diffusion d'événements.

## Composants

- `serveur_cerveau.py` : Serveur WebSocket asynchrone avec gestion des connexions et routage.
- `templates/app.py` : Interface web Flask pour monitoring système.
- `templates/index.html` : Dashboard de surveillance avec métriques temps réel.
- `install-hotspot.sh` : Installation automatique hotspot et dépendances.
- `robot.service` : Service systemd pour démarrage automatique.
- `requirements.txt` : Dépendances (websockets, flask, psutil).

## Classes et fonctions principales

### Fonctions serveur_cerveau.py
- `broadcast_system(message, exclude_path)` : Diffusion à tous clients.
- `move_robot(target_type, target_id)` : Lance script pilotage.
- `emergency_stop()` : Arrêt d'urgence, terminaison processus.
- `handler(websocket)` : Gestionnaire connexions WebSocket.

### Routes Flask (app.py)
- `/` : Dashboard monitoring.
- `/stats` : API JSON métriques système.

## Endpoints WebSocket

- `/` : Connexion générale (APK, site web, tables).
- `/pilote` : Données pilotage (angle, couleur) caméra.

## Flux de communication

### Réception commande
1. Site envoie `order/table/5`.
2. Diffusion à APK et robot.
3. APK valide, envoie `go/table/5`.
4. Serveur lance `pilote.py table 5`.
5. Arrivée : `arrived/table/5`.

### Pilotage automatique
- Caméra envoie `{"angle": 15, "color": "JAUNE"}` à `/pilote`.
- Stocké dans `/dev/shm/steering_angle`.
- Script lit angle pour ajustements direction.

## Messages supportés

### Reçus
- `go/table/X` : Déplacement table X.
- `go/bar` : Retour bar.
- `emergency_stop` : Arrêt urgence.
- `status/received` : Confirmation livraison.

### Envoyés
- `arrived/table/X` : Arrivée table X.
- `arrived/bar` : Arrivée bar.
- `emergency_stop` : Signal urgence.

## Installation et configuration

### Installation automatique
```bash
chmod +x install-hotspot.sh
./install-hotspot.sh
# Option 0 : hotspot complet
```

### Configuration réseau
- SSID : `Slaybot`
- Password : `MHI-Hotspot`
- IP : `10.42.0.1`
- Port WS : `8765`
- Port web : `5000`

### Démarrage service
```bash
sudo systemctl enable robot.service
sudo systemctl start robot.service
```

## API du module

::: slaybot_hotspot.serveur_cerveau
::: site_commande.restaurant_site.app

## Maintenance

- **Service** : `sudo systemctl status robot`
- **Logs** : `journalctl -u robot -f`
- **Redémarrer** : `sudo systemctl restart robot`
- **Monitoring** : `http://10.42.0.1:5000/`

## Dépannage

- **Connexion perdue** : Vérifier wlan0 (AP) et wlan1 (internet).
- **Processus bloqué** : Arrêt urgence depuis APK.
- **Température** : Surveiller via dashboard (>70°C ventiler).
- `clean/table/X` : demande de nettoyage via table X
- `order/table/X` : nouvelle commande de la table X
- `ready/table/X` : notification de préparation
- `cancel/table/X` : annulation de commande
- `paid/table/X` : paiement confirmé

## Notes de maintenance

- `broadcast(message)` envoie le message à tous les clients actifs.
- `piloter_deplacement(table_id)` exécute `pilote.py` et notifie le retour du robot.
- `get_local_ip()` indique l’adresse utilisable du serveur.

## Architecture réseau

- Le hotspot fournit une adresse IP fixe `10.42.0.1`.
- Les clients (APK, écran, ESP32) se connectent à ce réseau privé.
- Le serveur peut diffuser des messages à tous les clients en même temps.

## Logs et maintenance

- Status du service :

```bash
sudo systemctl status robot.service
```

- Logs en direct :

```bash
journalctl -u robot.service -f
```

- Pour arrêter :

```bash
sudo systemctl stop robot.service
```

- Pour redémarrer :

```bash
sudo systemctl restart robot.service
```
