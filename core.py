"""SociaSave media extraction and archive engine."""
import json
import hashlib
import logging
import mimetypes
import os
import re
import shutil
import subprocess
import tempfile

try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except Exception:
    pass


class DownloadError(RuntimeError):
    """A download failed or produced no usable media."""


class NeedLogin(DownloadError):
    """A public or authenticated session is required."""


MEDIA_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".heic", ".heif",
    ".mp4", ".m4v", ".mov", ".webm", ".mkv", ".avi", ".3gp",
    ".mp3", ".m4a", ".aac", ".wav", ".ogg", ".opus", ".flac",
}
VIDEO_EXTENSIONS = {".mp4", ".m4v", ".mov", ".webm", ".mkv", ".avi", ".3gp"}
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".aac", ".wav", ".ogg", ".opus", ".flac"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".heic", ".heif"}


def safe(value):
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(value or "")).strip(" .")
    text = re.sub(r"\s+", "_", text)
    return text[:100] or "unknown"


def extract_urls(text):
    urls = re.findall(r"https?://[^\s<>\"']+", text or "")
    result = []
    for url in urls:
        cleaned = url.rstrip(".,;!?)]}>")
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result


def detect_platform(url):
    value = (url or "").lower()
    if "instagram.com" in value:
        return "instagram"
    if "youtu.be" in value or "youtube.com" in value or "youtube-nocookie.com" in value:
        return "youtube"
    if "x.com" in value or "twitter.com" in value or "t.co/" in value:
        return "twitter"
    if "facebook.com" in value or "fb.watch" in value or "fb.com" in value:
        return "facebook"
    if "tiktok.com" in value:
        return "tiktok"
    if "pinterest.com" in value or "pin.it/" in value:
        return "pinterest"
    if "threads.net" in value or "threads.com" in value:
        return "threads"
    return None


def _media_files(folder):
    found = []
    for current, _directories, names in os.walk(folder):
        for name in names:
            if os.path.splitext(name)[1].lower() not in MEDIA_EXTENSIONS:
                continue
            path = os.path.join(current, name)
            try:
                if os.path.isfile(path) and os.path.getsize(path) > 0:
                    found.append(path)
            except OSError:
                pass
    return found


def _deep_value(data, keys):
    """Find the first useful metadata field, including nested owner/post objects."""
    if not isinstance(data, dict):
        return None
    for key in keys:
        value = data.get(key)
        if isinstance(value, (str, int, float)) and str(value).strip():
            return str(value).strip()
        if isinstance(value, dict):
            nested = _deep_value(value, ("text", "full_text", "username", "name", "id", "pk"))
            if nested:
                return nested
    for value in data.values():
        if isinstance(value, dict):
            result = _deep_value(value, keys)
            if result:
                return result
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    result = _deep_value(item, keys)
                    if result:
                        return result
    return None


def _caption(metadata):
    return _deep_value(metadata, (
        "caption", "description", "full_text", "tweet_text", "text",
        "content", "message", "title", "body",
    )) or ""


def _account_id(metadata):
    # Prefer a stable numeric/platform account ID; use the handle only as fallback.
    if isinstance(metadata, dict):
        for parent_key in ("owner", "user", "author", "uploader", "channel"):
            parent = metadata.get(parent_key)
            if isinstance(parent, dict):
                for key in ("id", "id_str", "pk", "user_id", "username", "screen_name", "name"):
                    value = parent.get(key)
                    if value not in (None, ""):
                        return safe(str(value).lstrip("@"))
    account = _deep_value(metadata, (
        "owner_id", "user_id", "author_id", "uploader_id", "channel_id",
        "screen_name", "username", "user_name", "account_id",
    ))
    if account:
        return safe(account.lstrip("@"))
    return "unknown"


