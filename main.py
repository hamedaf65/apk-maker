"""SociaSave — Android social media downloader by Hamed AI."""
import os
import shutil
import threading
import time
import webbrowser

import arabic_reshaper
from bidi.algorithm import get_display
from kivy.app import App
from kivy.animation import Animation
from kivy.graphics import Color, Ellipse, Line, RoundedRectangle, Triangle
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
from kivy.uix.behaviors import ButtonBehavior
from kivy.graphics import Rectangle
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
    from android.runnable import run_on_ui_thread
    from jnius import autoclass
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    BASE = "/storage/emulated/0/Download/SociaSave"
else:
    BASE = os.path.join(os.path.expanduser("~"), "SociaSave")

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
    value = fa(text) if any("\u0600" <= ch <= "\u06ff" for ch in text) else text
    lb = Label(text=value, font_name=FONT, size_hint_y=None, height=height, halign=halign, **kw)
    lb.bind(size=lambda w, size: setattr(w, "text_size", (size[0], None)))
    return lb


class SoftCard(BoxLayout):
    def __init__(self, fill=(1, 1, 1, 0.94), radius=dp(22), **kw):
        super().__init__(**kw)
        self.fill = fill
        self.corner_radius = radius
        with self.canvas.before:
            self._card_color = Color(*self.fill)
            self._card_rect = RoundedRectangle(pos=self.pos, size=self.size,
                                                radius=[self.corner_radius])
            self._border_color = Color(0.78, 0.70, 0.98, 0.72)
            self._border = Line(rounded_rectangle=(self.x, self.y, self.width,
                                                   self.height, self.corner_radius), width=1.1)
        self.bind(pos=self._sync_card, size=self._sync_card)

    def _sync_card(self, *_):
        self._card_rect.pos = self.pos
        self._card_rect.size = self.size
        self._border.rounded_rectangle = (self.x, self.y, self.width, self.height, self.corner_radius)


class LightPopup(Popup):
    """A light, rounded popup surface independent of the Android dark theme."""
    def __init__(self, **kwargs):
        kwargs.setdefault("background", "")
        kwargs.setdefault("background_color", (0, 0, 0, 0))
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(0.99, 0.98, 1, 1)
            self._light_bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(24)])
            Color(0.79, 0.72, 0.95, 0.75)
            self._light_border = Line(
                rounded_rectangle=(self.x, self.y, self.width, self.height, dp(24)),
                width=1.0)
        self.bind(pos=self._sync_light_bg, size=self._sync_light_bg)

    def _sync_light_bg(self, *_):
        self._light_bg.pos = self.pos
        self._light_bg.size = self.size
        self._light_border.rounded_rectangle = (
            self.x, self.y, self.width, self.height, dp(24))


class PlatformTile(BoxLayout):
    def __init__(self, symbol, name, fill, **kwargs):
        super().__init__(orientation="vertical", spacing=dp(2),
                         padding=(dp(3), dp(7)), **kwargs)
        with self.canvas.before:
            Color(*fill)
            self._tile_bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(15)])
        self.bind(pos=self._sync_tile, size=self._sync_tile)
        self.add_widget(Label(text=symbol, font_name=FONT, font_size="27sp",
                              bold=True, color=(1, 1, 1, 1)))
        self.add_widget(Label(text=name, font_name=FONT, font_size="10sp",
                              color=(1, 1, 1, 1), size_hint_y=None, height=dp(17)))

    def _sync_tile(self, *_):
        self._tile_bg.pos = self.pos
        self._tile_bg.size = self.size


class SocialBanner(BoxLayout):
    """Four clearly recognizable platform marks, safely contained in one banner."""
    def __init__(self, **kwargs):
        super().__init__(orientation="horizontal", spacing=dp(8),
                         padding=(dp(10), dp(10)), **kwargs)
        with self.canvas.before:
            Color(1, 1, 1, 0.96)
            self._banner_bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(23)])
            Color(0.78, 0.69, 0.96, 0.72)
            self._banner_border = Line(
                rounded_rectangle=(self.x, self.y, self.width, self.height, dp(23)),
                width=1.1)
        self.bind(pos=self._sync_banner, size=self._sync_banner)
        self.add_widget(PlatformTile("◎", "Instagram", (0.78, 0.18, 0.54, 1)))
        self.add_widget(PlatformTile("X", "X / Twitter", (0.10, 0.11, 0.14, 1)))
        self.add_widget(PlatformTile("▶", "YouTube", (0.87, 0.12, 0.16, 1)))
        self.add_widget(PlatformTile("f", "Facebook", (0.13, 0.38, 0.77, 1)))

    def _sync_banner(self, *_):
        self._banner_bg.pos = self.pos
        self._banner_bg.size = self.size
        self._banner_border.rounded_rectangle = (
            self.x, self.y, self.width, self.height, dp(23))




