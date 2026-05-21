import tkinter as tk
import asyncio
import threading
import websockets
import random
import time
import math

# --- CONFIGURATION ---
SERVER_IP = "10.42.0.1"
PORT = 8765
ADMIN_PASSWORD = "2403"
VERSION = "v4.1-MHI-INC"

class SlayBotTactical:
    def __init__(self, root):
        self.root = root
        self.root.title(f"SLAYBOT_OS_{VERSION}")
        
        self.root.configure(bg="#000500")
        self.root.overrideredirect(True)
        self.w = self.root.winfo_screenwidth()
        self.h = self.root.winfo_screenheight()
        self.root.geometry(f"{self.w}x{self.h}+0+0")
        self.root.attributes("-topmost", True)
        self.root.config(cursor="none")
        
        self.frame_count = 0
        self.pulse_val = 0
        self.pulse_dir = 1
        
        self.ws = None
        self.loop = None 
        self.connected = False
        self.state = "booting"
        self.boot_logs = []
        self.boot_progress = 0
        self.eye_height = 1.0

        self.canvas = tk.Canvas(root, bg="#000500", highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)

        # Lancement des processus
        threading.Thread(target=self.run_boot, daemon=True).start()
        
        # Bindings
        self.canvas.bind("<Button-1>", self.handle_click)
        
        self.update_ui()
        self.blink_logic()

    # --- LOGIQUE DE BOOT (UI) ---
    def run_boot(self):
        # Phase 1 : Le boot qui va crash (effect visuel volontaire pour rentre ca plus estetique)
        log_msgs_1 = [
            "INITIALIZING KERNEL_V4.2...",
            "CHECKING RAM_INTEGRITY... OK",
            "LOADING NEURAL_DRIVERS... DONE",
            "MOUNTING /DEV/SERIAL_0... OK",
            "BYPASSING SECURITY_PROTOCOL... DONE",
            "ERROR: MODULE_BERCHE DETECTED",
            "ENABLING TACTICAL_HUD_V3...",
            "DELETING MODULE_BERCHE... [OK]",
            "CRITICAL ERROR: BLUE BUTTON PRESSED BY USER:Marie",
            "REBOOTING SYSTEM..."
        ]

        for msg in log_msgs_1:
            self.boot_logs.append(f"[SYS] {msg}")
            if len(self.boot_logs) > 8: self.boot_logs.pop(0)
            speed = random.uniform(0.04, 0.12)
            for _ in range(10):
                self.boot_progress += 0.5
                time.sleep(speed)
            
            if "REBOOTING" in msg:
                time.sleep(1)
                self.boot_logs = []
                self.boot_progress = 0
                time.sleep(1.5)
                break

        # Phase 2 : Recovery
        self.boot_logs.append("[!] RECOVERY MODE ACTIVE")
        log_msgs_2 = [
            "RE-SYNCING SERVO_MOTORS...",
            "RE-ESTABLISHING CORE_LINK...",
            "SCANNING FOR CORE_SERVER..."
        ]

        for msg in log_msgs_2:
            self.boot_logs.append(f"[SYS] {msg}")
            for _ in range(10):
                self.boot_progress += 2.5
                time.sleep(0.04)

        time.sleep(1.5)
        self.boot_progress = 100
        self.boot_logs.append("[!] BOOT COMPLETE. STARTING OS...")
        time.sleep(1)
        self.state = "idle"

    # --- GESTION RÉSEAU ---
    async def listen(self):
        uri = f"ws://{SERVER_IP}:{PORT}"
        while True:
            try:
                async with websockets.connect(uri) as ws:
                    self.ws = ws
                    self.connected = True
                    await ws.send("STATUS/TACTICAL_CONNECTED")
                    async for msg in ws:
                        m = msg.lower()
                        print(f"Received: {m}") 

                        if "go/table" in m or "clean/table" in m or "statut: deplacement" in m:
                            self.state = "moving"
                        elif "arrived" in m or "arrivé" in m:
                            if "bar" in m:
                                self.state = "idle" 
                            else:
                                self.state = "arrived" 
                        elif "emergency" in m:
                            self.state = "emergency"
                                
            except Exception as e:
                print(f"Erreur connexion: {e}")
                self.connected = False
                self.ws = None
                await asyncio.sleep(2)

    def start_network(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.listen())

    def emergency_shutdown(self):
        if self.ws and self.loop:
            asyncio.run_coroutine_threadsafe(
                self.ws.send("[WARNING] !!! EMERGENCY STOP !!!"), 
                self.loop
            )
        self.state = "emergency"

    def confirm_reception(self):
        if self.ws and self.loop:
            asyncio.run_coroutine_threadsafe(
                self.ws.send("status/received"), 
                self.loop
            )
        self.state = "idle" 
            
    def handle_click(self, event):
        scale = self.h / 1000 
        
        if self.state == "emergency":
            self.state = "idle"
            print("[SYS] EMERGENCY RESET BY OPERATOR")
            return

        if event.x > self.w - 100 and event.y > self.h - 100:
            self.show_numpad()
                
        elif event.x > self.w - 120 and event.y < 80:
            self.emergency_shutdown()
            
        elif self.state == "arrived":
            cx, cy = self.w/2, self.h/2
            my = cy + 150 * scale
            bw, bh = 240 * scale, 70 * scale
            if cx-bw < event.x < cx+bw and my < event.y < my+bh:
                self.confirm_reception()

    def show_numpad(self):
        self.root.config(cursor="arrow")
        win = tk.Toplevel(self.root)
        win.geometry("300x450")
        win.configure(bg="#000")
        win.overrideredirect(True)
        win.geometry(f"+{int(self.w/2-150)}+{int(self.h/2-225)}")
        win.attributes("-topmost", True)
        
        entry_var = tk.StringVar()
        tk.Label(win, textvariable=entry_var, font=("Courier", 24), bg="#000", fg="#0f0").pack(pady=10)
        
        def press(k):
            if k == 'EXIT': 
                win.destroy()
                self.root.config(cursor="none")
            elif k == 'OFF' and entry_var.get() == ADMIN_PASSWORD: 
                self.root.destroy()
            elif k == 'C': 
                entry_var.set("")
            else: 
                entry_var.set(entry_var.get() + k)

        frame = tk.Frame(win, bg="#000")
        frame.pack()
        btns = ['7','8','9','4','5','6','1','2','3','C','0','OFF']
        for i, b in enumerate(btns):
            tk.Button(frame, text=b, width=5, height=2, bg="#001100", fg="#0f0", font=("Courier", 12, "bold"),
                      command=lambda x=b: press(x)).grid(row=i//3, column=i%3, padx=5, pady=5)
        
        tk.Button(win, text="[ CLOSE UI ]", bg="#300", fg="red", command=lambda: press('EXIT')).pack(fill="x", pady=10)

    # --- DESSIN & UI ---
    def update_ui(self):
        try:
            self.canvas.delete("all")
            self.frame_count += 1 
            cx, cy = self.w/2, self.h/2

            main_color = "#0f0" if (self.connected and self.state != "emergency") else "#f00"

            # 1. Scanlines CRT (Fond)
            for i in range(0, self.h, 4):
                self.canvas.create_line(0, i, self.w, i, fill="#000700")

            # 2. Effet Radar
            scan_y = (self.frame_count * 7) % self.h
            self.canvas.create_line(0, scan_y, self.w, scan_y, fill="#005500", width=3)
            self.canvas.create_line(0, scan_y-10, self.w, scan_y-10, fill="#025A02", width=1)
            if self.state == "booting":
                self.draw_boot_screen(cx, cy)
            else:
                self.draw_tactical_hud(cx, cy)
                self.draw_face(cx, cy, main_color)
                self.draw_tactical_buttons()

        except Exception as e:
            print(f"UI DRAW ERROR: {e}")
        
        self.root.after(16, self.update_ui)

    def draw_boot_screen(self, cx, cy):
        self.canvas.create_text(cx, cy-120, text="--- SLAYBOT MIL-SPEC BOOT ---", fill="#0f0", font=("Courier", 20, "bold"))
        self.canvas.create_rectangle(cx-200, cy-20, cx+200, cy, outline="#0f0")
        self.canvas.create_rectangle(cx-200, cy-20, cx-200 + (4*self.boot_progress), cy, fill="#0f0")
        for i, log in enumerate(self.boot_logs):
            self.canvas.create_text(cx, cy+50+(i*20), text=log, fill="#0f0", font=("Courier", 10))

    def draw_tactical_hud(self, cx, cy):
        color = "#0f0" if (self.connected and self.state != "emergency") else "#f00"
        d, s = 200, 40
        # Coins de visée
        self.canvas.create_line(cx-d, cy-d, cx-d+s, cy-d, fill=color, width=2)
        self.canvas.create_line(cx-d, cy-d, cx-d, cy-d+s, fill=color, width=2)
        self.canvas.create_line(cx+d, cy+d, cx+d-s, cy+d, fill=color, width=2)
        self.canvas.create_line(cx+d, cy+d, cx+d, cy+d-s, fill=color, width=2)
        
        status = "CORE_LINK: STABLE" if self.connected else "CORE_LINK: LOST - ANGRY_MODE"
        if self.state == "emergency": status = "CRITICAL: EMERGENCY_STOP_ACTIVE"
        
        self.canvas.create_text(20, self.h-30, text=f"> {status} | {self.state.upper()} | {VERSION}", fill=color, anchor="w", font=("Courier", 12))

    def draw_face(self, cx, cy, color):
            s = self.h / 1000 
            glow_color = "#001a00" if color == "#0f0" else "#1a0000"
            
            # --- 1. EFFET GLITCH (Si Emergency ou Déconnecté) ---
            gx, gy = 0, 0
            if self.state == "emergency" or not self.connected:
                gx = random.randint(-3, 3)
                gy = random.randint(-3, 3)

            # --- 2. LE NOEUD PAPILLON ---
            bx, by = cx + gx, cy + 240 * s + gy
            bw, bh = 50 * s, 28 * s
            self.canvas.create_polygon(bx, by, bx-bw, by-bh, bx-bw, by+bh, outline=color, fill="#000500", width=2)
            self.canvas.create_polygon(bx, by, bx+bw, by-bh, bx+bw, by+bh, outline=color, fill="#000500", width=2)
            self.canvas.create_rectangle(bx-8*s, by-8*s, bx+8*s, by+8*s, outline=color, fill=color)

            # --- 3. PARAMÈTRES D'EXPRESSION ---
            if self.state == "moving":
                m_curve, eye_y_off, m_style = 0.6, -10*s, 1
            elif self.state == "emergency" or not self.connected:
                m_curve, eye_y_off, m_style = -1.5, -20*s, 1
            elif self.state == "arrived":
                m_curve, eye_y_off, m_style = 1.8, 10*s, 1
            else: # IDLE
                m_curve, eye_y_off, m_style = 0.1, 0, 1

            # --- 4. LES YEUX & SOURCILS ---
            for side in [-1, 1]:
                ex = cx + (side * 160 * s) + gx
                ey = cy - 40 * s + eye_y_off + gy
                h = 80 * s * self.eye_height
                
                self.canvas.create_oval(ex-65*s, ey-h-5, ex+65*s, ey+h+5, outline=glow_color, width=2)
                self.canvas.create_oval(ex-60*s, ey-h, ex+60*s, ey+h, outline=color, width=4)
                
                if self.eye_height > 0.4:
                    if self.state == "emergency":
                        # Yeux en X
                        self.canvas.create_line(ex-15*s, ey-15*s, ex+15*s, ey+15*s, fill=color, width=3)
                        self.canvas.create_line(ex+15*s, ey-15*s, ex-15*s, ey+15*s, fill=color, width=3)
                    else:
                        px = math.sin(self.frame_count * 0.05) * 8 * s if self.state == "idle" else 0
                        self.canvas.create_oval(ex-12*s+px, ey-12*s, ex+12*s+px, ey+12*s, fill=color)

                brow_y = ey - 100 * s
                if self.state == "emergency" or not self.connected: # Colère /!\
                    self.canvas.create_line(ex-60*s, brow_y-20*s, ex+40*s*side, brow_y+20*s, fill=color, width=5)
                elif self.state == "arrived": # Content
                    self.canvas.create_line(ex-60*s, brow_y+10*s, ex+60*s, brow_y, fill=color, width=5)

            # --- 5. LA BOUCHE ---
            my = cy + 150 * s + gy
            if self.state == "arrived":
                bw_btn, bh_btn = 240 * s, 70 * s
                self.canvas.create_rectangle(cx-bw_btn, my, cx+bw_btn, my+bh_btn, outline=color, width=4, fill="#001500")
                self.canvas.create_text(cx, my+bh_btn/2, text=">> CONFIRM SYSTEM <<", fill=color, font=("Courier", int(18*s), "bold"))
            else:
                mw = 100 * s
                ctrl_y = my + (m_curve * 50 * s)
                self.canvas.create_line(cx-mw, my, cx, ctrl_y, cx+mw, my, fill=color, width=6, smooth=True)

    def draw_tactical_buttons(self):
        self.canvas.create_rectangle(self.w-70, self.h-70, self.w-20, self.h-20, outline="#0f0", width=2)
        self.canvas.create_text(self.w-45, self.h-45, text="CMD", fill="#0f0", font=("Courier", 10, "bold"))
        
        self.canvas.create_rectangle(self.w-110, 20, self.w-20, 70, outline="red", width=2)
        self.canvas.create_text(self.w-65, 45, text="KILL_SW", fill="red", font=("Courier", 10, "bold"))

    def blink_logic(self):
            if self.state != "booting" and self.state != "emergency":
                self.eye_height = 0.05
                self.root.after(80, lambda: setattr(self, 'eye_height', 1.0))
            
            # Fréquence de clignotement aléatoire
            next_blink = random.randint(2000, 5000) if self.state == "idle" else 8000
            self.root.after(next_blink, self.blink_logic)

# --- EXECUTION ---
if __name__ == "__main__":
    root = tk.Tk()
    app = SlayBotTactical(root)
    threading.Thread(target=app.start_network, daemon=True).start()
    root.mainloop()