def _post_id(metadata, url):
    post_id = _deep_value(metadata, (
        "post_shortcode", "shortcode", "tweet_id", "post_id", "media_id",
        "video_id", "id_str", "id", "pk",
    ))
    if post_id:
        return safe(post_id)
    match = re.search(
        r"/(?:reel|reels|p|tv|status|statuses|watch)/([A-Za-z0-9_-]+)",
        url or "", re.I
    )
    if match:
        return safe(match.group(1))
    digest = hashlib.sha256((url or "").encode("utf-8")).hexdigest()[:16]
    return "post_" + digest


def _write_post_text(folder, caption, source_url):
    os.makedirs(folder, exist_ok=True)
    caption_text = (caption or "").strip()
    if not caption_text:
        caption_text = "Caption was not provided by the source platform."
    with open(os.path.join(folder, "caption.txt"), "w", encoding="utf-8") as handle:
        handle.write(caption_text + "\n")
    with open(os.path.join(folder, "source.txt"), "w", encoding="utf-8") as handle:
        handle.write((source_url or "").strip() + "\n")


def _safe_move(source, destination):
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    target = destination
    if os.path.exists(target):
        stem, extension = os.path.splitext(target)
        index = 2
        while os.path.exists(f"{stem}_{index}{extension}"):
            index += 1
        target = f"{stem}_{index}{extension}"
    shutil.move(source, target)
    return target


def _ffmpeg_path():
    """Find the p4a FFmpeg executable, including Android's renamed native binary."""
    regular = shutil.which("ffmpeg")
    if regular:
        return regular
    try:
        native_dir = os.environ.get("SOCIASAVE_NATIVE_LIB_DIR")
        if not native_dir:
            from jnius import autoclass
            activity_class = autoclass("org.kivy.android.PythonActivity")
            native_dir = str(activity_class.mActivity.getApplicationInfo().nativeLibraryDir)
        candidate = os.path.join(native_dir, "libffmpegbin.so")
        if os.path.isfile(candidate):
            os.environ["LD_LIBRARY_PATH"] = native_dir + os.pathsep + os.environ.get("LD_LIBRARY_PATH", "")
            return candidate
    except Exception:
        pass
    return None


def ffmpeg_diagnostic():
    executable = _ffmpeg_path()
    if not executable:
        return "FFmpeg executable was not found in PATH or Android nativeLibraryDir."
    try:
        result = subprocess.run(
            [executable, "-version"], capture_output=True, text=True, timeout=20
        )
        if result.returncode != 0:
            return "FFmpeg exists but did not start: " + (result.stderr or result.stdout or "")[-500:]
        return "FFmpeg ready: " + (result.stdout or "").splitlines()[0]
    except Exception as exc:
        return "FFmpeg could not start: " + repr(exc)


def _probe_streams(path):
    executable = _ffmpeg_path()
    if not executable:
        return False, False
    try:
        result = subprocess.run(
            [executable, "-hide_banner", "-i", path],
            capture_output=True, text=True, timeout=30
        )
        details = (result.stderr or "") + (result.stdout or "")
        return "Video:" in details, "Audio:" in details
    except Exception:
        return False, False


