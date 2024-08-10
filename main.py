# Standard Library
import logging
import os

# Third-Party Libraries
import streamlit as st

# Local Modules
import services.config as config
import services.function as func
from embedded import Embedded as embed
from services.database import (
    DatabaseInitializer,
    StartFlask,
    DbIdVideoManager,
    app,
    WatchTimeAPI,
)

class CustomFormatter(logging.Formatter):
    def format(self, record):
        record.filename = os.path.basename(record.pathname)
        if record.filename.endswith('.py'):
            record.filename = record.filename[:-3]
        record.filename = record.filename.ljust(10)
        return super().format(record)

# Logging setting
def setup_logging():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    # コンソールハンドラー
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(CustomFormatter('%(asctime)s - %(filename)s - %(levelname)-8s - %(message)s'))

    # ファイルハンドラー
    file_handler = logging.FileHandler('app.log')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(CustomFormatter('%(asctime)s - %(filename)s - %(levelname)-8s - %(message)s'))

    # ハンドラーをロガーに追加
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

# Initialize logging
setup_logging()
logger = logging.getLogger(__name__)

# Initialize Classes
class CacheInitialize:
    def __init__(self, logger, DatabaseInitializer, ConfigManager, find_free_port, StartFlask):
        self.logger = logger
        self.config_manager = ConfigManager(self.logger)
        self.db_path = self.config_manager.get_db_path()
        self.DatabaseInitializer = DatabaseInitializer
        self.youtube_client = None
        self.port_number = find_free_port(self.logger)
        self.start_flask = StartFlask(self.logger, self.port_number).start_flask

    def initialize_database(self):
        self.logger.info("Initializing database...")
        self.DatabaseInitializer.create_tables(self.db_path, self.logger)
    
    def get_youtube_client(self):
        self.logger.info("Getting YouTube client...")
        self.youtube_client = self.config_manager.get_youtube_client()
        return self.youtube_client

    def start_server(self):
        self.logger.info(f"Starting Flask server on port {self.port_number}...")
        self.start_flask()

# Main Class
class YouTubeWatchTimeApp:
    def __init__(self, logger, cache_initializer, func, embed, DbIdVideoManager):
        self.logger = logger
        self.cache_initializer = cache_initializer
        self.db_path = self.cache_initializer.db_path
        self.func = func
        self.embed = embed
        self.DbIdVideoManager = DbIdVideoManager

    @st.cache_resource
    def initialize(_self):
        try:
            _self.cache_initializer.initialize_database()
            youtube_client = _self.cache_initializer.get_youtube_client()
            _self.cache_initializer.start_server()
            return youtube_client
        except Exception as e:
            _self.logger.error(f"Error initializing YouTubeWatchTimeApp: {e}", exc_info=True)
            st.error(f"Error initializing app: {e}")

    def run(self):
        try:
            youtube_client = self.initialize()
            st.title("YouTube-Watch-Time")
            url = st.text_input("Enter video or channel URL")

            if url:
                self.logger.info(f"The URL is entered: {url}")
                self.video_display(url, youtube_client)
        except Exception as e:
            self.logger.error(f"Error running YouTubeWatchTimeApp: {e}", exc_info=True)
            st.error(f"Error running app: {e}")

    def video_display(self, url, youtube_client):
        try:
            url_type = self.func.URLChecker(self.logger).check_url(url)
            self.logger.info(f"The URL type is: {url_type}")
            processed_urls = self.func.URLProcessor(self.logger).process_url(url, url_type, youtube_client, self.db_path)

            self.logger.info(f"Processed URLs: {processed_urls}")

            for video_url in processed_urls:
                video_db_id = self.DbIdVideoManager(self.logger, self.db_path).get_video_id(video_url)
                video_url = f"{video_url}?enablejsapi=1"

                self.logger.info(f"Video database ID: {video_db_id}")
                self.logger.info(f"Video URL: {video_url}")
                self.logger.info(f"Flask server port number: {self.cache_initializer.port_number}")
                
                self.embed(self.logger).video_html(video_db_id, video_url, self.cache_initializer.port_number)
        except Exception as e:
            self.logger.error(f"Error displaying video from YouTubeWatchTimeApp: {e}", exc_info=True)
            st.error(f"Error displaying video from YouTubeWatchTimeApp: {e}")

def add_watch_time_api_if_not_exists(app, logger, db_path):
    endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
    if 'watch_time_api' not in endpoints:
        watch_time_view = WatchTimeAPI.as_view('watch_time_api', logger=logger, db_path=db_path)
        app.add_url_rule('/save_watch_time', view_func=watch_time_view, methods=['GET'])

@st.cache_resource
def get_cache_initializer(_logger, DatabaseInitializer, ConfigManager, _find_free_port, StartFlask):
    return CacheInitialize(_logger, DatabaseInitializer, ConfigManager, _find_free_port, StartFlask)

@st.cache_resource
def get_youtube_watch_time_app(_logger, _cache_initializer, _func, _embed, _DbIdVideoManager):
    return YouTubeWatchTimeApp(_logger, _cache_initializer, _func, _embed, _DbIdVideoManager)

# Create an instance
cache_initializer = get_cache_initializer(
    logger, 
    DatabaseInitializer, 
    config.ConfigManager,
    func.find_free_port, 
    StartFlask
)

app_instance = get_youtube_watch_time_app(
    logger,
    cache_initializer,
    func,
    embed,
    DbIdVideoManager,
)

# Run the app
add_watch_time_api_if_not_exists(app, logger, cache_initializer.db_path)
app_instance.run()