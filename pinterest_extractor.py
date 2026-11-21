"""Clean-room Pinterest Pin resolver and media downloader.

This module deliberately uses only the app's existing requests + FFmpeg
dependencies. It reads public page metadata and downloads the original CDN
asset; it does not copy code from third-party downloader applications.
"""
import html
import http.cookiejar
import json
import os
import re
import subprocess
from html.parser import HTMLParser
from urllib.parse import urlparse

import requests

USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 13; Mobile) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)
PIN_ID_RE = re.compile(r"/pin/(?:[^/]*?--)?(\d{6,})", re.I)
VIDEO_RE = re.compile(
    r"https?://[^\s<>\\]+?\.(?:mp4|m3u8)(?:\?[^\s<>\\]*)?",
    re.I,
)
IMAGE_RE = re.compile(
    r"https?://i\.pinimg\.com/(?:originals|\d+x\d+(?:_RS)?)/"
    r"[A-Za-z0-9_./-]+?\.(?:jpe?g|png|webp|gif)(?:\?[^\s<>\\]*)?",
    re.I,
)


class _MetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "meta":
            return
        values = dict(attrs)
        key = (values.get("property") or values.get("name") or "").lower()
        value = values.get("content")
        if key and value:
            self.meta[key] = html.unescape(value)


def _clean_url(value):
    value = html.unescape(str(value or "")).replace("\\/", "/").replace("\\u002F", "/")
    value = value.replace("\\u003D", "=").replace("\\u0026", "&").replace("&amp;", "&")
    return value.strip().rstrip("),;]}")


def _walk_json(value, urls, texts):
    if isinstance(value, dict):
        for key, item in value.items():
            key_lower = str(key).lower()
            if isinstance(item, str):
                candidate = _clean_url(item)
                if candidate.startswith(("https://", "http://")):
                    urls.append((key_lower, candidate))
                if key_lower in ("description", "title", "text", "closeup_description"):
                    texts.append(item)
                # Pinterest sometimes stores serialized JSON inside a string.
                if len(item) > 80 and ("pinimg.com" in item or "video_list" in item or "videos" in item):
                    try:
                        _walk_json(json.loads(item), urls, texts)
                    except Exception:
                        pass
            elif isinstance(item, (dict, list)):
                _walk_json(item, urls, texts)
    elif isinstance(value, list):
        for item in value:
            _walk_json(item, urls, texts)


def extract_page_data(page, source_url):
    """Return (video_urls, image_urls, caption, pin_id) from Pinterest HTML."""
    parser = _MetaParser()
    try:
        parser.feed(page)
    except Exception:
        pass
    meta = parser.meta
    pin_match = PIN_ID_RE.search(source_url)
    pin_id = pin_match.group(1) if pin_match else ""
    caption = meta.get("og:description") or meta.get("description") or meta.get("twitter:description") or ""
    urls, texts = [], []

    # Parse JSON-LD and Pinterest's server-rendered state script payloads.
    for match in re.finditer(r"<script\b[^>]*>(.*?)</script\s*>", page, re.I | re.S):
        raw = html.unescape(match.group(1)).strip()
        if not raw or len(raw) < 2:
            continue
        try:
            _walk_json(json.loads(raw), urls, texts)
        except Exception:
            continue

    # Also scan raw markup: some state blobs are escaped/non-standard JSON.
    normalized = page.replace("\\/", "/").replace("\\u002F", "/")
    for match in VIDEO_RE.finditer(normalized):
        urls.append(("raw_video", _clean_url(match.group(0))))
    for match in IMAGE_RE.finditer(normalized):
        urls.append(("raw_image", _clean_url(match.group(0))))

    video_urls = []
    image_urls = []
    for key, candidate in urls:
        candidate = _clean_url(candidate)
        lower = candidate.lower()
        if "pinimg.com" in lower and (".mp4" in lower or ".m3u8" in lower):
            video_urls.append(candidate)
        elif re.search(r"\.(?:mp4|m3u8)(?:\?|$)", lower):
            video_urls.append(candidate)
        elif "i.pinimg.com/" in lower and re.search(r"\.(?:jpe?g|png|webp|gif)(?:\?|$)", lower):
            image_urls.append(candidate)

    og_image = meta.get("og:image") or meta.get("twitter:image:src") or meta.get("twitter:image")
    if og_image and "i.pinimg.com/" in og_image:
        image_urls.append(_clean_url(og_image))

    def unique(items):
        result = []
        for item in items:
            if item.startswith("https://") and item not in result:
                result.append(item)
        return result

    # Prefer progressive MP4 over HLS; within each class prefer 720p/original.
    videos = unique(video_urls)
    videos.sort(key=lambda u: (
        1 if ".m3u8" in u.lower() else 0,
        0 if "720p" in u.lower() else 1,
        0 if "expmp4" not in u.lower() else 1,
        -len(u),
    ))
    images = unique(image_urls)
    images.sort(key=lambda u: (
        0 if "/originals/" in u.lower() else 1,
        -len(u),
    ))
    if not caption and texts:
        caption = next((str(x).strip() for x in texts if str(x).strip()), "")
    return videos, images, caption, pin_id


def _session(cookies_file=None):
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.pinterest.com/",
    })
    if cookies_file and os.path.isfile(cookies_file):
        try:
            jar = http.cookiejar.MozillaCookieJar()
            jar.load(cookies_file, ignore_discard=True, ignore_expires=True)
            session.cookies.update(jar)
        except Exception:
            # Invalid or non-Netscape cookie exports should not block public Pins.
            pass
    return session