def merge_separate_audio_video(folder, log):
    """Mux one video-only and one audio-only source into a single file."""
    executable = _ffmpeg_path()
    if not executable:
        log("FFmpeg missing: " + ffmpeg_diagnostic())
        return False

    stream_extensions = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS
    files = []
    for current, _directories, names in os.walk(folder):
        for name in names:
            path = os.path.join(current, name)
            if os.path.isfile(path) and os.path.splitext(name)[1].lower() in stream_extensions:
                files.append(path)
    video_only, audio_only = [], []
    for path in files:
        has_video, has_audio = _probe_streams(path)
        if has_video and not has_audio:
            video_only.append(path)
        elif has_audio and not has_video:
            audio_only.append(path)

    if not video_only and not audio_only:
        return True
    if len(video_only) != 1 or len(audio_only) != 1:
        log("Separate audio/video files could not be paired uniquely; original files preserved.")
        return False

    video_path, audio_path = video_only[0], audio_only[0]
    output_path = os.path.join(
        folder, os.path.splitext(os.path.basename(video_path))[0] + "_with_audio.mkv"
    )
    temporary = output_path + ".part.mkv"
    base = [
        executable, "-y", "-hide_banner", "-loglevel", "error",
        "-i", video_path, "-i", audio_path,
        "-map", "0:v:0", "-map", "1:a:0", "-shortest",
    ]
    attempts = [
        base + ["-c:v", "copy", "-c:a", "copy", temporary],
        base + ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", temporary],
    ]
    for command in attempts:
        try:
            if os.path.exists(temporary):
                os.remove(temporary)
            result = subprocess.run(command, capture_output=True, text=True, timeout=300)
            if result.returncode == 0 and os.path.isfile(temporary) and os.path.getsize(temporary) > 0:
                os.replace(temporary, output_path)
                if _probe_streams(output_path) != (True, True):
                    os.remove(output_path)
                    continue
                for source in (video_path, audio_path):
                    try:
                        os.remove(source)
                    except OSError:
                        pass
                log("Separate video and audio streams successfully merged.")
                return True
            log("FFmpeg mux attempt failed: " + (result.stderr or "no diagnostic")[-700:])
        except Exception as exc:
            log("FFmpeg mux exception: " + repr(exc))
    try:
        if os.path.exists(temporary):
            os.remove(temporary)
    except OSError:
        pass
    return False


class _GalleryLogHandler(logging.Handler):
    def __init__(self, log):
        super().__init__(logging.INFO)
        self._log = log

    def emit(self, record):
        try:
            self._log(record.getMessage())
        except Exception:
            pass


