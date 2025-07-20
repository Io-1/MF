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

alpha = 0.065 # rate for rates of morphs_clusters values for sliding averages. The bigger, the more missed words are accented

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
    

select_due_query = f"""
SELECT *
FROM srs
WHERE (due_date <= CURRENT_DATE) AND active IS TRUE;
"""

select_morphs_query = """
SELECT m.id, m.morph, c.id, c.rate
FROM morphs m
LEFT JOIN morphs_cores mc
ON m.id = mc.morph_id
LEFT JOIN cores c
ON mc.core_id = c.id
WHERE m.id IN
(SELECT morph_id FROM morphs_{collection_type}s WHERE {collection_type}_id = %s);
"""

select_morphs_core_ids_rates_query = f"""
SELECT mc.morph_id, mc.core_id, c.rate
FROM morphs_cores mc
LEFT JOIN cores c
ON mc.core_id = c.id
WHERE mc.morph_id IN %s;
"""

update_srs_query = f"""
UPDATE srs
SET (reps, fails, ease, interval, due_date, reviewed_date) = (%s, %s, %s, %s, %s, %s)
WHERE id = %s;
"""

update_cores_rates_query = f"""
UPDATE cores
SET rate = %s
WHERE id = %s
"""

select_collection_query = f"""
SELECT *
FROM collections
WHERE id = %s;
"""

select_morph_core_family_query = f"""
SELECT m2.id, m2.morph, m1.id, m1.morph, c.id, c.rate
FROM morphs m1
LEFT JOIN morphs_cores mc1
ON m1.id = mc1.morph_id
LEFT JOIN morphs_cores mc2
ON mc1.core_id = mc2.core_id
LEFT JOIN morphs m2
ON mc2.morph_id = m2.id
LEFT JOIN cores c
ON mc2.core_id = c.id
WHERE m1.id in %s
"""

select_morph_core_ids_query = f"""
SELECT mc.core_id, c.rate
FROM morphs m
LEFT JOIN morphs_cores mc
ON m.id = mc.morph_id
LEFT JOIN cores c
ON mc.core_id = c.id
WHERE m.morph IN %s;
"""

insert_morph_to_morphs_query = f"""
INSERT INTO morphs(morph, entered)
VALUES (%s, 1)
ON CONFLICT (morph) DO UPDATE SET entered = morphs.entered + 1
RETURNING id;
"""

insert_into_sessions_query = f"""
INSERT INTO sessions (note)
VALUES (%s)
returning id;
"""

insert_into_sessions_morphs_query = f"""
INSERT INTO sessions_morphs (session_id, morph)
VALUES (%s, %s)
"""

insert_into_external_relations_query = f"""
INSERT INTO external_relations (m1_id, m2_id, n)
SELECT m1.id, m2.id, 1
FROM morphs m1
CROSS JOIN morphs m2
WHERE m1.morph = %s
AND m2.morph = %s
AND m1.id < m2.id
ON CONFLICT (m1_id, m2_id)
DO UPDATE SET w = external_relations.n + EXCLUDED.n;
"""



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

# SRS

input("Press any key to initiate SRS.")
print("---\nStarting clusters SRS.")

all_run_morphs = []

