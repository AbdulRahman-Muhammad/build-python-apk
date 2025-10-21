[app]
title = Collepedia Mobile
package.name = app
package.domain = com.collepedia
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,json,ttf,otf
version = 4.0
requirements = python3,kivy,kivymd,requests,beautifulsoup4,lxml,deep_translator,collepedia,plyer,certifi,asyncio,cachetools,html2text,pycountry,httpx
orientation = portrait

# Android API Levels: Min 21 (5.0 Lollipop) to Target 34 (Android 14) ensures wide compatibility
android.api = 34
android.minapi = 21
# Include common architectures
android.archs = arm64-v8a, armeabi-v7a

android.permissions = INTERNET, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE, FOREGROUND_SERVICE, RECEIVE_BOOT_COMPLETED, VIBRATE

android.presplash = data/icon.png
android.presplash_color = #FFFFFF
android.icon = data/icon.png
# android.adaptive_icon = data/adaptive-icon.png # Optional adaptive icon
android.package_source_dir = src # Standard source directory
android.manifest.author = Nanasoft Technologies Agency

# Add hooks if needed by plyer or other libraries for specific features, e.g., notifications
# p4a.hook = hooks/hook-plyer.py # Create this file if necessary

p4a.local_recipes = ~/.buildozer/android/platform/python-for-android/pythonforandroid/recipes

# iOS specific settings (if targeting iOS later)
#ios.kivy_ios_url = https://github.com/kivy/kivy-ios
#ios.kivy_ios_branch = master
#ios.codesign.allowed = true

# macOS specific settings (if targeting macOS later)
#osx.python_version = 3
#osx.kivy_version = 2.1.0

[buildozer]
# Log level 2 provides maximum detail during build
log_level = 2
warn_on_root = 1
# Optional: Increase RAM for build process, helpful on limited machines
# android.gradle_command = --no-daemon -Porg.gradle.jvmargs="-Xmx4096m"
