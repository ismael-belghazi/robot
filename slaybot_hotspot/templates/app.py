import os
import subprocess
import time
import spidev
from flask import Flask, render_template, jsonify, make_response

app = Flask(__name__, template_folder='.')

# ==============================================================================
# CONFIGURATION MATÉRIELLE AJUSTÉE (MCP3008 en 5V)
# ==============================================================================
V_REF = 5.0            # Alimentation et référence de l'ADC à 5V

# Rapports des ponts diviseurs physiques sur chaque canal (R_total / R_ground)
# À ajuster selon les résistances réelles soudées sur le PCB :
PONT_CH0 = 1.014   # Cellule 1 seule (~4.2V max -> pas besoin de diviser beaucoup)
PONT_CH1 = 2.0     # Cellule 1 + Cellule 2 (~8.4V max -> division par 2 nécessaire)
PONT_CH2 = 3.0     # Cellule 1 + 2 + 3 (~12.6V max -> division par 3 nécessaire)
PONT_CH3 = 4.0     # Tension totale LiPo 4S (~16.8V max -> division par 4 nécessaire)

RAPPORTS_PONTS = [PONT_CH0, PONT_CH1, PONT_CH2, PONT_CH3]
# ==============================================================================

spi = spidev.SpiDev()
try:
    spi.open(0, 0)
    spi.max_speed_hz = 1350000
    print("[MATÉRIEL] Liaison SPI avec le MCP3008 en 5V activée.")
except Exception as e:
    print(f"[ERREUR] Impossible d'ouvrir le bus SPI : {e}")

# --- FONCTION INITIALE STRICTEMENT INCHANGÉE ---
def read_adc(channel):
    if channel < 0 or channel > 7:
        return -1
    r = spi.xfer2([1, (8 + channel) << 4, 0])
    data = ((r[1] & 3) << 8) + r[2]
    return data

# --- FONCTION DE CONVERSION (PONT DIVISEUR EN CASCADE) ---
def get_battery_cells():
    tensions_cumulees = []
    
    # 1. Lecture des tensions aux nœuds du connecteur d'équilibrage
    for channel in range(4):
        raw_val = read_adc(channel)
        if raw_val == -1:
            tensions_cumulees.append(0.0)
            continue
            
        # Conversion brute -> Tension réelle au nœud du circuit
        v_adc = (raw_val / 1023.0) * V_REF
        v_noeud = v_adc * RAPPORTS_PONTS[channel]
        tensions_cumulees.append(max(0.0, round(v_noeud, 2)))

    # 2. Déduction du voltage propre à CHAQUE cellule (Soustraction de la cellule précédente)
    cells_list = [
        tensions_cumulees[0],                                           # Cellule 1
        max(0.0, round(tensions_cumulees[1] - tensions_cumulees[0], 2)), # Cellule 2
        max(0.0, round(tensions_cumulees[2] - tensions_cumulees[1], 2)), # Cellule 3
        max(0.0, round(tensions_cumulees[3] - tensions_cumulees[2], 2))  # Cellule 4
    ]

    # La tension totale est directement la tension lue sur le dernier canal (CH3)
    total_voltage = tensions_cumulees[3]
    
    print(f"[TELEMETRIE] Cellules : {cells_list} | Total : {total_voltage}V")
    return cells_list, total_voltage

def get_cpu_temperature():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp = float(f.read()) / 1000.0
            return round(temp, 1)
    except Exception:
        return "N/A"

def get_network_status(interface):
    try:
        cmd = f"nmcli -t -f DEVICE,STATE,CONNECTION device | grep ^{interface}"
        output = subprocess.check_output(cmd, shell=True).decode("utf-8").strip()
        parts = output.split(':')
        if len(parts) >= 3 and parts[1] == "connected":
            return "ONLINE", parts[2]
        return "OFFLINE", "NONE"
    except:
        return "ERROR", "N/A"

def get_signal_strength(interface):
    try:
        cmd = f"nmcli -f IN-USE,SIGNAL,DEVICE dev wifi | grep '*' | grep {interface} | awk '{{print $2}}'"
        signal = subprocess.check_output(cmd, shell=True).decode("utf-8").strip()
        return signal if signal else "0"
    except:
        try:
            cmd = f"grep {interface} /proc/net/wireless | awk '{{print int($3 * 100 / 70)}}'"
            return subprocess.check_output(cmd, shell=True).decode("utf-8").strip()
        except:
            return "0"

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/stats")
def stats():
    # Optimisation : Utilisation des commandes internes ou de calculs directs plus rapides que top
    try:
        cmd = "free | grep Mem | awk '{print $3/$2 * 100.0}'"
        ram_val = float(subprocess.check_output(cmd, shell=True).decode())
    except:
        ram_val = 0

    try:
        # Remplacement de top (lent) par un calcul d'intervalle ultra-rapide via /proc/stat
        with open('/proc/stat', 'r') as f:
            fields = [float(column) for column in f.readline().strip().split()[1:]]
        idle_time, total_time = fields[3], sum(fields)
        time.sleep(0.1)
        with open('/proc/stat', 'r') as f:
            fields = [float(column) for column in f.readline().strip().split()[1:]]
        idle_time_2, total_time_2 = fields[3], sum(fields)
        
        cpu_val = 100.0 * (1.0 - (idle_time_2 - idle_time) / (total_time_2 - total_time))
    except:
        cpu_val = 0

    w1_status, w1_ssid = get_network_status("wlan1")
    w1_signal = get_signal_strength("wlan1")
    w0_status, _ = get_network_status("wlan0")
    
    battery_cells, total_voltage = get_battery_cells()

    response_data = jsonify(
        cpu_usage=round(cpu_val, 1),
        ram_usage=round(ram_val, 1),
        inet_signal=w1_signal,
        cpu_temp=get_cpu_temperature(),
        inet_ssid=w1_ssid,
        ap_status=w0_status,
        cells=battery_cells,
        total_voltage=total_voltage
    )
    
    resp = make_response(response_data)
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=False)