class ContactAction(ButtonBehavior, BoxLayout):
    def __init__(self, icon, icon_color, title, subtitle, url, **kw):
        super().__init__(orientation="horizontal", padding=(dp(16), dp(10)),
                         spacing=dp(14), size_hint_y=None, height=dp(92), **kw)
        with self.canvas.before:
            Color(1, 1, 1, 0.97)
            self._card = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(20)])
            Color(0.79, 0.71, 0.98, 0.8)
            self._outline = Line(rounded_rectangle=(self.x, self.y, self.width,
                                                    self.height, dp(20)), width=1.1)
        self.bind(pos=self._sync, size=self._sync)
        icon_box = BoxLayout(size_hint=(None, 1), width=dp(62), padding=dp(4))
        with icon_box.canvas.before:
            Color(*icon_color)
            self._icon_bg = Ellipse(pos=icon_box.pos, size=icon_box.size)
        icon_box.bind(pos=lambda w, *_: setattr(self._icon_bg, "pos", w.pos),
                      size=lambda w, *_: setattr(self._icon_bg, "size", w.size))
        icon_label = Label(text=icon, font_size="32sp", bold=True,
                           color=(1, 1, 1, 1), halign="center", valign="middle")
        icon_box.add_widget(icon_label)
        self.add_widget(icon_box)

        texts = BoxLayout(orientation="vertical", spacing=dp(3), padding=(0, dp(5)))
        texts.add_widget(label(title, height=dp(30), halign="left",
                               font_size="17sp", bold=True, color=(0.10, 0.10, 0.27, 1)))
        texts.add_widget(label(subtitle, height=dp(30), halign="left",
                               font_size="13sp", color=(0.40, 0.39, 0.52, 1)))
        self.add_widget(texts)
        self.url = url
        self.bind(on_release=lambda *_: open_url(self.url))

    def _sync(self, *_):
        self._card.pos = self.pos
        self._card.size = self.size
        self._outline.rounded_rectangle = (self.x, self.y, self.width, self.height, dp(20))


