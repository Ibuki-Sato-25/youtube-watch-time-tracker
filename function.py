# Standard Library
import re
import socket
import datetime

# Third-Party Library
import streamlit as st

# Local Module
from services.database import (
    ChannelManager,
    VideoManager,
)

def find_free_port(logger):
    try:
        logger.info("Finding free port...")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('', 0))
        addr, port = s.getsockname()
        if port is None:
            raise ValueError("Failed to find free port")
        logger.info(f"Free port found: {port}")
        return port
    except Exception as e:
        logger.error(f"Failed to find free port: {e}")
        st.error(f"Failed to find free port: {e}")
        return None
    finally:
        if s:
            s.close()

class URLChecker:
    def __init__(self, logger):
        try:
            self.logger = logger
            self.channel_patterns = [
                re.compile(r'(https?://)?(www\.)?(youtube\.com|youtu\.?be)/channel/'),
                re.compile(r'(https?://)?(www\.)?(youtube\.com|youtu\.?be)/@'),
                re.compile(r'(https?://)?(www\.)?(youtube\.com|youtu\.?be)/user/')
            ]
            self.video_pattern = re.compile(r'(https?://)?(www\.)?(youtube\.com|youtu\.?be)/watch\?v=')
        except Exception as e:
            self.logger.error(f"Error initializing URLChecker: {e}", exc_info=True)
            st.error(f"Error initializing URLChecker: {e}")
            raise e

    def check_url(self, url):
        try:
            for pattern in self.channel_patterns:
                if pattern.match(url):
                    return "channel"
            if self.video_pattern.match(url):
                return "video"
            else:
                raise ValueError("Invalid URL")
        except Exception as e:
            self.logger.error(f"Error checking URL: {e}", exc_info=True)
            st.error(f"Error checking URL: {e}")
            raise e

class YouTubeInfoFetcher:
    def __init__(self, logger, youtube_client):
        self.logger = logger
        self.youtube_client = youtube_client

    def channel_info(self, channel_id):
        try:
            request = self.youtube_client.channels().list(
                part="snippet",
                id=channel_id
            )
            response = request.execute()

            if response is None:
                raise ValueError("API response is None")

            self.logger.info(f"Channel information: {response}")

            if 'items' in response and len(response['items']) > 0:
                channel_name = response['items'][0]['snippet']['title']
                channel_url = f"https://www.youtube.com/channel/{channel_id}"
                date_retrieved = datetime.datetime.now()
                return channel_name, channel_id, channel_url, date_retrieved
            else:
                raise ValueError("Channel not found or invalid API key")
        except Exception as e:
            self.logger.error(f"Error fetching channel info: {e}", exc_info=True)
            raise e
    
    def channel_info_insert(self, channel_id, db_path):
        try:
            channel_info = ChannelManager(self.logger, db_path).channel_id_search(channel_id)
            if channel_info is None:
                channel_name, channel_id, channel_url, channel_date_retrieved = self.channel_info(channel_id) 
                if channel_name is None or channel_id is None or channel_url is None or channel_date_retrieved is None:
                    raise ValueError("Channel name, channel ID, channel URL, or channel date retrieved is None")
                self.logger.info(f"Channel name: {channel_name}, Channel ID: {channel_id}, Channel URL: {channel_url}, Channel date retrieved: {channel_date_retrieved}")
                channel_table_id = ChannelManager(self.logger, db_path).insert_channel(channel_name, channel_id, channel_url, channel_date_retrieved)
                self.logger.info(f"Channel table ID: {channel_table_id}")
            else:
                self.logger.info(f"Channel information already exists: {channel_info}")
                channel_table_id = channel_info[0]
            return channel_table_id
        except Exception as e:
            self.logger.error(f"Error processing channel information: {e}", exc_info=True)
            st.error(f"Error processing channel information: {e}")
            raise e

