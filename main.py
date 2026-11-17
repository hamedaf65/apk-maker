"""Social Downloader - Android (Kivy) UI. Creator: Hamed Afshari."""
import os
import threading
import time
import webbrowser

import arabic_reshaper
from bidi.algorithm import get_display
from kivy.app import App
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


def button(text, **kw):
    return Button(text=fa(text), font_name=FONT, **kw)


def label(text, height=36, halign="right", **kw):
    lb = Label(text=fa(text), font_name=FONT, size_hint_y=None, height=height, halign=halign, **kw)
    lb.bind(size=lambda w, s: setattr(w, "text_size", (s[0], None)))
    return lb


class Root(BoxLayout):
    def __init__(self, user_dir, **kw):
        super().__init__(orientation="vertical", padding=10, spacing=6, **kw)
        self.user_dir = user_dir
        self.cookies_path = os.path.join(user_dir, "ig_cookies.txt")
        self.busy = False
        self.wv = None

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
        box.add_widget(label("لینک پست اینستاگرام یا ویدئوی یوتیوب را اینجا بچسبانید"))
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

        self.bar = ProgressBar(max=100, value=0, size_hint_y=None, height=14)
        box.add_widget(self.bar)

        self.login_btn = button("ورود به اینستاگرام (فقط برای پیج‌های خصوصی)", size_hint_y=None, height=44)
        self.login_btn.bind(on_release=lambda *_: self.instagram_login())
        box.add_widget(self.login_btn)

        self.logview = Label(text="", size_hint_y=None, halign="left", valign="top", font_name=FONT)
        self.logview.bind(width=lambda *_: setattr(self.logview, "text_size", (self.logview.width, None)))
        self.logview.bind(texture_size=lambda *_: setattr(self.logview, "height", self.logview.texture_size[1]))
        sv = ScrollView()
        sv.add_widget(self.logview)
        box.add_widget(sv)
        self.log(fa("ذخیره در: Download/SocialDownloader"))
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
        Clock.schedule_once(lambda dt: setattr(self.logview, "text", (self.logview.text + "\n" + str(msg)).strip()))

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
        threading.Thread(target=self.work, args=(urls, root), daemon=True).start()

    def work(self, urls, root):
        has_cookies = os.path.exists(self.cookies_path)
        for i, u in enumerate(urls, 1):
            self.log("--- (%d/%d)" % (i, len(urls)))
            self.progress(0)
            try:
                try:
                    core.run(u, root, None, self.log, self.progress)          # public post: no login
                except core.NeedLogin:
                    if has_cookies:
                        self.log(fa("در حال تلاش با حساب اینستاگرام شما ..."))
                        core.run(u, root, self.cookies_path, self.log, self.progress)
                    else:
                        raise
                self.log(fa("✔ دانلود تمام شد."))
            except core.NeedLogin:
                self.log(fa("این پست خصوصی است یا اینستاگرام ورود می‌خواهد."))
                self.log(fa("دکمه «ورود به اینستاگرام» را بزنید و یک بار وارد شوید."))
            except Exception as e:
                self.log(fa("خطا:") + " %s" % e)
        self.progress(100)
        Clock.schedule_once(lambda dt: (setattr(self, "busy", False), setattr(self.btn, "disabled", False)))

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
