import requests
import json
import os
from kivy.app import App
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.properties import StringProperty, BooleanProperty, ListProperty
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.metrics import dp
from kivy.graphics import Color, RoundedRectangle

ROBOT_IP_DEFAULT = "192.168.1.50"
CONFIG_FILE = "config.json"
TIMEOUT = 1.5
STATUS_INTERVAL = 5  # secondes

# ---------- Robot API ----------
class RobotAPI:
    online = False
    robot_ip = ROBOT_IP_DEFAULT

    @staticmethod
    def send(cmd):
        try:
            requests.get(f"http://{RobotAPI.robot_ip}/{cmd}", timeout=TIMEOUT)
            RobotAPI.online = True
            return True
        except:
            RobotAPI.online = False
            return False

    @staticmethod
    def status():
        try:
            r = requests.get(f"http://{RobotAPI.robot_ip}/status", timeout=TIMEOUT)
            RobotAPI.online = True
            return r.text
        except:
            RobotAPI.online = False
            return "hors ligne"

# ---------- CustomButton (avec couleur et arrondi) ----------
class CustomButton(Button):
    bg_color = ListProperty([0.2, 0.6, 1, 1])  # couleur par défaut

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""  # Désactive l'image de fond
        self.background_color = self.bg_color

    def on_size(self, *args):
        # Gère les coins arrondis de manière plus propre
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self.bg_color)
            RoundedRectangle(size=self.size, pos=self.pos, radius=[dp(20)])

# ---------- MainScreen ----------
class MainScreen(Screen):
    robot_status = StringProperty("Robot : connexion...")
    robot_online = BooleanProperty(False)
    command_queue = []
    robot_busy = False
    emergency_active = False
    _last_status_time = 0

    def on_enter(self):
        Clock.schedule_interval(self.update_robot, 1)

    def update_robot(self, dt):
        if dt - self._last_status_time >= STATUS_INTERVAL:
            status = RobotAPI.status()
            self._last_status_time = dt
            self.robot_status = f"Robot : {status}" if RobotAPI.online else "Robot : hors ligne"
            self.robot_online = RobotAPI.online

        if not self.robot_busy and not self.emergency_active:
            self.process_queue()

    def add_command(self, table):
        self.command_queue.append(f"Table {table}")
        print("Queue:", self.command_queue)

    def add_bar(self):
        self.command_queue.append("Bar")
        print("Queue:", self.command_queue)

    def toggle_emergency(self):
        if not self.emergency_active:
            RobotAPI.send("stop")  # Arrêt immédiat
            self.emergency_active = True
            self.robot_status = "ARRÊT D'URGENCE ACTIVÉ"
            print("Robot stoppé !")
        else:
            self.emergency_active = False
            self.robot_status = "Robot : attente commandes"
            print("Arrêt d'urgence désactivé")

    def process_queue(self):
        if not RobotAPI.online or self.robot_busy or not self.command_queue:
            return
        cmd = self.command_queue[0]
        if "Table" in cmd:
            table = cmd.split()[1]
            if RobotAPI.send(f"go/{table}"):
                self.robot_busy = True
        elif cmd == "Bar":
            if RobotAPI.send("bar"):
                self.robot_busy = True

    def robot_finished(self):
        if self.command_queue:
            self.command_queue.pop(0)
        self.robot_busy = False

# ---------- QueueScreen ----------
class QueueScreen(Screen):
    def on_enter(self):
        self.refresh()

    def refresh(self):
        layout = self.ids.queue_layout
        layout.clear_widgets()
        main = self.manager.get_screen("main")
        for i, cmd in enumerate(main.command_queue):
            row = BoxLayout(size_hint_y=None, height=70, spacing=10)
            label = Label(text=cmd, font_size="20sp")
            btn = Button(
                text="Supprimer",
                size_hint_x=0.4,
                background_normal="",
                background_color=(1, 0.3, 0.3, 1)
            )

            def delete_cmd(instance, index=i):
                if index < len(main.command_queue):
                    main.command_queue.pop(index)
                self.refresh()

            btn.bind(on_press=delete_cmd)
            row.add_widget(label)
            row.add_widget(btn)
            layout.add_widget(row)

# ---------- SettingsScreen ----------
class SettingsScreen(Screen):
    pass