def _download_gallery_post(url, root, platform_name, cookies_file, log):
    """Use gallery-dl for image-rich Instagram and X posts, including carousels."""
    from gallery_dl import config, job

    temp_root = tempfile.mkdtemp(prefix="sociasave_" + platform_name + "_", dir=root)
    handler = _GalleryLogHandler(log)
    logger = logging.getLogger()
    old_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(min(old_level or logging.WARNING, logging.INFO))
    try:
        config.clear()
        config.set(("extractor",), "base-directory", temp_root)
        config.set(("extractor",), "directory", [])
        config.set(("extractor",), "filename", "{filename}.{extension}")
        if cookies_file and os.path.isfile(cookies_file):
            config.set(("extractor",), "cookies", cookies_file)
        config.set(("extractor",), "postprocessors", [
            {"name": "metadata", "mode": "json", "filename": "{filename}.{extension}.json"}
        ])
        if platform_name == "instagram":
            config.set(("extractor", "instagram"), "include", "posts,reels")
            config.set(("extractor", "instagram"), "videos", True)
            # gallery-dl's audio=True downloads a separate audio rendition.
            # Reels should be saved as their original video container with sound.
            config.set(("extractor", "instagram"), "audio", False)
            config.set(("extractor", "instagram"), "previews", False)
            if cookies_file and os.path.isfile(cookies_file):
                config.set(("extractor", "instagram"), "cookies", cookies_file)
                log("Instagram: using saved app-private session cookies.")
        elif platform_name == "facebook":
            config.set(("extractor", "facebook"), "videos", True)
            config.set(("extractor", "facebook"), "include", "photos")
            if cookies_file and os.path.isfile(cookies_file):
                config.set(("extractor", "facebook"), "cookies", cookies_file)
                log("Facebook: using saved app-private session cookies.")
        elif platform_name == "tiktok":
            # Avoid gallery-dl's optional separate audio rendition.
            config.set(("extractor", "tiktok"), "videos", True)
            config.set(("extractor", "tiktok"), "audio", False)
            config.set(("extractor", "tiktok"), "photos", True)
            if cookies_file and os.path.isfile(cookies_file):
                config.set(("extractor", "tiktok"), "cookies", cookies_file)
                log("TikTok: using saved app-private session cookies.")
        elif platform_name == "pinterest":
            config.set(("extractor", "pinterest"), "videos", True)
            config.set(("extractor", "pinterest"), "stories", True)
            config.set(("extractor", "pinterest"), "sections", True)
            if cookies_file and os.path.isfile(cookies_file):
                config.set(("extractor", "pinterest"), "cookies", cookies_file)
                log("Pinterest: using saved app-private session cookies.")
        elif platform_name == "twitter":
            log("X/Twitter: downloading media from the public post.")
            if cookies_file and os.path.isfile(cookies_file):
                config.set(("extractor", "twitter"), "cookies", cookies_file)
        job.DownloadJob(url).run()

        media = _media_files(temp_root)
        if not media:
            if platform_name == "instagram":
                raise NeedLogin("Instagram returned no media. The session may have expired or the post may require access.")
            raise DownloadError(platform_name + " returned no public media for this post.")

        folders, moved, captions = [], set(), {}
        for current, _dirs, names in os.walk(temp_root):
            for name in names:
                if not name.lower().endswith(".json"):
                    continue
                sidecar = os.path.join(current, name)
                media_path = sidecar[:-5]
                if not os.path.isfile(media_path):
                    continue
                try:
                    with open(sidecar, "r", encoding="utf-8") as handle:
                        metadata = json.load(handle)
                except Exception:
                    metadata = {}

                account_id = _account_id(metadata)
                # Keep every carousel/reel asset under the post URL's stable ID.
                post_id = _post_id({}, url) or _post_id(metadata, url)
                destination = os.path.join(root, platform_name, account_id, post_id)
                os.makedirs(destination, exist_ok=True)
                target = os.path.join(destination, os.path.basename(media_path))
                saved = _safe_move(media_path, target)
                moved.add(os.path.abspath(media_path))
                captions[destination] = _caption(metadata) or captions.get(destination, "")
                if destination not in folders:
                    folders.append(destination)

        remaining = [
            path for path in media
            if os.path.exists(path) and os.path.abspath(path) not in moved
        ]
        if remaining:
            account_id = "unknown"
            post_id = _post_id({}, url)
            destination = os.path.join(root, platform_name, account_id, post_id)
            os.makedirs(destination, exist_ok=True)
            for media_path in remaining:
                _safe_move(media_path, os.path.join(destination, os.path.basename(media_path)))
            if destination not in folders:
                folders.append(destination)

        for destination in folders:
            _write_post_text(destination, captions.get(destination, ""), url)
            if not merge_separate_audio_video(destination, log):
                raise DownloadError(
                    platform_name + " returned separate audio/video tracks, but FFmpeg could not combine them. "
                    "Original tracks were preserved in the staging folder."
                )

        if not folders:
            raise DownloadError("The extractor found files but could not organize them.")
        log(platform_name + " post media saved into its account/post folder.")
        return folders[0]
    except (NeedLogin, DownloadError):
        raise
    except Exception as exc:
        raise DownloadError(platform_name + " extraction failed: " + str(exc)) from exc
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)
        shutil.rmtree(temp_root, ignore_errors=True)


class _YtLogger:
    def __init__(self, log):
        self.log = log

    def debug(self, _message):
        pass

    def info(self, _message):
        pass

    def warning(self, message):
        self.log("Extractor warning: " + str(message))

    def error(self, message):
        self.log("Extractor error: " + str(message))


