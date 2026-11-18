[app]
title = ClipDrop
package.name = socialdownloader
package.domain = org.hamedafshari
source.dir = .
source.include_exts = py,ttf,xml
version = 1.3
requirements = python3,kivy==2.3.2,yt-dlp==2026.10.26,gallery-dl==1.32.20,ffmpeg,av_codecs,requests,urllib3,idna,charset-normalizer,certifi,sqlite3,openssl,arabic-reshaper,python-bidi==0.4.2,six
orientation = portrait
fullscreen = 0
android.permissions = INTERNET
android.manifest.intent_filters = intent_filters.xml
android.manifest.launch_mode = singleTask
# Android 16 target API; modern python-for-android toolchain.
android.api = 36
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.ndk = 28c
p4a.branch = v2026.05.09

[buildozer]
log_level = 2
warn_on_root = 1
