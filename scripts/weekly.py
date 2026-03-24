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

silent_gap = 15000 # Time in ms for silent gap between calling words in TTS.

load_dotenv(find_dotenv(filename='MF.env'))
locale.setlocale(locale.LC_COLLATE, "lt_LT.UTF-8")
z_dir = os.getenv("z_dir")
opus_dir = os.getenv("opus_dir")

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
    chunks_path = os.path.join(z_dir, file_name_)
    with open(chunks_path, "w", encoding="utf-8") as file:
        file.write("[[()_Rėpas]]")
        return None
    

conn = psycopg2.connect(
    dbname=os.getenv("database"),
    user=os.getenv("user"),
    password=os.getenv("password"),
    host=os.getenv("host"),
    port=os.getenv("port")
) 

cur = conn.cursor()

select_pattern_morphs_to_cores_query = """
SELECT m.id, mc.core_id, c.morph_id, c.core
    FROM morphs m
    LEFT JOIN morphs_cores mc
    ON m.id = mc.morph_id
    LEFT JOIN cores c
    ON mc.core_id = c.id
    WHERE m.morph ~ '{pattern}'
"""

insert_collection_item = """
INSERT INTO collections ({collection_type}_id)
VALUES (%s)
ON CONFLICT ({collection_type}_id) DO UPDATE
  SET {collection_type}_id = EXCLUDED.{collection_type}_id
RETURNING id;
"""

insert_srs_item = f"""
INSERT INTO SRS (collection_id, collection_name, collection_note)
VALUES (%s, %s, %s)
ON CONFLICT (collection_id) DO NOTHING;
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

insert_into_relations_query = f"""
INSERT INTO relations (m1_id, m2_id, sn)
SELECT m1.id, m2.id, 1
FROM morphs m1
CROSS JOIN morphs m2
WHERE m1.morph = %s
AND m2.morph = %s
AND m1.id < m2.id
ON CONFLICT (m1_id, m2_id)
DO UPDATE SET sn = relations.sn + EXCLUDED.sn;
"""

insert_into_cores_query = f"""
INSERT INTO cores (core, morph_id)
VALUES (%s, %s)
"""

select_morph_id_core_id_query = f"""
SELECT m.id, c.morph_id
FROM morphs m
LEFT JOIN morphs_cores mc
ON m.id = mc.morph_id
LEFT JOIN cores c
ON mc.cores_id = c.id
WHERE m.morph in %s
"""

insert_collection_morph_ids = """
INSERT INTO morphs_{collection_type}s ({collection_type}_id, morph_id)
VALUES (%s, %s)
ON CONFLICT DO NOTHING;
"""

insert_collection_query = """
INSERT INTO {collection_type}s ({collection_type}, note)
VALUES (%s, %s)
ON CONFLICT ({collection_type}) 
DO UPDATE SET {collection_type} = EXCLUDED.{collection_type}
RETURNING id;
"""

insert_morph_to_morphs_query = f"""
INSERT INTO morphs(morph, entered)
VALUES (%s, 1)
ON CONFLICT (morph) DO UPDATE SET entered = morphs.entered + 1
RETURNING id;
"""

select_morphs_cores_query = f"""
SELECT m.id, mc.core_id, c.morph_id, c.core
    FROM morphs m
    LEFT JOIN morphs_cores mc
    ON m.id = mc.morph_id
    LEFT JOIN cores c
    ON mc.core_id = c.id
    WHERE m.morph IN %s
