import threading
import websocket
import json
import os
from kivy.app import App
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.properties import StringProperty, ListProperty
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.metrics import dp

try:
    from plyer import notification
except ImportError:
    notification = None

CONFIG_FILE = "config.json"

# Table 1: Rouge | Table 2: Vert | Table 3: Jaune | Table 4: Bleu
TABLE_COLORS = {
    1: (0.9, 0.2, 0.2, 1),
    2: (0.1, 0.6, 0.3, 1),
    3: (0.9, 0.7, 0.1, 1),
    4: (0.1, 0.4, 0.8, 1)
}

# =============================================================================
# GESTION DES COMMUNICATIONS (WebSocket)
# =============================================================================
class RobotAPI:
    ws = None
    online = False
    callback = None
    robot_ip = "10.42.0.1"
    port = 8765

    @staticmethod
    def connect():
        if RobotAPI.ws:
            try:
                RobotAPI.ws.close()
            except:
                pass

        RobotAPI.online = False
        if RobotAPI.callback:
            Clock.schedule_once(lambda dt: RobotAPI.callback(f"Connexion à {RobotAPI.robot_ip}..."))

        def on_msg(ws, message):
            raw = message.strip()
            msg = raw.lower()
            
            is_background = App.get_running_app().root_window is None or Clock.get_fps() < 5

            if msg.startswith("sync/validate/order/"):
                table_id = raw.split("/")[-1]
                if MainScreen.instance:
                    Clock.schedule_once(lambda dt, t=table_id: MainScreen.instance.remote_validate_order(t))
                return
            elif msg.startswith("sync/validate/clean/"):
                table_id = raw.split("/")[-1]
                if MainScreen.instance:
                    Clock.schedule_once(lambda dt, t=table_id: MainScreen.instance.remote_validate_clean(t))
                return
            elif msg.startswith("sync/remove/queue/"):
                task_name = raw.replace("sync/remove/queue/", "")
                if MainScreen.instance:
                    Clock.schedule_once(lambda dt, t=task_name: MainScreen.instance.remote_remove_queue(t))
                return
            elif msg == "sync/emergency_stop":
                if MainScreen.instance:
                    Clock.schedule_once(lambda dt: MainScreen.instance.remote_emergency_stop())
                if is_background and notification:
                    notification.notify(title="Robot-Server", message="ARRÊT D'URGENCE DECLENCHÉ !", timeout=5)
                return

            if msg.startswith("order/table/") or raw.startswith("ORD Table "):
                table_id = raw.split("/")[-1] if "order/table/" in msg else raw.split()[-1]
                if MainScreen.instance:
                    Clock.schedule_once(lambda dt, t=table_id: MainScreen.instance.notify_new_order(t))
                if is_background and notification:
                    notification.notify(title="Nouvelle Commande !", message=f"Table {table_id} demande le robot.", timeout=4)

            elif msg.startswith("clean/table/") or raw.startswith("CLEAN Table "):
                table_id = raw.split("/")[-1] if "clean/table/" in msg else raw.split()[-1]
                if MainScreen.instance:
                    Clock.schedule_once(lambda dt, t=table_id: MainScreen.instance.notify_new_clean(t))
                if is_background and notification:
                    notification.notify(title="Nettoyage requis !", message=f"Table {table_id} doit être nettoyée.", timeout=4)

            elif raw.startswith("CANCEL Table ") or msg.startswith("cancel/table/"):
                table_id = raw.split()[-1] if raw.startswith("CANCEL Table ") else raw.split("/")[-1]
                if MainScreen.instance:
                    Clock.schedule_once(lambda dt, t=table_id: MainScreen.instance.notify_cancel_order(t))

            elif raw.startswith("READY Table ") or msg.startswith("ready/table/"):
                table_id = raw.split()[-1] if raw.startswith("READY Table ") else raw.split("/")[-1]
                if MainScreen.instance:
                    Clock.schedule_once(lambda dt, t=table_id: MainScreen.instance.notify_order_ready(t))

            elif raw.startswith("PAID Table ") or msg.startswith("paid/table/"):
                table_id = raw.split()[-1] if raw.startswith("PAID Table ") else raw.split("/")[-1]
                if MainScreen.instance:
                    Clock.schedule_once(lambda dt, t=table_id: MainScreen.instance.notify_payment(t))

            elif msg == "arrived/bar":
                if MainScreen.instance:
                    Clock.schedule_once(lambda dt: MainScreen.instance.on_mission_complete())
                if is_background and notification:
                    notification.notify(title="Robot-Server", message="Le robot est arrivé au bar.", timeout=3)

        def on_open(ws):
            RobotAPI.online = True
            if RobotAPI.callback:
                Clock.schedule_once(lambda dt: RobotAPI.callback(f"Connecté à {RobotAPI.robot_ip}"))

        def on_close(ws, x, y):
            RobotAPI.online = False
            if RobotAPI.callback:
                Clock.schedule_once(lambda dt: RobotAPI.callback("Déconnecté"))

        def on_error(ws, error):
            RobotAPI.online = False
            if RobotAPI.callback:
                Clock.schedule_once(lambda dt: RobotAPI.callback(f"Erreur connexion : {error}"))

        uri = f"ws://{RobotAPI.robot_ip}:{RobotAPI.port}"
        RobotAPI.ws = websocket.WebSocketApp(uri, on_message=on_msg, on_open=on_open, on_close=on_close, on_error=on_error)
        threading.Thread(target=RobotAPI.ws.run_forever, daemon=True).start()

    @staticmethod
    def send(cmd):
        if RobotAPI.ws and RobotAPI.online:
            try:
                RobotAPI.ws.send(cmd)
            except:
                pass

