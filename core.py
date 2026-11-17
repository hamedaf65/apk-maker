"""Download logic (no UI). Works on Android and desktop."""
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


def safe(name):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(name)).strip(" .")
    return name[:120] or "unknown"


def extract_urls(text):
    return re.findall(r"https?://[^\s]+", text)


class _LogHandler(logging.Handler):
    def __init__(self, log):
        super().__init__(logging.INFO)
        self.log = log

    def emit(self, record):
        try:
            self.log(record.getMessage())
        except Exception:
            pass


def download_instagram(url, root, cookies_file, log):
    from gallery_dl import config, job

    tmp = tempfile.mkdtemp(prefix="igdl_", dir=root)
    handler = _LogHandler(log)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
    try:
        config.clear()
        config.set((), "base-directory", tmp)
        config.set(("extractor",), "directory", [])
        config.set(("extractor",), "filename", "{filename}.{extension}")
        config.set(("extractor",), "postprocessors", [
            {"name": "metadata", "mode": "json", "filename": "{filename}.{extension}.json"}])
        if cookies_file and os.path.exists(cookies_file):
            config.set(("extractor",), "cookies", cookies_file)

        log("Downloading from Instagram ...")
        job.DownloadJob(url).run()

        groups = {}
        for fn in os.listdir(tmp):
            if not fn.endswith(".json"):
                continue
            media = fn[:-5]
            if not os.path.exists(os.path.join(tmp, media)):
                continue
            with open(os.path.join(tmp, fn), encoding="utf-8") as f:
                meta = json.load(f)
            user = meta.get("username") or (meta.get("owner") or {}).get("username") or "unknown"
            code = meta.get("post_shortcode") or meta.get("shortcode") or meta.get("post_id") or "post"
            g = groups.setdefault((user, str(code)), {"files": [], "caption": meta.get("description") or ""})
            g["files"].append(media)

        if not groups:
            raise RuntimeError("Nothing downloaded. Instagram needs login: put cookies.txt in the "
                               "SocialDownloader folder (see README).")

        last = None
        for (user, code), g in groups.items():
            dest = os.path.join(root, safe(user), safe(code))
            os.makedirs(dest, exist_ok=True)
            for media in g["files"]:
                target = os.path.join(dest, media)
                if os.path.exists(target):
                    os.remove(target)
                shutil.move(os.path.join(tmp, media), target)
            with open(os.path.join(dest, "caption.txt"), "w", encoding="utf-8") as f:
                f.write(g["caption"])
            log("Saved: " + dest)
            last = dest
        return last
    finally:
        root_logger.removeHandler(handler)
        shutil.rmtree(tmp, ignore_errors=True)


class _YtLogger:
    def __init__(self, log):
        self.log = log

    def debug(self, m):
        pass

    info = debug

    def warning(self, m):
        pass

    def error(self, m):
        self.log(str(m))


def download_youtube(url, root, cookies_file, log, on_progress=None):
    import yt_dlp

    base = {"quiet": True, "no_warnings": True, "noplaylist": True,
            "windowsfilenames": True, "logger": _YtLogger(log)}
    if cookies_file and os.path.exists(cookies_file):
        base["cookiefile"] = cookies_file

    log("Fetching video info ...")
    with yt_dlp.YoutubeDL(base) as y:
        info = y.extract_info(url, download=False)

    channel = info.get("uploader_id") or info.get("channel") or info.get("uploader") or "unknown"
    dest = os.path.join(root, safe(str(channel).lstrip("@")), safe(info.get("id")))
    os.makedirs(dest, exist_ok=True)

    def hook(d):
        if d["status"] == "downloading" and on_progress:
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            if total:
                on_progress(d["downloaded_bytes"] * 100.0 / total)

    opts = dict(base)
    opts.update({
        # no ffmpeg on the phone -> best single file that already contains video+audio
        "format": "b[ext=mp4]/b",
        "outtmpl": os.path.join(dest, "%(title).100B.%(ext)s"),
        "progress_hooks": [hook],
    })
    with yt_dlp.YoutubeDL(opts) as y:
        y.download([url])

    with open(os.path.join(dest, "caption.txt"), "w", encoding="utf-8") as f:
        f.write(info.get("description") or "")
    log("Saved: " + dest)
    return dest


def run(url, root, cookies_file, log, on_progress=None):
    low = url.lower()
    if "instagram.com" in low:
        return download_instagram(url, root, cookies_file, log)
    if "youtube.com" in low or "youtu.be" in low:
        return download_youtube(url, root, cookies_file, log, on_progress)
    log("Unsupported link.")
    return None
