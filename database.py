# Standard Library
import sqlite3
import datetime
import re
import threading

# Third-Party Libraries
from flask import Flask, request, jsonify
from flask.views import MethodView
from flask_cors import CORS
import streamlit as st

class DatabaseManager:
    def __init__(self, db_path, logger):
        self.db_path = db_path
        self.logger = logger
        self.conn = None
        self.cursor = None

    def connect(self):
        try:
            self.logger.info(f"Connecting to database at {self.db_path}...")
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
            self.logger.info("Database connected successfully.")
        except sqlite3.Error as e:
            self.logger.error(f"An error occurred while connecting to the database: {e}")
            st.error(f"An error occurred while connecting to the database: {e}")
            raise

    def close(self, commit=True):
        try:
            self.logger.info("Closing database connection...")
            if self.conn:
                if commit:
                    self.conn.commit()
                self.conn.close()
                self.conn, self.cursor = None, None
                self.logger.info("Database connection closed successfully.")
        except sqlite3.Error as e:
            self.logger.error(f"Error closing the database: {e}")
            st.error(f"Error closing the database: {e}")
            raise

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close(commit=exc_type is None)

class DatabaseInitializer:
    @classmethod
    def create_tables(cls, db_path, logger):
        db_manager = DatabaseManager(db_path, logger)
        with db_manager as db:
            try:
                db.cursor.execute('''
                CREATE TABLE IF NOT EXISTS videos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_title TEXT NOT NULL,
                    channel_table_id INTEGER,
                    video_url TEXT NOT NULL,
                    date_retrieved DATE NOT NULL,
                    FOREIGN KEY(channel_table_id) REFERENCES channels(id)
                )
                ''')
                db.cursor.execute('''
                CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_name TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    channel_url TEXT NOT NULL,
                    date_retrieved DATE NOT NULL
                )
                ''')
                db.cursor.execute('''
                CREATE TABLE IF NOT EXISTS video_watch_times (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id INTEGER NOT NULL,
                    total_watch_time INTEGER DEFAULT 0,
                    date_retrieved DATE NOT NULL,
                    FOREIGN KEY(video_id) REFERENCES videos(id)
                )
                ''')
                logger.info("Database initialized successfully.")
            except sqlite3.Error as e:
                logger.error(f"An error occurred: {e}")
                st.error(f"An error occurred: {e}")
                raise

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

class StartFlask:
    def __init__(self, logger, port_number):
        self.logger = logger
        self.port_number = port_number

    def run_flask(self):
        app.run(port=self.port_number)

    def start_flask(self):
        try:
            self.logger.info(f"Running Flask server on port {self.port_number}...")
            flask_thread = threading.Thread(target=self.run_flask)
            flask_thread.start()
            self.logger.info("Flask server started.")
        except Exception as e:
            self.logger.error(f"Error starting Flask server: {e}", exc_info=True)
            st.error(f"Error starting Flask server: {e}")
            raise e

#Insert channel into database.
class ChannelManager:
    def __init__(self, logger, db_path):
        self.logger = logger
        self.db_path = db_path

    def channel_id_search(self, channel_id):
        with DatabaseManager(self.db_path, self.logger) as db:
            db.cursor.execute('SELECT * FROM channels WHERE channel_id = ?', (channel_id,))
            result = db.cursor.fetchone()
            if result:
                return result
            else:
                return None
                
    def insert_channel(self, channel_name, channel_id, channel_url, date_retrieved):
        with DatabaseManager(self.db_path, self.logger) as db:
            try:
                db.cursor.execute('''
                INSERT INTO channels (channel_name, channel_id, channel_url, date_retrieved)
                VALUES (?, ?, ?, ?)
                ''', (channel_name, channel_id, channel_url, date_retrieved))
                channel_table_id = db.cursor.lastrowid
                self.logger.info('channel inserted successfully')
                return channel_table_id
            except sqlite3.Error as e:
                self.logger.error(f"An error occurred: {e}")
                st.error(f"An error occurred: {e}")
                raise