# =============================================================================
# LOGIQUE INTERFACE PRINCIPALE
# =============================================================================
class MainScreen(Screen):
    instance = None
    status = StringProperty("Connexion...")
    connection_info = StringProperty("")
    queue = ListProperty([])              
    orders_to_prepare = ListProperty([])  
    clean_tasks = ListProperty([])        
    is_busy = False
    active_submenu = None

    def __init__(self, **kw):
        super().__init__(**kw)
        MainScreen.instance = self

    def on_enter(self):
        RobotAPI.callback = self.set_status
        self.connection_info = f"Hotspot: {RobotAPI.robot_ip}:{RobotAPI.port}"
        if not RobotAPI.online:
            self.set_status(f"Connexion à {RobotAPI.robot_ip}..." )
        Clock.schedule_interval(self.check_queue, 1)

    def set_status(self, text):
        self.status = text
        self.connection_info = f"Hotspot: {RobotAPI.robot_ip}:{RobotAPI.port}"

    def reconnect(self):
        self.status = "Tentative de reconnexion..."
        RobotAPI.connect()

    def display_current_tab_state(self):
        if self.active_submenu in ["commande", "nettoyage"]:
            self.toggle_submenu(self.active_submenu)
        else:
            self.update_orders_ui()

    def notify_new_order(self, table_id):
        task = f"ORD Table {table_id}"
        if task not in self.orders_to_prepare and task not in self.queue:
            self.orders_to_prepare.append(task)
            self.display_current_tab_state()

    def notify_cancel_order(self, table_id):
        task = f"ORD Table {table_id}"
        if task in self.orders_to_prepare:
            self.orders_to_prepare.remove(task)
        if task in self.queue:
            self.queue.remove(task)
            self.update_queue_ui()
        self.display_current_tab_state()
        self.status = f"Commande annulée Table {table_id}"

    def notify_order_ready(self, table_id):
        self.status = f"Commande prête Table {table_id}"

    def notify_payment(self, table_id):
        self.status = f"Paiement confirmé Table {table_id}"
        
    def validate_order(self, task_name):
        if task_name in self.orders_to_prepare:
            self.orders_to_prepare.remove(task_name)
            table_id = task_name.split()[-1]
            
            if RobotAPI.online:
                RobotAPI.send(f"sync/validate/order/{table_id}")
                RobotAPI.send(f"go/table/{table_id}")
            
            self.add_to_queue(table_id, task_type="commande")
            self.is_busy = True
            self.status = f"En route (Commande) : Table {table_id}"
            self.display_current_tab_state()

    def remote_validate_order(self, table_id):
        task = f"ORD Table {table_id}"
        if task in self.orders_to_prepare:
            self.orders_to_prepare.remove(task)
        self.add_to_queue(table_id, task_type="commande")
        self.display_current_tab_state()
        self.status = f"Autre appareil : Envoi Table {table_id}"

    # --- Nettoyage ---
    def notify_new_clean(self, table_id):
        task = f"CLEAN Table {table_id}"
        if task not in self.clean_tasks and task not in self.queue:
            self.clean_tasks.append(task)
            self.display_current_tab_state()

    def validate_clean(self, task_name):
        if task_name in self.clean_tasks:
            self.clean_tasks.remove(task_name)
            table_id = task_name.split()[-1]
            
            if RobotAPI.online:
                RobotAPI.send(f"sync/validate/clean/{table_id}")
                RobotAPI.send(f"go/table/{table_id}")
                
            self.add_to_queue(table_id, task_type="nettoyage")
            self.is_busy = True
            self.status = f"En route (Nettoyage) : Table {table_id}"
            self.display_current_tab_state()

    def remote_validate_clean(self, table_id):
        task = f"CLEAN Table {table_id}"
        if task in self.clean_tasks:
            self.clean_tasks.remove(task)
        self.add_to_queue(table_id, task_type="nettoyage")
        self.display_current_tab_state()
        self.status = f"Autre appareil : Nettoyage Table {table_id}"

    def update_orders_ui(self):
        container = self.ids.orders_list
        container.clear_widgets()
        
        if self.active_submenu is None:
            for item in self.orders_to_prepare:
                table_id = int(item.split()[-1])
                btn_color = TABLE_COLORS.get(table_id, (0.3, 0.3, 0.3, 1))
                
                line = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
                lbl = Label(text=f"[b]{item}[/b]\n[size=12sp]À PRÉPARER[/size]", markup=True, halign='left')
                btn = Button(text="PRÊT", size_hint_x=None, width=dp(80),
                             background_normal='', background_color=btn_color)
                btn.bind(on_release=lambda x, it=item: self.validate_order(it))
                line.add_widget(lbl)
                line.add_widget(btn)
                container.add_widget(line)
                
            for item in self.clean_tasks:
                table_id = int(item.split()[-1])
                btn_color = TABLE_COLORS.get(table_id, (0.3, 0.3, 0.3, 1))
                
                line = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
                lbl = Label(text=f"[b]{item}[/b]\n[size=12sp]À NETTOYER[/size]", markup=True, halign='left')
                btn = Button(text="NETTOYÉ", size_hint_x=None, width=dp(80),
                             background_normal='', background_color=btn_color)
                btn.bind(on_release=lambda x, it=item: self.validate_clean(it))
                line.add_widget(lbl)
                line.add_widget(btn)
                container.add_widget(line)

        container.height = max(container.minimum_height, dp(50))

    def add_to_queue(self, table_id, task_type="commande"):
        task = f"ORD Table {table_id}" if task_type=="commande" else f"CLEAN Table {table_id}"
        if task not in self.queue:
            self.queue.append(task)
            self.update_queue_ui()

    def remove_from_queue(self, task_name):
        if task_name in self.queue:
            if self.queue.index(task_name) == 0 and self.is_busy:
                self.is_busy = False
            self.queue.remove(task_name)
            self.update_queue_ui()
            if RobotAPI.online:
                RobotAPI.send(f"sync/remove/queue/{task_name}")

    def remote_remove_queue(self, task_name):
        if task_name in self.queue:
            if self.queue.index(task_name) == 0 and self.is_busy:
                self.is_busy = False
            self.queue.remove(task_name)
            self.update_queue_ui()

    def update_queue_ui(self):
        container = self.ids.queue_list
        container.clear_widgets()
        for item in self.queue:
            line = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(10))
            lbl = Label(text=item, halign='left')
            btn = Button(text="X", size_hint_x=None, width=dp(45),
                         background_normal='', background_color=(0.8, 0.2, 0.2, 1))
            btn.bind(on_release=lambda x, it=item: self.remove_from_queue(it))
            line.add_widget(lbl)
            line.add_widget(btn)
            container.add_widget(line)

    def on_mission_complete(self):
        if self.queue:
            self.queue.pop(0)
            self.update_queue_ui()
        self.is_busy = False
        self.status = "Prêt"

    def check_queue(self, dt):
        if self.queue and not self.is_busy and RobotAPI.online:
            next_task = self.queue[0]
            table_id = next_task.split()[-1]
            RobotAPI.send(f"go/table/{table_id}")
            self.is_busy = True

            if next_task.startswith("ORD"):
                self.status = f"En route (Commande) : Table {table_id}"
            elif next_task.startswith("CLEAN"):
                self.status = f"En route (Nettoyage) : Table {table_id}"
            else:
                self.status = f"En route : Table {table_id}"

    def toggle_submenu(self, task_type):
        container = self.ids.orders_list
        container.clear_widgets()
        
        if self.active_submenu == task_type and container.height > 0:
            self.active_submenu = None
            self.update_orders_ui()
            return

        self.active_submenu = task_type
        box = BoxLayout(orientation='vertical', spacing=dp(10), size_hint_y=None)
        box.height = 0
        
        # Attribution dynamique du code couleur individuel demandé pour chaque bouton table
        for i in range(1, 5):
            table_color = TABLE_COLORS.get(i, (0.3, 0.3, 0.3, 1))
            
            btn = Button(
                text=f"Table {i} ({task_type.upper()})",
                size_hint_y=None,
                height=dp(50),
                background_normal='',
                background_color=table_color
            )
            btn.bind(on_release=lambda x, tid=i, ttype=task_type: self.program_table(tid, ttype))
            box.add_widget(btn)
            box.height += dp(50) + dp(10)
            
        container.add_widget(box)
        container.height = box.height

    def program_table(self, table_id, task_type):
        self.add_to_queue(table_id, task_type)
        self.status = f"Table {table_id} programmée ({task_type})"
        
        if RobotAPI.online:
            RobotAPI.send(f"sync/validate/{task_type}/{table_id}")
            
        self.active_submenu = None
        self.update_orders_ui()

    def emergency_stop(self):
        self.remote_emergency_stop()
        if RobotAPI.online:
            RobotAPI.send("sync/emergency_stop") 
            RobotAPI.send("emergency_stop")

    def remote_emergency_stop(self):
        self.queue.clear()
        self.orders_to_prepare.clear()
        self.clean_tasks.clear()
        self.is_busy = False
        self.active_submenu = None
        self.update_queue_ui()
        self.update_orders_ui()
        self.status = "ARRÊT D'URGENCE INTER-APPLICATIONS !"

    def go_to_bar(self):
        if RobotAPI.online:
            RobotAPI.send("go/bar")
        self.status = "En route vers le bar..."

