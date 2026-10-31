import os
import time
from datetime import datetime, timedelta, timezone

import feedparser
import requests
from dotenv import load_dotenv
from google import genai


load_dotenv() #le as chaves do .env

FEEDS = {
    "G1 tecnologia": "https://g1.globo.com/rss/g1/tecnologia/",
    "G1 economia": "https://g1.globo.com/rss/g1/economia/",
}