class Root(BoxLayout):
    def __init__(self, user_dir, **kw):
        super().__init__(orientation="vertical", padding=0, spacing=0, **kw)
        self.user_dir = user_dir
        self.cookies_path = os.path.join(user_dir, "ig_cookies.txt")
        self.log_path = os.path.join(user_dir, "downloader-internal.log")
        self.download_root = os.path.join(user_dir, "downloads")
        self.busy = False
        self.wv = None
        self.login_open = False
        self.status_popup = None
        self.status_ring = None
        self.status_title = None
        self.status_detail = None
        self.status_close_btn = None
        self.spin_animation = None
        self.current_view = None
        Window.clearcolor = (0.975, 0.965, 1, 1)
        with self.canvas.before:
            Color(0.975, 0.965, 1, 1)
            self._background = Rectangle(pos=self.pos, size=self.size)
            Color(0.88, 0.79, 1, 0.30)
            self._blob_top = Ellipse()
            Color(1, 0.77, 0.70, 0.22)
            self._blob_bottom = Ellipse()
        self.bind(pos=self._sync_background, size=self._sync_background)
        if platform == "android":
            try:
                native_dir = str(PythonActivity.mActivity.getApplicationInfo().nativeLibraryDir)
                os.environ["SOCIASAVE_NATIVE_LIB_DIR"] = native_dir
            except Exception:
                pass
        self.main_view = self.build_download()
        self.contact_view = self.build_contact()
        self.show_main()

    def _sync_background(self, *_):
        self._background.pos = self.pos
        self._background.size = self.size
        self._blob_top.pos = (self.x - dp(90), self.top - dp(230))
        self._blob_top.size = (self.width * 0.78, dp(300))
        self._blob_bottom.pos = (self.right - self.width * 0.55, self.y - dp(160))
        self._blob_bottom.size = (self.width * 0.75, dp(260))

    def show_main(self):
        if self.current_view is not None:
            self.remove_widget(self.current_view)
        self.current_view = self.main_view
        self.add_widget(self.main_view)

    def show_contact(self):
        if self.current_view is not None:
            self.remove_widget(self.current_view)
        self.current_view = self.contact_view
        self.add_widget(self.contact_view)

    def _make_scroll_page(self, padding=(dp(18), dp(12))):
        scroll = ScrollView(do_scroll_x=False, bar_width=dp(3),
                            scroll_type=["bars", "content"])
        content = BoxLayout(orientation="vertical", padding=padding,
                            spacing=dp(12), size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))
        scroll.add_widget(content)
        return scroll, content

    # ------------------------------------------------------------ pages
    def build_download(self):
        scroll, content = self._make_scroll_page()
        hero = BoxLayout(orientation="vertical", spacing=dp(5),
                         size_hint_y=None, height=dp(205))
        brand_mark = SocialBanner(size_hint_y=None, height=dp(112))
        brand = Label(text="[color=151A3D][b]Socia[/b][/color][color=8A27DD][b]Save[/b][/color]",
                      markup=True, font_name=FONT, font_size="31sp",
                      size_hint_y=None, height=dp(42))
        tagline = label("دانلود محتوا از Instagram، X، YouTube و Facebook",
                        height=dp(38), halign="center", font_size="13sp",
                        color=(0.34, 0.33, 0.49, 1))
        hero.add_widget(brand_mark)
        hero.add_widget(brand)
        hero.add_widget(tagline)
        content.add_widget(hero)

        input_card = SoftCard(orientation="vertical", padding=(dp(15), dp(13)),
                              spacing=dp(8), size_hint_y=None, height=dp(190))
        input_card.add_widget(label("آدرس لینک پست مورد نظر خود را از اینستاگرام یا یوتیوب اینجا قرار دهید:",
                                    height=dp(44), font_size="13sp", color=(0.13, 0.13, 0.31, 1)))
        self.url = TextInput(
            multiline=False, size_hint_y=None, height=dp(68),
            hint_text="Paste your link here...",
            background_normal="", background_active="",
            background_color=(0.98, 0.97, 1, 1),
            foreground_color=(0.13, 0.13, 0.29, 1),
            hint_text_color=(0.55, 0.53, 0.66, 1),
            cursor_color=(0.48, 0.19, 0.91, 1),
            padding=(dp(14), dp(20)), font_size="15sp",
            selection_color=(0.72, 0.62, 0.98, 0.55))
        input_card.add_widget(self.url)
        tools_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        clear_button = button("Delete", fill=(0.94, 0.91, 1, 1),
                              color=(0.17, 0.14, 0.36, 1), size_hint_x=1)
        clear_button.bind(on_release=lambda *_: setattr(self.url, "text", ""))
        paste_button = button("Paste", fill=(0.94, 0.91, 1, 1),
                              color=(0.17, 0.14, 0.36, 1), size_hint_x=1)
        paste_button.bind(on_release=lambda *_: self.paste())
        tools_row.add_widget(clear_button)
        tools_row.add_widget(paste_button)
        input_card.add_widget(tools_row)
        content.add_widget(input_card)

        self.btn = button("↓   Download Content", size_hint_y=None, height=dp(60),
                          font_size="19sp", bold=True, fill=(0.56, 0.18, 0.92, 1))
        self.btn.bind(on_release=lambda *_: self.start())
        content.add_widget(self.btn)

        self.bar = ProgressBar(max=100, value=0, size_hint_y=None, height=1, opacity=0)
        content.add_widget(self.bar)

        connect_row = BoxLayout(size_hint_y=None, height=dp(68), spacing=dp(9))
        self.login_btn = button("◎   Connect to Instagram", fill=(0.94, 0.89, 1, 1),
                                color=(0.15, 0.12, 0.34, 1), font_size="13sp")
        self.login_btn.bind(on_release=lambda *_: self.instagram_login())
        self.youtube_btn = button("▶   Connect to YouTube", fill=(1, 0.90, 0.93, 1),
                                  color=(0.15, 0.12, 0.34, 1), font_size="13sp")
        self.youtube_btn.bind(on_release=lambda *_: self.youtube_connect_info())
        connect_row.add_widget(self.login_btn)
        connect_row.add_widget(self.youtube_btn)
        content.add_widget(connect_row)

        self.files_btn = button("▣   Open SociaSave Folder", fill=(0.93, 0.89, 1, 1),
                                color=(0.15, 0.12, 0.34, 1),
                                size_hint_y=None, height=dp(58), font_size="16sp")
        self.files_btn.bind(on_release=lambda *_: self.show_downloads())
        content.add_widget(self.files_btn)

        credit = Label(text="[color=47425F]Developed by [/color][color=7521D6][b]Hamed AI[/b][/color]",
                       markup=True, font_name=FONT, size_hint_y=None, height=dp(34),
                       font_size="14sp")
        content.add_widget(credit)
        contact = button("Contact Us", fill=(1, 1, 1, 1),
                         color=(0.42, 0.15, 0.82, 1),
                         size_hint_y=None, height=dp(44), font_size="15sp")
        contact.bind(on_release=lambda *_: self.show_contact())
        content.add_widget(contact)
        content.add_widget(Widget(size_hint_y=None, height=dp(8)))
        return scroll

    def build_contact(self):
        scroll, content = self._make_scroll_page(padding=(dp(18), dp(18)))
        back = button("←   Back", fill=(0.94, 0.91, 1, 1),
                      color=(0.18, 0.14, 0.38, 1),
                      size_hint_y=None, height=dp(48), size_hint_x=0.42)
        back.bind(on_release=lambda *_: self.show_main())
        content.add_widget(back)
        content.add_widget(label("Contact Us", height=dp(54), halign="center",
                                 font_size="27sp", color=(0.13, 0.12, 0.31, 1)))
        content.add_widget(label("برای ارتباط، از راه‌های زیر با من در تماس باشید",
                                 height=dp(46), halign="center", font_size="14sp",
                                 color=(0.36, 0.34, 0.51, 1)))
        telegram = ContactAction("➤", (0.13, 0.62, 0.88, 1),
                                 "Telegram Channel", "برای ارتباط از طریق تلگرام",
                                 TELEGRAM_URL)
        instagram = ContactAction("◎", (0.79, 0.20, 0.66, 1),
                                  "Instagram Page", "برای مشاهده صفحه اینستاگرام",
                                  "https://www.instagram.com/hamedafshar.ir/")
        content.add_widget(telegram)
        content.add_widget(instagram)
        content.add_widget(Widget(size_hint_y=None, height=dp(18)))
        content.add_widget(label("Developed by Hamed AI", height=dp(34),
                                 halign="center", color=(0.48, 0.23, 0.80, 1)))
        return scroll

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
        """Link shared from a supported platform into SociaSave."""
        self.show_main()
        self.url.text = text
        self.start()

    # ---------------------------------------------------------- download
    def start(self):
        if self.busy:
            return
        urls = core.extract_urls(self.url.text)
        if not urls:
            self.log(fa("لینکی پیدا نشد."))
            return
        # Downloads are staged privately, then exported through Android MediaStore
        # to the public Download/SociaSave folder using the original post hierarchy.
        root = os.path.join(self.user_dir, "socia_save_staging")
        try:
            os.makedirs(root, exist_ok=True)
        except Exception as exc:
            self.log("Could not create app download folder: " + repr(exc))
            return
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
                if platform == "android":
                    Storage = autoclass("org.hamedafshari.sociasave.SociaSaveStorage")
                    relative_dir = os.path.relpath(destination, root).replace(os.sep, "/")
                    exported = Storage.exportDirectory(
                        PythonActivity.mActivity, destination, relative_dir)
                    if not exported:
                        raise RuntimeError("Android could not export files to Download/SociaSave.")
                    self.log("Exported files to Download/SociaSave/" + relative_dir)
                    shutil.rmtree(destination, ignore_errors=True)
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
        panel = BoxLayout(orientation="vertical", padding=(dp(20), dp(18)), spacing=dp(10))
        self.status_ring = StatusRing(size_hint=(1, None), height=dp(112))
        self.status_title = Label(
            text="Downloading...", font_name=FONT, font_size="19sp",
            color=(0.12, 0.10, 0.26, 1), size_hint_y=None, height=dp(36))
        self.status_detail = Label(
            text="در حال دریافت محتوا؛ لطفاً برنامه را نبندید",
            font_name=FONT, font_size="14sp", color=(0.36, 0.34, 0.49, 1),
            size_hint_y=None, height=dp(82), halign="center", valign="middle")
        self.status_detail.bind(size=lambda widget, size: setattr(widget, "text_size", size))
        self.status_close_btn = button(
            "Close", size_hint_y=None, height=dp(46),
            fill=(0.93, 0.89, 1, 1), color=(0.20, 0.14, 0.36, 1))
        self.status_close_btn.disabled = True
        self.status_close_btn.bind(on_release=lambda *_: self.dismiss_status())
        panel.add_widget(self.status_ring)
        panel.add_widget(self.status_title)
        panel.add_widget(self.status_detail)
        panel.add_widget(self.status_close_btn)
        self.status_popup = LightPopup(
            title="", content=panel, size_hint=(0.88, None), height=dp(350),
            auto_dismiss=False, separator_height=0,
            background="", background_color=(0.99, 0.98, 1, 1))
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
            self.files_btn.text = "★   Open SociaSave Folder"
            self.files_btn.set_fill((0.83, 0.97, 0.87, 1))
        else:
            self.status_ring.state = "error"
            self.status_title.text = "Download failed"
            self.status_detail.text = failures[0] if failures else fa("دانلود انجام نشد؛ لینک را بررسی کنید.")
        self.status_close_btn.disabled = False
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
        if platform == "android":
            try:
                Storage = autoclass("org.hamedafshari.sociasave.SociaSaveStorage")
                if Storage.openSociaSaveFolder(PythonActivity.mActivity):
                    return
            except Exception as exc:
                self.log("Could not open SociaSave folder in Android file manager: " + repr(exc))

        # Desktop fallback: open the local folder instead of showing an unreadable file list.
        root = self.download_root
        os.makedirs(root, exist_ok=True)
        try:
            if platform == "win":
                os.startfile(root)
            else:
                open_url("file://" + root)
        except Exception:
            self.show_folder_help()

    def show_folder_help(self):
        panel = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(12))
        panel.add_widget(label("SociaSave download location", height=dp(40),
                               halign="center", font_size="18sp",
                               color=(0.12, 0.10, 0.28, 1)))
        panel.add_widget(label("Download / SociaSave", height=dp(42),
                               halign="center", font_size="15sp",
                               color=(0.42, 0.18, 0.80, 1)))
        panel.add_widget(label("فایل‌ها پس از دانلود در پوشه عمومی Download گوشی ذخیره می‌شوند.",
                               height=dp(58), halign="center",
                               color=(0.35, 0.33, 0.48, 1)))
        close = button("Close", size_hint_y=None, height=dp(46))
        panel.add_widget(close)
        popup = LightPopup(title="", content=panel, size_hint=(0.88, None),
                           height=dp(235))
        close.bind(on_release=popup.dismiss)
        popup.open()


    # ------------------------------------------ Instagram login (private)
    def instagram_login(self):
        if platform != "android":
            self.log(fa("ورود فقط روی گوشی اندروید پشتیبانی می‌شود."))
            return
        try:
            Storage = autoclass("org.hamedafshari.sociasave.SociaSaveStorage")
            Storage.openInstagramLogin(PythonActivity.mActivity)
            self.login_open = True
            Clock.schedule_interval(self._poll_login, 1.5)
        except Exception as exc:
            self.login_open = False
            self.log("Could not open Instagram login: " + repr(exc))

    def _close_webview(self):
        try:
            if platform == "android":
                Storage = autoclass("org.hamedafshari.sociasave.SociaSaveStorage")
                Storage.closeInstagramLogin(PythonActivity.mActivity)
        except Exception as exc:
            self.log("Could not close Instagram login view: " + repr(exc))
        self.login_open = False

    def _poll_login(self, dt):
        if not self.login_open:
            return False
        try:
            Storage = autoclass("org.hamedafshari.sociasave.SociaSaveStorage")
            raw = str(Storage.getInstagramCookies() or "")
        except Exception:
            return True

        if "sessionid=" in raw:
            expiry = int(time.time()) + 365 * 24 * 3600
            lines = ["# Netscape HTTP Cookie File"]
            for part in raw.split(";"):
                if "=" in part:
                    key, value = part.strip().split("=", 1)
                    prefix = "#HttpOnly_" if key.lower() in ("sessionid", "csrftoken") else ""
                    lines.append("%s.instagram.com\tTRUE\t/\tTRUE\t%d\t%s\t%s" %
                                 (prefix, expiry, key, value))
            os.makedirs(self.user_dir, exist_ok=True)
            with open(self.cookies_path, "w", encoding="utf-8") as handle:
                handle.write("\n".join(lines) + "\n")
            self._close_webview()
            self.log(fa("✔ ورود انجام شد. به SociaSave برگشتید؛ لینک را دانلود کنید."))
            return False
        try:
            if not Storage.isInstagramLoginVisible():
                self.login_open = False
                return False
        except Exception:
            pass
        return True

    def on_back(self):
        """Android back button: close login view or return from Contact Us."""
        if self.login_open:
            self._close_webview()
            self.log(fa("ورود لغو شد."))
            return True
        if self.current_view is self.contact_view:
            self.show_main()
            return True
        return False


class SociaSaveApp(App):
    def build(self):
        self.title = "SociaSave"
        self.root_widget = Root(self.user_data_dir)
        Window.bind(on_keyboard=self.on_key)
        return self.root_widget

    def on_key(self, window, key, *args):
        if key == 27:
            return self.root_widget.on_back()
        return False

    def on_start(self):
        if platform == "android":
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
    SociaSaveApp().run()
