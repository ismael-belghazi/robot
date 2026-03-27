# robot

# sur pc pour avoire les requirment pour l application
pip install -r requirements.txt

# sur la rasberry 
sudo apt update
sudo apt install python3-pip
pip install -r requirements.txt

# etape build le project vers apk (prevoire 20 30 minute pour le 1 er build docker essentiel)
# si c est pas deja fait 
docker compose build 
docker compose run kivy-apk buildozer init
# modfier le buildoze.spec comme vous le shouataier
# run le build de l'application mobile
docker compose run kivy-apk buildozer android clean
# finaliser le build
docker compose run kivy-apk buildozer android debug