import os
import sys
import locale
import re
from dotenv import load_dotenv, find_dotenv
import psycopg2

load_dotenv(find_dotenv(filename='MF.env'))
locale.setlocale(locale.LC_COLLATE, "lt_LT.UTF-8")
z_dir = os.getenv("z_dir")
opus_dir = os.getenv("opus_dir")

conn = psycopg2.connect(
    dbname=os.getenv("database"),
    user=os.getenv("user"),
    password=os.getenv("password"),
    host=os.getenv("host"),
    port=os.getenv("port")
)

cur = conn.cursor()

def read_chunks(file_name):
    file_name = f"{file_name}.md"
    chunks_path = os.path.join(z_dir, file_name)
    chunks = []
    with open(chunks_path, "r", encoding="utf-8") as file:
        chunks += [line.strip().split(", ") for line in file if not bool(re.match(r".*(?:\(\)_|---|blokas).*", line.strip())) and line.strip()]
        return chunks

def append_words(file_name, words):
    file_path = os.path.join(z_dir, f"{file_name}.md")
    with open(file_path
    , "a", encoding="utf-8") as file:
        stringed_words = "\n\n".join(words)
        if stringed_words: stringed_words = "\n\n" + stringed_words
        file.write(stringed_words)
    return

def empty_file(file_name):
    file_name_ = f"{file_name}.md"
    backup_name = f"{file_name}_backup.md"
    chunks_path = os.path.join(z_dir, file_name_)
    backup_path = os.path.join(z_dir, backup_name)
    with open(chunks_path, "r", encoding="utf-8") as file:
        with open(backup_path, "w", encoding="utf-8") as backup:
            backup.write(file.read())
    with open(chunks_path, "w", encoding="utf-8") as file:
        file.write("[[()_Rėpas]]")
        return None
    


print(read_chunks("ešeriai"))
    
cur.execute(f"SELECT morph FROM morphs WHERE id NOT IN (SELECT DISTINCT morph_id FROM morphs_cores) ORDER BY morph")

morphs = [item[0] for item in cur.fetchall()]


append_words("cores", morphs)

    
# append_words