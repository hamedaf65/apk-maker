import unittest

from facebook_diagnostics import inspect_public_facebook_page


class FacebookDiagnosticTests(unittest.TestCase):
    def test_reports_video_and_image_candidates_without_logging_signed_urls(self):
        markup = """
        <meta property="og:title" content="Public test reel">
        <div data-store='{"browser_native_hd_url":"https://video.xx.fbcdn.net/reel.mp4?token=secret","photo_image":"https://scontent.xx.fbcdn.net/photo.jpg"}'></div>
        """
        messages = []
        report = inspect_public_facebook_page(
            "https://www.facebook.com/reel/123",
            messages.append,
            capture=lambda _url: markup,
        )
        self.assertEqual(report["video_count"], 1)
        self.assertEqual(report["image_count"], 1)
        joined = "\n".join(messages)
        self.assertIn("Public test reel", joined)
        self.assertIn("video candidate", joined)
        self.assertNotIn("token=secret", joined)

    def test_reports_empty_public_page(self):
        messages = []
        report = inspect_public_facebook_page(
            "https://www.facebook.com/posts/123",
            messages.append,
            capture=lambda _url: "<html><body>Nothing exposed</body></html>",
        )
        self.assertEqual(report["video_count"], 0)
        self.assertEqual(report["image_count"], 0)
        self.assertTrue(any("no supported media URLs" in line for line in messages))


if __name__ == "__main__":
    unittest.main()