def _download_file(session, url, destination, referer, timeout=60, on_progress=None):
    headers = {"Referer": referer, "User-Agent": USER_AGENT}
    response = session.get(url, headers=headers, stream=True, timeout=timeout)
    response.raise_for_status()
    content_type = (response.headers.get("Content-Type") or "").lower()
    try:
        total_bytes = int(response.headers.get("Content-Length") or 0)
    except (TypeError, ValueError):
        total_bytes = 0
    downloaded_bytes = 0
    if on_progress and not total_bytes:
        on_progress(None)
    if "text/html" in content_type:
        raise RuntimeError("Pinterest CDN returned an HTML page instead of media.")
    temporary = destination + ".part"
    try:
        with open(temporary, "wb") as handle:
            for chunk in response.iter_content(256 * 1024):
                if chunk:
                    handle.write(chunk)
                    downloaded_bytes += len(chunk)
                    if on_progress and total_bytes:
                        on_progress(min(100.0, downloaded_bytes * 100.0 / total_bytes))
        if not os.path.isfile(temporary) or os.path.getsize(temporary) < 128:
            raise RuntimeError("Pinterest returned an empty media file.")
        os.replace(temporary, destination)
        if on_progress and total_bytes:
            on_progress(100.0)
    finally:
        response.close()
        if os.path.exists(temporary):
            os.remove(temporary)


def _download_hls(url, destination, referer, ffmpeg_path, log, on_progress=None):
    if not ffmpeg_path:
        raise RuntimeError("Pinterest supplied HLS video, but FFmpeg is unavailable.")
    temporary = destination + ".part.mp4"
    if on_progress:
        on_progress(None)
    headers = "User-Agent: " + USER_AGENT + "\r\nReferer: " + referer + "\r\n"
    command = [
        ffmpeg_path, "-y", "-hide_banner", "-loglevel", "error",
        "-headers", headers, "-i", url, "-c", "copy", "-movflags", "+faststart",
        temporary,
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=900)
    if result.returncode != 0 or not os.path.isfile(temporary) or os.path.getsize(temporary) < 1024:
        detail = (result.stderr or "FFmpeg could not read the Pinterest HLS stream.")[-500:]
        if os.path.exists(temporary):
            os.remove(temporary)
        raise RuntimeError(detail)
    os.replace(temporary, destination)
    if on_progress:
        on_progress(100.0)
    log("Pinterest HLS stream was remuxed to MP4.")


def download_pin(url, root, cookies_file=None, log=None, ffmpeg_path=None, on_progress=None):
    """Resolve a public Pin and save its image/video plus caption/source files."""
    log = log or (lambda _message: None)
    session = _session(cookies_file)
    response = session.get(url, allow_redirects=True, timeout=45)
    response.raise_for_status()
    final_url = response.url
    page = response.text or ""
    if "pinterest." not in urlparse(final_url).netloc.lower():
        raise RuntimeError("The short link did not resolve to a Pinterest Pin.")
    videos, images, caption, pin_id = extract_page_data(page, final_url)
    if not pin_id:
        match = PIN_ID_RE.search(final_url)
        pin_id = match.group(1) if match else "pin"

    account_id = "unknown"
    destination = os.path.join(root, "pinterest", account_id, pin_id)
    os.makedirs(destination, exist_ok=True)

    # Prefer video when Pinterest exposes a video rendition; otherwise save the Pin image.
    failures = []
    for media_url in videos:
        is_hls = ".m3u8" in media_url.lower()
        extension = ".mp4"
        target = os.path.join(destination, "pinterest_" + pin_id + extension)
        try:
            if is_hls:
                _download_hls(media_url, target, final_url, ffmpeg_path, log, on_progress)
            else:
                _download_file(session, media_url, target, final_url, on_progress=on_progress)
            _write_text(destination, caption, final_url)
            log("Pinterest video downloaded from the Pin page.")
            response.close()
            return destination
        except Exception as exc:
            failures.append(str(exc))
            log("Pinterest video candidate failed: " + str(exc)[:220])

    downloaded_images = 0
    for index, media_url in enumerate(images, 1):
        path = urlparse(media_url).path.lower()
        extension = os.path.splitext(path)[1]
        if extension == ".jpeg":
            extension = ".jpg"
        if extension not in (".jpg", ".png", ".webp", ".gif"):
            extension = ".jpg"
        suffix = "" if index == 1 else "_" + str(index)
        target = os.path.join(destination, "pinterest_" + pin_id + suffix + extension)
        try:
            _download_file(session, media_url, target, final_url, on_progress=on_progress)
            downloaded_images += 1
            log("Pinterest image " + str(index) + " downloaded.")
        except Exception as exc:
            failures.append(str(exc))
            log("Pinterest image candidate failed: " + str(exc)[:220])

    if downloaded_images:
        _write_text(destination, caption, final_url)
        log("Pinterest Pin image media saved (" + str(downloaded_images) + " file(s)).")
        response.close()
        return destination

    response.close()
    if not videos and not images:
        raise RuntimeError(
            "Pinterest page contained no public media URL. The Pin may require login, "
            "or Pinterest changed its page payload."
        )
    raise RuntimeError("Pinterest media URLs were found but none downloaded: " + "; ".join(failures[-3:]))


def _write_text(folder, caption, source_url):
    with open(os.path.join(folder, "caption.txt"), "w", encoding="utf-8") as handle:
        handle.write((caption or "Caption was not provided by the source platform.").strip() + "\n")
    with open(os.path.join(folder, "source.txt"), "w", encoding="utf-8") as handle:
        handle.write(source_url.strip() + "\n")