def _download_ytdlp(url, root, platform_name, log, on_progress=None, cookies_file=None):
    """Use yt-dlp for YouTube and Facebook video posts."""
    import yt_dlp

    executable = _ffmpeg_path()
    if not executable:
        raise DownloadError("FFmpeg is not executable on this device. " + ffmpeg_diagnostic())
    log(ffmpeg_diagnostic())

    attempts = (None, ["web_embedded"], ["mweb"]) if platform_name == "youtube" else (None,)
    last_error = None
    for player_clients in attempts:
        options = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "logger": _YtLogger(log),
            "retries": 3,
            "fragment_retries": 3,
            "extractor_retries": 3,
            "socket_timeout": 35,
            "ffmpeg_location": executable,
        }
        if cookies_file and os.path.isfile(cookies_file):
            options["cookiefile"] = cookies_file
            log(platform_name + ": using saved app-private session cookies.")
        if platform_name == "youtube":
            options["remote_components"] = ["ejs:github"]
            if player_clients:
                options["extractor_args"] = {"youtube": {"player_client": player_clients}}

        label = "yt-dlp defaults" if not player_clients else ",".join(player_clients)
        log(platform_name + ": extracting metadata using " + label + ".")
        try:
            with yt_dlp.YoutubeDL(options) as downloader:
                info = downloader.extract_info(url, download=False)
            if not isinstance(info, dict) or not info.get("formats"):
                raise DownloadError(platform_name + " returned no downloadable formats.")
            if info.get("is_live") and not info.get("was_live"):
                raise DownloadError("Live streams are not supported.")

            account_id = safe(
                info.get("channel_id") or info.get("uploader_id")
                or info.get("channel") or info.get("uploader") or "unknown"
            )
            post_id = safe(info.get("id") or "post")
            destination = os.path.join(root, platform_name, account_id, post_id)
            os.makedirs(destination, exist_ok=True)

            def progress_hook(data):
                if not on_progress:
                    return
                if data.get("status") == "downloading":
                    total = data.get("total_bytes") or data.get("total_bytes_estimate")
                    if total:
                        on_progress((data.get("downloaded_bytes") or 0) * 100.0 / total)
                elif data.get("status") == "finished":
                    on_progress(100)

            options.update({
                # Prefer a progressive stream (video+audio in one file).
                # Only fall back to separate best-video + best-audio when needed.
                "format": "best[acodec!=none][vcodec!=none]/bv+ba/b",
                "merge_output_format": "mkv",
                "outtmpl": os.path.join(destination, "%(title).120B.%(ext)s"),
                "progress_hooks": [progress_hook],
                "overwrites": False,
                "keepvideo": False,
            })
            with yt_dlp.YoutubeDL(options) as downloader:
                result = downloader.download([url])
            if result not in (None, 0):
                raise DownloadError("yt-dlp returned exit code " + str(result))

            saved = _media_files(destination)
            combined = [path for path in saved if _probe_streams(path) == (True, True)]
            if not combined:
                merged = merge_separate_audio_video(destination, log)
                saved = _media_files(destination)
                combined = [path for path in saved if _probe_streams(path) == (True, True)]
                if not merged or not combined:
                    raise DownloadError(
                        platform_name + " completed extraction but produced no single file containing both video and audio."
                    )

            _write_post_text(destination, info.get("description") or info.get("title") or "", url)
            log(platform_name + " media and caption saved into the account/post folder.")
            return destination
        except Exception as exc:
            last_error = exc
            log(platform_name + " attempt (" + label + ") failed: " + repr(exc))
            if "destination" in locals() and os.path.isdir(destination):
                shutil.rmtree(destination, ignore_errors=True)
            continue

    raise DownloadError(str(last_error or platform_name + " could not extract this post."))


