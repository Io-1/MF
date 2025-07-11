import os
from dotenv import load_dotenv, find_dotenv
import psycopg2
import datetime
import re
import locale
import sys
from itertools import product
import time
import random

import pyttsx3
from pydub import AudioSegment
import tempfile

from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

load_dotenv(find_dotenv(filename='MF.env'))
locale.setlocale(locale.LC_COLLATE, "lt_LT.UTF-8")
z_dir = os.getenv("z_dir")
opus_dir = os.getenv("opus_dir")

dbname=os.getenv("database")
user=os.getenv("user")
password=os.getenv("password")
host=os.getenv("host")
port=os.getenv("port"


