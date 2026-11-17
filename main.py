"""Social Downloader - Android (Kivy) UI."""
import os
import threading

from kivy.app import App
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.utils import platform

import core

if platform == "android":
    from android.permissions import Permission, request_permissions
    BASE = "/storage/emulated/0/Download/SocialDownloader"
else:
    BASE = os.path.join(os.path.expanduser("~"), "SocialDownloader")

COOKIES = os.path.join(BASE, "cookies.txt")


class Root(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical", padding=12, spacing=8, **kw)
        self.add_widget(Label(text="Instagram / YouTube Downloader", size_hint_y=None, height=40, font_size="18sp"))

        self.url = TextInput(hint_text="Paste link here", multiline=True, size_hint_y=None, height=110)
        self.add_widget(self.url)

        row = BoxLayout(size_hint_y=None, height=48, spacing=8)
        b1 = Button(text="Paste")
        b1.bind(on_release=lambda *_: self.paste())
        b2 = Button(text="Clear")
        b2.bind(on_release=lambda *_: setattr(self.url, "text", ""))
        row.add_widget(b1)
        row.add_widget(b2)
        self.add_widget(row)

        self.add_widget(Label(text="Save folder:", size_hint_y=None, height=24, halign="left"))
        self.folder = TextInput(text=BASE, multiline=False, size_hint_y=None, height=44)
        self.add_widget(self.folder)

        self.btn = Button(text="DOWNLOAD", size_hint_y=None, height=60, font_size="18sp")
        self.btn.bind(on_release=lambda *_: self.start())
        self.add_widget(self.btn)

        self.bar = ProgressBar(max=100, value=0, size_hint_y=None, height=16)
        self.add_widget(self.bar)

        self.logview = Label(text="Ready.\ncookies.txt for Instagram goes in:\n" + COOKIES,
                             size_hint_y=None, halign="left", valign="top", markup=False)
        self.logview.bind(width=lambda *_: setattr(self.logview, "text_size", (self.logview.width, None)))
        self.logview.bind(texture_size=lambda *_: setattr(self.logview, "height", self.logview.texture_size[1]))
        sv = ScrollView()
        sv.add_widget(self.logview)
        self.add_widget(sv)
        self.busy = False

    def paste(self):
        try:
            self.url.text = Clipboard.paste() or ""
        except Exception:
            pass

    def log(self, msg):
        Clock.schedule_once(lambda dt: setattr(self.logview, "text", self.logview.text + "\n" + str(msg)))

    def progress(self, v):
        Clock.schedule_once(lambda dt: setattr(self.bar, "value", v))

    def start(self):
        if self.busy:
            return
        urls = core.extract_urls(self.url.text)
        if not urls:
            self.log("No link found.")
            return
        root = self.folder.text.strip() or BASE
        try:
            os.makedirs(root, exist_ok=True)
        except Exception as e:
            self.log("Cannot use folder: %s" % e)
            return
        self.busy = True
        self.btn.disabled = True
        threading.Thread(target=self.work, args=(urls, root), daemon=True).start()

    def work(self, urls, root):
        cookies = COOKIES if os.path.exists(COOKIES) else None
        if cookies:
            self.log("Using cookies.txt")
        for i, u in enumerate(urls, 1):
            self.log("--- (%d/%d) %s" % (i, len(urls), u))
            self.progress(0)
            try:
                core.run(u, root, cookies, self.log, self.progress)
            except Exception as e:
                self.log("ERROR: %s" % e)
        self.progress(100)
        Clock.schedule_once(self.done)

    def done(self, dt):
        self.busy = False
        self.btn.disabled = False
        self.log("Finished.")


class SocialDownloaderApp(App):
    def build(self):
        self.title = "Social Downloader"
        return Root()

    def on_start(self):
        if platform == "android":
            request_permissions([Permission.WRITE_EXTERNAL_STORAGE, Permission.READ_EXTERNAL_STORAGE])


if __name__ == "__main__":
    SocialDownloaderApp().run()
