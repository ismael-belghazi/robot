import cv2
import numpy as np
import threading
import time
import json
import asyncio
import websockets
import atexit
from flask import Flask, Response, render_template, jsonify
from picamera2 import Picamera2

# ==========================================
# CONFIGURATION ET PARAMÈTRES PID
# ==========================================
KP = 0.32  
KI = 0.002 
KD = 0.22  
MAX_INTEGRAL = 12 

# ==========================================
# CLASSE PRINCIPALE : TRAITEMENT VISION
# ==========================================
class SlayBotVision:
    def __init__(self):
        self.picam = None
        self.running = True
        self.encoded_frame = None 
        
        self.steering_angle = 0
        self.current_color = "NONE"
        self.target_color = "NONE" 
        self.lock = threading.Lock()
        
        self.last_error = 0
        self.integral = 0
        self.base_x = 160 
        self.line_lost_time = 0
        self.last_valid_angle = 0

        self.thread = threading.Thread(target=self._vision_engine, daemon=True)
        self.thread.start()

    def is_valid_line(self, contour, roi_w, roi_h):
        area = cv2.contourArea(contour)
        max_allowed_area = (roi_w * roi_h) * 0.35
        if area < 120 or area > max_allowed_area: 
            return False
        x, y, w, h = cv2.boundingRect(contour)
        aspect_ratio = float(w) / h
        if 0.6 < aspect_ratio < 1.5 and area > 600:
            return False
        hull = cv2.convexHull(contour)
        hull_area = cv2.contourArea(hull)
        solidity = float(area) / hull_area if hull_area > 0 else 0
        return solidity > 0.45 

    def _vision_engine(self):
        try:
            self.picam = Picamera2()
            self.picam.configure(self.picam.create_video_configuration(main={"size": (320, 240)}))
            self.picam.start()
            self.picam.set_controls({"FrameRate": 40, "AwbMode": 3, "AeConstraintMode": 0})
        except Exception as e:
            print(f"Erreur caméra : {e}")
            self.running = False
            return

        ranges = {
            "JAUNE": (np.array([16, 60, 80]), np.array([38, 255, 255])),
            "BLEU":  (np.array([95, 90, 45]), np.array([135, 255, 255])),
            "VERT":  (np.array([40, 50, 50]), np.array([85, 255, 255])),
            "ROUGE": [(np.array([0, 100, 55]), np.array([13, 255, 255])),
                      (np.array([165, 100, 55]), np.array([180, 255, 255]))]
        }

        kernel_open = np.ones((3,3), np.uint8)  
        kernel_close = np.ones((5,5), np.uint8) 

        while self.running:
            try:
                raw_frame = self.picam.capture_array()
            except Exception:
                continue
            if raw_frame is None:
                continue

            h, w = raw_frame.shape[:2]
            roi_rgb = raw_frame[int(h * 0.60):int(h * 0.95), :]
            roi_filtered = cv2.medianBlur(roi_rgb, 3)
            hsv = cv2.cvtColor(roi_filtered, cv2.COLOR_RGB2HSV)
            
            best_mask = None
            
            with self.lock:
                active_target = self.target_color
                detected_color = self.current_color

            if active_target in ranges:
                r = ranges[active_target]
                if active_target == "ROUGE":
                    m = cv2.bitwise_or(cv2.inRange(hsv, r[0][0], r[0][1]), cv2.inRange(hsv, r[1][0], r[1][1]))
                else:
                    m = cv2.inRange(hsv, r[0], r[1])
                
                m = cv2.morphologyEx(m, cv2.MORPH_OPEN, kernel_open)
                m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, kernel_close)
                cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if cnts:
                    c = max(cnts, key=cv2.contourArea)
                    if self.is_valid_line(c, roi_rgb.shape[1], roi_rgb.shape[0]):
                        best_mask = m
                        detected_color = active_target

            if best_mask is None and active_target != "NONE":
                for color_name, r in ranges.items():
                    if color_name == "ROUGE":
                        m = cv2.bitwise_or(cv2.inRange(hsv, r[0][0], r[0][1]), cv2.inRange(hsv, r[1][0], r[1][1]))
                    else:
                        m = cv2.inRange(hsv, r[0], r[1])
                    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, kernel_open)
                    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, kernel_close)
                    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    if cnts:
                        c = max(cnts, key=cv2.contourArea)
                        if self.is_valid_line(c, roi_rgb.shape[1], roi_rgb.shape[0]):
                            detected_color = color_name
                            break

            target_angle = self.steering_angle
            frame = cv2.cvtColor(raw_frame, cv2.COLOR_RGB2BGR)

            if best_mask is not None:
                self.line_lost_time = 0 
                n_windows = 4 
                win_h = best_mask.shape[0] // n_windows
                curr_x = self.base_x
                pts = []

                for i in range(n_windows):
                    y_low = best_mask.shape[0] - (i + 1) * win_h
                    y_high = best_mask.shape[0] - i * win_h
                    x_min, x_max = max(0, int(curr_x - 30)), min(w, int(curr_x + 30))
                    win_roi = best_mask[y_low:y_high, x_min:x_max]
                    M = cv2.moments(win_roi)
                    if M["m00"] > 50: 
                        curr_x = int(M["m10"] / M["m00"]) + x_min
                        pts.append((curr_x, y_low + int(h * 0.60)))

                if len(pts) >= 2:
                    self.base_x = pts[0][0]
                    error = pts[-1][0] - (w // 2)
                    if abs(error) < 2: error = 0 
                    self.integral = np.clip(self.integral + error, -MAX_INTEGRAL, MAX_INTEGRAL)
                    output = (error * KP) + (self.integral * KI) + ((error - self.last_error) * KD)
                    target_angle = np.clip(output, -45, 45)
                    self.last_error = error
                    self.last_valid_angle = target_angle
                    cv2.polylines(frame, [np.array(pts)], False, (0, 255, 0), 2)
            else:
                if self.line_lost_time == 0: self.line_lost_time = time.time()
                if (time.time() - self.line_lost_time) < 0.7:
                    target_angle = self.last_valid_angle
                else:
                    target_angle *= 0.8 

            _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 40])
            with self.lock:
                self.encoded_frame = buffer.tobytes()
                self.steering_angle = int(target_angle)
                self.current_color = detected_color

    def get_stream(self):
        while self.running:
            with self.lock: frame_to_send = self.encoded_frame
            if frame_to_send is not None:
                yield (b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: ' + str(len(frame_to_send)).encode() + b'\r\n\r\n' + frame_to_send + b'\r\n')
            time.sleep(0.02)

    def close(self):
        self.running = False
        if self.picam: self.picam.stop()

# ==========================================
# CLIENT WEBSOCKET (COMMUNICATION SERVEUR)
# ==========================================
async def websocket_client(bot_v):
    uri_ecoute = "ws://10.42.0.1:8765/"        
    uri_envoi = "ws://10.42.0.1:8765/pilote" 
    mapping_tables = {"1": "ROUGE", "2": "VERT", "3": "JAUNE", "4": "BLEU"}
    couleur_table_actuelle = "" 

    async def talk_loop():
        while True:
            try:
                print("DEBUG: Tentative de connexion talk_loop...")
                async with websockets.connect(uri_envoi, ping_interval=5, ping_timeout=5) as ws_talk:
                    print("DEBUG: Connexion réussie à /pilote")
                    while True:
                        with bot_v.lock:
                            col_to_send = bot_v.current_color
                            if col_to_send == "NONE" and bot_v.target_color != "NONE":
                                col_to_send = bot_v.target_color
                                
                            payload = json.dumps({
                                "angle": bot_v.steering_angle, 
                                "color": col_to_send
                            })
                        await ws_talk.send(payload)
                        await asyncio.sleep(0.05)
            except Exception as e:
                print(f"DEBUG: Erreur talk_loop: {e}")
                await asyncio.sleep(0.5)

    async def listen_loop():
        nonlocal couleur_table_actuelle
        while True:
            try:
                async with websockets.connect(uri_ecoute, ping_interval=5, ping_timeout=5) as ws_listen:
                    print("[WS-LISTEN] Connecté au Hotspot.")
                    async for message in ws_listen:
                        msg_clean = message.strip().upper()
                        print(f"[WS-LISTEN] Ordre reçu : '{msg_clean}'")

                        if "TABLE" in msg_clean:
                            table_id = "".join([c for c in msg_clean if c.isdigit()])
                            if table_id in mapping_tables:
                                couleur_table_actuelle = mapping_tables[table_id]
                                with bot_v.lock:
                                    bot_v.target_color = couleur_table_actuelle

                        elif "BAR" in msg_clean:
                            with bot_v.lock:
                                bot_v.target_color = couleur_table_actuelle

            except Exception as e:
                print(f"DEBUG: Erreur listen_loop: {e}")
                await asyncio.sleep(0.5)

    await asyncio.gather(talk_loop(), listen_loop())

# ==========================================
# SERVEUR FLASK ET POINT D'ENTRÉE
# ==========================================
app = Flask(__name__)
bot = SlayBotVision()
atexit.register(bot.close)

@app.route('/')
def index(): return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(bot.get_stream(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status', methods=['GET'])
def status_endpoint():
    with bot.lock:
        angle, color = bot.steering_angle, bot.current_color
    hint = "SEARCHING" if color == "NONE" else f"{color}_{'LEFT' if angle < -5 else 'RIGHT' if angle > 5 else 'FORWARD'}"
    return jsonify({"angle": int(angle), "color": str(color), "hint": str(hint)}), 200

if __name__ == '__main__':
    threading.Thread(target=lambda: asyncio.run(websocket_client(bot)), daemon=True).start()
    app.run(host='0.0.0.0', port=5001, threaded=True, use_reloader=False)