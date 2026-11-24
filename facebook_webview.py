"""Python adapter for the isolated Android Facebook page-capture WebView.

This is a metadata acquisition step only. It does not download media or bypass
Facebook authentication, privacy settings, or other access controls.
"""
import time
from urllib.parse import urlparse


_ALLOWED_HOSTS = ("facebook.com", "fb.com", "fb.watch")


def _is_allowed_page(url):
    try:
        parsed = urlparse(str(url or ""))
        host = (parsed.hostname or "").lower()
        return (
            parsed.scheme == "https"
            and any(host == suffix or host.endswith("." + suffix)
                    for suffix in _ALLOWED_HOSTS)
        )
    except Exception:
        return False


def capture_facebook_page(url, timeout=22.0, poll_interval=0.25,
                          storage=None, activity=None):
    """Capture rendered HTML from a public Facebook page on Android.

    storage and activity are injectable to keep this adapter unit-testable
    on desktop. On Android they are resolved lazily from PyJNIus.
    """
    if not _is_allowed_page(url):
        raise ValueError("Only HTTPS Facebook page URLs are supported.")

    if storage is None or activity is None:
        try:
            from jnius import autoclass
            if storage is None:
                storage = autoclass(
                    "org.hamedafshari.sociasave.SociaSaveStorage")
            if activity is None:
                activity = autoclass(
                    "org.kivy.android.PythonActivity").mActivity
        except Exception as exc:
            raise RuntimeError(
                "Facebook WebView capture is available only in the Android app: "
                + repr(exc)
            ) from exc

    started = storage.startFacebookPageCapture(activity, str(url))
    if not started:
        raise RuntimeError("Android rejected this Facebook page URL.")

    deadline = time.monotonic() + max(1.0, float(timeout))
    try:
        while time.monotonic() < deadline:
            status = str(storage.getFacebookPageCaptureStatus() or "")
            if status == "done":
                markup = str(storage.getFacebookPageCaptureHtml() or "")
                if not markup:
                    raise RuntimeError(
                        "Facebook WebView completed without returning page markup.")
                return markup
            if status == "error":
                raise RuntimeError(
                    "Facebook WebView could not load or inspect this public page.")
            time.sleep(max(0.05, float(poll_interval)))
        raise TimeoutError(
            "Facebook page capture timed out. The page may require login, "
            "be unavailable, or have blocked WebView access.")
    finally:
        try:
            storage.stopFacebookPageCapture(activity)
        except Exception:
            pass
