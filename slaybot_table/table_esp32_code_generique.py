import network
import time
import usocket as socket
import ubinascii
import urandom
from machine import Pin, PWM, reset

#-------------------------------------------------------------------------

SSID, PASSWORD = "Slaybot", "MHI-Hotspot"
WS_HOST, WS_PORT = "10.42.0.1", 8765
TARGET_TABLE = 1

COOLDOWN_DURATION = 10 
#-------------------------------------------------------------------------

print(">> SLAYBOT ESP PROGRAM")

class WiFi:
    def __init__(self, ssid, password):
        self.ssid = ssid
        self.password = password
        self.wlan = network.WLAN(network.STA_IF)

    def connect(self):
        self.wlan.active(False)
        time.sleep(1)
        self.wlan.active(True)
        time.sleep(1)
        
        try: network.hostname("Slaybot-Client")
        except: pass
        
        try: self.wlan.config(pm=network.WLAN.PM_NONE)
        except: pass

        print("[1] Connexion a:", self.ssid)
        try:
            self.wlan.connect(self.ssid, self.password)
        except OSError as e:
            print("DRIVER >> ERREUR : ", e)
            return False

        attempts = 0
        while attempts < 30:
            if self.wlan.isconnected():
                print("WIFI >> CONNECTE : ", self.wlan.ifconfig()[0])
                return True
            print(".", end="")
            time.sleep(1)
            attempts += 1
            
        return False

#-------------------------------------------------------------------------

class LED:
    def __init__(self):
        self.R = PWM(Pin(12), freq=1000)
        self.G = PWM(Pin(15), freq=1000)
        self.B = PWM(Pin(26), freq=1000)
        self.off()

    def off(self):
        self.R.duty(0)
        self.G.duty(0)
        self.B.duty(0)

    def set_raw(self, r, g, b):
        self.R.duty(r)
        self.G.duty(g)
        self.B.duty(b)

    def green(self):     self.set_raw(0, 1023, 0)
    def orange(self):    self.set_raw(1023, 250, 0)
    def red(self):       self.set_raw(1023, 0, 0)
    def blue(self):      self.set_raw(0, 0, 1023)

#-------------------------------------------------------------------------

class WSClient:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.sock = None
        self.connected = False

    def connect(self):
        self.connected = False
        try:
            if self.sock:
                try: self.sock.close()
                except: pass

            addr = socket.getaddrinfo(self.host, self.port)[0][4]
            self.sock = socket.socket()
            self.sock.settimeout(3.0)
            self.sock.connect(addr)

            key = ubinascii.b2a_base64(bytes(urandom.getrandbits(8) for _ in range(16))).strip()
            hs = (
                "GET / HTTP/1.1\r\n"
                "Host: {}:{}\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                "Sec-WebSocket-Key: {}\r\n"
                "Sec-WebSocket-Version: 13\r\n\r\n"
            ).format(self.host, self.port, key.decode())

            self.sock.send(hs.encode())
            resp = self.sock.recv(1024)
            if b"101" in resp:
                print("WEBSOCKET >> CONNECTE")
                self.connected = True
                return True
            return False
        except Exception as e:
            print("WEBSOCKET >> ECHEC CO :", e)
            return False

    def send(self, msg):
        if not self.connected: 
            print("WEBSOCKET >> ECHEC ENVOI.")
            return
        try:
            msg = msg.encode()
            mask = bytes(urandom.getrandbits(8) for _ in range(4))
            frame = bytearray([0x81])
            length = len(msg)
            if length < 126:
                frame.append(0x80 | length)
            else:
                frame.append(0x80 | 126)
                frame += length.to_bytes(2, "big")
            frame += mask
            frame += bytearray(msg[i] ^ mask[i % 4] for i in range(len(msg)))
            self.sock.send(frame)
        except Exception as e:
            print("WEBSOCKET >> Erreur:", e)
            self.connected = False

    def receive(self):
        if not self.connected:
            return None
        
        try:
            data = self.sock.recv(1024)
            if not data: 
                self.connected = False
                return None
                
            if len(data) < 2: 
                return None
            
            opcode = data[0] & 0x0F
            if opcode == 0x8: 
                print(">> ERREUR")
                self.connected = False
                return None
                
            payload_len = data[1] & 0x7F
            idx = 2
            
            if payload_len == 126:
                payload_len = int.from_bytes(data[2:4], "big")
                idx = 4
            elif payload_len == 127:
                payload_len = int.from_bytes(data[2:10], "big")
                idx = 10
            
            text_bytes = data[idx:idx + payload_len]
            if not text_bytes: return None
            
            text = text_bytes.decode('utf-8', 'ignore').strip().lower()
            text = text.replace("é", "e").replace("è", "e").replace("à", "a")
            return text
        except OSError:
            return None
        except Exception as e:
            print("WEBSOCKET >> Erreur packet")
            return None

    def flush_buffer(self):
        if not self.connected: return
        try:
            self.sock.settimeout(0.0)
            while True:
                discard = self.sock.recv(1024)
                if not discard: break
        except: pass
        try: self.sock.settimeout(0.01)
        except: pass

