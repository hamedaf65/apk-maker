[app]
title = Social Downloader
package.name = socialdownloader
package.domain = org.hamed
source.dir = .
source.include_exts = py
version = 1.0
requirements = python3,kivy,yt-dlp,gallery-dl,requests,urllib3,idna,charset-normalizer,certifi,sqlite3,openssl
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
# target API 28 keeps classic access to /sdcard/Download (sideloaded app, not for Play Store)
android.api = 28
android.minapi = 21
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
