import unittest

from facebook_extractor import parse_facebook_page, parse_facebook_payload


class FacebookParserTests(unittest.TestCase):
    def test_page_parser_reads_meta_and_video_variants(self):
        page = r'''
        <meta property="og:title" content="Public reel">
        <meta property="og:description" content="A test caption">
        <div data-store='{"video_id":"12345","browser_native_hd_url":"https://scontent.xx.fbcdn.net/v/t42/hd.mp4","browser_native_sd_url":"https://scontent.xx.fbcdn.net/v/t42/sd.mp4"}'></div>
        '''
        result = parse_facebook_page(page, "https://www.facebook.com/reel/12345")
        self.assertEqual(result["title"], "Public reel")
        self.assertEqual(result["description"], "A test caption")
        self.assertEqual(result["video_id"], "12345")
        self.assertEqual(len(result["videos"]), 2)
        self.assertEqual(result["videos"][0]["quality"], "HD")
        self.assertEqual(result["videos"][1]["quality"], "SD")

    def test_payload_parser_reads_progressive_dash_hls_and_photo(self):
        payload = {
            "video_id": "9988",
            "progressive_url": "https://video.xx.fbcdn.net/video.mp4",
            "dash_manifest_url": "https://video.xx.fbcdn.net/video.mpd",
            "hls_playlist_url": "https://video.xx.fbcdn.net/video.m3u8",
            "photo_image": "https://scontent.xx.fbcdn.net/photo.jpg",
        }
        result = parse_facebook_payload(payload)
        self.assertEqual(result["video_id"], "9988")
        self.assertEqual({item["kind"] for item in result["videos"]},
                         {"progressive", "dash", "hls"})
        self.assertEqual(len(result["images"]), 1)

    def test_rejects_unrelated_external_urls(self):
        result = parse_facebook_payload({
            "playable_url": "https://example.com/not-facebook.mp4",
            "thumbnail_url": "https://example.com/image.jpg",
        })
        self.assertEqual(result["videos"], [])
        self.assertEqual(result["images"], [])


if __name__ == "__main__":
    unittest.main()
