# Build Movie Crawler APK using only an Android phone

This package is preconfigured to build the APK on GitHub's cloud runner. MT Manager is only used to extract/manage files; it does not compile Python/Kivy projects.

## Steps
1. Extract this ZIP in MT Manager.
2. In Chrome, sign in to https://github.com/ and create a **new public repository** named `movie-crawler-android` (a public repo makes it easier to use GitHub Actions minutes on a free account; do not upload passwords, API keys, or private data).
3. Open the empty repository. Choose **Add file → Upload files**.
4. Upload the contents of the extracted folder: `main.py`, `buildozer.spec`, `README_ANDROID.md`, `PHONE_BUILD_GUIDE.md`, and the `.github` folder. Keep `.github/workflows/build-apk.yml` at exactly that path. If Android's file picker hides dot-folders, use GitHub's **Add file → Create new file** and enter `.github/workflows/build-apk.yml`, then paste the workflow from this ZIP.
5. Commit the files.
6. Open the repository's **Actions** tab. If GitHub asks, enable Actions for the repository.
7. Select **Build Movie Crawler APK** on the left, tap **Run workflow**, then tap the green **Run workflow** button.
8. Wait for the run to finish. Open the completed run and find **Artifacts** near the bottom. Tap `movie-crawler-apk` to download the APK artifact ZIP.
9. Extract that artifact ZIP in MT Manager. Tap the `.apk` file and install it. Android may ask you to allow installs from that source.

## If it fails
Open the failed workflow run and inspect the build log. A first Android build can take several minutes and can fail due to upstream Android/NDK dependency changes. Re-running may help with temporary network failures.
