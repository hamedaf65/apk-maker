# SociaSave — Android social media downloader

SociaSave is an Android app by Hamed AI for organizing media posts that the user is authorized to save from Instagram, YouTube, X (Twitter), and Facebook.

## App features

- A four-platform landing banner for Instagram, X/Twitter, YouTube, and Facebook.
- Dedicated Instagram sign-in screen with Back and Close controls.
- Paste a supported post/video URL or share a link from another app.
- A download status overlay with a progress ring and clear success/failure feedback.
- A dedicated Contact Us page for the Telegram channel and Instagram page.

## Supported extraction engines

- Instagram: gallery-dl for supported posts, carousels and Reels; Instagram cookies are stored in the app-private directory.
- X/Twitter: gallery-dl for supported public posts and media.
- YouTube: yt-dlp with FFmpeg for supported public videos. YouTube's current JavaScript challenge requirements may still require a compatible JS runtime, and PO-token / anti-bot restrictions can block some videos.
- Facebook: yt-dlp for supported public videos and Reels. Private or login-gated media is not guaranteed.

## Download archive layout

On Android 10 and newer, supported downloaded files are exported through MediaStore to the public Downloads directory:

Download/SociaSave/{platform}/{account_id}/{post_id}/

Each post folder contains the downloaded media, caption.txt, and source.txt. Files are staged in app-private storage first and then copied to the public Downloads collection. The SociaSave folder button opens the system file manager/document picker at the archive location.

## Android implementation

- Android target API: 36
- Android minimum API: 29 (MediaStore Downloads support)
- Android architectures: arm64-v8a and armeabi-v7a
- Custom Java bridge: android_src/org/hamedafshari/sociasave/SociaSaveStorage.java
- python-for-android: develop, pinned to commit 9562d1b4f306d0af1e76991c711114010dea4152
- Buildozer: pinned to commit 76bac28545c66bbcc671d49aca553a747d69608e
- Build host Python: 3.14
- Kivy: 2.3.2
- yt-dlp: 2026.10.26 plus yt-dlp-ejs scripts
- gallery-dl: 1.32.20
- FFmpeg: python-for-android FFmpeg executable recipe with av_codecs

GitHub Actions validates Python syntax and Java source presence, builds a debug APK, and uploads it as SociaSave-Android-APK.

## Known limitations

- YouTube currently requires an external JavaScript runtime for full challenge-solving support. The APK includes yt-dlp-ejs scripts, but a compatible Android runtime still needs to be validated. Some public videos may work without it; others may fail.
- Instagram and X/Twitter may rate-limit or restrict automated extraction.
- Facebook posts that require a login or special access may not be available.
- A successful CI build is not proof of successful device-side downloads. Test each platform with content you own or are authorized to save.

Only download content that you own or are authorized to save, and follow each platform's terms.
