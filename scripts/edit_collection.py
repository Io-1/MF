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

select_pattern_morphs_to_cores_query = """
SELECT m.id, mc.core_id, c.morph_id, c.core
    FROM morphs m
    LEFT JOIN morphs_cores mc
    ON m.id = mc.morph_id
    LEFT JOIN cores c
    ON mc.core_id = c.id
    WHERE m.morph ~ '{pattern}'
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

select_collection_morphs = """
SELECT m.morph
    FROM morphs m
    JOIN morphs_{collection_type}s mc
    ON m.id = mc.morph_id
    WHERE mc.{collection_type}_id = %s
"""

insert_collection_query = """
INSERT INTO {collection_type}s ({collection_type}, note)
VALUES (%s, %s)
ON CONFLICT DO NOTHING
RETURNING id;
"""

insert_collection_morph_ids = """
INSERT INTO morphs_{collection_type}s ({collection_type}_id, morph_id)
VALUES (%s, %s)
ON CONFLICT DO NOTHING;
"""

insert_collection_item = """
INSERT INTO collections ({collection_type}_id)
VALUES (%s)
RETURNING id;
"""

insert_srs_item = f"""
INSERT INTO SRS (collection_id, collection_name, collection_note)
VALUES (%s, %s, %s);
"""

insert_morph_to_morphs_query = f"""
INSERT INTO morphs(morph, entered)
VALUES (%s, 1)
ON CONFLICT (morph) DO UPDATE SET entered = morphs.entered + 1
RETURNING id;
"""

delete_collection_morph_ids = """
DELETE FROM morphs_{collection_type}s 
WHERE {collection_type}_id = %s
AND morph_id = %s;
"""
while True:
    mode = input("Edit/Add | ").lower()

    if mode == "edit":
        while True:
            collection_type = input("Collection type | ").lower()
            if collection_type == "q": break
            cur.execute(f"SELECT id, {collection_type}, note FROM {collection_type}s ORDER BY id")
            for collection_id, name, note in cur.fetchall():
                print(f"{collection_id}: {name} | {note}")
            selection = input("")
            if selection == "q": break
            cur.execute(select_collection_morphs.format(collection_type=collection_type), (int(selection), ))
            collection = [row[0] for row in cur.fetchall()]
            print("---")
            for id, morph in enumerate(collection):
                print(f"{morph}")

            new_inputs = []
            while True:
                morph = input()
                if morph in ("n", "q"): break
                elif len(morph) < 2: continue
                new_inputs.append((morph, ))
            if morph == "q": break
            new_inputs = tuple(new_inputs)

            if new_inputs:
                cur.executemany(insert_morph_to_morphs_query, new_inputs)
                conn.commit()
                cur.execute(select_morphs_cores_query, (new_inputs, ))
            morphs_join_cores = cur.fetchall()
            add_ids = tuple((int(selection), item[0] ) for item in morphs_join_cores)


            cur.executemany(insert_collection_morph_ids.format(collection_type=collection_type), add_ids)
            conn.commit()

            cur.execute(select_collection_morphs.format(collection_type=collection_type), (int(selection), ))
            collection = [row[0] for row in cur.fetchall()]

            while True:
                for id, morph in enumerate(collection):
                    print(f"{id}. {morph}")
                rm_ids = input("")
                if rm_ids == "q": break
                rm_ids = tuple(i.strip() for i in rm_ids.split(","))
                try:
                    rm_ids = [int(x) for x in rm_ids]
                except ValueError:
                    continue
                if (rm_ids != ("", ) or rm_ids != ("n", )) and not all(0 <= i <= len(collection) for i in rm_ids): continue
                rm_morphs = tuple((collection[rm_id], ) for rm_id in rm_ids)
                break
            if rm_ids == "q": continue
            cur.execute(select_morphs_cores_query, (rm_morphs, ))
            morphs_join_cores = cur.fetchall()
            rm_ids = tuple((int(selection), item[0]) for item in morphs_join_cores)
            cur.executemany(delete_collection_morph_ids.format(collection_type=collection_type), rm_ids)
            conn.commit()

    elif mode == "add":
        while True:
            collection_type = input("Collection type | ").lower()
            if collection_type == "q": break
            elif collection_type not in ("cluster", "theme", "pattern", "cores"): continue

            name = input( f"{collection_type.capitalize()} | ")
            if name == "q": break
            elif len(name) < 2: continue

            note = input(f"Note | ")
            if note == "q": break
            elif note == "n": continue



            print("---")

            inputs = []

            if collection_type == "pattern":
                cur.execute(select_pattern_morphs_to_cores_query.format(pattern = name))
                morphs_join_cores = cur.fetchall()
                morph_ids = tuple(dict.fromkeys(tuple(item[2] if item[3] is not None and bool(re.search(name, item[3])) else item[0] for item in morphs_join_cores)))
                morph_ids_rm = tuple(dict.fromkeys(item[1] for item in morphs_join_cores if item[3] is not None and bool(re.search(name, item[3])) and item[0] != item[2]))
                morph_ids = tuple(m_id for m_id in morph_ids if m_id not in morph_ids_rm)
            else: 
                while True:
                    morph = input()
                    if morph in ("q", "n"): break
                    elif len(morph) < 2: continue

                    inputs.append(morph)
                if morph == "q": continue

                while True:
                    for i, morph in enumerate(inputs):
                        print(f"{i}.{morph}")
                    rm_ids = input("")
                    rm_ids = tuple(i.strip() for i in rm_ids.split(","))
                    if "q" in rm_ids or "" in rm_ids: break
                    try:
                        rm_ids = [int(x) for x in rm_ids]
                    except ValueError:
                        continue
                    if (rm_ids != ("", ) or rm_ids != ("n", )) and not all(0 <= i <= len(inputs) for i in rm_ids): continue
                    inputs = [morph.lower() for morph in inputs if inputs.index(morph) not in rm_ids]
                    break
                
                if "q" in rm_ids: continue

                inputs = tuple((item, ) for item in inputs)

                cur.executemany(insert_morph_to_morphs_query, inputs)
                conn.commit()

                cur.execute(select_morphs_cores_query, (inputs, ))
                morphs_join_cores = cur.fetchall()

            if collection_type == "pattern": morph_ids = tuple(dict.fromkeys(tuple(item[2] if item[3] is not None and bool(re.search(name, item[3])) else item[0] for item in morphs_join_cores)))
            else: morph_ids = tuple(dict.fromkeys(tuple(item[0] for item in morphs_join_cores)))
                
            
            cur.execute(insert_collection_query.format(collection_type = collection_type), (name, note))
            type_id = cur.fetchone()
            collection_morph_ids = tuple((type_id, morph_id) for morph_id in morph_ids)
            cur.executemany(insert_collection_morph_ids.format(collection_type = collection_type), collection_morph_ids)
            if collection_type not in ("pattern", "cores"):
                cur.execute(insert_collection_item.format(collection_type = collection_type), (type_id, ))
                collection_id = cur.fetchone()
                cur.execute(insert_srs_item, (collection_id, name, note))
                conn.commit()

    if mode == "q": break
    continue
    

    
    