#Insert video into database.
class VideoManager:
    def __init__(self, logger, db_path, video_title, channel_table_id, video_url, date_retrieved):
        self.logger = logger
        self.db_path = db_path
        self.video_title = video_title
        self.channel_table_id = channel_table_id
        self.video_url = video_url
        self.date_retrieved = date_retrieved

    def insert_video(self):
        with DatabaseManager(self.db_path, self.logger) as db:
            try:
                db.cursor.execute('''
                INSERT INTO videos (video_title, channel_table_id, video_url, date_retrieved)
                VALUES (?, ?, ?, ?)
                ''', (self.video_title, self.channel_table_id, self.video_url, self.date_retrieved))
                self.logger.info('Video inserted successfully')
            except sqlite3.Error as e:
                self.logger.error(f"An error occurred: {e}")
                st.error(f"An error occurred: {e}")
                raise

class DbIdVideoManager:
    def __init__(self, logger, db_path):
        self.logger = logger
        self.db_path = db_path

    def get_video_id(self, video_url):
        youtube_video_id = re.search(r'embed/([^&]+)', video_url).group(1)
        video_url = f"https://www.youtube.com/watch?v={youtube_video_id}"
        with DatabaseManager(self.db_path, self.logger) as db:
            try:
                db.cursor.execute('''
                SELECT id FROM videos 
                WHERE video_url = ? 
                ORDER BY date_retrieved DESC 
                LIMIT 1
                ''', (video_url,))
                result = db.cursor.fetchone()
                if result:
                    self.logger.info(f"This video database ID is founded: {result[0]}")
                    return result[0]
                else:
                    raise ValueError(f"No video found for URL: {video_url}")
            except sqlite3.Error as e:
                self.logger.error(f"An error occurred while querying the database: {e}")
                st.error(f"An error occurred while querying the database: {e}")
                raise

class WatchTimeAPI(MethodView):
    def __init__(self, logger, db_path):
        self.logger = logger
        self.db_path = db_path

    def get(self):
        try:
            video_id = request.args.get('video_id')
            watch_time = request.args.get('watch_time')
        
            if not video_id or not watch_time:
                self.logger.error('Missing video_id or watch_time')
                return jsonify({'status': 'error', 'message': 'Missing video_id or watch_time'}), 400
            
            return self.save_watch_time(video_id, watch_time)

        except Exception as e:
            self.logger.error(f"An error occurred: {e}")
            st.error(f"An error occurred: {e}")
            raise

    def save_watch_time(self, video_id, watch_time):
        with DatabaseManager(self.db_path, self.logger) as db:
            try:
                db.cursor.execute('SELECT total_watch_time FROM video_watch_times WHERE video_id = ?', (video_id,))
                result = db.cursor.fetchone()
                date_retrieved = datetime.datetime.now()

                if result:
                    total_watch_time = result[0] + float(watch_time)
                    db.cursor.execute('UPDATE video_watch_times SET total_watch_time = ?, date_retrieved = ? WHERE video_id = ?', (total_watch_time, date_retrieved, video_id))
                else:
                    total_watch_time = float(watch_time)
                    self.logger.info(f'video_id: {video_id}')
                    self.logger.info(f'total_watch_time: {total_watch_time}')
                    db.cursor.execute('INSERT INTO video_watch_times (video_id, total_watch_time, date_retrieved) VALUES (?, ?, ?)', (video_id, total_watch_time, date_retrieved))
                    
                return jsonify({'status': 'success', 'video_id': video_id, 'total_watch_time': total_watch_time})
            
            except sqlite3.Error as e:
                self.logger.error(f"An error occurred: {e}")
                st.error(f"An error occurred: {e}")
                return jsonify({'status': 'error', 'message': str(e)}), 500