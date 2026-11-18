[app]
title = ClipDrop
package.name = socialdownloader
package.domain = org.hamedafshari
source.dir = .
source.include_exts = py,ttf,xml
version = 1.2
requirements = python3,kivy==2.3.0,yt-dlp,gallery-dl==1.32.20,requests,urllib3,idna,charset-normalizer,certifi,sqlite3,openssl,arabic-reshaper,python-bidi==0.4.2,six
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.manifest.intent_filters = intent_filters.xml
android.manifest.launch_mode = singleTask
# Retain the existing compatibility setting for shared Downloads folder writes.
android.api = 28
android.minapi = 21
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.ndk = 25b
p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1
