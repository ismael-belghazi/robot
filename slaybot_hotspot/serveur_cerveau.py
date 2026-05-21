import asyncio
import websockets
import socket
import os
import json
import logging

# ---------------- CONFIG ----------------
HOST = "0.0.0.0"
PORT = 8765
BASE_DIR = "/home/hotspot/Documents/slaybot_hotspot"
PILOTE_PATH = os.path.join(BASE_DIR, "pilote.py")
ANGLE_FILE = "/dev/shm/steering_angle"
LOG_PILOTE_FILE = os.path.join(BASE_DIR, "pilote.log")

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger("MAIN")

pilote_logger = logging.getLogger("PILOTE")
pilote_logger.setLevel(logging.INFO)
pilote_logger.propagate = False 

fh = logging.FileHandler(LOG_PILOTE_FILE, mode='w')
fh.setFormatter(logging.Formatter('%(asctime)s | %(message)s', datefmt='%H:%M:%S'))
pilote_logger.addHandler(fh)

clients_actifs = set()
process_en_cours = None 
lock = asyncio.Lock()

if not os.path.exists(ANGLE_FILE):
    with open(ANGLE_FILE, "w") as f: f.write("0")

# --- BROADCAST GLOBAL ---
async def broadcast_system(message, exclude_path=None):
    if clients_actifs:
        clean_msg = str(message).lower().strip()
        targets = [c for c in clients_actifs if getattr(c, 'path', '') != exclude_path]
        
        if targets:
            logger.info(f"Broadcast System: {clean_msg} vers {len(targets)} clients")
            await asyncio.gather(*(t.send(clean_msg) for t in targets), return_exceptions=True)
        else:
            logger.warning(f"Aucune cible pour le message : {clean_msg}")
    else:
        logger.warning(f"Aucun client connecté pour : {clean_msg}")

async def broadcast_apk(message):
    await broadcast_system(message, exclude_path="/pilote")

async def run_process(*args):
    global process_en_cours
    async with lock:
        try:
            process_en_cours = await asyncio.create_subprocess_exec(
                *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process_en_cours.communicate()
            code = process_en_cours.returncode
            process_en_cours = None
            return code, stdout.decode(), stderr.decode()
        except Exception as e:
            process_en_cours = None
            logger.error(f"Erreur Process: {e}")
            return -1, "", str(e)

async def move_robot(target_type, target_id=None):
    if target_type == "table":
        logger.info(f"ORDRE : Direction Table {target_id}")
        await broadcast_system(f"statut: deplacement table {target_id}")
        code, out, err = await run_process("python3", PILOTE_PATH, "table", str(target_id))
        msg_suffix = f"table/{target_id}"
    else:
        logger.info("ORDRE : Retour BAR")
        await broadcast_system("statut: deplacement bar")
        code, out, err = await run_process("python3", PILOTE_PATH, "bar")
        msg_suffix = "bar"

    if code == 0:
        logger.info(f"ARRIVÉ (Succès script) : {msg_suffix}")
        await asyncio.sleep(0.5) 
        await broadcast_system(f"arrived/{msg_suffix}")
    else:
        logger.error(f"ÉCHEC script (code {code}): {err}")
        await broadcast_system(f"error/{msg_suffix}")

async def emergency_stop():
    global process_en_cours
    logger.warning("!!! EMERGENCY STOP !!!")
    if process_en_cours:
        try: 
            process_en_cours.terminate()
            logger.info("Processus pilote terminé par Emergency Stop")
        except: 
            pass
        process_en_cours = None
    
    with open(ANGLE_FILE, "w") as f: f.write("0")
    await broadcast_system("emergency_stop")
    await asyncio.sleep(1)
    await broadcast_system("arrived/bar")

async def handler(websocket):
    path = websocket.request.path
    websocket.path = path
    clients_actifs.add(websocket)
    logger.info(f"Connexion établie sur : {path}")
    
    try:
        async for message in websocket:
            if path == "/pilote":
                try:
                    data = json.loads(message)
                    angle = data.get("angle", 0)
                    color = data.get("color", "NONE")
                    msg_pour_robot = f"Angle: {angle} | Couleur: {color}"
                    
                    await broadcast_system(msg_pour_robot, exclude_path=None)
                    logger.info(f"Relais Vision -> Robot: {msg_pour_robot}")
                except Exception as e:
                    logger.error(f"Erreur traitement vision: {e}")
            
            else:
                msg = message.strip().lower()
                logger.info(f"RX (APK/Robot): {msg}")
                
                if msg.startswith("go/table/"):
                    table_id = msg.split("/")[-1]
                    asyncio.create_task(move_robot("table", table_id))
                
                elif msg == "go/bar":
                    asyncio.create_task(move_robot("bar"))
                
                elif msg == "emergency_stop":
                    await emergency_stop()
                
                elif msg == "status/received":
                    await asyncio.sleep(2)
                    asyncio.create_task(move_robot("bar"))
                
                elif any(x in msg for x in ["order/", "clean/", "ready/", "paid/", "status/", "tactical_connected"]):
                    await broadcast_system(msg)

    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Déconnexion de : {path}")
    finally:
        clients_actifs.discard(websocket)

async def main():
    logger.info(f"Serveur SLAYBOT démarré sur ws://{HOST}:{PORT}")
    async with websockets.serve(handler, HOST, PORT):
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Serveur arrêté par l'utilisateur")