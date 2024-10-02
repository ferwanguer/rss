""" This module defines the main classes and methods that will be executed in main.py.
source.py is mainly for testing.
"""
#pylint: disable=E0401,E0611
import asyncio
import json
import logging
import os
from datetime import datetime
from typing import List, Optional

import colorlog
import feedparser
import requests
from requests_oauthlib import OAuth1Session
from telegram import Bot
from utils import download_latest_blob, get_secret, upload_blob

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
# Classes
#-------------------------------------------------------------------------------------

class Newspaper:                                                            #pylint: disable=R0902
    """Defining class, it has the name, rss link and editorial
    """
    bucket_name = "rss-feed_opinion"
    def __init__(self, name: str, rss_link: str, editorial:str, authors: Optional[list] = None):
        self.name = name
        self.formated_name = self.name.lower().replace(" ", "")
        self.rss_link = rss_link
        self.editorial = editorial
        self.path = f"{self.formated_name}/{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.local_path = "/tmp/" + self.path
        #Were the blob is downloaded locally
        self.latest_feed_path_from_bucket = "/tmp/" +  f'{self.formated_name}/latest_feed'
        self.authors = authors or []
        self.telegram_token = get_secret('telegram_token')

        # We download the new feed.xml
        response = requests.get(
            self.rss_link,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML'\
                    ', like Gecko) Chrome/85.0.4183.121 Safari/537.36'
            },
            timeout=180
        )

        if response.status_code == 200:
            logger.info("Correctly downloaded RSS from %s", self.name)

            # Saving the resulting text into a file
            os.makedirs(os.path.dirname(f'{self.local_path}.xml'), exist_ok=True)
            with open(f'{self.local_path}.xml', 'w', encoding='utf-8') as file:
                file.write(response.text)

            self.feed: feedparser.FeedParserDict = feedparser.parse(f'{self.local_path}.xml')
        else:
            logger.error("Coud not retrieve %s RSS", self.name)


    def __str__(self):
        return f"Newspaper(name={self.name}, rss_link={self.rss_link}, editorial={self.editorial})"

    def compare_feeds(self):
        """ Compare the most recent feed with the latest one saved (if it exists already) """

        old_feed_path = download_latest_blob(
            self.bucket_name,
            folder_prefix=self.formated_name,
            local_blob_name=f'{self.latest_feed_path_from_bucket}.xml'
        )
        old_feed: feedparser.FeedParserDict = feedparser.parse(old_feed_path)

        # Extract unique identifiers
        old_entries_links = set(entry.link for entry in old_feed.entries)

        # Retrieve the new entries
        new_entries = [
            entry for entry in self.feed.entries if entry.link not in old_entries_links
        ]

        if new_entries:

            logger.info("%s has new entries", self.name)
            upload_blob(
                self.bucket_name,
                bucket_blob_name=f'{self.path}',
                local_blob_name=f'{self.local_path}.xml'
            )

            for entry in new_entries:
                if self.format_name() == "vozpopuli" and entry.author in self.authors:
                    self.post_telegram(entry)

                if self.format_name() !="vozpopuli":
                    self.post_telegram(entry)

                if entry.author in self.authors and self.editorial == "right":
                    self.create_tweet(entry)

            logger.info("Finished tweeting, updating RSS file of %s", self.name)

            # Optionally process new_entries here
            return new_entries  # If you need to use them elsewhere
        logger.info("%s no news", self.name)
        return None


    def create_text(self, entry):
        """ Create text for publication """
        if self.formated_name != "elabc":
            return f'Nuevo artículo de {entry.author} en {self.name}: {entry.title}\n {entry.link}'
        return f'Nuevo artículo de {entry.author} en {self.name}: {entry.title}\n {entry.link}'\
                f'\n\n {entry.description}'


    def create_tweet(self, entry):
        """ CReate a tweet to publish """
        text = f'Nuevo artículo de {entry.author} en {self.name}: {entry.title}\n {entry.link}'

        payload = {"text": text}

        if self.editorial == "right":
            access_token = get_secret("oauth_token")
            access_token_secret = get_secret("oauth_token_secret")
            consumer_key = get_secret("consumer_key")
            consumer_secret = get_secret("consumer_secret")
        else:
            logger.warning("LEFT TWEETS NOT IMPLEMENTED YET")
            return
            # access_token = get_secret("oauth_token")
            # access_token_secret = get_secret("oauth_token_secret")
            # consumer_key = get_secret("consumer_key")
            # consumer_secret = get_secret("consumer_secret")

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
                raise ConnectionRefusedError(
                    f"Request returned an error: {response.status_code} {response.text}"
                )
            logger.info("Successful tweet of newspaper %s ", self.name)
        except Exception as e:                                              #pylint: disable=W0718
            logger.error("FAILED TO POST TWEET: %s", e)
        return

    def post_telegram(self, entry):
        """ Send message to telegram """
        bot = Bot(token=self.telegram_token)
        chat_id = "@opderecha" if self.editorial =="right" else "@opizquierda"
        # Send a message
        try:
            message = asyncio.run(bot.send_message(chat_id=chat_id, text=self.create_text(entry)))
            if message.message_id:
                logger.info("TELEGRAM POSTED. Message ID: %s", message.message_id)
        except Exception as e:                                              #pylint: disable=W0718
            logger.error("TELEGRAM FAILED. %s", e)


#-------------------------------------------------------------------------------------
# Functions
#-------------------------------------------------------------------------------------

def load_newspapers_from_json(file_path: str) -> List[Newspaper]:
    """ This method loads the json with the newspaper attributes and outputs a list of Newspapers.
    """
    with open(file_path, 'r', encoding="utf-8") as file:
        newspapers_data = json.load(file)
        newspapers = [Newspaper(**data) for data in newspapers_data]
    return newspapers