def run(url, root, cookies_file, log, on_progress=None):
    platform_name = detect_platform(url)
    if not platform_name:
        raise DownloadError("Unsupported link. Use Instagram, YouTube, X, Facebook, TikTok or Pinterest.")
    os.makedirs(root, exist_ok=True)
    log("Detected platform: " + platform_name)
    if platform_name in ("instagram", "twitter"):
        return _download_gallery_post(url, root, platform_name, cookies_file, log)
    if platform_name == "pinterest":
        # First use a dedicated public Pin-page extractor. Keep maintained
        # extractors as fallback for page variants we do not yet understand.
        try:
            from pinterest_extractor import download_pin
            return download_pin(
                url, root, cookies_file=cookies_file, log=log,
                ffmpeg_path=_ffmpeg_path(),
            )
        except Exception as direct_error:
            log("Pinterest direct page extraction failed; trying gallery-dl: " + repr(direct_error))
        try:
            return _download_gallery_post(url, root, platform_name, cookies_file, log)
        except Exception as gallery_error:
            log("Pinterest gallery-dl path failed; trying yt-dlp: " + repr(gallery_error))
            try:
                return _download_ytdlp(url, root, platform_name, log, on_progress, cookies_file)
            except Exception as ytdlp_error:
                raise DownloadError(
                    "Pinterest direct extractor, gallery-dl and yt-dlp all failed. "
                    "Direct: " + str(direct_error)[:180] +
                    " | gallery-dl: " + str(gallery_error)[:180] +
                    " | yt-dlp: " + str(ytdlp_error)[:180]
                ) from ytdlp_error
    if platform_name in ("facebook", "tiktok"):
        # Use a second maintained extractor when the first one cannot parse the
        # current page or cannot produce a muxed audio/video file.
        try:
            return _download_ytdlp(url, root, platform_name, log, on_progress, cookies_file)
        except Exception as ytdlp_error:
            log(platform_name + " yt-dlp path failed; trying gallery-dl: " + repr(ytdlp_error))
            return _download_gallery_post(url, root, platform_name, cookies_file, log)
    return _download_ytdlp(url, root, platform_name, log, on_progress, cookies_file)


def friendly_error(url, error):
    platform_name = detect_platform(url) or "social media"
    message = str(error or "")
    lowered = message.lower()
    if "ffmpeg" in lowered:
        return "Media processing failed: " + message[:240]
    if platform_name == "instagram":
        if any(token in lowered for token in ("login", "checkpoint", "challenge", "401", "403", "session")):
            return "Instagram needs a fresh login or access to this post. Tap Connect to Instagram and sign in again."
        if "429" in lowered or "rate limit" in lowered:
            return "Instagram temporarily limited requests. Wait and retry later."
        return "Instagram could not retrieve this post. Check its link and account permissions."
    if platform_name == "youtube":
        if any(token in lowered for token in ("ejs", "javascript runtime", "deno", "js challenge")):
            return "YouTube needs its JavaScript challenge runtime, which is not available in this build. A public video may still work when YouTube supplies a direct stream."
        if any(token in lowered for token in ("po token", "pot provider", "403", "sabr", "not a bot")):
            return "YouTube blocked this stream request with an anti-bot or PO Token check. This can happen even when the video plays in the YouTube app."
        if any(token in lowered for token in ("sign in to confirm", "age-restricted", "members-only", "private video", "login required")):
            return "This YouTube video requires login, age verification or membership. Try a public video."
        if "unavailable" in lowered or "removed" in lowered:
            return "This YouTube video is unavailable or region-restricted."
        return "YouTube could not retrieve compatible media streams: " + message[:220]
    if platform_name == "twitter":
        if "login" in lowered or "protected" in lowered:
            return "This X/Twitter post may be private or require an account session. Only accessible posts are supported."
        return "X/Twitter could not retrieve media from this post: " + message[:220]
    if platform_name == "facebook":
        if any(token in lowered for token in ("login", "private", "cookie", "403")):
            return "This Facebook post may require login or permission. Only publicly accessible content is supported."
        return "Facebook could not retrieve compatible media: " + message[:220]
    if platform_name == "tiktok":
        return "TikTok could not retrieve this post. Check that it is public and available in your region: " + message[:180]
    if platform_name == "pinterest":
        return "Pinterest could not retrieve this Pin. Check that the Pin is public and the link is valid: " + message[:180]
    if platform_name == "threads":
        return "Threads supports public video posts only in this build. Private, login-gated, image-only and text-only posts are not supported."
    return "The link could not be downloaded: " + message[:220]
