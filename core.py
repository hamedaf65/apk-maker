"""Separate download engine used by the ClipDrop mobile UI."""
import json
import logging
import os
import re
import shutil
import tempfile

try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except Exception:
    pass


class DownloadError(RuntimeError):
    """A download failed or produced no media."""


class NeedLogin(DownloadError):
    """A service requires a valid authenticated session."""


MEDIA_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".heic", ".heif",
    ".mp4", ".m4v", ".mov", ".webm", ".mkv", ".avi", ".3gp", ".mp3", ".m4a",
}


def safe(name):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(name)).strip(" .")
    return value[:120] or "unknown"


def extract_urls(text):
    urls = re.findall(r"https?://[^\s<>""']+", text or "")
    return [url.rstrip(".,;!?)]}>") for url in urls]


def _media_files(folder):
    result = []
    for current, _dirs, names in os.walk(folder):
        for name in names:
            if os.path.splitext(name)[1].lower() not in MEDIA_EXTENSIONS:
                continue
            path = os.path.join(current, name)
            try:
                if os.path.getsize(path) > 0:
                    result.append(path)
            except OSError:
                pass
    return result


class _LogHandler(logging.Handler):
    def __init__(self, log):
        super().__init__(logging.INFO)
        self._write_log = log

    def emit(self, record):
        try:
            self._write_log(record.getMessage())
        except Exception:
            pass


def download_instagram(url, root, cookies_file, log):
    """Download supported Instagram posts/reels; retain media even without sidecar metadata."""
    from gallery_dl import config, job

    temp_root = tempfile.mkdtemp(prefix="clipdrop_ig_", dir=root)
    handler = _LogHandler(log)
    root_logger = logging.getLogger()
    previous_level = root_logger.level
    root_logger.addHandler(handler)
    root_logger.setLevel(min(previous_level or logging.WARNING, logging.INFO))
    try:
        config.clear()
        config.set(("extractor",), "base-directory", temp_root)
        config.set(("extractor",), "directory", [])
        config.set(("extractor",), "filename", "{filename}.{extension}")
        config.set(("extractor",), "postprocessors", [
            {"name": "metadata", "mode": "json", "filename": "{filename}.{extension}.json"}
        ])
        # gallery-dl supports both individual Posts and Reels; videos=True makes
        # video media explicit rather than silently limiting downloads to photos.
        config.set(("extractor", "instagram"), "include", "posts,reels")
        config.set(("extractor", "instagram"), "videos", True)
        config.set(("extractor", "instagram"), "previews", False)
        if cookies_file and os.path.isfile(cookies_file):
            config.set(("extractor", "instagram"), "cookies", cookies_file)
            log("Instagram: using saved app-private session cookies.")
        else:
            log("Instagram: attempting public post/reel access.")

        job.DownloadJob(url).run()
        media = _media_files(temp_root)
        if not media:
            if cookies_file:
                raise NeedLogin("No media returned with saved cookies; the session may be expired or Instagram may require a new login.")
            raise NeedLogin("No media returned. This post may require an Instagram login or may be unavailable.")

        # Match media to metadata where possible, but do not depend on JSON
        # sidecars: some Reel responses produce video files without sidecars.
        moved = set()
        folders = []
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
                    owner = metadata.get("username") or (metadata.get("owner") or {}).get("username") or "Instagram"
                    post_id = metadata.get("post_shortcode") or metadata.get("shortcode") or metadata.get("post_id") or "post"
                except Exception:
                    owner, post_id = "Instagram", "post"
                destination = os.path.join(root, safe(owner), safe(post_id))
                os.makedirs(destination, exist_ok=True)
                target = os.path.join(destination, os.path.basename(media_path))
                if os.path.exists(target):
                    stem, ext = os.path.splitext(target)
                    index = 2
                    while os.path.exists(f"{stem}_{index}{ext}"):
                        index += 1
                    target = f"{stem}_{index}{ext}"
                shutil.move(media_path, target)
                moved.add(os.path.abspath(media_path))
                if destination not in folders:
                    folders.append(destination)

        # Fallback: media exists but extractor did not supply a paired JSON file.
        remaining = [path for path in media if os.path.exists(path) and os.path.abspath(path) not in moved]
        if remaining:
            match = re.search(r"/(?:reel|reels|p|tv)/([A-Za-z0-9_-]+)", url)
            post_id = safe(match.group(1) if match else "instagram_post")
            destination = os.path.join(root, "Instagram", post_id)
            os.makedirs(destination, exist_ok=True)
            for media_path in remaining:
                target = os.path.join(destination, os.path.basename(media_path))
                if os.path.exists(target):
                    stem, ext = os.path.splitext(target)
                    index = 2
                    while os.path.exists(f"{stem}_{index}{ext}"):
                        index += 1
                    target = f"{stem}_{index}{ext}"
                shutil.move(media_path, target)
            folders.append(destination)

        if not folders:
            raise DownloadError("Instagram extractor returned no files that could be saved.")
        log("Instagram media saved.")
        return folders[-1]
    except NeedLogin:
        raise
    except Exception as exc:
        raise DownloadError(f"Instagram download failed: {exc}") from exc
    finally:
        root_logger.removeHandler(handler)
        root_logger.setLevel(previous_level)
        shutil.rmtree(temp_root, ignore_errors=True)