# ---------- App ----------
class RobotRestaurantApp(App):
    robot_ip = ROBOT_IP_DEFAULT

    def build(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    self.robot_ip = data.get("robot_ip", ROBOT_IP_DEFAULT)
                    RobotAPI.robot_ip = self.robot_ip
            except:
                pass
        return Builder.load_string(KV)

    def save_robot_ip(self, ip):
        if ip.strip():
            self.robot_ip = ip.strip()
            RobotAPI.robot_ip = self.robot_ip
            with open(CONFIG_FILE, "w") as f:
                json.dump({"robot_ip": self.robot_ip}, f)
            print("Nouvelle IP du robot enregistrée:", self.robot_ip)
            self.root.current = "main"


KV = '''
#:import dp kivy.metrics.dp

ScreenManager:
    MainScreen:
        name: "main"
    QueueScreen:
        name: "queue"
    SettingsScreen:
        name: "settings"

<CustomButton@Button>:
    bg_color: [0.2, 0.6, 1, 1]  # couleur par défaut
    background_normal: ""
    background_color: self.bg_color
    size_hint_y: None
    height: dp(60)
    font_size: "22sp"
    canvas.before:
        Color:
            rgba: self.bg_color
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(20)]

<MainScreen>:
    BoxLayout:
        orientation: "vertical"
        padding: dp(20)
        spacing: dp(20)
        canvas.before:
            Color:
                rgb: 0.08, 0.08, 0.08
            Rectangle:
                pos: self.pos
                size: self.size

        Label:
            text: root.robot_status
            font_size: "26sp"
            bold: True
            color: (0,1,0,1) if root.robot_online else (1,0,0,1)
            size_hint_y: None
            height: dp(40)

        GridLayout:
            cols: 2
            spacing: dp(20)
            size_hint_y: 0.6

            CustomButton:
                text: "Table 1"
                on_press: root.add_command("1")
            CustomButton:
                text: "Table 2"
                on_press: root.add_command("2")
            CustomButton:
                text: "Table 3"
                on_press: root.add_command("3")
            CustomButton:
                text: "Table 4"
                on_press: root.add_command("4")

        BoxLayout:
            size_hint_y: None
            height: dp(90)
            spacing: dp(15)

            CustomButton:
                text: "Retour Bar"
                background_color: [0.3, 0.8, 0.4, 1]
                on_press: root.add_bar()
            CustomButton:
                text: "File d'attente"
                background_color: [1, 0.6, 0.2, 1]
                on_press: app.root.current = "queue"
            CustomButton:
                text: "Paramètres"
                background_color: [0.6, 0.4, 1, 1]
                on_press: app.root.current = "settings"
            CustomButton:
                text: "STOP ROBOT"
                background_color: [1, 0.2, 0.2, 1]
                on_press: root.toggle_emergency()

<QueueScreen>:
    BoxLayout:
        orientation: "vertical"
        padding: dp(20)
        spacing: dp(15)
        canvas.before:
            Color:
                rgb: 0.1, 0.1, 0.1
            Rectangle:
                pos: self.pos
                size: self.size
        Label:
            text: "File d'attente"
            font_size: "26sp"
            bold: True
            size_hint_y: None
            height: dp(40)
        ScrollView:
            GridLayout:
                id: queue_layout
                cols: 1
                spacing: dp(10)
                size_hint_y: None
                height: self.minimum_height
        CustomButton:
            text: "Retour"
            size_hint_y: None
            height: dp(70)
            font_size: "20sp"
            background_color: [0.2, 0.6, 1, 1]
            on_press: app.root.current = "main"

<SettingsScreen>:
    BoxLayout:
        orientation: "vertical"
        padding: dp(20)
        spacing: dp(20)
        canvas.before:
            Color:
                rgb: 0.08, 0.08, 0.08
            Rectangle:
                pos: self.pos
                size: self.size
        Label:
            text: "Paramètres du robot"
            font_size: "26sp"
            bold: True
            size_hint_y: None
            height: dp(50)
        BoxLayout:
            orientation: "horizontal"
            spacing: dp(10)
            size_hint_y: None
            height: dp(50)
            Label:
                text: "IP du robot:"
                font_size: "22sp"
                size_hint_x: 0.4
            TextInput:
                id: robot_ip
                text: app.robot_ip
                font_size: "20sp"
                multiline: False
        CustomButton:
            text: "Enregistrer"
            size_hint_y: None
            height: dp(60)
            font_size: "22sp"
            background_color: [0.3, 0.8, 0.4, 1]
            on_press: app.save_robot_ip(robot_ip.text)
        CustomButton:
            text: "Retour"
            size_hint_y: None
            height: dp(60)
            font_size: "22sp"
            background_color: [0.2, 0.6, 1, 1]
            on_press: app.root.current = "main"
'''

# Lancer l'application
RobotRestaurantApp().run()