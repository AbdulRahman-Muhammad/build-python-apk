# main.py
# Collepedia Mobile App - Final Integrated Version
# Developed by Nanasoft Technologies Agency - CEO AbdulRahman Muhammad Rabie Ahmed

import os
import json
import asyncio
import threading
import shutil
import random
from functools import partial
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty, ListProperty, ObjectProperty, NumericProperty, BooleanProperty
from kivy.clock import Clock, mainthread
from kivy.lang import Builder
from kivy.utils import get_color_from_hex, platform
from kivy.core.window import Window
from kivymd.app import MDApp
from kivymd.uix.list import TwoLineAvatarIconListItem, BaseListItem, IRightBodyTouch
from kivymd.uix.selectioncontrol import MDCheckbox
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton, MDRaisedButton, MDIconButton
from kivymd.uix.spinner import MDSpinner
from kivymd.uix.label import MDLabel
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.toolbar import MDTopAppBar
from kivymd.uix.navigationdrawer import MDNavigationLayout
from kivymd.uix.card import MDCard
from kivymd.uix.bottomnavigation import MDBottomNavigation, MDBottomNavigationItem
from kivymd.theming import ThemableBehavior
from kivymd.uix.snackbar import Snackbar
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.textfield import MDTextField

from collepedia import CollepediaClient
from deep_translator import GoogleTranslator
import requests
from bs4 import BeautifulSoup
from plyer import notification
import html2text
from urllib.parse import urlparse, urljoin, quote
import pycountry
from cachetools import LRUCache

# --- Configuration ---
APP_NAME = "Collepedia Mobile"
APP_VERSION = "4.0"
CACHE_DIR_NAME = "app_data"
BASE_CACHE_FILE_NAME = "ar_base_cache.json"
LANG_CACHE_PREFIX = "list_cache_"
OFFLINE_ARTICLE_DIR_NAME = "offline_articles"
SETTINGS_FILE_NAME = "settings.json"
LAST_POST_FILE_NAME = "last_post.json"
FAVORITES_FILE_NAME = "favorites.json"

DEFAULT_CONTENT_LANG = 'ar'
DEFAULT_UI_LANG = 'en'

MAX_ARTICLES_IN_BASE_CACHE = 500
ARTICLES_PER_PAGE_IN_LIST = 25
BACKGROUND_TASK_INTERVAL_SECONDS = 3600 # 1 hour
MARKDOWN_CACHE_SIZE = 50
FALLBACK_IMAGE = 'atlas://kivymd/images/logo/kivymd-icon-256'

ALL_LANGUAGES = {}
try:
    for lang in pycountry.languages:
        code = getattr(lang, 'alpha_2', None)
        if code: ALL_LANGUAGES[code] = lang.name
except Exception as e:
    print(f"Could not load pycountry languages: {e}")
    ALL_LANGUAGES = {'en': 'English', 'ja': 'Japanese', 'es': 'Spanish', 'fr': 'French', 'de': 'German', 'ar': 'Arabic'}

# --- Global Variables ---
collepedia_client = CollepediaClient(user_agent=f"{APP_NAME}/{APP_VERSION}")
app_data_dir = ""
BASE_CACHE_FILE = ""
OFFLINE_ARTICLE_DIR = ""
SETTINGS_FILE = ""
FAVORITES_FILE = ""

base_cache = []
language_caches = {}
downloaded_languages = []
current_language = DEFAULT_CONTENT_LANG
last_post_id = None
favorites = []
markdown_cache = LRUCache(maxsize=MARKDOWN_CACHE_SIZE)

# --- Helper Functions ---
def load_json_safe(file_path, default_value):
    if not os.path.exists(file_path): return default_value
    try:
        with open(file_path, 'r', encoding='utf-8') as f: return json.load(f)
    except Exception as e: print(f"Error loading {file_path}: {e}"); return default_value

def save_json_safe(data, file_path):
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e: print(f"Error saving {file_path}: {e}")

def translate_sync(text, target_lang):
    if not text or target_lang == DEFAULT_CONTENT_LANG: return text or ""
    try:
        translated = GoogleTranslator(source='auto', target=target_lang).translate(text)
        return translated or ""
    except Exception as e:
        print(f"Translate error ({target_lang}): {e}")
        return f"(Translation Failed)"

