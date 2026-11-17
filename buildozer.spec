[app]
title = Social Downloader
package.name = socialdownloader
package.domain = org.hamedafshari
source.dir = .
source.include_exts = py,ttf,xml
version = 1.1
requirements = python3,kivy==2.3.0,yt-dlp,gallery-dl,requests,urllib3,idna,charset-normalizer,certifi,sqlite3,openssl,arabic-reshaper,python-bidi==0.4.2,six
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
# receive links shared from the Instagram / YouTube apps
android.manifest.intent_filters = intent_filters.xml
android.manifest.launch_mode = singleTask
# target API 28 keeps classic access to /sdcard/Download (sideloaded app, not for Play Store)
android.api = 28
android.minapi = 21
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.ndk = 25b
# pin a stable python-for-android release (the newest branch has no kivy wheels yet)
p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1
