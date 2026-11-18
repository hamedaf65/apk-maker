# ClipDrop — Android media downloader

ClipDrop is a Kivy-based Android app by Hamed AI for downloading supported Instagram posts/Reels and public YouTube videos.

## Features

- Paste an Instagram or YouTube link, or share a link from another app.
- Instagram login uses an in-app session stored in the app-private directory.
- Instagram Reels request video and audio media. When gallery-dl provides separate tracks, bundled FFmpeg attempts to mux them into a single file.
- Public YouTube downloads use yt-dlp and request the best available video + audio streams, then merge them with bundled FFmpeg.
- YouTube PO-token and anti-bot checks can still block specific videos. Signing in to YouTube in the separate YouTube app or Chrome does not automatically share those cookies with ClipDrop.
- Technical diagnostics are written to the app-private downloader-internal.log, not shown in the UI.
- Download status is displayed using an animated progress ring, then a green success mark or red failure mark with a readable message.
- The ClipDrop interface includes a dedicated Contact Us page with Telegram and Instagram links.

## Storage and Android permissions

Downloads and the internal diagnostic log are kept in ClipDrop's app-private storage. The app requests only the Internet permission; it no longer requests broad legacy external-storage permissions. This avoids direct writes to shared storage that are restricted by modern Android scoped storage. Downloaded files remain visible in the app's Downloaded Files view.

## Build

- Android target API: 36
- Minimum Android API: 24
- python-for-android: v2026.05.09
- Buildozer: 1.6.0
- Kivy: 2.3.2
- yt-dlp: 2026.10.26
- gallery-dl: 1.32.20
- FFmpeg: bundled through the python-for-android recipe

GitHub Actions builds a debug APK and uploads it as the ClipDrop-Android-APK artifact.

## Important

Only download content that you own or are authorized to save. Platform restrictions and account permissions may prevent some downloads.
