# Social Downloader (Android)

## Build the APK (no PC tools needed)
1. Create a free account on github.com and a new **private** repository.
2. Upload all files of this folder (keep `.github/workflows/build.yml`).
3. Open the **Actions** tab -> "Build APK" -> **Run workflow**. Wait ~20-40 minutes.
4. Open the finished run -> **Artifacts** -> download `SocialDownloader-apk` (zip) -> extract the `.apk`.
5. Copy to the phone, allow "install unknown apps", install.

## Use
Paste link -> DOWNLOAD. Output: `Download/SocialDownloader/<page id>/<post id>/` with `caption.txt` + media.

Instagram login: export `cookies.txt` (Kiwi Browser + "Get cookies.txt LOCALLY", or from PC) and put it at
`Download/SocialDownloader/cookies.txt`.

YouTube: no ffmpeg on the phone, so it downloads the best single-file stream (usually up to 720p).
