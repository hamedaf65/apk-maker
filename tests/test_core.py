import re
import unittest

import core
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