class VideoProcessor(YouTubeInfoFetcher):
    def __init__(self, logger, url, youtube_client, db_path):
        super().__init__(logger, youtube_client)
        self.logger = logger
        self.video_url = url
        self.youtube_client = youtube_client
        self.db_path = db_path
        self.video_id = re.search(r'v=([^&]+)', self.video_url).group(1)

    def video_info(self):
        try:
            request = self.youtube_client.videos().list(
                part="snippet",
                id=self.video_id
            )
            response = request.execute()

            if response is None:
                raise ValueError("API response is None")

            self.logger.info(f"Video information: {response}")

            if 'items' in response and len(response['items']) > 0:
                video_title = response['items'][0]['snippet']['title']
                channel_id = response['items'][0]['snippet']['channelId']
                date_retrieved = datetime.datetime.now()
                return video_title, date_retrieved, channel_id
            else:
                raise ValueError("Video not found or invalid API key")
        except Exception as e:
            self.logger.error(f"Error fetching video info: {e}", exc_info=True)
            raise e

    def process_video(self):
        try:
            video_title, date_retrieved, channel_id = self.video_info()
            if video_title is None or date_retrieved is None or channel_id is None:
                raise ValueError("Video title, date retrieved, or channel ID is None")
            self.logger.info(f"Video title: {video_title}, Channel ID: {channel_id}, Date retrieved: {date_retrieved}")
            channel_table_id = self.channel_info_insert(channel_id, self.db_path)
            VideoManager(self.logger, self.db_path, video_title, channel_table_id, self.video_url, date_retrieved).insert_video()
            return [f"https://www.youtube.com/embed/{self.video_id}"]
        except Exception as e:
            self.logger.error(f"Error processing video: {e}", exc_info=True)
            st.error(f"Error processing video: {e}")
            raise e

class ChannelProcessor(YouTubeInfoFetcher):
    def __init__(self, logger, url, youtube_client, db_path):
        super().__init__(logger, youtube_client)
        self.logger = logger
        self.url = url
        self.youtube_client = youtube_client
        self.db_path = db_path
        self.channel_id = None

    def check_channel(self):
        if 'channel/' in self.url:
            self.channel_id = re.search(r'channel/([^/?]+)', self.url).group(1)
            return self.channel_id
        elif '@' in self.url:
            username = re.search(r'@([^/?]+)', self.url).group(1)
            response = self.youtube_client.search().list(
                q=username,
                type="channel",
                part="id,snippet"
            ).execute()
            return response['items'][0]['id']['channelId']
        elif 'user/' in self.url:
            username = re.search(r'user/([^/?]+)', self.url).group(1)
            response = self.youtube_client.search().list(
                q=username,
                type="channel",
                part="id,snippet"
            ).execute()
            return response['items'][0]['id']['channelId']
        else:
            raise ValueError("Invalid channel URL")

    def get_channel_videos(self, channel_id):
        response = self.youtube_client.search().list(
            part='snippet',
            channelId=channel_id,
            maxResults=5,
            order='date'
        ).execute()

        if 'items' not in response or not response['items']:
            raise ValueError("No channel details found for the given ID")
        
        videos = []
        for item in response['items']:
            video_title = item['snippet']['title']
            video_id = item['id']['videoId']
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            videos.append({
                'title': video_title,
                'url': video_url,
                'id': video_id
            })
        
        return videos

    def process_channel(self):
        channel_id = self.check_channel()
        videos = self.get_channel_videos(channel_id)
        channel_table_id = self.channel_info_insert(channel_id, self.db_path)

        for video in videos:
            video_title = video['title']
            video_url = video['url']
            date_retrieved = datetime.datetime.now()
            VideoManager(self.logger, self.db_path, video_title, channel_table_id, video_url, date_retrieved).insert_video()
        
        return [f"https://www.youtube.com/embed/{video['id']}" for video in videos]

#check URL type and process
class URLProcessor:
    def __init__(self, logger):
        self.logger = logger

    def process_url(self, url, url_type, youtube_client, db_path):
        try:
            if url_type == "video":
                self.logger.info("Processing video URL...")
                return VideoProcessor(self.logger, url, youtube_client, db_path).process_video()
            elif url_type == "channel":
                self.logger.info("Processing channel URL...")
                return ChannelProcessor(self.logger, url, youtube_client, db_path).process_channel()
            else:
                raise ValueError("Invalid URL")
        except Exception as e:
            self.logger.error(f"Error processing URL: {e}", exc_info=True)
            st.error(f"Error processing URL: {e}")
            raise e