# robot

# sur pc pour avoir les requirements pour l application
pip install -r requirements.txt

# sur la raspberry 
sudo apt update
sudo apt install python3-pip
pip install -r requirements.txt

# etape build le project vers apk (prévoir 20, 30 minutes pour le 1er build docker essentiel)
# si c est pas deja fait 
docker compose build 
docker compose run kivy-apk buildozer init
# modfier le buildoze.spec comme vous le souhaitez
# run le build de l'application mobile
docker compose run kivy-apk buildozer android clean
# finaliser le build
docker compose run kivy-apk buildozer android debug