"""

insert_collection_item = """
INSERT INTO collections ({collection_type}_id)
VALUES (%s)
ON CONFLICT ({collection_type}_id) 
DO UPDATE SET {collection_type}_id = EXCLUDED.{collection_type}_id
RETURNING id;
"""

insert_collection_morph_ids = """
INSERT INTO morphs_{collection_type}s ({collection_type}_id, morph_id)
VALUES (%s, %s)
ON CONFLICT DO NOTHING;
"""

insert_srs_item = f"""
INSERT INTO SRS (collection_id, collection_name, collection_note)
VALUES (%s, %s, %s)
ON CONFLICT (collection_id) DO NOTHING;
"""

insert_morph_to_morphs_query = f"""
INSERT INTO morphs (morph, entered)
VALUES (%s, 1)
ON CONFLICT (morph) DO UPDATE SET entered = morphs.entered + 1
RETURNING id;
"""

insert_core_query = f"""
INSERT INTO cores (core, morph_id)
VALUES (%s, %s)
ON CONFLICT (core)
DO NOTHING
"""

conn = psycopg2.connect(
    dbname=os.getenv("database"),
    user=os.getenv("user"),
    password=os.getenv("password"),
    host=os.getenv("host"),
    port=os.getenv("port")
)

cur = conn.cursor()


head_items = read_chunks("galva")
head_chains = list(item for item in head_items if len(item) > 1)
head_links = tuple(morph for item in head_items for morph in item if len(item) == 1)
snappers_items = read_chunks("ešeriai")

chains = head_chains + snappers_items

if input("y to upload current session, any to skip.") == "y" and chains:
    chains = [[re.sub(r"\s", r"", s.lower()) for s in subchain] for subchain in chains]
    chain_relations = tuple(pair for chain in chains for pair in product(chain, repeat=2))
    morphs = tuple((morph,) for item in chains for morph in item)
    link_morphs = tuple(morph for item in chains for morph in item if len(item) == 1)
    special_items = [item[0] for item in morphs if re.search(r"[^a-ząčęėįšųūž]", item[0])]

    if special_items:
        print("Special characters in chains to upload to database found.")
        for item in list(dict.fromkeys(special_items)):
            print(item)
        print("Exiting script until items with special characters are resolved.")
        sys.exit(1)

    cur.executemany(insert_morph_to_morphs_query, morphs)
    cur.executemany(insert_into_relations_query, chain_relations)
    conn.commit()

    empty_file("galva")
    empty_file("ešeriai")

    link_morphs = list(dict.fromkeys(head_links + link_morphs))

    append_words("galva", link_morphs)


    engine = pyttsx3.init()
    engine.setProperty('rate', 140)
    engine.setProperty('voice', 'HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Speech\\Voices\\Tokens\\LIEPA Edvardas')

    audio_final = AudioSegment.empty()
    silence_segment = AudioSegment.silent(duration=silent_gap)

    with tempfile.TemporaryDirectory() as tmpdir:
        temp_files = []
        for i, morph in enumerate(list(dict.fromkeys(morphs))):
            temp_path = os.path.join(tmpdir, f"temp_{i}.wav")
            engine.save_to_file(morph, temp_path)
            temp_files.append(temp_path)
        engine.runAndWait()

        for temp_wav in temp_files:
            segment = AudioSegment.from_wav(temp_wav)
            audio_final += segment + silence_segment

    # Passe en mono 16 kHz
    audio_final = audio_final.set_channels(1).set_frame_rate(16000)

    audio_final_dur = round(len(audio_final) / 60000, 2)

    # ------------------------
    # 2) Export local avec timestamp
    # ------------------------
    now = datetime.datetime.now().strftime("%m%d")
    opus_name = f"MF_{audio_final_dur}_{now}.opus"
    opus_path = os.path.join(opus_dir, opus_name)

    audio_final.export(
        opus_path,
        format="opus",
        parameters=["-c:a", "libopus", "-b:a", "16k"]
    )

    # ------------------------
    # 3) Authentification PyDrive
    # ------------------------
    gauth = GoogleAuth()
    gauth.settings['client_config_file'] = 'client_secrets.json'

    CRED_FILE = 'pydrive_credentials.json'
    gauth.settings['save_credentials'] = True
    gauth.settings['save_credentials_backend'] = 'file'
    gauth.settings['save_credentials_file'] = CRED_FILE

    gauth.LoadCredentialsFile(CRED_FILE)
    if gauth.credentials is None:
        gauth.LocalWebserverAuth()
    elif gauth.access_token_expired:
        gauth.Refresh()
    else:
        gauth.Authorize()
    gauth.SaveCredentialsFile(CRED_FILE)

    drive = GoogleDrive(gauth)

    # ------------------------
    # 4) Upload dans un dossier donné
    # ------------------------

    file_drive = drive.CreateFile({
        'title': opus_name, 
        'mimeType': 'audio/opus',
        'parents': [{'id': '1HN2Qp_0UYIVzKUdJl7GjhEX_915azfu1'}]
    })
    file_drive.SetContentFile(opus_path)
    file_drive.Upload()

if input("y to initiate core updating procedure.") == "y" and chains:
    cur.execute("SELECT morph FROM morphs WHERE id NOT in (SELECT morph_id FROM morphs_cores)")

    morphs_without_cores = tuple(item[0] for item in cur.fetchall())

    cores = []
    morphs_cores = []
    cores_cores = []
    for morph in morphs_without_cores:
        while True:
            core = input(f"{morph} | ")
            if core == "q": break
            elif len(core) < 2: continue
            cores.append((core,))
            morphs_cores.append((morph, core))
            cores_cores.append((core, core))

    cores = tuple(cores)
    morphs_cores = morphs_cores + cores_cores
    cores_cores = tuple(cores_cores)
    morphs_cores = tuple(morphs_cores)

    while True:
        for i, line in enumerate(morphs_cores):
            print(f"{i}.{line}")
        rm_ids = input("")
        rm_ids = tuple(i.strip() for i in rm_ids.split(","))
        if "q" in rm_ids or "" in rm_ids: break
        try:
            rm_ids = [int(x) for x in rm_ids]
        except ValueError:
            continue
        if (rm_ids != ("", ) or rm_ids != ("n", )) and not all(0 <= i <= len(inputs) for i in rm_ids): continue
        inputs = [line for line in morphs_cores if inputs.index(line) not in rm_ids]
        break

    cur.executemany(insert_morph_to_morphs_query, cores)
    conn.commit()

    cur.execute(f"SELECT morph, id FROM morphs WHERE morph IN %s", (cores, ))
    cores_morph_ids = cur.fetchall()

    cur.executemany(insert_into_cores_query, cores_morph_ids)
    conn.commit()

    cur.execute(select_morph_id_core_id_query, (morphs_cores, ))

    morph_ids_core_ids = cur.fetchall()

    collection_type = "core"
    cur.execute(insert_collection_morph_ids, morph_ids_core_ids)
    conn.commit()



if input("y to upload current krill to morphs and clusters, any to skip.") == "y":
    
    inputs = read_chunks("krilius")

    collection_type = "cluster"

    # Process everything in a SINGLE loop to prevent data loss
    for snapper in inputs:
        # 1. Prepare morphs tuple for this batch
        snapper_t = tuple((morph, ) for morph in snapper) 
        
        # 2. Insert Morphs
        cur.executemany(insert_morph_to_morphs_query, snapper_t)
        conn.commit() # Commit the morphs first
        
        # 3. Retrieve IDs for THIS batch immediately
        # We use the morphs we just processed to find their IDs
        cur.execute(select_morphs_cores_query, (tuple(x[0] for x in snapper_t), ))
        morphs_join_cores = cur.fetchall() 
        
        # 4. Insert the Collection (Cluster)
        cur.execute(insert_collection_query.format(collection_type=collection_type), (snapper[0], ""))
        type_id_row = cur.fetchone() 
        
        # Check if cluster insertion was successful (or returned an existing ID)
        if type_id_row:
            type_id = type_id_row[0] # Safely extract the ID integer from the tuple
            
            # 5. Link Morphs to this Cluster
            # Get unique morph IDs from the fetchall result
            current_morph_ids = list(set(item[0] for item in morphs_join_cores))
            
            # Create link pairs: (Cluster_ID, Morph_ID)
            collection_morph_ids = [(type_id, m_id) for m_id in current_morph_ids]
            
            cur.executemany(insert_collection_morph_ids.format(collection_type=collection_type), collection_morph_ids)

            # 6. SRS / Collections Table Insert (The logic I missed!)
            if collection_type not in ("pattern", "cores"):
                # Insert into the main collections table to get the global ID
                cur.execute(insert_collection_item.format(collection_type=collection_type), (type_id, ))
                collection_id_row = cur.fetchone()
                
                if collection_id_row:
                    collection_id = collection_id_row[0] # Safely extract ID
                    # Insert into SRS using the global collection_id and the cluster name (snapper[0])
                    cur.execute(insert_srs_item, (collection_id, snapper[0], ""))
            
            # Commit the links and SRS data for this batch
            conn.commit()

    # Clear the file only after all batches are processed
    empty_file("krilius")
    

if input("y to update current cores to morphs and cores, any to skip.") == "y":
    cores = read_chunks("cores")
    delete_morphs = tuple((item[0],) for item in cores if "delete" in item)

    cur.executemany(f"DELETE FROM morphs WHERE morph = %s", delete_morphs)
    conn.commit()

    cores = [item for item in cores if "delete" not in item]

    to_core_pairs = tuple((item[0], core) for item in cores for core in item[1:])

    new_morphs = tuple((item[1],) for item in to_core_pairs)

    cur.executemany(insert_morph_to_morphs_query, new_morphs)

    conn.commit()

    morphs = tuple(item[0] for item in to_core_pairs)

    cur.execute(f'SELECT morph, id FROM morphs WHERE morph in %s', (morphs,))
    morph_morph_id = cur.fetchall()

    morph_to_morph_id = {item[0]: item[1] for item in morph_morph_id}

    cores = tuple(item[1] for item in to_core_pairs)

    cur.execute(f"SELECT morph, id FROM morphs WHERE morph in %s", (tuple(core for core in cores),))
    cores_morph_ids = tuple(cur.fetchall())

    cur.executemany(insert_core_query, cores_morph_ids)

    cur.execute(f'SELECT core, id FROM cores WHERE core in %s', (cores,))
    core_core_id = cur.fetchall()

    core_to_core_id = {item[0]: item[1] for item in core_core_id}

    the_thing = tuple((morph_to_morph_id[item[0]], core_to_core_id[item[1]]) for item in to_core_pairs)

    cur.executemany(f'INSERT INTO morphs_cores (morph_id, core_id) VALUES (%s, %s) ON CONFLICT DO NOTHING', the_thing)
    conn.commit()

    core_thing = tuple((core_to_core_id[core], core_to_core_id[core]) for core in core_to_core_id)

    cur.execute(f"SELECT morph_id, id FROM cores")
    core_core = cur.fetchall()

    cur.executemany(f'INSERT INTO morphs_cores (morph_id, core_id) VALUES (%s, %s) ON CONFLICT DO NOTHING', core_core)
    conn.commit()

    cur.execute("SELECT morph FROM MORPHS WHERE id NOT in (SELECT morph_id FROM morphs_cores)")
    no_core_morphs = sorted([morph[0] for morph in cur.fetchall()])

    empty_file("cores")
    append_words("cores", no_core_morphs)

collection_type = "pattern"
cur.execute(f"SELECT id, pattern FROM patterns")
pattern_items = cur.fetchall()

for item in pattern_items:
    cur.execute(select_pattern_morphs_to_cores_query.format(pattern = item[1]))
    morphs_join_cores = cur.fetchall()
    morph_ids = tuple(dict.fromkeys(tuple(line[2] if line[3] is not None and bool(re.search(item[1], line[3])) else line[0] for line in morphs_join_cores)))
    morph_ids_rm = tuple(dict.fromkeys(line[0] for line in morphs_join_cores if line[3] is not None and bool(re.search(item[1], line[3])) and line[0] != line[2]))
    morph_ids = tuple(m_id for m_id in morph_ids if m_id not in morph_ids_rm)

    collection_morphs_rm = tuple((item[0], morph_id) for morph_id in morph_ids_rm)
    cur.executemany(f"DELETE FROM morphs_patterns WHERE pattern_id = %s AND morph_id = %s", collection_morphs_rm)
    conn.commit()
    collection_morph_ids = tuple((item[0], morph_id) for morph_id in morph_ids)
    cur.executemany(insert_collection_morph_ids.format(collection_type = collection_type), collection_morph_ids)
    cur.execute(insert_collection_item.format(collection_type = collection_type), (item[0], ))
    collection_id = cur.fetchone()
    cur.execute(insert_srs_item, (collection_id, item[1], None))
    conn.commit()

for item in pattern_items:
    cur.execute(f"SELECT id FROM morphs WHERE morph ~ %s", (item[1], ))
    collection = tuple((item[0], morph_id[0]) for morph_id in cur.fetchall())
    cur.executemany(f"INSERT INTO morphs_patterns (pattern_id, morph_id) VALUES (%s, %s) ON CONFLICT (pattern_id, morph_id) DO NOTHING", collection)
    conn.commit()
