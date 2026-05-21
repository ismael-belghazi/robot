#!/bin/bash

# ==============================================================================
# SlayBot Camera - Script d'installation automatisé v2
# ==============================================================================

set -euo pipefail

# Configuration
APP_NAME="slaybot_camera"
PORT=5001
VENV_DIR=".venv"

# Fonctions utilitaires pour l'affichage
info() { echo -e "\033[1;34m[INFO]\033[0m $1"; }
success() { echo -e "\033[1;32m[OK]\033[0m $1"; }
error() { echo -e "\033[1;31m[ERREUR]\033[0m $1"; exit 1; }

[[ $EUID -ne 0 ]] && error "Ce script doit être exécuté avec sudo."

USER_NAME=${SUDO_USER:-$USER}
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
INPUT_ARG=${1:-0} 

if [[ "$INPUT_ARG" == "1" ]]; then
    info "Désinstallation complète de SlayBot Camera (Mode 1)..."
    systemctl stop "${APP_NAME}.service" || true
    systemctl disable "${APP_NAME}.service" || true
    rm -f "/etc/systemd/system/${APP_NAME}.service"
    systemctl daemon-reload
    rm -rf "${SCRIPT_DIR}/${VENV_DIR}"
    success "Désinstallation terminée."
    exit 0
fi

info "Installation de SlayBot Camera (Mode 0)..."
systemctl stop "${APP_NAME}.service" 2>/dev/null || true

info "Nettoyage des anciens processus..."
sudo fuser -k /dev/video0 2>/dev/null || true
sudo kill -9 $(sudo lsof -t -i:$PORT) 2>/dev/null || true

info "Installation des dépendances système (Inclus libcap-dev pour Picamera2)..."
apt-get update -qq && apt-get install -y python3-pip python3-venv v4l-utils libopenblas-dev libgl1 libcap-dev > /dev/null

info "Configuration de l'environnement Python avec accès aux paquets système..."
cd "${SCRIPT_DIR}"
sudo -u "$USER_NAME" python3 -m venv --system-site-packages "$VENV_DIR"
sudo -u "$USER_NAME" "$VENV_DIR/bin/pip" install --upgrade pip -q

info "Installation des modules Python (Flask, OpenCV, Picamera2, Websockets)..."
sudo -u "$USER_NAME" "$VENV_DIR/bin/pip" install flask opencv-python numpy websockets picamera2 > /dev/null

info "Configuration du service Systemd..."
cat <<EOF > "/etc/systemd/system/${APP_NAME}.service"
[Unit]
Description=SlayBot Camera Streaming Service
After=network.target

[Service]
User=$USER_NAME
WorkingDirectory=${SCRIPT_DIR}
Environment="CAMERA_PORT=$PORT"
# Exécution directe en python standard pour éviter les problèmes de chemin d'accès dans le service
ExecStart=${SCRIPT_DIR}/${VENV_DIR}/bin/python3 ${SCRIPT_DIR}/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "${APP_NAME}.service"
systemctl start "${APP_NAME}.service"

success "SlayBot Camera est installé avec support natif Picamera2 !"
info "-------------------------------------------------------"
info "  - Interface Live  : http://$(hostname -I | cut -d' ' -f1):$PORT"
info "  - WebSocket Sortie: ws://10.42.0.1:8765/pilote"
info "  - Désinstaller    : sudo ./install-camera.sh 1"
info "-------------------------------------------------------"