# =============================================================================
# CONFIGURATION ET CHARGEMENT
# =============================================================================
class SettingsScreen(Screen):
    def on_pre_enter(self):
        ip = RobotAPI.robot_ip or "127.0.0.1"
        self.ids.ip_input.text = ip

    def save_config(self, new_ip):
        ip = new_ip.strip()
        if not ip:
            return
        RobotAPI.robot_ip = ip
        with open(CONFIG_FILE, "w") as f:
            json.dump({"ip": ip}, f)
        RobotAPI.connect()
        self.manager.current = "main"

class RobotApp(App):
    def build(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                try:
                    data = json.load(f)
                    RobotAPI.robot_ip = data.get("ip", "127.0.0.1")
                except:
                    pass
        RobotAPI.connect()
        return Builder.load_string(KV)

# =============================================================================
# STRUCTURE KV
# =============================================================================
KV = '''
<StyledButton@Button>:
    background_normal: ''
    background_down: ''
    font_size: '16sp'
    bold: True
    canvas.before:
        Color:
            rgba: (self.background_color[0]*0.6, self.background_color[1]*0.6, self.background_color[2]*0.6, 1) if self.state == 'down' else self.background_color
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(10)]

ScreenManager:
    MainScreen:
    SettingsScreen:

<MainScreen>:
    name: "main"
    BoxLayout:
        orientation: "horizontal"
        canvas.before:
            Color:
                rgb: 0.08, 0.08, 0.12
            Rectangle:
                pos: self.pos
                size: self.size

        BoxLayout:
            orientation: "vertical"
            padding: dp(20)
            spacing: dp(15)

            Label:
                text: root.status
                font_size: "22sp"
                bold: True
                color: (0, 0.4, 0.9, 1) if "Connecté" in self.text or "route" in self.text else (0.9, 0.2, 0.2, 1)
                size_hint_y: None
                height: dp(50)
                halign: 'left'
                valign: 'middle'
                text_size: self.size

            Label:
                text: root.connection_info
                font_size: "14sp"
                color: (0.8, 0.8, 0.9, 1)
                size_hint_y: None
                height: dp(24)
                halign: 'left'
                valign: 'middle'
                text_size: self.size

            StyledButton:
                text: "Commande"
                size_hint_y: None
                height: dp(50)
                background_color: 0.2, 0.4, 0.3, 1
                on_release: root.toggle_submenu("commande")

            StyledButton:
                text: "Nettoyage"
                size_hint_y: None
                height: dp(50)
                background_color: 0.5, 0.4, 0.3, 1
                on_release: root.toggle_submenu("nettoyage")

            Widget:
                size_hint_y: 1 

            BoxLayout:
                size_hint_y: None
                height: dp(55)
                spacing: dp(10)
                StyledButton:
                    text: "RECO"
                    background_color: 0.1, 0.5, 0.3, 1
                    on_press: root.reconnect()
                StyledButton:
                    text: "ARRÊT"
                    background_color: 0.8, 0.1, 0.1, 1
                    on_press: root.emergency_stop()
                StyledButton:
                    text: "BAR  "
                    background_color: 0.4, 0.4, 0.8, 1
                    on_press: root.go_to_bar()
                StyledButton:
                    text: "PARAMS"
                    background_color: 0.3, 0.3, 0.3, 1
                    on_press: app.root.current = "settings"

        BoxLayout:
            orientation: "vertical"
            size_hint_x: 0.55
            padding: dp(15)
            spacing: dp(10)
            canvas.before:
                Color:
                    rgb: 0.14, 0.14, 0.18
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [dp(20), 0, 0, dp(20)]

            Label:
                text: "--- RECEPTION ---"
                bold: True
                color: 1, 0.7, 0, 1
                size_hint_y: None
                height: dp(30)

            ScrollView:
                size_hint_y: 0.5
                BoxLayout:
                    id: orders_list
                    orientation: "vertical"
                    size_hint_y: None
                    height: self.minimum_height
                    spacing: dp(8)

            Widget:
                size_hint_y: None
                height: dp(2)
                canvas:
                    Color:
                        rgba: 1, 1, 1, 0.1
                    Rectangle:
                        pos: self.pos
                        size: self.size

            Label:
                text: "--- ROBOT ---"
                bold: True
                color: 0.5, 0.7, 1, 1
                size_hint_y: None
                height: dp(30)

            ScrollView:
                size_hint_y: 0.5
                BoxLayout:
                    id: queue_list
                    orientation: "vertical"
                    size_hint_y: None
                    height: self.minimum_height
                    spacing: dp(8)

<SettingsScreen>:
    name: "settings"
    BoxLayout:
        orientation: "vertical"
        padding: dp(40)
        spacing: dp(20)
        canvas.before:
            Color:
                rgb: 0.08, 0.08, 0.12
            Rectangle:
                pos: self.pos
                size: self.size

        Label:
            text: "CONFIGURATION IP"
            font_size: "24sp"
            bold: True
            size_hint_y: None
            height: dp(60)

        TextInput:
            id: ip_input
            text: "127.0.0.1"
            multiline: False
            size_hint_y: None
            height: dp(50)
            font_size: "18sp"

        StyledButton:
            text: "ENREGISTRER"
            size_hint_y: None
            height: dp(60)
            background_color: 0.1, 0.6, 0.3, 1
            on_press: root.save_config(ip_input.text)
        
        StyledButton:
            text: "RETOUR"
            size_hint_y: None
            height: dp(60)
            background_color: 0.6, 0.2, 0.2, 1
            on_press: app.root.current = "main"
        
        Widget:
'''

if __name__ == "__main__":
    RobotApp().run()