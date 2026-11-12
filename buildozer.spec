[app]
title = Movie Crawler
package.name = moviecrawler
package.domain = org.openai.sample
source.dir = .
source.include_exts = py,kv,png,jpg,atlas,json,txt
version = 1.0.0
requirements = python3,kivy==2.3.0,requests,beautifulsoup4,openpyxl
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,ACCESS_NETWORK_STATE
android.api = 35
android.minapi = 23
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = False
p4a.bootstrap = sdl2
[buildozer]
log_level = 2
warn_on_root = 1
