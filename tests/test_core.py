import re
import unittest
from unittest.mock import patch

import core
import pinterest_extractor
from yt_dlp_plugins.extractor.threads import ThreadsIE


class SociaSaveCoreTests(unittest.TestCase):
    def test_platform_routing(self):
        cases = {
            "https://www.instagram.com/reel/abc123/": "instagram",
            "https://youtu.be/abc123": "youtube",
            "https://x.com/example/status/123456": "twitter",
            "https://www.facebook.com/reel/123456": "facebook",
            "https://www.tiktok.com/@sample/video/123456": "tiktok",
            "https://www.pinterest.com/pin/123456/": "pinterest",
            "https://www.threads.net/@sample/post/ABC123": "threads",
        }
        for url, expected in cases.items():
            with self.subTest(url=url):
                self.assertEqual(core.detect_platform(url), expected)


    def test_pinterest_pin_id_from_canonical_url(self):
        result = pinterest_extractor.extract_page_data(
            "<html></html>",
            "https://www.pinterest.com/pin/718324209369027318/",
        )
        self.assertEqual(result[3], "718324209369027318")

    def test_pinterest_extracts_video_and_image_from_embedded_json(self):
        page = '''<html><head><meta property="og:description" content="A sample Pin"></head>
        <script type="application/json">
        {"videos":{"video_list":{"V_720P":{"url":"https://v1.pinimg.com/videos/mc/expMp4/abc.mp4"}}},
         "images":{"orig":{"url":"https://i.pinimg.com/originals/ab/cd/image.jpg"}}}
        </script></html>'''
        videos, images, caption, pin_id = pinterest_extractor.extract_page_data(
            page, "https://www.pinterest.com/pin/718324209369027318/"
        )
        self.assertTrue(any(url.endswith("abc.mp4") for url in videos))
        self.assertTrue(any(url.endswith("image.jpg") for url in images))
        self.assertEqual(caption, "A sample Pin")
        self.assertEqual(pin_id, "718324209369027318")

    def test_pinterest_extracts_og_image(self):
        page = '<meta property="og:image" content="https://i.pinimg.com/originals/ab/cd/photo.jpg">'
        videos, images, _caption, _pin_id = pinterest_extractor.extract_page_data(
            page, "https://www.pinterest.com/pin/123456789012345/"
        )
        self.assertEqual(videos, [])
        self.assertEqual(images, ["https://i.pinimg.com/originals/ab/cd/photo.jpg"])

    def test_facebook_share_url_resolves_to_canonical_url(self):
        class FakeResponse:
            url = "https://www.facebook.com/posts/123456789/"
            def close(self):
                pass
        class FakeSession:
            def __init__(self):
                self.headers = {}
                self.cookies = type("Cookies", (), {"update": lambda self, jar: None})()
            def get(self, *args, **kwargs):
                return FakeResponse()
        with patch("requests.Session", return_value=FakeSession()):
            resolved = core._resolve_facebook_share_url("https://www.facebook.com/share/p/shortcode/")
        self.assertEqual(resolved, "https://www.facebook.com/posts/123456789/")

    def test_facebook_share_url_keeps_original_if_redirect_requires_login(self):
        class FakeResponse:
            url = "https://www.facebook.com/login/?next=%2Fposts%2F123"
            def close(self):
                pass
        class FakeSession:
            def __init__(self):
                self.headers = {}
                self.cookies = type("Cookies", (), {"update": lambda self, jar: None})()
            def get(self, *args, **kwargs):
                return FakeResponse()
        with patch("requests.Session", return_value=FakeSession()):
            original = "https://www.facebook.com/share/p/shortcode/"
            self.assertEqual(core._resolve_facebook_share_url(original), original)

    def test_extract_urls_removes_trailing_punctuation(self):
        self.assertEqual(
            core.extract_urls("Save this https://x.com/a/status/1)."),
            ["https://x.com/a/status/1"],
        )

    def test_account_and_post_ids(self):
        self.assertEqual(
            core._account_id({"owner": {"id": "998877", "username": "sample"}}),
            "998877",
        )
        self.assertEqual(
            core._post_id({}, "https://www.instagram.com/reel/POST123/"),
            "POST123",
        )

    def test_threads_plugin_matches_canonical_and_short_links(self):
        urls = [
            "https://www.threads.com/@someone/post/ABC123",
            "https://www.threads.net/@someone/post/ABC123",
            "https://www.threads.com/share/shortCode/",
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertIsNotNone(re.match(ThreadsIE._VALID_URL, url, re.VERBOSE))


if __name__ == "__main__":
    unittest.main()