class _YtLogger:
    def __init__(self, log):
        self.log = log

    def debug(self, _message):
        pass

    def info(self, _message):
        pass

    def warning(self, message):
        self.log("YouTube warning: " + str(message))

    def error(self, message):
        self.log("YouTube error: " + str(message))


def download_youtube(url, root, cookies_file, log, on_progress=None):
    """Download public YouTube media; accepts only a YouTube-specific cookie file."""
    import yt_dlp

    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "logger": _YtLogger(log),
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 25,
    }
    if cookies_file and os.path.isfile(cookies_file):
        options["cookiefile"] = cookies_file

    log("YouTube: retrieving video information.")
    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(url, download=False)
    except Exception as exc:
        raise DownloadError(str(exc)) from exc

    if not isinstance(info, dict):
        raise DownloadError("YouTube did not return video information.")
    if info.get("is_live") and not info.get("was_live"):
        raise DownloadError("Live streams are not supported.")

    owner = info.get("uploader_id") or info.get("channel") or info.get("uploader") or "YouTube"
    video_id = info.get("id") or "video"
    destination = os.path.join(root, safe(str(owner).lstrip("@")), safe(video_id))
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

    download_options = dict(options)
    download_options.update({
        # Android build does not package FFmpeg; choose one progressive video+audio file.
        "format": "b[ext=mp4]/b",
        "outtmpl": os.path.join(destination, "%(title).100B.%(ext)s"),
        "progress_hooks": [progress_hook],
        "overwrites": False,
    })
    try:
        with yt_dlp.YoutubeDL(download_options) as downloader:
            result = downloader.download([url])
        if result not in (None, 0):
            raise DownloadError(f"yt-dlp returned exit code {result}.")
    except Exception as exc:
        raise DownloadError(str(exc)) from exc

    if not _media_files(destination):
        raise DownloadError("No video file was saved. This format may not be available for this video.")
    log("YouTube video saved.")
    return destination


def run(url, root, cookies_file, log, on_progress=None):
    lowered = (url or "").lower()
    if "instagram.com" in lowered:
        return download_instagram(url, root, cookies_file, log)
    if "youtube.com" in lowered or "youtu.be" in lowered:
        return download_youtube(url, root, None, log, on_progress)
    raise DownloadError("Unsupported link. Use an Instagram or YouTube URL.")


def friendly_error(url, error):
    message = str(error or "").lower()
    instagram = "instagram.com" in (url or "").lower()

    if instagram:
        if any(word in message for word in ("429", "too many requests", "rate limit")):
            return "Instagram temporarily limited requests. Wait and retry later."
        if any(word in message for word in ("login", "checkpoint", "challenge", "401", "403", "session")):
            return "Instagram needs a fresh login or has challenged this session. Tap Connect to Instagram, sign in again, then retry."
        return "Instagram could not download this post/reel. Check the link and account access, then try again."

    if any(word in message for word in ("sign in to confirm", "confirm you're not a bot", "confirm you’re not a bot",
                                        "age-restricted", "members-only", "private video", "login required")):
        return ("YouTube requires account verification or restricts this video. This app does not embed Google sign-in; "
                "try a public video that plays without login or age verification.")
    if any(word in message for word in ("video unavailable", "not available in your country", "has been removed")):
        return "This YouTube video is unavailable, removed or region-restricted."
    if any(word in message for word in ("ffmpeg", "requested format", "format is not available")):
        return "No compatible single-file video format was found on this device. Try another public video."
    return "YouTube could not download this video. Check the link and try a public, playable video."
