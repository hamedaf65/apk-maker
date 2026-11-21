[app]
title = SociaSave
package.name = sociasave
package.domain = org.hamedafshari
source.dir = .
source.include_exts = py,ttf,xml
version = 2.0
requirements = python3,kivy==2.3.2,yt-dlp==2026.10.26,yt-dlp-ejs,gallery-dl==1.32.20,ffmpeg,av_codecs,requests,urllib3,idna,charset-normalizer,certifi,sqlite3,openssl,arabic-reshaper,python-bidi==0.4.2,six
orientation = portrait
fullscreen = 0
android.permissions = INTERNET
android.manifest.intent_filters = intent_filters.xml
android.manifest.launch_mode = singleTask
android.add_src = android_src
android.api = 36
android.minapi = 29
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.ndk = 28c
p4a.branch = develop
p4a.commit = 9562d1b4f306d0af1e76991c711114010dea4152

[buildozer]
log_level = 2
warn_on_root = 1