#-------------------------------------------------------------------------

class Robot:
    def __init__(self, ws, led, table_number):
        self.ws, self.led = ws, led
        self.table_number = table_number
        self.table_pattern_space = "table {}".format(table_number)
        self.table_pattern_slash = "table/{}".format(table_number)
        
        self.IDLE = 0         
        self.GOING = 1        
        self.ARRIVED = 2      
        self.BAR_COOLDOWN = 3 
        self.EMERGENCY = 4    
        
        self.state = self.IDLE
        self.btn = Pin(14, Pin.IN, Pin.PULL_UP)
        
        self.emergency_start = 0
        self.cooldown_start = 0

    def handle_receive(self, text):
        print("RECV PROPRE:", text)
        
        if "emergency_stop" in text or "urgence" in text:
            print(">> Arrêt d'urgence")
            self.state = self.EMERGENCY
            self.emergency_start = time.ticks_ms()
            return
            
        has_table = (self.table_pattern_space in text) or (self.table_pattern_slash in text)
        has_arrived = "arrived" in text
            
        if self.state == self.IDLE and has_table and not has_arrived:
            self.state = self.GOING
            return
            
        if self.state == self.GOING and has_arrived and has_table:
            self.state = self.ARRIVED
            return

        if self.state == self.ARRIVED and "bar" in text:
            self.state = self.BAR_COOLDOWN
            self.cooldown_start = time.ticks_ms()
            return

    def loop(self):
        now = time.ticks_ms()
        
        if self.state == self.EMERGENCY:
            if time.ticks_diff(now, self.emergency_start) < COOLDOWN_DURATION * 1000:
                if (now // 200) % 2: self.led.red()
                else: self.led.off()
            else: 
                self.ws.flush_buffer()
                self.emergency_start = 0
                self.state = self.IDLE
            return

        if self.state == self.BAR_COOLDOWN:
            self.led.orange()
            if time.ticks_diff(now, self.cooldown_start) >= COOLDOWN_DURATION * 1000: 
                self.ws.flush_buffer()
                self.cooldown_start = 0
                self.state = self.IDLE 
            return 

        if self.state == self.IDLE and self.btn.value() == 0:
            time.sleep(0.05) 
            if self.btn.value() == 0:
                self.ws.send("clean/table/{}".format(self.table_number))
                self.state = self.GOING
                time.sleep(0.5) 

        if self.state == self.GOING:
            if (now // 250) % 2: self.led.orange()
            else: self.led.off()
        elif self.state == self.ARRIVED:
            self.led.green()
        elif self.state == self.IDLE:
            self.led.blue()


#-------------------------------------------------------------------------


led = LED()
wifi = WiFi(SSID, PASSWORD)

if not wifi.connect():
    print("Echec WiFi. Nouvelle tentative soon")
    led.red()
    time.sleep(3)
    reset()

ws = WSClient(WS_HOST, WS_PORT)
ws.connect()

robot = Robot(ws, led, TARGET_TABLE)
print(">> SYSTEM PRET")

while True:
    if not ws.connected:
        led.red()
        print(">> Erreur : tentative de reco ")
        if ws.connect():
            ws.flush_buffer()
        else:
            time.sleep(1)
            continue

    try:
        ws.sock.settimeout(0.01)
    except:
        pass
        
    text_packet = ws.receive()
    if text_packet: 
        robot.handle_receive(text_packet)
    
    robot.loop()
    time.sleep(0.01)