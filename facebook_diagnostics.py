"""Diagnostic-only inspection of publicly rendered Facebook page media.

This module reports what the Android WebView and clean-room parser can see.
It deliberately does not download media, authenticate, or bypass access controls.
"""
from urllib.parse import urlparse


def inspect_public_facebook_page(url, log, capture=None):
    """Capture a public page and report media candidate counts and safe metadata."""
    if capture is None:
        from facebook_webview import capture_facebook_page
        capture = capture_facebook_page

    from facebook_extractor import parse_facebook_page

    log("Facebook: inspecting rendered page markup after extractor failures.")
    markup = capture(url)
    result = parse_facebook_page(markup, url)
    title = (result.get("title") or "").strip()
    description = (result.get("description") or "").strip()
    if title:
        log("Facebook page title: " + title[:180])
    if description:
        log("Facebook page description detected (" + str(len(description)) + " characters).")

    videos = result.get("videos") or []
    images = result.get("images") or []
    log("Facebook page inspection found " + str(len(videos)) +
        " video candidate(s) and " + str(len(images)) + " image candidate(s).")
    for index, item in enumerate(videos[:8], 1):
        host = urlparse(item.get("url", "")).hostname or "unknown-host"
        log("Facebook video candidate " + str(index) + ": " +
            str(item.get("kind", "unknown")) + ", " +
            str(item.get("quality", "Unknown")) + ", host=" + host)
    for index, item in enumerate(images[:8], 1):
        host = urlparse(item.get("url", "")).hostname or "unknown-host"
        log("Facebook image candidate " + str(index) + ": host=" + host)
    if not videos and not images:
        log("Facebook page exposed no supported media URLs in its rendered markup; " +
            "it may require login, be unavailable, or use an unsupported page structure.")

    return {
        "title": title,
        "video_count": len(videos),
        "image_count": len(images),
        "videos": videos,
        "images": images,
    }
