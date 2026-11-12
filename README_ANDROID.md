# Movie Crawler Android APK source

This is an Android-oriented Kivy port of the desktop crawler.

## Build the APK (Linux or WSL2 recommended)

Buildozer needs Android SDK/NDK and internet access to download build dependencies.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install buildozer cython
buildozer android debug
```

The APK should be created under `bin/`, with a name similar to `moviecrawler-1.0.0-arm64-v8a-debug.apk`.

For Windows, use WSL2 Ubuntu and keep the project inside the Linux filesystem (for example `~/movie-crawler-android`), not `/mnt/c`.

## Install on a device

Enable installation from the source you use, then install the generated debug APK. For USB debugging:

```bash
buildozer android deploy run
```

## App behavior

- Enter one or more permitted website URLs.
- Set maximum pages and per-domain delay.
- Start/stop the crawl.
- Metadata is extracted from Schema.org JSON-LD, Open Graph and common HTML patterns.
- Excel and CSV files are written to the app's private files directory under `exports/`.

Android versions restrict direct access to app-private files. To make exports easier to retrieve, the next improvement should add Android's Storage Access Framework / share-sheet integration. This starter port currently logs the export directory; it does not request broad storage permission.

## Limitations

- Generic extraction cannot guarantee compatibility with every site; custom adapters may be required.
- This version checks robots.txt and does not bypass logins, CAPTCHAs, paywalls or anti-bot systems.
- Link validation is lightweight and does not download movie files. Server blocks and rate limits can make a valid URL appear unknown.
- Long background crawls may be paused or killed by Android when the app is backgrounded. Keep the app open during crawling in this initial version.
- Test the APK on a device before production use. The APK itself must be built on a machine with the Android toolchain.