while True:
    cur.execute(select_due_query)
    srs_data = cur.fetchall()

    for i, item in enumerate(srs_data):
        
        card = item[0]
        collection_id = item[1]
        name = item[2]
        reps = item[5]
        fails = item[6]
        ease = item[7]
        interval = item[8]
        due = item[9]
        reviewed = item[10]
        created = item[11]

        cur.execute(select_collection_query, (collection_id, ))
        collection = cur.fetchall()[0][1:]

        keys = ["pattern", "cluster", "theme", "core"]
        collection_type_dict = dict(zip(keys, collection))
        collection_type, collection_type_id = next(((k, v) for k, v in collection_type_dict.items() if v is not None), None)

        cur.execute(f"""SELECT {collection_type}, note FROM {collection_type}s WHERE id = %s""", (collection_type_id, ))
        collection_line = cur.fetchone()
        collection_name = collection_line[0]
        collection_note = collection_line[1]

        cur.execute(select_morphs_query.format(collection_type = collection_type), (collection_type_id, ))
        collection_items = tuple(dict.fromkeys(tuple(item if item[3] is not None else (item[0], item[1], item[3], 0.7) for item in cur.fetchall())))
        grouped_collection_morph_to_core_and_rate = dict()
        for morph_id, morph, core_id, rate in collection_items:
            if morph not in grouped_collection_morph_to_core_and_rate: grouped_collection_morph_to_core_and_rate[morph] = []
            grouped_collection_morph_to_core_and_rate[morph].append((core_id, rate))
        collection_morph_to_core_and_rate = {morph: tuple(core_and_rate) for morph, core_and_rate in grouped_collection_morph_to_core_and_rate.items()}
        collection_morph_ids = tuple(item[0] for item in collection_items)
        collection_core_ids = tuple(dict.fromkeys(tuple(item[2] for item in collection_items)))
        collection_core_ids_to_rates = dict(zip((item[2] for item in collection_items if item[2] is not None), (item[3] for item in collection_items if item[2] is not None)))

        cur.execute(select_morph_core_family_query, (collection_morph_ids, ))
        collection_morph_core_families_with_orphans = tuple(dict.fromkeys(cur.fetchall()))
        collection_morph_core_families = tuple(dict.fromkeys(tuple((item[0], item[1], item[4], item[5]) if item[0] is not None else (item[2], item[3], item[4], item[5]) if item[5] is not None else (item[2], item[3], item[4], 0.7) for item in collection_morph_core_families_with_orphans)))

        grouped_collection_core_family_morph_to_core_and_rate = dict()
        for morph_id, morph, core_id, rate in collection_morph_core_families:
            if morph not in grouped_collection_core_family_morph_to_core_and_rate: grouped_collection_core_family_morph_to_core_and_rate[morph] = []
            grouped_collection_core_family_morph_to_core_and_rate[morph].append((core_id, rate))
        collection_core_family_morph_to_core_and_rate = {morph: tuple(core_and_rate) for morph, core_and_rate in grouped_collection_core_family_morph_to_core_and_rate.items()}

        core_family_morph_to_rate = dict(zip((item[1] for item in collection_morph_core_families), (item[3] for item in collection_morph_core_families)))

        
        collection_morphs = tuple(dict.fromkeys(tuple(item[1] for item in collection_items)))

        input(f"---\n{collection_type} | {collection_name}{f" | {collection_note}" * (collection_note is not None)}\n---")

        time_start = time.perf_counter()

        inputs = []
        while True:
            input_morph = input("")
            if input_morph in ("n", "q"): break
            elif input_morph == "p": print(f"--- {tuple(morph for morph in collection_morphs if morph not in inputs)}")
            elif input_morph == "z": input(f"--- Paused")
            elif len(input_morph) < 2: continue
            else: inputs.append(input_morph)

        inputs = tuple(dict.fromkeys(inputs))
        duration = int(time.perf_counter() - time_start)

        if inputs:
            cur.execute(select_morph_core_ids_query, (inputs, ))
            input_core_ids_rates = cur.fetchall()
        else: input_core_ids_rates = tuple()
        input_core_ids_rates = tuple(item for item in input_core_ids_rates if (item[0] is not None) and (item[0] in collection_core_ids))
        input_core_id_to_rate = dict(zip((item[0] for item in input_core_ids_rates), (item[1] for item in input_core_ids_rates)))


        
        action = input("---\nq to quit, n to skip.")

        if action == "q": break
        elif action == "n": continue

        correct_sum = sum(rate for core_id, rate in input_core_id_to_rate.items() if core_id in collection_core_ids_to_rates)
        total_sum = max(sum(rate for core_id, rate in collection_core_ids_to_rates.items()), 0.0001)
        quality = 5 * min((correct_sum / total_sum), 1)
        print("---")
        print(tuple(morph for morph in collection_morphs if morph not in inputs))
        print(quality)
        reps += 1
        if quality < 3.5:
            fails += 1
            interval = 1
        elif quality < 2: interval = 0.5
        else: interval = int(max(interval, 1) * ease)
        ease = round( (ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))) , 2)
        print(ease)
        if ease < 0.8:
            ease = 0.8
        reviewed = datetime.date.today()
        due = reviewed + datetime.timedelta(days = int(interval * ease))
        print(due)
        srs_card_updated = (reps, fails, ease, interval, due, reviewed, card)
        cur.execute(update_srs_query, srs_card_updated)
        conn.commit()

        updated_rate_core_id = tuple( (max(alpha * (core_id not in input_core_id_to_rate) + (1 - alpha) * (rate), 0.2), core_id) for core_id, rate in collection_core_ids_to_rates.items())

        cur.executemany(update_cores_rates_query, updated_rate_core_id)
        conn.commit()

        new_collection_morphs = (f"{card}, {morph}" for morph in inputs if morph not in collection_morphs)

        append_words("krilius", new_collection_morphs)

    if not srs_data or action == 'q': break

        
