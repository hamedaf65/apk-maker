import unittest

from facebook_webview import capture_facebook_page


class FakeStorage:
    def __init__(self, status="done", markup="<html><body>public post</body></html>"):
        self.status = status
        self.markup = markup
        self.started = None
        self.stopped = False

    def startFacebookPageCapture(self, activity, url):
        self.started = (activity, url)
        return True

    def getFacebookPageCaptureStatus(self):
        return self.status

    def getFacebookPageCaptureHtml(self):
        return self.markup

    def stopFacebookPageCapture(self, activity):
        self.stopped = True


class FacebookWebViewAdapterTests(unittest.TestCase):
    def test_captures_html_through_storage_contract(self):
        storage = FakeStorage()
        result = capture_facebook_page(
            "https://www.facebook.com/reel/123",
            storage=storage, activity=object(), poll_interval=0.01)
        self.assertIn("public post", result)
        self.assertEqual(storage.started[1], "https://www.facebook.com/reel/123")
        self.assertTrue(storage.stopped)

    def test_rejects_non_facebook_url_before_android_access(self):
        with self.assertRaises(ValueError):
            capture_facebook_page("https://example.com/post",
                                  storage=FakeStorage(), activity=object())

    def test_reports_webview_error_and_stops_capture(self):
        storage = FakeStorage(status="error", markup="")
        with self.assertRaises(RuntimeError):
            capture_facebook_page("https://facebook.com/post",
                                  storage=storage, activity=object(),
                                  poll_interval=0.01)
        self.assertTrue(storage.stopped)


if __name__ == "__main__":
    unittest.main()
