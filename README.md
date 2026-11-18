# ClipDrop — Android social media downloader

A Kivy-based Android app by Hamed AI for saving supported Instagram posts/reels and public YouTube videos.

## Current behavior

- Paste a supported Instagram or YouTube URL, or share a link to ClipDrop from another app.
- Instagram sign-in takes place in the app. Its session cookies are saved only inside the app's private data directory.
- Instagram post/reel extraction explicitly enables video media. The app also retains downloaded media if the extractor does not return a matching JSON metadata sidecar.
- Public YouTube videos are downloaded without requiring an account connection.
- The YouTube connection button explains why Google sign-in is not embedded in an Android WebView. Private, members-only, login-gated or age-verified videos may not be supported.
- Technical downloader messages are written to a private app log. The screen shows only the final success/failure state and a user-friendly explanation.
- Downloads are saved under `Download/SocialDownloader` when Android permissions allow it; otherwise the app falls back to its private app storage.
- A completed download highlights the Downloaded Files button. Tap the green check or red cross to dismiss the status overlay.

## Build

The project uses Buildozer and python-for-android. See `buildozer.spec` and `.github/workflows/build.yml`.

## Important

Only download content that you own or have permission to save. Platform restrictions, account permissions, and regional availability may prevent some downloads.
