#!/bin/bash
# --- SLAYBOT NETWORK SHIELD - V11.8 ULTIMATE (OPTIMISÉ IP FIXE) ---
set -e

# --- CONFIGURATION ---
USER_HOME="/home/hotspot"
LOG_DIR="$USER_HOME/Documents/slaybot_hotspot"
VENV_PATH="$LOG_DIR/venv"
WATCHDOG_SCRIPT="$LOG_DIR/slaybot_watchdog.sh"

WIFI_AP="wlan0"      
WIFI_INET="wlan1"    

MAC_INTERNAL="d8:3a:dd:55:94:13"
MAC_DONGLE="74:da:38:ea:66:3c"

HOTSPOT_SSID="Slaybot"
HOTSPOT_PWD="MHI-Hotspot"
INET_ID="pc-link-internet" 
INET_SSID="raspberry"
INET_PWD="Awawawawa"

# --- VÉRIFICATION ---
if ! command -v nmcli > /dev/null; then
    echo "[!] NetworkManager est requis."
    exit 1
fi

mkdir -p "$LOG_DIR"

echo "======================================================="
echo "       SLAYBOT OS - V12 cristal                        "
echo "======================================================="
echo "Mode : AP=$WIFI_AP | INET=$WIFI_INET"
echo "0: Reset Total & Installation Stable (FIXE 137.60)"
echo "1: Nettoyage et Arrêt Complet"
read -p "Choix : " CHOICE

system_hardening() {
    echo "[1/6] Nettoyage des verrous et forçage RF..."
    sudo fuser -kk /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock 2>/dev/null || true
    
    sudo rfkill unblock all
    sudo iw reg set FR

    sudo chattr -i /etc/resolv.conf 2>/dev/null || true
    echo -e "nameserver 8.8.8.8\nnameserver 1.1.1.1" | sudo tee /etc/resolv.conf > /dev/null

    sudo systemctl stop slaybot-net.service robot.service slaybot_web.service 2>/dev/null || true
    
    sudo sysctl -w net.ipv4.ip_forward=1 >/dev/null
}

install_hotspot() {
    system_hardening

    echo "[2/6] Purge et Mise en Sommeil Radio..."
    sudo nmcli radio wifi off
    sleep 2
    sudo nmcli radio wifi on
    sleep 2

    for con in $(nmcli -g uuid connection show); do
        sudo nmcli connection delete uuid "$con" 2>/dev/null || true
    done

    echo "[3/6] Configuration - Priorité au Dongle USB (FIXE 137.60)..."
    
    sudo nmcli connection add type wifi con-name "$INET_ID" ifname "$WIFI_INET" ssid "$INET_SSID" -- \
        wifi.mode infrastructure wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$INET_PWD" \
        ipv4.method manual ipv4.addresses 192.168.137.60/24 ipv4.gateway 192.168.137.1 \
        ipv4.dns "8.8.8.8,1.1.1.1" ipv4.route-metric 10

    sudo nmcli connection add type wifi con-name "$HOTSPOT_SSID" ifname "$WIFI_AP" ssid "$HOTSPOT_SSID" -- \
        wifi.mode ap wifi.band bg wifi.channel 11 \
        wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$HOTSPOT_PWD" \
        wifi-sec.proto rsn wifi-sec.group ccmp wifi-sec.pairwise ccmp \
        wifi-sec.pmf 1 \
        ipv4.method shared ipv4.addresses 10.42.0.1/24 ipv4.never-default true

    echo "[4/6] Séquençage Chronométré (Critique)..."
    
    echo "[!] Phase 1 : Recherche du PC (wlan1)..."
    if sudo nmcli connection up "$INET_ID"; then
        echo "[OK] Connecté au PC (192.168.137.60)."
    else
        echo "[ECHEC] Le PC reste invisible. On tente un redémarrage..."
        sudo systemctl restart wpa_supplicant
        sleep 5
        sudo nmcli connection up "$INET_ID" || (echo "Abandon." && exit 1)
    fi

    sudo chattr -i /etc/resolv.conf 2>/dev/null || true
    echo -e "nameserver 8.8.8.8\nnameserver 1.1.1.1" | sudo tee /etc/resolv.conf > /dev/null
    sudo chattr +i /etc/resolv.conf

    echo "[!] Phase 2 : Installation Python AVANT activation Hotspot..."
    setup_python_env

    echo "[!] Phase 3 : Ouverture du Hotspot Slaybot..."
    sudo nmcli connection up "$HOTSPOT_SSID"

    sudo iptables -F
    sudo iptables -t nat -F
    sudo iptables -t nat -A POSTROUTING -o "$WIFI_INET" -j MASQUERADE
    sudo iptables -A FORWARD -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
    sudo iptables -A FORWARD -i "$WIFI_AP" -o "$WIFI_INET" -j ACCEPT

    create_robot_service
    create_web_service
    create_services
}

