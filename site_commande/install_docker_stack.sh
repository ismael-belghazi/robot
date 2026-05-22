#!/bin/bash
set -e

APP_NAME="restaurant_site"
APP_DIR="$HOME/Documents/site_commande/restaurant_site"
SRC_DIR="$APP_DIR" 

echo "=== Mise à jour du système ==="
sudo apt update && sudo apt upgrade -y

echo "=== Installation des dépendances ==="
sudo apt install -y ca-certificates curl gnupg lsb-release git rsync inotify-tools

echo "=== Installation de Docker ==="
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
"deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
$(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
| sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "=== Activation de Docker ==="
sudo systemctl enable docker
sudo systemctl start docker

echo "=== Ajout de l'utilisateur au groupe Docker ==="
sudo usermod -aG docker $USER || true

echo "=== Création du dossier projet ==="
mkdir -p "$APP_DIR"

echo "=== Synchronisation du projet dans $APP_DIR ==="
rsync -av --delete "$SRC_DIR/" "$APP_DIR/"

echo "=== Correction des permissions ==="
sudo chown -R $USER:$USER "$APP_DIR"
chmod -R 755 "$APP_DIR"

echo "=== Création du service systemd principal ==="
sudo tee /etc/systemd/system/${APP_NAME}.service > /dev/null <<EOF
[Unit]
Description=Restaurant Site Docker Stack
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
WorkingDirectory=$APP_DIR
ExecStart=/usr/bin/docker compose up -d --build
ExecStop=/usr/bin/docker compose down
RemainAfterExit=yes
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ${APP_NAME}.service

echo "=== Démarrage initial du container ==="
sudo systemctl start ${APP_NAME}.service

echo "=== Création du service systemd Auto-Update ==="
sudo tee /etc/systemd/system/auto_update_docker.service > /dev/null <<EOF
[Unit]
Description=Auto-Update Docker container on file changes
After=docker.service
Requires=docker.service

[Service]
Type=simple
ExecStart=/bin/bash -c 'while inotifywait -r -e modify,create,delete,move "$SRC_DIR"; do echo "\$(date): Changement détecté, redémarrage Docker..."; cd "$APP_DIR"; docker compose restart web; done'
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable auto_update_docker.service
sudo systemctl start auto_update_docker.service

echo "=== Installation et configuration terminées ! ==="
echo ""
echo "Le projet fonctionne en mode autonome :"
echo "- Tout changement dans $SRC_DIR redémarrera automatiquement le container Docker"
echo "- Flask prendra en compte les modifications grâce aux volumes"
echo ""
echo "Commandes utiles :"
echo "docker compose restart web"
echo "docker compose logs -f"