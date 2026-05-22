# =============================================================================
#  CONFIG BUILDOZER - VERSION OPTIMISÉE POUR DOCKER (RSapp)
# =============================================================================

[app]
# Nom affiché sous l'icône
title = Robot-Server

# Nom technique utilisé par Android
package.name = RSapp
package.domain = com.mhi_robotics

# Code source
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
source.exclude_dirs = tests, bin, venv, .buildozer

# --- GESTION DE L'ICÔNE POUR DOCKER ---
# On force l'utilisation du dossier source courant de manière brute
icon.filename = logo.png

# Version de l'application
version = 0.7

# Bibliothèques Python à inclure (Ta base stable + plyer pour tes notifications)
requirements = python3,kivy==2.3.1,kivymd==1.1.1,pyserial,websocket-client,requests,pyjnius,filetype,plyer

# Orientation et affichage
orientation = landscape
fullscreen = 0

# --- Partie ANDROID ---
android.permissions = INTERNET, ACCESS_NETWORK_STATE
android.api = 33
android.minapi = 24

# NDK / architectures
android.ndk = 25b
android.ndk_api = 24

# Configuration pour le Google Play Store (32/64 bits et format .aab)
android.archs = arm64-v8a, armeabi-v7a
android.release_artifact = aab

# Compilation Java et optimisation APK
android.use_javac = True
android.proguard = True

# Debugging avec logcat
android.logcat_filters = *:S python:D

[buildozer]
log_level = 2
warn_on_root = 0

# FORCE le stockage temporaire hors du partage Windows NTFS
storage_dir = /home/user/.buildozer_storage
use_git = 0