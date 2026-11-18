"""Social Downloader - Android (Kivy) UI. Creator: Hamed Afshari."""
import os
import threading
import time
import webbrowser

import arabic_reshaper
from bidi.algorithm import get_display
from kivy.app import App
from kivy.animation import Animation
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.metrics import dp
from kivy.properties import NumericProperty, StringProperty
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.uix.scrollview import ScrollView
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.utils import platform

import core

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "Vazirmatn-Regular.ttf")

TELEGRAM_URL = "https://t.me/hamedaf_ir"
INSTAGRAM_URL = "https://www.instagram.com/hamedafshar.ir?igsh=MTA1cmR5eTZjdjRxYQ=="

_reshaper = arabic_reshaper.ArabicReshaper()


def fa(text):
    """Make Persian text display correctly in Kivy (shaping + right-to-left)."""
    return get_display(_reshaper.reshape(text), base_dir="R")


if platform == "android":
    from android.permissions import Permission, request_permissions
    from android.runnable import run_on_ui_thread
    from jnius import autoclass
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    BASE = "/storage/emulated/0/Download/SocialDownloader"
else:
    BASE = os.path.join(os.path.expanduser("~"), "SocialDownloader")

    def run_on_ui_thread(f):
        return f


def open_url(url):
    try:
        if platform == "android":
            Intent = autoclass("android.content.Intent")
            Uri = autoclass("android.net.Uri")
            PythonActivity.mActivity.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
        else:
            webbrowser.open(url)
    except Exception:
        webbrowser.open(url)


class RoundedButton(Button):
    def __init__(self, text="", fill=(0.39, 0.16, 0.90, 1), **kw):
        self.fill = fill
        kw.setdefault("background_normal", "")
        kw.setdefault("background_down", "")
        kw.setdefault("background_color", (0, 0, 0, 0))
        kw.setdefault("color", (1, 1, 1, 1))
        kw.setdefault("font_size", "15sp")
        super().__init__(text=text, font_name=FONT, **kw)
        with self.canvas.before:
            self._fill_color = Color(*self.fill)
            self._rounded = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(15)])
        self.bind(pos=self._sync_shape, size=self._sync_shape, disabled=self._sync_fill)

    def _sync_shape(self, *_):
        self._rounded.pos = self.pos
        self._rounded.size = self.size

    def _sync_fill(self, *_):
        self._fill_color.rgba = (0.72, 0.70, 0.79, 1) if self.disabled else self.fill

    def set_fill(self, value):
        self.fill = value
        self._sync_fill()


class StatusRing(Widget):
    angle = NumericProperty(0)
    state = StringProperty("loading")

    def __init__(self, **kw):
        self.on_finished = None
        super().__init__(**kw)
        self.bind(pos=self.redraw, size=self.redraw, angle=self.redraw, state=self.redraw)
        self.redraw()

    def redraw(self, *_):
        self.canvas.clear()
        radius = min(self.width, self.height) * 0.40
        cx, cy = self.center
        with self.canvas:
            Color(0.86, 0.83, 0.95, 1)
            Line(circle=(cx, cy, radius), width=dp(3))
            if self.state == "loading":
                Color(0.40, 0.18, 0.91, 1)
                Line(circle=(cx, cy, radius, self.angle, self.angle + 255), width=dp(5), cap="round")
            elif self.state == "success":
                Color(0.08, 0.66, 0.34, 1)
                Line(points=[cx-radius*0.48, cy, cx-radius*0.10, cy-radius*0.35,
                             cx+radius*0.52, cy+radius*0.38], width=dp(6), cap="round", joint="round")
            else:
                Color(0.84, 0.15, 0.20, 1)
                Line(points=[cx-radius*0.38, cy-radius*0.38, cx+radius*0.38, cy+radius*0.38],
                     width=dp(6), cap="round")
                Line(points=[cx-radius*0.38, cy+radius*0.38, cx+radius*0.38, cy-radius*0.38],
                     width=dp(6), cap="round")

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos) and self.state != "loading":
            if self.on_finished:
                self.on_finished()
            return True
        return super().on_touch_down(touch)


def button(text, **kw):
    value = fa(text) if any("\u0600" <= ch <= "\u06ff" for ch in text) else text
    return RoundedButton(text=value, **kw)


