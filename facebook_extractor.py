"""Clean-room Facebook public-page metadata and media-variant parser.

This module does not authenticate, bypass access controls, or download media.
It normalizes media references exposed in public HTML / structured payloads so
the Android WebView layer can later hand them to a dedicated resolver.
"""
import html
import json
import re
from html.parser import HTMLParser
from urllib.parse import urlparse


_MEDIA_HOST_SUFFIXES = (
    "fbcdn.net",
    "fbsbx.com",
    "facebook.com",
)
_VIDEO_KEYS = {
    "playable_url", "playable_url_quality_hd", "browser_native_hd_url",
    "browser_native_sd_url", "progressive_url", "video_url",
    "dash_manifest_url", "manifest_url", "playable_url_dash", "browser_native_hd_url",
    "browser_native_sd_url", "hls_playlist_url", "dashmanifesturl", "dashmanifest",
}
_IMAGE_KEYS = {
    "image", "image_url", "photo", "photo_url", "photo_image",
    "thumbnail", "thumbnail_url", "preview_image",
}
_VIDEO_ID_KEYS = {"video_id", "videoid", "root_video_id"}
_URL_RE = re.compile(r"https?://[^\s<>\"'\\]+", re.I)


def _clean(value):
    value = html.unescape(str(value or ""))
    return (value.replace("\\/", "/").replace("\\u002F", "/")
            .replace("\\u003D", "=").replace("\\u0026", "&")
            .strip())


def _is_facebook_media_url(value):
    try:
        host = (urlparse(value).hostname or "").lower()
    except Exception:
        return False
    return any(host == suffix or host.endswith("." + suffix)
               for suffix in _MEDIA_HOST_SUFFIXES)


def _media_kind(key, value):
    key = str(key or "").lower()
    lower = value.lower().split("?", 1)[0]
    if key in _VIDEO_KEYS or any(token in key for token in (
            "playable_url", "progressive_url", "browser_native", "dash_manifest", "hls_playlist")):
        if "dash" in key or lower.endswith(".mpd"):
            return "dash"
        if "hls" in key or lower.endswith(".m3u8"):
            return "hls"
        return "progressive"
    if key in _IMAGE_KEYS or any(token in key for token in (
            "thumbnail", "photo_image", "image_url")):
        if re.search(r"\.(?:jpe?g|png|webp|gif|avif)(?:$)", lower):
            return "image"
    return None


def _quality(key, width=None, height=None):
    text = str(key or "").lower()
    if "hd" in text or "high" in text:
        return "HD"
    if "sd" in text or "standard" in text:
        return "SD"
    try:
        if int(width or 0) >= 720 or int(height or 0) >= 720:
            return "HD"
    except (TypeError, ValueError):
        pass
    return "Unknown"


class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.structured = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag.lower() == "meta":
            key = (values.get("property") or values.get("name") or "").lower()
            content = values.get("content")
            if key and content:
                self.meta[key] = html.unescape(content)
        for attr in ("data-store", "data-extra"):
            raw = values.get(attr)
            if raw:
                self.structured.append(raw)


def _walk(value, candidates, video_ids, inherited_key="", width=None, height=None):
    if isinstance(value, dict):
        local_width = value.get("width", width)
        local_height = value.get("height", height)
        for key, item in value.items():
            key_text = str(key).lower()
            if key_text in _VIDEO_ID_KEYS and isinstance(item, (str, int)):
                video_ids.append(str(item))
            if isinstance(item, str):
                candidate = _clean(item)
                if candidate.startswith(("https://", "http://")) and _is_facebook_media_url(candidate):
                    kind = _media_kind(key_text, candidate)
                    if kind:
                        candidates.append({
                            "url": candidate,
                            "kind": kind,
                            "quality": _quality(key_text, local_width, local_height),
                            "source_key": key_text,
                            "width": local_width,
                            "height": local_height,
                        })
                # Facebook occasionally embeds JSON as a string value.
                if len(item) > 40 and item.lstrip().startswith(("{", "[")):
                    try:
                        _walk(json.loads(item), candidates, video_ids,
                              key_text, local_width, local_height)
                    except (ValueError, TypeError):
                        pass
            elif isinstance(item, (dict, list)):
                _walk(item, candidates, video_ids, key_text,
                      local_width, local_height)
    elif isinstance(value, list):
        for item in value:
            _walk(item, candidates, video_ids, inherited_key, width, height)


def _parse_json_text(raw, candidates, video_ids):
    raw = _clean(raw)
    if not raw:
        return
    try:
        _walk(json.loads(raw), candidates, video_ids)
        return
    except (ValueError, TypeError):
        pass
    # Some script tags wrap JSON in assignment text; inspect balanced-looking
    # object/array fragments without executing JavaScript.
    for match in re.finditer(r"(\{.{20,}\}|\[.{20,}\])", raw, re.S):
        fragment = match.group(1)
        try:
            _walk(json.loads(fragment), candidates, video_ids)
        except (ValueError, TypeError):
            continue


def parse_facebook_page(page_html, page_url=""):
    """Return metadata and deduplicated media candidates from page HTML.

    The result is intentionally descriptive; it does not assert that a URL is
    downloadable until a later HTTP/WebView validation step succeeds.
    """
    parser = _PageParser()
    parser.feed(page_html or "")
    candidates = []
    video_ids = []
    for raw in parser.structured:
        _parse_json_text(raw, candidates, video_ids)

    for match in re.finditer(
            r"<script\b[^>]*>(.*?)</script\s*>",
            page_html or "", re.I | re.S):
        _parse_json_text(match.group(1), candidates, video_ids)

    # De-duplicate by URL while retaining the richer first structured record.
    unique = {}
    for item in candidates:
        unique.setdefault(item["url"], item)
    media = list(unique.values())
    videos = [item for item in media if item["kind"] in (
        "progressive", "dash", "hls")]
    images = [item for item in media if item["kind"] == "image"]

    # Prefer explicit HD progressive streams in presentation order, but keep
    # every discovered variant so the UI can offer a quality selector.
    videos.sort(key=lambda item: (
        item["kind"] != "progressive",
        item["quality"] != "HD",
        item["quality"] == "Unknown",
    ))
    return {
        "page_url": page_url,
        "title": parser.meta.get("og:title", ""),
        "description": (parser.meta.get("og:description")
                        or parser.meta.get("description", "")),
        "thumbnail": (parser.meta.get("og:image")
                      or parser.meta.get("twitter:image", "")),
        "video_id": next(iter(dict.fromkeys(video_ids)), ""),
        "videos": videos,
        "images": images,
    }


def parse_facebook_payload(payload):
    """Parse a decoded GraphQL / structured response using the same rules."""
    candidates = []
    video_ids = []
    _walk(payload, candidates, video_ids)
    unique = {}
    for item in candidates:
        unique.setdefault(item["url"], item)
    media = list(unique.values())
    videos = [item for item in media if item["kind"] in (
        "progressive", "dash", "hls")]
    images = [item for item in media if item["kind"] == "image"]
    videos.sort(key=lambda item: (
        item["kind"] != "progressive",
        item["quality"] != "HD",
        item["quality"] == "Unknown",
    ))
    return {
        "video_id": next(iter(dict.fromkeys(video_ids)), ""),
        "videos": videos,
        "images": images,
    }