setup_python_env() {
    echo "[5/6] Configuration Réseau & Environnement Python..."

    sudo chattr -i /etc/resolv.conf 2>/dev/null
    sudo tee /etc/resolv.conf <<EOF > /dev/null
nameserver 193.49.184.5
nameserver 193.49.184.17
nameserver 10.0.0.1
search u-picardie.fr
EOF
    sudo chattr +i /etc/resolv.conf 2>/dev/null

    sudo ip route add default via 192.168.137.1 dev "$WIFI_INET" metric 1 2>/dev/null || true

    echo "[!] Installation des librairies (Mode Survie HTTP)..."
    
    "$VENV_PATH/bin/pip" install --no-cache-dir \
        --index-url http://pypi.org/simple \
        --extra-index-url http://pypi.python.org/simple \
        --trusted-host pypi.org \
        --trusted-host files.pythonhosted.org \
        --trusted-host pypi.python.org \
        --timeout 120 \
        flask psutil websockets spidev
}
create_robot_service() {
    sudo bash -c "cat > /etc/systemd/system/robot.service << EOF
[Unit]
Description=Slaybot Robot Core
After=network-online.target
[Service]
Type=simple
User=hotspot
WorkingDirectory=$LOG_DIR
ExecStart=$VENV_PATH/bin/python3 $LOG_DIR/serveur_cerveau.py
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
EOF"
    sudo systemctl daemon-reload
    sudo systemctl enable robot.service && sudo systemctl restart robot.service
}

create_web_service() {
    sudo bash -c "cat > /etc/systemd/system/slaybot_web.service << EOF
[Unit]
Description=Slaybot Web Interface
After=robot.service
[Service]
Type=simple
User=hotspot
WorkingDirectory=$LOG_DIR
ExecStart=$VENV_PATH/bin/python3 $LOG_DIR/templates/app.py
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
EOF"
    sudo systemctl enable slaybot_web.service && sudo systemctl restart slaybot_web.service
}

create_services() {
    cat > "$WATCHDOG_SCRIPT" << 'EOF'
#!/bin/bash
echo "--- SHIELD WATCHDOG INTELLIGENT ACTIVÉ ---"
while true; do
    iw dev wlan0 set power_save off >/dev/null 2>&1

    if ! nmcli -t -f ACTIVE,NAME connection show --active | grep -q "^yes:Slaybot"; then
        echo "RÉPARATION: Relance du Hotspot Slaybot..."
        nmcli connection up "Slaybot" >/dev/null 2>&1
    fi

    if ! nmcli -t -f ACTIVE,NAME connection show --active | grep -q "^yes:pc-link-internet"; then
        echo "RÉPARATION: Relance du lien PC (wlan1)..."
        nmcli connection up "pc-link-internet" >/dev/null 2>&1
    fi

    sleep 10
done
EOF

    chmod +x "$WATCHDOG_SCRIPT"

    sudo bash -c "cat > /etc/systemd/system/slaybot-net.service << EOF
[Unit]
Description=Slaybot Network Watchdog
After=NetworkManager.service

[Service]
ExecStart=/bin/bash $WATCHDOG_SCRIPT
Restart=always
RestartSec=20

[Install]
WantedBy=multi-user.target
EOF"

    sudo systemctl daemon-reload
    sudo systemctl enable --now slaybot-net.service
    sudo systemctl restart slaybot-net.service
}
case "$CHOICE" in
    0) install_hotspot ;;
    1) 
        sudo systemctl stop slaybot-net.service robot.service slaybot_web.service 2>/dev/null || true
        for con in "$HOTSPOT_SSID" "$INET_ID"; do sudo nmcli connection delete "$con" 2>/dev/null || true; done
        sudo chattr -i /etc/resolv.conf 2>/dev/null || true
        sudo systemctl restart NetworkManager
        echo "Arrêt et nettoyage terminés." 
        ;;
    *) exit 1 ;;
esac