async def get_full_article_content_async(url):
    details = {"html_content": "", "image_url": None}
    try:
        response = await asyncio.to_thread(requests.get, url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        img_tag = soup.find("meta", property="og:image")
        img = img_tag['content'] if img_tag else None
        if not img:
            first_img = soup.select_one('.post-body img')
            if first_img: img = first_img.get('src')
        if img:
            if img.startswith('//'): img = 'https:' + img
            elif not img.startswith(('http://', 'https://')): img = None
        details['image_url'] = img
        post_body = soup.select_one('.post-body')
        if post_body: details['html_content'] = str(post_body)
    except Exception as e: print(f"Full content fetch error for {url}: {e}")
    return details

# --- Kivy UI Definition (KV Language) ---
KV_STRING = '''
#:import get_color_from_hex kivy.utils.get_color_from_hex
#:import FadeTransition kivy.uix.screenmanager.FadeTransition
#:import partial functools.partial

<ArticleListItem>:
    ImageLeftWidget:
        source: root.image_source if root.image_source else app.fallback_image
        radius: [12,]
        size_hint: None, None
        size: "56dp", "56dp"

<LanguageListItem>:
    secondary_text: root.status_text
    RightCheckbox:
        id: checkbox
        active: root.is_active
        on_release: app.select_language(root.lang_code) if root.is_downloaded or root.lang_code == app.DEFAULT_CONTENT_LANG else None
    MDIconButton:
        icon: "download-circle-outline" if root.can_download else ("delete-circle" if root.can_delete else "")
        disabled: not (root.can_download or root.can_delete)
        opacity: 1 if (root.can_download or root.can_delete) else 0
        on_release: app.handle_language_download_delete(root.lang_code, root.is_downloaded)

<RightCheckbox@MDCheckbox>:
    pos_hint: {'center_y': .5}
    _no_ripple_effect: True

<LoadingSpinnerPopup@ModalView>:
    size_hint: None, None
    size: dp(120), dp(120)
    background_color: 0, 0, 0, 0.5
    border_radius: [16,]
    MDSpinner:
        size_hint: None, None
        size: dp(46), dp(46)
        pos_hint: {'center_x': 0.5, 'center_y': 0.5}
        active: True

MDBoxLayout:
    orientation: 'vertical'
    MDTopAppBar:
        id: main_toolbar
        title: app.title
        elevation: 3
        md_bg_color: app.theme_cls.primary_color
        specific_text_color: app.theme_cls.text_color
        left_action_items: [["menu", lambda x: app.root.ids.nav_layout.set_state("open")]]
        right_action_items: [["magnify", lambda x: app.open_search_dialog()]]

    MDNavigationLayout:
        id: nav_layout
        ScreenManager:
            id: screen_manager
            transition: FadeTransition(duration=0.15)

            HomeScreen:
                name: 'home'

            FavoritesScreen:
                name: 'favorites'

            ArticleScreen:
                name: 'article'

            SettingsScreen:
                name: 'settings'

        MDNavigationDrawer:
            id: nav_drawer
            anchor: 'left'
            elevation: 16
            md_bg_color: app.theme_cls.bg_light
            BoxLayout:
                orientation: 'vertical'
                padding: "8dp"
                spacing: "8dp"
                Image:
                    source: 'data/icon.png'
                    size_hint_y: None
                    height: "120dp"
                    allow_stretch: True
                    keep_ratio: True
                    padding: "10dp"
                MDLabel:
                    text: app.config.get('app', 'title') if app.config else config.APP_NAME
                    font_style: "H5"
                    halign: 'center'
                    adaptive_height: True
                    theme_text_color: "Primary"
                MDLabel:
                    text: f"v{app.config.get('app', 'version') if app.config else config.APP_VERSION}"
                    font_style: "Caption"
                    halign: 'center'
                    adaptive_height: True
                    theme_text_color: "Secondary"
                ScrollView:
                    MDList:
                        id: nav_drawer_list
                        OneLineIconListItem:
                            text: 'Latest Articles'
                            on_release: app.switch_screen('home')
                            IconLeftWidget: icon: 'newspaper-variant-multiple'
                        OneLineIconListItem:
                            text: 'Favorites'
                            on_release: app.switch_screen('favorites')
                            IconLeftWidget: icon: 'heart-outline'
                        MDSeparator:
                        OneLineIconListItem:
                            text: 'Settings'
                            on_release: app.switch_screen('settings')
                            IconLeftWidget: icon: 'cog-outline'
                        OneLineIconListItem:
                            text: 'About'
                            on_release: app.show_about_dialog()
                            IconLeftWidget: icon: 'information-outline'

'''
# --- Widget Classes ---
class ArticleListItem(TwoLineAvatarIconListItem):
    article_data = ObjectProperty(None)
    list_data = ObjectProperty(None)
    image_source = StringProperty('')

class LanguageListItem(BaseListItem):
    lang_code = StringProperty('')
    lang_name = StringProperty('')
    status_text = StringProperty('')
    is_active = BooleanProperty(False)
    is_downloaded = BooleanProperty(False)
    can_download = BooleanProperty(False)
    can_delete = BooleanProperty(False)

class RightCheckbox(MDCheckbox):
    pass

class LoadingSpinnerPopup(ModalView):
    pass

# --- Screen Classes ---
class BaseScreen(Screen):
    app = ObjectProperty(None)
    content_built = BooleanProperty(False)

    def on_enter(self, *args):
        self.app = App.get_running_app()
        if not self.content_built:
            self.build_content()
            self.content_built = True
        self.refresh_content()

    def build_content(self): pass
    def refresh_content(self): pass

class HomeScreen(BaseScreen):
    article_list_widget = ObjectProperty(None)
    def build_content(self):
        layout = MDBoxLayout(orientation='vertical', id='home_screen_layout')
        self.article_list_widget = MDList(id='home_article_list')
        layout.add_widget(MDScrollView(self.article_list_widget))
        self.add_widget(layout)

    def refresh_content(self):
        Clock.schedule_once(lambda dt: self.app.populate_article_list(self.article_list_widget))

class FavoritesScreen(BaseScreen):
    fav_list_widget = ObjectProperty(None)
    def build_content(self):
        layout = MDBoxLayout(orientation='vertical', id='fav_screen_layout')
        self.fav_list_widget = MDList(id='fav_article_list')
        layout.add_widget(MDScrollView(self.fav_list_widget))
        self.add_widget(layout)

    def refresh_content(self):
        Clock.schedule_once(lambda dt: self.app.populate_favorites_list(self.fav_list_widget))

class ArticleScreen(BaseScreen):
    toolbar = ObjectProperty(None)
    content_label = ObjectProperty(None)
    def build_content(self):
        layout = MDBoxLayout(orientation='vertical', id='article_screen_layout')
        self.toolbar = MDTopAppBar(title="Article", elevation=2,
                                    left_action_items=[["arrow-left", lambda x: self.app.switch_screen('home')]],
                                    right_action_items=[["heart-outline", lambda x: self.app.toggle_favorite()]]
                                    )
        self.content_label = MDLabel(padding="20dp", markup=True, size_hint_y=None, on_ref_press=self.open_link)
        self.content_label.bind(texture_size=self.content_label.setter('height'))
        layout.add_widget(self.toolbar)
        layout.add_widget(MDScrollView(self.content_label, id='article_scroll'))
        self.add_widget(layout)

    def update_content(self, title, content_html, is_favorite):
        self.toolbar.title = title[:40] + ('...' if len(title) > 40 else '')
        self.content_label.text = self._basic_html_to_markup(content_html)
        self.toolbar.right_action_items = [[("heart" if is_favorite else "heart-outline"), lambda x: self.app.toggle_favorite()]]

    def _basic_html_to_markup(self, html_content):
        # Very basic conversion for MDLabel, consider html2text for better results if needed
        if not html_content: return ""
        markup = html_content.replace('<p>', '').replace('</p>', '\n').replace('<br>', '\n').replace('<br/>', '\n')
        markup = markup.replace('<b>', '[b]').replace('</b>', '[/b]')
        markup = markup.replace('<i>', '[i]').replace('</i>', '[/i]')
        # Remove images for now, handle links
        soup = BeautifulSoup(markup, 'lxml')
        for img in soup.find_all('img'): img.decompose()
        for a in soup.find_all('a'):
             href = a.get('href', '#')
             a.replace_with(f'[ref={href}][color=0000ff]{a.get_text()}[/color][/ref]')
        return soup.get_text() # Get text after processing tags

    def open_link(self, instance, ref):
        try:
             import webbrowser
             webbrowser.open(ref)
        except Exception as e:
             print(f"Error opening link {ref}: {e}")

    def refresh_content(self): pass

class SettingsScreen(BaseScreen):
    language_list = ObjectProperty(None)
    def build_content(self):
        layout = MDBoxLayout(orientation='vertical', padding="20dp", spacing="20dp")
        layout.add_widget(MDLabel(text="Manage Content Languages", font_style="H6", adaptive_height=True, halign='center'))
        self.filter_field = MDTextField(hint_text="Filter languages...", on_text_validate=self.filter_languages, size_hint_y=None, height="48dp")
        layout.add_widget(self.filter_field)
        self.language_list = MDList(id='language_list_widget')
        layout.add_widget(MDScrollView(self.language_list))
        layout.add_widget(MDRaisedButton(text="Clear Offline Articles Cache", on_release=lambda x: self.app.clear_offline_cache(), pos_hint={'center_x': 0.5}, size_hint_y=None, height="48dp"))
        self.add_widget(layout)

    def refresh_content(self):
         Clock.schedule_once(lambda dt: self.app.populate_language_list(self.language_list, self.filter_field.text.lower()))

    def filter_languages(self, instance):
        self.app.populate_language_list(self.language_list, instance.text.lower())

# --- Main KivyMD App Class ---
class CollepediaApp(MDApp):
    dialog = None
    title = StringProperty(APP_NAME)
    current_article = ObjectProperty(None)
    current_language = StringProperty(DEFAULT_CONTENT_LANG)
    downloaded_languages = ListProperty([])
    last_post_id = StringProperty(None)
    fallback_image = StringProperty(FALLBACK_IMAGE)

    def build(self):
        self.theme_cls.theme_style_switch_animation = True
        self.theme_cls.theme_style = "Light"
        self.theme_cls.primary_palette = "BlueGray"
        self.theme_cls.accent_palette = "Indigo"
        initialize_paths(self.user_data_dir)
        initialize_background()
        return Builder.load_string(KV_STRING)

    def on_start(self):
        self.load_app_state()
        self.root.ids.screen_manager.current = 'home'
        Clock.schedule_once(self.initial_load, 1)
        Clock.schedule_interval(self.run_background_kivy, BACKGROUND_TASK_INTERVAL_SECONDS)

    def load_app_state(self):
        settings = load_all_data()
        self.current_language = settings.get('current_language', DEFAULT_CONTENT_LANG)
        self.downloaded_languages = settings.get('downloaded_languages', [])
        self.last_post_id = settings.get('last_post_id', None)
        print(f"App State Loaded: Lang={self.current_language}, DL_Langs={self.downloaded_languages}")

    def save_app_state(self):
        settings = {'current_language': self.current_language, 'downloaded_languages': self.downloaded_languages, 'last_post_id': self.last_post_id}
        save_settings(settings)

    def run_background_kivy(self, dt):
        threading.Thread(target=run_background_tasks_thread, daemon=True).start()

    def initial_load(self, dt):
        if not base_cache:
            self.show_progress_dialog("Fetching initial articles...")
            threading.Thread(target=self._initial_fetch_thread, daemon=True).start()
        else:
            self.refresh_ui_lists()

    def _initial_fetch_thread(self):
        if fetch_base_cache_sync():
            Clock.schedule_once(lambda dt: self.refresh_ui_lists())
        else:
            Clock.schedule_once(lambda dt: self.show_snackbar("Error: Could not load initial data."))
        self.dismiss_dialog()

    @mainthread
    def refresh_ui_lists(self):
        self.populate_article_list()
        self.populate_favorites_list()
        self.populate_language_list()

    @mainthread
    def populate_article_list(self, list_widget=None):
        if not list_widget:
            try: list_widget = self.root.ids.screen_manager.get_screen('home').article_list_widget
            except Exception as e: print(f"Error getting list widget: {e}"); return
        list_widget.clear_widgets()
        
        display_cache = get_list_display_cache(self.current_language)
        if not display_cache:
            msg = f"Language '{self.current_language}' not downloaded. Go to Settings." if self.current_language != DEFAULT_CONTENT_LANG else "No articles loaded yet. Try refreshing."
            list_widget.add_widget(MDLabel(text=msg, halign='center', theme_text_color="Secondary", padding_y="20dp"))
            return

        for item_data in display_cache[:ARTICLES_PER_PAGE_IN_LIST]:
            original_post = next((p for p in base_cache if p.get('id') == item_data.get('id')), item_data)
            list_item = ArticleListItem(
                text=item_data.get('title', 'No Title'),
                secondary_text=(item_data.get('snippet', '') or '')[:120] + '...',
                image_source=item_data.get('image_url', ''),
                list_data=item_data, article_data=original_post
            )
            list_item.bind(on_release=self.open_article)
            list_widget.add_widget(list_item)
            
    @mainthread
    def populate_favorites_list(self, list_widget=None):
        if not list_widget:
            try: list_widget = self.root.ids.screen_manager.get_screen('favorites').fav_list_widget
            except: return
        list_widget.clear_widgets()
        
        favs_data = get_favorite_articles_sync(self.current_language)
        
        if not favs_data:
            list_widget.add_widget(MDLabel(text="No favorite articles saved yet.", halign='center', theme_text_color="Secondary", padding_y="20dp"))
            return

        for item_data in favs_data:
            list_item = ArticleListItem(
                text=item_data.get('title', 'No Title'),
                secondary_text=item_data.get('snippet', 'Saved Offline')[:120] + '...',
                image_source=item_data.get('image_url', ''),
                list_data=item_data, article_data=item_data
            )
            list_item.bind(on_release=self.open_article)
            list_widget.add_widget(list_item)
            
    @mainthread
    def populate_language_list(self, list_widget=None, filter_text=''):
        if not list_widget:
            try: list_widget = self.root.ids.screen_manager.get_screen('settings').language_list
            except: return
        list_widget.clear_widgets()
        
        filtered_langs = {code: name for code, name in ALL_LANGUAGES.items() if not filter_text or filter_text in code or filter_text in name.lower()}

        def sort_key(lang_tuple):
            code, name = lang_tuple
            if code == self.current_language: return (0, name)
            if code in self.downloaded_languages or code == DEFAULT_CONTENT_LANG: return (1, name)
            return (2, name)

        sorted_langs = sorted(filtered_langs.items(), key=sort_key)

        for lang_code, lang_name in sorted_langs:
            is_downloaded = lang_code in self.downloaded_languages
            is_active = self.current_language == lang_code
            is_base = lang_code == DEFAULT_CONTENT_LANG
            can_download = lang_code in ACTIVE_TRANSLATION_LANGUAGES and not is_downloaded and not is_base
            can_delete = is_downloaded and not is_base
            status = "Active" if is_active else ("Base" if is_base else ("Downloaded" if is_downloaded else "Available"))

            item = LanguageListItem(
                lang_code=lang_code, lang_name=lang_name, text=lang_name,
                status_text=status, is_active=is_active, is_downloaded=is_downloaded,
                can_download=can_download, can_delete=can_delete
            )
            list_widget.add_widget(item)

    def handle_language_download_delete(self, lang_code, is_downloaded):
         if is_downloaded: self.delete_language(lang_code)
         else: self.download_language(lang_code)

    def delete_language(self, lang_code):
         if delete_language_pack(lang_code):
             if lang_code in self.downloaded_languages: self.downloaded_languages.remove(lang_code)
             if self.current_language == lang_code: self.current_language = DEFAULT_CONTENT_LANG
             self.save_app_state()
             self.populate_language_list()
             self.populate_article_list()
             self.show_snackbar(f"Language pack {lang_code.upper()} deleted.")
         else:
             self.show_snackbar(f"Error deleting language pack {lang_code.upper()}.")

    def handle_language_action(self, lang_code, *args):
        if lang_code == DEFAULT_CONTENT_LANG or lang_code in self.downloaded_languages:
            self.select_language(lang_code)

    def select_language(self, lang_code, *args):
        self.current_language = lang_code
        self.save_app_state()
        self.populate_language_list()
        self.populate_article_list()
        self.populate_favorites_list()
        self.show_snackbar(f"Content language set to {lang_code.upper()}")

    def download_language(self, lang_code):
        if lang_code not in ACTIVE_TRANSLATION_LANGUAGES:
            self.show_snackbar(f"Automated translation for {lang_code.upper()} is not enabled.")
            return
        self.show_progress_dialog(f"Preparing language pack {lang_code.upper()}...")
        threading.Thread(target=download_language_thread,
                         args=(lang_code, self.update_progress, self.on_language_download_complete),
                         daemon=True).start()

    @mainthread
    def update_progress(self, text):
        if self.dialog and hasattr(self.dialog, 'title'): self.dialog.title = text

    @mainthread
    def on_language_download_complete(self, success, message):
        self.dismiss_dialog()
        if success:
            lang_code = message.split(" ")[1]
            self.downloaded_languages = list(set(self.downloaded_languages + [lang_code]))
            self.save_app_state()
            self.populate_language_list()
            self.select_language(lang_code)
            self.show_snackbar(message)
        else:
            self.show_snackbar(f"Error: {message}")

    def open_article(self, list_item):
        self.current_article = list_item.article_data
        if not self.current_article: return
        
        self.switch_screen('article')
        article_screen = self.root.ids.screen_manager.get_screen('article')
        
        display_lang = self.current_language
        is_fav = False
        is_offline = False
        if list_item.list_data and list_item.list_data.get('is_offline'):
             display_lang = list_item.list_data.get('lang', self.current_language)
             is_fav = True
             is_offline = True

        display_title = list_item.list_data.get('title', 'Loading...')

        article_screen.update_content(display_title, "<i>Loading full article content...</i>", is_fav)
        
        threading.Thread(target=self._load_article_content_thread,
                         args=(self.current_article, display_lang, is_offline),
                         daemon=True).start()

    def _load_article_content_thread(self, article_data, lang, force_offline=False):
        url = article_data.get('link')
        is_fav = is_favorite_sync(url, lang)
        
        offline_content = load_offline_article_sync(url, lang)
        
        if offline_content and (force_offline or is_fav):
            print(f"Loading offline article: {url} ({lang})")
            title = translate_sync(article_data.get('title'), lang)
            Clock.schedule_once(lambda dt: self.root.ids.screen_manager.get_screen('article').update_content(title, offline_content, is_fav))
            return

        print(f"Fetching online article: {url} for lang {lang}")
        try:
            full_content_data = asyncio.run(get_full_article_content_async(url)) # Use async version
            translated_content = translate_sync(full_content_data.get('html_content'), lang)
            title = translate_sync(article_data.get('title'), lang)
            Clock.schedule_once(lambda dt: self.root.ids.screen_manager.get_screen('article').update_content(title, translated_content, is_fav))
        except Exception as e:
            Clock.schedule_once(lambda dt: self.root.ids.screen_manager.get_screen('article').update_content("Error", f"Could not load article: {e}", is_fav))

    def toggle_favorite(self):
        if not self.current_article: return
        url = self.current_article.get('link')
        lang = self.current_language
        
        if is_favorite_sync(url, lang):
            if remove_favorite_sync(url, lang):
                self.show_snackbar("Removed from Favorites")
                self.root.ids.screen_manager.get_screen('article').toolbar.right_action_items = [["heart-outline", lambda x: self.toggle_favorite()]]
        else:
             self.show_progress_dialog(f"Saving article to Favorites ({lang.upper()})...")
             threading.Thread(target=self._save_and_add_favorite_thread, args=(url, lang), daemon=True).start()

    def _save_and_add_favorite_thread(self, url, lang):
         save_article_offline_sync(url, lang, self.update_progress, self.on_save_for_favorite_complete)

    @mainthread
    def on_save_for_favorite_complete(self, success, message):
         self.dismiss_dialog()
         if success:
             url = self.current_article.get('link')
             lang = self.current_language
             if add_favorite_sync(url, lang):
                 self.show_snackbar("Article saved offline & added to Favorites!")
                 self.root.ids.screen_manager.get_screen('article').toolbar.right_action_items = [["heart", lambda x: self.toggle_favorite()]]
         else:
             self.show_snackbar(f"Error saving article for favorite: {message}")

    def clear_offline_cache(self):
         success, message = clear_offline_articles_sync()
         self.show_snackbar(message)
         self.populate_favorites_list()

    def switch_screen(self, screen_name):
        self.root.ids.screen_manager.current = screen_name
        self.root.ids.nav_layout.set_state("close")
        if screen_name == 'home': self.title = "Latest Articles"
        elif screen_name == 'favorites': self.title = "Favorites"
        elif screen_name == 'settings': self.title = "Settings"

    @mainthread
    def reload_data_and_refresh_ui(self):
         self.load_app_state() # Reload all caches and settings
         self.refresh_ui_lists() # Refresh all visible lists
         self.show_snackbar("Article list updated.")

    def send_notification(self, post):
         lang = self.current_language
         title = translate_sync(post.get('title', 'New Article'), lang)
         try: notification.notify(title=f"New Collepedia Article", message=title, app_name=APP_NAME)
         except Exception as e: print(f"Failed to send notification: {e}")

    @mainthread
    def show_progress_dialog(self, text):
        if self.dialog: self.dialog.dismiss()
        self.dialog = LoadingSpinnerPopup() # Use the KV definition
        # How to set title on ModalView? KivyMD Dialog might be better if title needed
        self.dialog.open()

    @mainthread
    def dismiss_dialog(self, *args):
        if self.dialog: self.dialog.dismiss(); self.dialog = None

    @mainthread
    def show_snackbar(self, text):
        Snackbar(text=text, duration=2.5).open()

    def show_about_dialog(self): pass
    def open_search_dialog(self): pass

if __name__ == '__main__':
    CollepediaApp().run()
