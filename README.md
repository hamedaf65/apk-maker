# SociaSave — Android social media downloader

SociaSave is an Android app by Hamed AI for organizing media posts that the user is authorized to save from Instagram, YouTube, X (Twitter), Facebook, TikTok, Pinterest, and experimental Threads link recognition.

## App features

- A four-platform landing banner for Instagram, X/Twitter, YouTube, and Facebook.
- Dedicated Instagram sign-in screen with Back and Close controls.
- Paste a supported post/video URL or share a link from another app.
- A download status overlay with a progress ring and clear success/failure feedback.
- A dedicated Contact Us page for the Telegram channel and Instagram page.

## Supported extraction engines

- Instagram: gallery-dl for supported posts, carousels, Reels and Stories. The app's embedded login can save an app-private cookie file. Separate audio extraction is disabled so the original Reel video is preferred.
- X/Twitter: gallery-dl for supported posts and media. Existing X download behavior remains unchanged; optional cookie support is available in the engine.
- YouTube: yt-dlp with FFmpeg for supported public videos. Google sign-in is not embedded because Google blocks sign-in in embedded WebViews. A logged-in YouTube app or Chrome session is not automatically shared with SociaSave. PO-token / anti-bot restrictions can still block videos even when the account is signed in.
- Facebook: yt-dlp first, then gallery-dl fallback. Optional in-app Facebook cookies are passed to both extractors. Facebook's current extractor can still fail when the site changes its page markup.
- TikTok: yt-dlp first, then gallery-dl fallback. Video+audio progressive formats are preferred; optional in-app session cookies are supported.
- Pinterest: gallery-dl first to support image Pins as well as supported video Pins, then yt-dlp fallback. Optional in-app session cookies are supported.
- Threads: bundled third-party yt-dlp plugin supports publicly viewable video posts and video carousels. Image-only, text-only, private and login-gated posts are not supported. The plugin uses crawler-visible public page data and has no account-cookie support.

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

GitHub Actions validates Python syntax, runs offline routing/plugin tests, checks Java source presence, builds a debug APK, verifies the Java bridge in DEX, and uploads it as SociaSave-Android-APK.

## Known limitations

- YouTube currently requires an external JavaScript runtime for full challenge-solving support. The APK includes yt-dlp-ejs scripts, but a compatible Android runtime still needs to be validated. Some public videos may work without it; others may fail.
- Instagram, X/Twitter, Facebook, TikTok and Pinterest may rate-limit or restrict automated extraction. A logged-in session helps only when the platform accepts the request and the extractor supports the page variant.
- Embedded login sessions are stored in app-private Netscape cookie files. They are not shared with the native social apps or Chrome, and may expire or be invalidated.
- YouTube's PO-token challenge is not equivalent to a login requirement; signing in alone does not guarantee access to a stream.
- Threads plugin support is third-party and fragile because it relies on public crawler-rendered page data.
- A successful CI build is not proof of successful device-side downloads. Test each platform with content you own or are authorized to save.

Only download content that you own or are authorized to save, and follow each platform's terms.
