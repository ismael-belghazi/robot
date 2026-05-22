import os
import json
import uuid
import threading
import websocket
from functools import wraps
from collections import defaultdict
from datetime import datetime, timedelta

from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room, leave_room
import eventlet
import time

eventlet.monkey_patch()

# ----------------- App & Config -----------------
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecretkey")
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

socketio = SocketIO(app, cors_allowed_origins="*", manage_session=True)

POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "restaurant")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "db")

app.config['SQLALCHEMY_DATABASE_URI'] = (
    f'postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:5432/{POSTGRES_DB}'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

state_lock = threading.Lock()

# ----------------- Models -----------------
class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    table_number = db.Column(db.Integer, nullable=False)
    plats = db.Column(db.String, nullable=False)
    status = db.Column(db.String, nullable=False, default='EN_ATTENTE')
    token = db.Column(db.String, nullable=False)
    paid = db.Column(db.Boolean, default=False)
    cancelled_at = db.Column(db.DateTime, nullable=True)

class TableToken(db.Model):
    __tablename__ = 'table_tokens'
    token = db.Column(db.String, primary_key=True)
    table_number = db.Column(db.Integer, nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

# ----------------- Auth Config -----------------
USERNAME = os.getenv("RESTO_USER", "admin")
PASSWORD = os.getenv("RESTO_PASSWORD", "admin")

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ----------------- Helpers -----------------
table_clients = defaultdict(set)
socket_to_table = {} 

def has_unpaid_orders(table_number):
    """Vérifie s'il y a des commandes actives ou impayées pour cette table."""
    return Order.query.filter(
        Order.table_number == table_number,
        Order.paid == False,
        Order.status != 'ANNULE'
    ).first() is not None

def get_table_summary(table_number):
    orders = Order.query.filter(
        Order.table_number == table_number, 
        Order.paid == False,
        Order.status != 'ANNULE'
    ).all()
    summary = {}
    total = 0

    try:
        with open('menu.json') as f:
            menu = json.load(f)
    except Exception as e:
        print(f"[ERROR] Impossible de lire menu.json : {e}")
        return {'summary': {}, 'total': 0.0}

    all_items = {i['name']: i['price'] for cat in ['entrees','plats','desserts','boissons'] for i in menu.get(cat, [])}

    for order in orders:
        if not order.plats:
            continue
        for p in order.plats.split(','):
            if ':' not in p:
                continue
            name, qty = p.split(':')
            qty = int(qty)
            summary[name] = summary.get(name, 0) + qty
            total += all_items.get(name, 0) * qty

    return {'summary': summary, 'total': round(total, 2)}


def serialize_order(order):
    plats_list = []
    if isinstance(order.plats, str):
        for item in order.plats.split(','):
            if ':' in item:
                nom, qty = item.split(':')
                plats_list.extend([nom.strip()] * int(qty))
            else:
                plats_list.append(item.strip())
    else:
        plats_list = order.plats

    vrai_total_commande = 0.0

    try:
        with open('menu.json', 'r', encoding='utf-8') as f:
            menu_data = json.load(f)
    except:
        menu_data = {}

    for plat_name in plats_list:
        prix_trouve = 0.0
        for categorie in ['entrees', 'plats', 'desserts', 'boissons']:
            if categorie in menu_data:
                item = next((i for i in menu_data[categorie] if i['name'] == plat_name), None)
                if item:
                    prix_trouve = float(item['price'])
                    break
        vrai_total_commande += prix_trouve

    return {
        'id': order.id,
        'table': order.table_number,
        'status': order.status,
        'plats': plats_list, 
        'total_price': vrai_total_commande  
    }

def get_dashboard_orders():
    orders = Order.query.filter(
        Order.paid == False,
        Order.status != 'ANNULE'
    ).order_by(Order.id.desc()).all()
    return [serialize_order(order) for order in orders]


def validate_token(table_number, token):
    if not token:
        return False
    token_obj = TableToken.query.get(token)
    if not token_obj or not token_obj.active or token_obj.table_number != table_number:
        return False
        
    if has_unpaid_orders(table_number):
        return True

    nb_clients_actifs = len(table_clients.get(table_number, set()))
    if nb_clients_actifs == 0:
        maintenant = datetime.utcnow()
        if maintenant - token_obj.created_at > timedelta(minutes=20):
            token_obj.active = False
            db.session.commit()
            print(f"[AUTH] Table {table_number} inactive et sans commande > 20 min. Token expiré.")
            return False
            
    return True


def activate_token(table_number, token):
    token_obj = TableToken.query.get(token)
    maintenant = datetime.utcnow()
    
    if token_obj:
        if token_obj.table_number != table_number or not token_obj.active:
            return None
            
        if maintenant - token_obj.created_at > timedelta(minutes=20):
            if has_unpaid_orders(table_number):
                return token_obj
            if token_obj.active:
                token_obj.active = False
                db.session.commit()
            return None
        return token_obj

    token_obj = TableToken(token=token, table_number=table_number, active=True, created_at=maintenant)
    db.session.add(token_obj)
    db.session.commit()
    return token_obj


def invalidate_token(token):
    token_obj = TableToken.query.get(token)
    if token_obj:
        token_obj.active = False
        db.session.commit()
    return token_obj


def invalidate_table_tokens(table_number):
    tokens = TableToken.query.filter_by(table_number=table_number, active=True).all()
    for token in tokens:
        token.active = False
    db.session.commit()
    return tokens


class HotspotBridge:
    ws = None
    connected = False
    is_connecting = False
    url = os.getenv('HOTSPOT_WS_URL', 'ws://10.42.0.1:8765')

    last_msg = None
    last_msg_time = 0

    @classmethod
    def connect(cls):
        if cls.connected or cls.is_connecting:
            return
        
        cls.is_connecting = True

        def on_message(ws, message):
            clean_msg = message.strip().lower()
            now = time.time()
            
            with state_lock:
                if clean_msg == cls.last_msg and (now - cls.last_msg_time) < 2.0:
                    return
                cls.last_msg = clean_msg
                cls.last_msg_time = now

            print(f"[HOTSPOT] reçu : {clean_msg}")
            
            if clean_msg.startswith("arrived/table/"):
                try:
                    table_num = int(clean_msg.split("/")[-1])
                    cls.handle_status_received(table_num)
                except Exception as e:
                    print(f"[HOTSPOT] Erreur de parsing du message arrived : {e}")

        def on_open(ws):
            cls.connected = True
            cls.is_connecting = False
            print("[HOTSPOT] Connecté au serveur cerveau")

        def on_close(ws, close_status_code, close_msg):
            cls.connected = False
            cls.is_connecting = False
            print("[HOTSPOT] Déconnecté du serveur cerveau")

        def on_error(ws, error):
            cls.is_connecting = False
            print(f"[HOTSPOT] Erreur : {error}")

        cls.ws = websocket.WebSocketApp(
            cls.url,
            on_message=on_message,
            on_open=on_open,
            on_close=on_close,
            on_error=on_error
        )
        socketio.start_background_task(cls.ws.run_forever)

    @classmethod
    def handle_status_received(cls, table_number):
        with app.app_context():
            try:
                orders = Order.query.filter_by(table_number=table_number, status='PRET', paid=False).all()
                if orders:
                    for order in orders:
                        order.status = 'LIVRE'
                    db.session.commit()
                    
                    socketio.emit('update_orders', get_dashboard_orders(), room='dashboard')
                    socketio.emit('update_summary', get_table_summary(table_number), room=f"table_{table_number}")                    
                    socketio.emit('order_delivered', {'table': table_number}, room=f"table_{table_number}")
                    
            except Exception as sql_err:
                db.session.rollback()
                print(f"[ERR] {sql_err}")
            finally:
                db.session.remove()

    @classmethod
    def send(cls, message):
        if cls.ws and cls.connected:
            try:
                cls.ws.send(message)
                print(f"[HOTSPOT] envoyé : {message}")
            except Exception as ex:
                print(f"[HOTSPOT] impossible d'envoyer : {ex}")
        else:
            print(f"[HOTSPOT] pas connecté, message ignoré : {message}")

    @classmethod
    def send_order(cls, table_number):
        cls.send(f"order/table/{table_number}")

    @classmethod
    def send_cancel(cls, table_number):
        cls.send(f"cancel/table/{table_number}")

    @classmethod
    def send_payment(cls, table_number):
        cls.send(f"paid/table/{table_number}")


def update_order_item(table_number, token, item_name, delta, replace=False):
    order = Order.query.filter_by(table_number=table_number, token=token, status='EN_ATTENTE', paid=False).first()
    plats_dict = {}
    if order and order.plats:
        for p in order.plats.split(','):
            if ':' in p:
                name, qty = p.split(':')
                plats_dict[name] = int(qty)

    if replace:
        plats_dict[item_name] = delta
    else:
        plats_dict[item_name] = plats_dict.get(item_name, 0) + delta

    plats_dict = {k: v for k, v in plats_dict.items() if v > 0}

    if order:
        order.plats = ','.join(f"{k}:{v}" for k, v in plats_dict.items())
    else:
        order = Order(
            table_number=table_number,
            plats=','.join(f"{k}:{v}" for k, v in plats_dict.items()),
            token=token,
            status='EN_ATTENTE'
        )
        db.session.add(order)
    db.session.commit()

# ----------------- Routes -----------------
@app.route('/')
def home():
    return redirect(url_for('dashboard') if session.get('logged_in') else url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
        if user == USERNAME and pwd == PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        return render_template('login.html', error="Identifiants invalides")
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/client')
def client():
    table_param = request.args.get('table')
    if not table_param:
        return "Table non spécifiée", 400
    table = int(table_param)
    token = request.args.get('token')
    
    if token:
        token_obj = TableToken.query.get(token)
        if token_obj and token_obj.table_number != table:
            return "Action non autorisée : Jeton invalide pour cette table.", 403
            
        token_obj = activate_token(table, token)
        if not token_obj:
            return "Le token est expiré. Veuillez rescanner le QR code.", 403
            
        session['table_token'] = token
        return render_template('client.html', table=table, token=token)

    maintenant = datetime.utcnow()
    limite_temps = maintenant - timedelta(minutes=20)
    token_actuel = TableToken.query.filter_by(table_number=table, active=True).first()
    
    if token_actuel:
        nb_clients = len(table_clients.get(table, set()))
        if nb_clients > 0 or (token_actuel.created_at >= limite_temps) or has_unpaid_orders(table):
            token = token_actuel.token
        else:
            token_actuel.active = False
            db.session.commit()
            token = str(uuid.uuid4())
    else:
        token = str(uuid.uuid4())

    activate_token(table, token)
    return redirect(url_for('client', table=table, token=token))


@app.route('/menu')
def menu_anonyme():
    token = session.get('table_token')
    if token:
        token_obj = TableToken.query.get(token)
        if token_obj and token_obj.active:
            return render_template('client.html', table=token_obj.table_number, token=token)
            
    return "Veuillez scanner le QR code de votre table pour accéder au menu.", 403


@app.route('/api/menu')
def get_menu():
    try:
        with open('menu.json') as f:
            menu = json.load(f)
        return jsonify(menu)
    except Exception as e:
        return jsonify({"error": f"Impossible de charger le menu: {str(e)}"}), 500

# ----------------- SocketIO -----------------
@socketio.on('connect')
def handle_connect():
    sid = request.sid
    if session.get('logged_in'):
        join_room('dashboard')
        emit('update_orders', get_dashboard_orders(), room=sid)
        return

@socketio.on('join_table')
def handle_join_table(data):
    sid = request.sid
    table_raw = data.get('table')
    token = data.get('token')
    if not table_raw or not token:
        emit('join_error', {'message': 'Table ou token manquant'})
        return

    table = int(table_raw)
    if not validate_token(table, token):
        emit('join_error', {'message': 'Token invalide ou expiré'})
        return

    join_room(f"table_{table}")
    table_clients[table].add(sid)
    socket_to_table[sid] = table
    session['table_token'] = token

    emit('joined_table', {'table': table}, room=sid)
    emit('update_summary', get_table_summary(table), room=f"table_{table}")
    emit('update_clients_count', len(table_clients[table]), room=f"table_{table}")

@socketio.on('join_dashboard')
def handle_join_dashboard():
    sid = request.sid
    if not session.get('logged_in'):
        emit('join_error', {'message': 'Non autorisé'})
        return

    join_room('dashboard')
    emit('update_orders', get_dashboard_orders(), room=sid)

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    table = socket_to_table.pop(sid, None)
    if table is not None:
        clients = table_clients.get(table, set())
        if sid in clients:
            clients.remove(sid)
            socketio.emit('update_clients_count', len(clients), room=f"table_{table}")

@socketio.on('update_item')
def handle_update_item(data):
    table_raw = data.get('table')
    token = data.get('token')
    item_name = data.get('item')
    quantityDelta = int(data.get('quantityDelta', 0))

    if not table_raw or not token or not item_name:
        return

    table = int(table_raw)
    if not validate_token(table, token):
        return

    update_order_item(table, token, item_name, quantityDelta)
    socketio.emit('update_summary', get_table_summary(table), room=f"table_{table}")

@socketio.on('request_summary')
def handle_request_summary(data):
    table_raw = data.get('table')
    token = data.get('token')
    if not table_raw or not token:
        return

    table = int(table_raw)
    if not validate_token(table, token):
        return

    emit('update_summary', get_table_summary(table), room=f"table_{table}")

@socketio.on('send_order')
def handle_send_order(data):
    table_raw = data.get('table')
    token = data.get('token')
    order_dict = data.get('order')

    if not table_raw or not token or not order_dict:
        return

    table = int(table_raw)
    if not validate_token(table, token):
        return

    existing_orders = Order.query.filter_by(table_number=table, status='EN_ATTENTE', paid=False).all()
    if existing_orders:
        socketio.emit('order_already_submitted', {'table': table}, room=f"table_{table}")
        return

    plats_str = ','.join(f"{k}:{v}" for k, v in order_dict.items())

    new_order = Order(
        table_number=table,
        token=token,
        plats=plats_str,
        status='EN_ATTENTE'
    )
    db.session.add(new_order)
    db.session.commit()

    socketio.emit('update_summary', get_table_summary(table), room=f"table_{table}")
    socketio.emit('order_submitted', {'table': table}, room=f"table_{table}")
    socketio.emit('update_orders', get_dashboard_orders(), room='dashboard')
    

@socketio.on('confirm_order')
def handle_confirm_order(data):
    if not session.get('logged_in'):
        return

    table = int(data.get('table'))
    orders = Order.query.filter_by(table_number=table, status='EN_ATTENTE', paid=False).all()
    if not orders:
        return

    for order in orders:
        order.status = 'PRET'
    db.session.commit()

    HotspotBridge.send_order(table)
    socketio.emit('order_ready', {'table': table}, room=f"table_{table}")
    socketio.emit('update_orders', get_dashboard_orders(), room='dashboard')
    socketio.emit('update_summary', get_table_summary(table), room=f"table_{table}")


@socketio.on('cancel_order')
def handle_cancel_order(data):
    if not session.get('logged_in'):
        return

    table = int(data.get('table'))
    orders = Order.query.filter_by(table_number=table, status='EN_ATTENTE', paid=False).all()
    
    for order in orders:
        order.status = 'ANNULE'
    db.session.commit()

    HotspotBridge.send_cancel(table)
    socketio.emit('update_orders', get_dashboard_orders(), room='dashboard')
    socketio.emit('update_summary', get_table_summary(table), room=f"table_{table}")
    socketio.emit('order_cleared', {'table': table}, room=f"table_{table}")


@socketio.on('complete_order')
def handle_complete_order(data):
    if not session.get('logged_in'):
        return

    table = int(data.get('table'))
    token = data.get('token')
    orders = Order.query.filter_by(table_number=table, token=token, paid=False).all()
    
    for order in orders:
        order.status = 'LIVRE'
    db.session.commit()
    
    socketio.emit('order_completed', {'table': table, 'token': token}, room=f"table_{table}")
    socketio.emit('update_orders', get_dashboard_orders(), room='dashboard')
    socketio.emit('update_summary', get_table_summary(table), room=f"table_{table}")


@socketio.on('pay_order')
def handle_pay(data):
    if not session.get('logged_in'):
        return

    table = int(data.get('table'))
    orders = Order.query.filter_by(table_number=table, paid=False).all()
    
    for order in orders:
        order.paid = True
        order.status = 'PAYE'
    
    invalidate_table_tokens(table)
    db.session.commit()

    socketio.emit('update_summary', get_table_summary(table), room=f"table_{table}")
    socketio.emit('session_ended', {'table': table}, room=f"table_{table}")
    socketio.emit('order_cleared', {'table': table}, room=f"table_{table}")
    socketio.emit('update_orders', get_dashboard_orders(), room='dashboard')
    
    HotspotBridge.send_payment(table)

# ----------------- Run App -----------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.start_background_task(HotspotBridge.connect)
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)