def label(text, height=36, halign="right", **kw):
    lb = Label(text=fa(text), font_name=FONT, size_hint_y=None, height=height, halign=halign, **kw)
    lb.bind(size=lambda w, s: setattr(w, "text_size", (s[0], None)))
    return lb


class Root(BoxLayout):
    def __init__(self, user_dir, **kw):
        super().__init__(orientation="vertical", padding=10, spacing=6, **kw)
        self.user_dir = user_dir
        self.cookies_path = os.path.join(user_dir, "ig_cookies.txt")
        self.log_path = os.path.join(user_dir, "downloader-internal.log")
        self.download_root = BASE
        self.busy = False
        self.wv = None
        self.status_popup = None
        self.status_ring = None
        self.status_title = None
        self.status_detail = None
        self.spin_animation = None

        # ---- header: "سازنده: حامد افشاری" (the name is a link to the About tab)
        self.header = Label(
            text="[ref=about][color=4da6ff][u]%s[/u][/color][/ref]  %s" % (fa("حامد افشاری"), fa("سازنده:")),
            markup=True, font_name=FONT, size_hint_y=None, height=40, halign="right", font_size="16sp")
        self.header.bind(size=lambda w, s: setattr(w, "text_size", (s[0], None)))
        self.header.bind(on_ref_press=lambda *_: self.tabs.switch_to(self.about_tab))
        self.add_widget(self.header)

        self.tabs = TabbedPanel(do_default_tab=False, tab_width=170)
        self.dl_tab = TabbedPanelItem(text=fa("دانلود"), font_name=FONT)
        self.about_tab = TabbedPanelItem(text=fa("درباره ما"), font_name=FONT)
        self.dl_tab.add_widget(self.build_download())
        self.about_tab.add_widget(self.build_about())
        self.tabs.add_widget(self.dl_tab)
        self.tabs.add_widget(self.about_tab)
        self.tabs.switch_to(self.dl_tab)
        self.add_widget(self.tabs)

    # ------------------------------------------------------------ tabs
    def build_download(self):
        box = BoxLayout(orientation="vertical", padding=6, spacing=8)
        box.add_widget(label("◎   ▶   ↓", height=82, halign="center", font_size="46sp",
                             color=(0.43, 0.16, 0.88, 1)))
        box.add_widget(label("ClipDrop", height=46, halign="center", font_size="30sp",
                             color=(0.10, 0.09, 0.25, 1)))
        box.add_widget(label("دانلود محتوا از اینستاگرام و یوتیوب؛ کافیه لینک رو اینجا بفرستی",
                             height=48, halign="center", font_size="14sp"))
        box.add_widget(label("آدرس لینک پست مورد نظر خود را اینجا قرار دهید:"))
        self.url = TextInput(multiline=True, size_hint_y=None, height=100)
        box.add_widget(self.url)

        row = BoxLayout(size_hint_y=None, height=48, spacing=8)
        b1 = button("چسباندن")
        b1.bind(on_release=lambda *_: self.paste())
        b2 = button("پاک کردن")
        b2.bind(on_release=lambda *_: setattr(self.url, "text", ""))
        row.add_widget(b1)
        row.add_widget(b2)
        box.add_widget(row)

        self.btn = button("دانلود", size_hint_y=None, height=60, font_size="20sp")
        self.btn.bind(on_release=lambda *_: self.start())
        box.add_widget(self.btn)

        self.bar = ProgressBar(max=100, value=0, size_hint_y=None, height=1, opacity=0)
        box.add_widget(self.bar)

        connect_row = BoxLayout(size_hint_y=None, height=52, spacing=8)
        self.login_btn = button("Connect to Instagram", fill=(0.93, 0.88, 1, 1),
                                color=(0.12, 0.10, 0.28, 1))
        self.login_btn.bind(on_release=lambda *_: self.instagram_login())
        self.youtube_btn = button("Connect to YouTube", fill=(1, 0.89, 0.92, 1),
                                  color=(0.12, 0.10, 0.28, 1))
        self.youtube_btn.bind(on_release=lambda *_: self.youtube_connect_info())
        connect_row.add_widget(self.login_btn)
        connect_row.add_widget(self.youtube_btn)
        box.add_widget(connect_row)

        self.files_btn = button("Downloaded Files", fill=(0.91, 0.87, 1, 1),
                                color=(0.12, 0.10, 0.28, 1),
                                size_hint_y=None, height=52)
        self.files_btn.bind(on_release=lambda *_: self.show_downloads())
        box.add_widget(self.files_btn)
        box.add_widget(label("Developed by Hamed AI", height=32, halign="center"))
        contact = button("Contact Us", fill=(1, 1, 1, 1), color=(0.39, 0.16, 0.90, 1),
                         size_hint_y=None, height=42)
        contact.bind(on_release=lambda *_: open_url(TELEGRAM_URL))
        box.add_widget(contact)
        return box

    def build_about(self):
        box = BoxLayout(orientation="vertical", padding=16, spacing=14)
        box.add_widget(label("دانلودر اینستاگرام و یوتیوب", height=44, font_size="20sp", halign="center"))
        box.add_widget(label("سازنده: حامد افشاری", halign="center"))
        box.add_widget(label("ارتباط با ما:", halign="center"))

        for text, url in (("کانال تلگرام", TELEGRAM_URL), ("صفحه اینستاگرام", INSTAGRAM_URL)):
            lb = Label(text="[ref=x][color=4da6ff][u]%s[/u][/color][/ref]" % fa(text), markup=True,
                       font_name=FONT, size_hint_y=None, height=48, font_size="18sp")
            lb.bind(on_ref_press=lambda inst, ref, u=url: open_url(u))
            box.add_widget(lb)
        box.add_widget(Label())  # spacer
        return box

    # ----------------------------------------------------------- helpers
    def log(self, msg):
        # Technical reports stay in app-private storage; never put them on screen.
        try:
            os.makedirs(self.user_dir, exist_ok=True)
            if os.path.exists(self.log_path) and os.path.getsize(self.log_path) > 512 * 1024:
                os.remove(self.log_path)
            with open(self.log_path, "a", encoding="utf-8") as handle:
                handle.write(time.strftime("%Y-%m-%d %H:%M:%S ") + str(msg)[:1200] + "\n")
        except Exception:
            pass

    def progress(self, v):
        Clock.schedule_once(lambda dt: setattr(self.bar, "value", v))

    def paste(self):
        try:
            self.url.text = Clipboard.paste() or ""
        except Exception:
            pass

    def receive_shared(self, text):
        """Link shared from the Instagram / YouTube app into this app."""
        self.url.text = text
        self.tabs.switch_to(self.dl_tab)
        self.start()

    # ---------------------------------------------------------- download
    def start(self):
        if self.busy:
            return
        urls = core.extract_urls(self.url.text)
        if not urls:
            self.log(fa("لینکی پیدا نشد."))
            return
        root = BASE
        try:
            os.makedirs(root, exist_ok=True)
            test = os.path.join(root, ".w")
            open(test, "w").close()
            os.remove(test)
        except Exception:
            root = os.path.join(self.user_dir, "downloads")
            os.makedirs(root, exist_ok=True)
            self.log(fa("اجازه ذخیره در Download داده نشد. محل ذخیره:") + " " + root)
        self.busy = True
        self.btn.disabled = True
        self.download_root = root
        self.show_processing()
        threading.Thread(target=self.work, args=(urls, root), daemon=True).start()

    def work(self, urls, root):
        successes, failures = [], []
        total = len(urls)
        for index, url in enumerate(urls, 1):
            self.log("Starting: " + url)
            try:
                cookies = self.cookies_path if ("instagram.com" in url.lower() and os.path.exists(self.cookies_path)) else None
                def on_progress(value, current=index):
                    overall = ((current - 1) + max(0, min(100, float(value))) / 100.0) * 100.0 / total
                    self.progress(overall)
                destination = core.run(url, root, cookies, self.log, on_progress)
                if not destination or not os.path.isdir(destination):
                    raise RuntimeError("Downloader returned no saved folder.")
                successes.append(destination)
                self.log("Completed: " + destination)
            except Exception as exc:
                self.log("Failure: " + repr(exc))
                try:
                    failures.append(core.friendly_error(url, exc))
                except Exception:
                    failures.append("Download failed. Check the link and try again.")
            self.progress(index * 100.0 / total)
        Clock.schedule_once(lambda dt: self.finish_download(successes, failures))

    def show_processing(self):
        if self.status_popup:
            self.status_popup.dismiss()
        panel = BoxLayout(orientation="vertical", padding=18, spacing=12)
        self.status_ring = StatusRing(size_hint=(1, None), height=dp(106))
        title = Label(text="Downloading...", font_name=FONT, font_size="19sp",
                      color=(0.10, 0.09, 0.24, 1), size_hint_y=None, height=34)
        self.status_title = title
        self.status_detail = label("در حال دریافت محتوا؛ لطفاً برنامه را نبندید",
                                   height=52, halign="center", color=(0.38, 0.37, 0.51, 1))
        panel.add_widget(self.status_ring)
        panel.add_widget(title)
        panel.add_widget(self.status_detail)
        self.status_popup = Popup(title="", content=panel, size_hint=(0.84, None),
                                  height=dp(280), auto_dismiss=False,
                                  separator_height=0, background_color=(1, 1, 1, 1))
        self.status_ring.on_finished = self.dismiss_status
        self.status_popup.open()
        self.spin_animation = Animation(angle=360, duration=1.05)
        self.spin_animation.bind(on_complete=self._repeat_spin)
        self.spin_animation.start(self.status_ring)

    def _repeat_spin(self, _animation, ring):
        if ring.state == "loading":
            ring.angle = 0
            self.spin_animation.start(ring)

    def finish_download(self, successes, failures):
        self.busy = False
        self.btn.disabled = False
        if self.spin_animation:
            self.spin_animation.cancel(self.status_ring)
            self.spin_animation = None
        if successes:
            self.status_ring.state = "success"
            self.status_title.text = "Download completed"
            if failures:
                self.status_detail.text = fa(str(len(successes)) + " مورد ذخیره شد؛ " + str(len(failures)) + " مورد ناموفق بود.")
            else:
                self.status_detail.text = fa(str(len(successes)) + " مورد با موفقیت ذخیره شد.")
            self.files_btn.text = "★   Open Downloaded Files"
            self.files_btn.set_fill((0.83, 0.97, 0.87, 1))
        else:
            self.status_ring.state = "error"
            self.status_title.text = "Download failed"
            self.status_detail.text = failures[0] if failures else fa("دانلود انجام نشد؛ لینک را بررسی کنید.")
        self.status_ring.redraw()

    def dismiss_status(self):
        if self.status_popup:
            self.status_popup.dismiss()
            self.status_popup = None

    def youtube_connect_info(self):
        message = ("Public YouTube videos can be downloaded without connecting an account. "
                   "Google blocks sign-in inside embedded Android WebViews, so this app cannot "
                   "safely reuse your Google account session. Private, members-only or age-verified "
                   "videos may not be supported.")
        body = BoxLayout(orientation="vertical", padding=14, spacing=10)
        body.add_widget(Label(text=message, font_name=FONT, color=(0.12, 0.10, 0.28, 1),
                              halign="center", valign="middle"))
        open_btn = button("Open YouTube", size_hint_y=None, height=44, fill=(0.88, 0.10, 0.16, 1))
        close_btn = button("Close", size_hint_y=None, height=44,
                           fill=(0.91, 0.87, 1, 1), color=(0.12, 0.10, 0.28, 1))
        body.add_widget(open_btn)
        body.add_widget(close_btn)
        popup = Popup(title="YouTube connection", content=body, size_hint=(0.88, None),
                      height=dp(300), auto_dismiss=False)
        open_btn.bind(on_release=lambda *_: (popup.dismiss(), open_url("https://www.youtube.com")))
        close_btn.bind(on_release=popup.dismiss)
        popup.open()

    def show_downloads(self):
        root = self.download_root
        os.makedirs(root, exist_ok=True)
        items = []
        for current, _dirs, names in os.walk(root):
            for name in names:
                if name.startswith(".") or name.endswith(".json"):
                    continue
                path = os.path.join(current, name)
                if os.path.isfile(path):
                    items.append(path)
        items.sort(key=lambda path: os.path.getmtime(path), reverse=True)
        text = "\n".join(os.path.basename(path) for path in items) or "No downloaded files yet"
        panel = BoxLayout(orientation="vertical", padding=12, spacing=8)
        scroll = ScrollView()
        listing = Label(text=text, font_name=FONT, color=(0.12, 0.10, 0.28, 1),
                        halign="left", valign="top", size_hint_y=None)
        listing.bind(width=lambda *_: setattr(listing, "text_size", (listing.width, None)))
        listing.bind(texture_size=lambda *_: setattr(listing, "height", listing.texture_size[1]))
        scroll.add_widget(listing)
        panel.add_widget(scroll)
        panel.add_widget(label("Download/SocialDownloader", height=26, halign="center"))
        close = button("Close", size_hint_y=None, height=44)
        panel.add_widget(close)
        popup = Popup(title="Downloaded Files (" + str(len(items)) + ")", content=panel,
                      size_hint=(0.90, 0.78), auto_dismiss=False)
        close.bind(on_release=popup.dismiss)
        popup.open()

    # ------------------------------------------ Instagram login (private)
    def instagram_login(self):
        if platform != "android":
            self.log(fa("ورود فقط روی گوشی اندروید پشتیبانی می‌شود."))
            return
        self.log(fa("وارد اینستاگرام شوید. بعد از ورود، خودکار بسته می‌شود. (دکمه برگشت = انصراف)"))
        self._open_webview()
        Clock.schedule_interval(self._poll_login, 1.5)

    @run_on_ui_thread
    def _open_webview(self):
        WebView = autoclass("android.webkit.WebView")
        WebViewClient = autoclass("android.webkit.WebViewClient")
        LayoutParams = autoclass("android.view.ViewGroup$LayoutParams")
        act = PythonActivity.mActivity
        wv = WebView(act)
        s = wv.getSettings()
        s.setJavaScriptEnabled(True)
        s.setDomStorageEnabled(True)
        wv.setWebViewClient(WebViewClient())
        wv.loadUrl("https://www.instagram.com/accounts/login/")
        act.addContentView(wv, LayoutParams(-1, -1))
        self.wv = wv

    @run_on_ui_thread
    def _close_webview(self):
        try:
            if self.wv is not None:
                parent = self.wv.getParent()
                if parent is not None:
                    parent.removeView(self.wv)
                self.wv.destroy()
        except Exception:
            pass
        self.wv = None

    def _poll_login(self, dt):
        if self.wv is None:
            return False
        try:
            CookieManager = autoclass("android.webkit.CookieManager")
            raw = CookieManager.getInstance().getCookie("https://www.instagram.com") or ""
        except Exception:
            return True
        if "sessionid=" in raw:
            expiry = int(time.time()) + 365 * 24 * 3600
            lines = ["# Netscape HTTP Cookie File"]
            for part in raw.split(";"):
                if "=" in part:
                    k, v = part.strip().split("=", 1)
                    lines.append(".instagram.com\tTRUE\t/\tTRUE\t%d\t%s\t%s" % (expiry, k, v))
            with open(self.cookies_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            self._close_webview()
            self.log(fa("✔ ورود انجام شد. حالا لینک پست خصوصی را دانلود کنید."))
            return False
        return True

    def on_back(self):
        """Android back button: close login window if open."""
        if self.wv is not None:
            self._close_webview()
            self.log(fa("ورود لغو شد."))
            return True
        return False


class SocialDownloaderApp(App):
    def build(self):
        self.title = "Social Downloader"
        self.root_widget = Root(self.user_data_dir)
        Window.bind(on_keyboard=self.on_key)
        return self.root_widget

    def on_key(self, window, key, *args):
        if key == 27:
            return self.root_widget.on_back()
        return False

    def on_start(self):
        if platform == "android":
            request_permissions([Permission.WRITE_EXTERNAL_STORAGE, Permission.READ_EXTERNAL_STORAGE])
            try:
                from android import activity
                activity.bind(on_new_intent=self.handle_intent)
                self.handle_intent(PythonActivity.mActivity.getIntent())
            except Exception:
                pass

    def handle_intent(self, intent):
        try:
            if intent is not None and intent.getAction() == "android.intent.action.SEND":
                text = intent.getStringExtra("android.intent.extra.TEXT")
                intent.setAction("android.intent.action.MAIN")
                if text:
                    Clock.schedule_once(lambda dt: self.root_widget.receive_shared(text), 0.5)
        except Exception:
            pass


if __name__ == "__main__":
    SocialDownloaderApp().run()
