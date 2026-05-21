import qrcode
import os

os.makedirs("qrcodes", exist_ok=True)


nombre_de_tables = 69
IP_SERVEUR = "192.168.137.235:5000"

for numero_table in range(1, nombre_de_tables + 1):
    url_fixe = f"http://{IP_SERVEUR}/client?table={numero_table}"
    
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url_fixe)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(f"qrcodes/qr_table_{numero_table}.png")

print("QR codes permanents générés avec la bonne route !")