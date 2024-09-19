"""This module defines the main classes and methods that will be executed in main.py.
source.py is mainly for testing.
"""

import asyncio
from datetime import datetime
import json
import os
import feedparser
import requests
from requests_oauthlib import OAuth1Session
from utils import download_latest_blob, get_secret, upload_blob
import logging
import colorlog
import tweepy
from telegram import Bot

#-------------------------------------------------------------------------------------
# Basic Logging configuration
#-------------------------------------------------------------------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create a handler
handler = logging.StreamHandler()

# Define color format
formatter = colorlog.ColoredFormatter(
    '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    log_colors={
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'bold_red',
    }
)

# Add the formatter to the handler
handler.setFormatter(formatter)

# Add the handler to the logger
logger.addHandler(handler)

#-------------------------------------------------------------------------------------
# Functions
#-------------------------------------------------------------------------------------


def load_newspapers_from_json(file_path: str):
    """ This method loads the json with the newspaper attributes and outputs a list of Newspapers.
    """
    with open(file_path, 'r', encoding="utf-8") as file:
        newspapers_data = json.load(file)
        newspapers = [Newspaper(**data) for data in newspapers_data]
    return newspapers

#-------------------------------------------------------------------------------------
# Classes
#-------------------------------------------------------------------------------------

class Newspaper:
    """Defining class, it has the name, rss link and editorial
    """
    bucket_name = "rss-feed_opinion"
    def __init__(self, name: str, rss_link: str, editorial):
        self.name = name
        self.formated_name = self.format_name()
        self.rss_link = rss_link
        self.editorial = editorial
        self.path = f"{self.formated_name}/{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.local_path = "/tmp/" + self.path 
        self.latest_feed_path_from_bucket = "/tmp/" +  f'{self.formated_name}/latest_feed'
        self.telegram_chat_id = get_secret('telegram_chat_id')
        self.telegram_token = get_secret('telegram_token')

        # We download the new feed.xml

        response = requests.get(self.rss_link, headers={
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.121 Safari/537.36'})

        if response.status_code == 200:
            logger.info(f"Correctly downloaded RSS from {self.name}")
            # Saving the resulting text into a file
            os.makedirs(os.path.dirname(f'{self.local_path}.xml'), exist_ok=True)
            with open(f'{self.local_path}.xml', 'w', encoding='utf-8') as file:
                file.write(response.text)
            self.feed = feedparser.parse(f'{self.local_path}.xml')  
        else: 
            logger.error(f"Coud not retrieve {self.name} RSS")


    def __str__(self):
        """Nothing to comment here
        """
        return f"Newspaper(name={self.name}, rss_link={self.rss_link}, editorial={self.editorial})"
    
    def format_name(self):
        """Formats the name and adds the executiontime. Useful to save the rss.
        """
        transformed_string = self.name.lower().replace(" ", "")

        return transformed_string

    def compare_feeds(self):
        """Compare the most recent feed with the latest one saved (if it exists already)"""

        old_feed_path = download_latest_blob(
            self.bucket_name,
            folder_prefix=self.formated_name,
            local_blob_name=f'{self.latest_feed_path_from_bucket}.xml'
        )
        logger.warning(old_feed_path)
        old_feed = feedparser.parse(old_feed_path)

        # Extract unique identifiers
        entries_links = set(entry.link for entry in self.feed.entries)
        old_entries_links = set(entry.link for entry in old_feed.entries)

        intersection = entries_links.intersection(old_entries_links)
        # Identify new entries
        new_entries_links = entries_links - intersection

        # Retrieve the new entries
        new_entries = [
            entry for entry in self.feed.entries if entry.link in new_entries_links
        ]
        if new_entries:

            logger.info(f"{self.name} has new entries")
            for entry in new_entries:
                self.create_tweet(entry)
                self.post_telegram(entry)

            logger.info("Finished tweeting, updating RSS file of {self.name}")    

            upload_blob(self.bucket_name,bucket_blob_name=f'{self.path}', local_blob_name=f'{self.local_path}.xml')
            
            logger.info("Adding new entries")
            # Optionally process new_entries here
            return new_entries  # If you need to use them elsewhere
        else:
            logger.info(f"{self.name} no news")

    def create_text(self, entry):
        if entry.author:
            return f'Nuevo artículo de {entry.author} en {self.name}: {entry.title}\n {entry.link}'
        if entry.creator:
            f'Nuevo artículo de {entry.creator} en {self.name}: {entry.title}\n {entry.link}'
    
    
    def create_tweet(self, entry):
        payload = {"text": self.create_text(entry)}

        access_token = get_secret("oauth_token")
        access_token_secret = get_secret("oauth_token_secret")
        consumer_key = get_secret("consumer_key")
        consumer_secret = get_secret("consumer_secret")

        try:
            # Make the request
            oauth = OAuth1Session(
                consumer_key,
                client_secret=consumer_secret,
                resource_owner_key=access_token,
                resource_owner_secret=access_token_secret,
            )

            # Making the request
            response = oauth.post(
                "https://api.twitter.com/2/tweets",
                json=payload,
            )

            if response.status_code != 201:
                raise Exception(
                    "Request returned an error: {} {}".format(response.status_code, response.text)
                    )
            else:      
                logger.info(f"Successful tweet of newspaper {self.name} ")
        except Exception as e:
             logger.error(f"FAILED TO POST TWEET: {e}")

    def post_telegram(self, entry):

        bot = Bot(token=self.telegram_token)

        # Send a message
        try:
            message = asyncio.run(bot.send_message(chat_id="@opderecha", text=self.create_text(entry)))
            if message.message_id:
                logger.info(f"TELEGRAM POSTED. Message ID: {message.message_id}")
        except Exception as e:
            logger.error(f"TELEGRAM FAILED.")










