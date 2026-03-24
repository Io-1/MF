import os
import sys
import locale
import re
from dotenv import load_dotenv, find_dotenv
import psycopg2

import pandas as pd


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

def append_words(file_name, words):
    file_path = os.path.join(z_dir, f"{file_name}.md")
    with open(file_path
    , "a", encoding="utf-8") as file:
        stringed_words = ", ".join(words)
        if stringed_words: stringed_words = "\n\n" + stringed_words
        file.write(stringed_words)
    return

select_random_morph_query = """
SELECT *
FROM morphs
ORDER BY RANDOM() LIMIT 1;
"""

select_all_patterns_morphs = """
SELECT p.pattern, m.morph
FROM patterns p
    LEFT JOIN morphs_patterns mp
        ON p.id = mp.pattern_id
    LEFT JOIN morphs m
        ON mp.morph_id = m.id
WHERE %s ~ p.pattern
"""

select_all_pattern_morphs = """
SELECT pattern_id, morph_id, morph
FROM morphs_patterns mp
    LEFT JOIN morphs m
    ON mp.morph_id = m.id
"""

select_clusters_of_word_query = """
SELECT c.cluster, m.morph
FROM clusters c
    LEFT JOIN morphs_clusters mc
        ON c.id = mc.cluster_id
    LEFT JOIN morphs m
        ON mc.morph_id = m.id
WHERE cluster_id in (SELECT cluster_id FROM morphs_clusters WHERE morph_id = %s)
"""

select_themes_of_word_query = """
SELECT mt.theme_id, m.morph
FROM themes t
    LEFT JOIN morphs_themes mt
        ON t.id = mt.theme_id
    LEFT JOIN morphs m
        ON mt.morph_id = m.id
WHERE theme_id in (SELECT theme_id FROM morphs_themes WHERE morph_id = %s)
"""

select_relations_of_word_query = """
SELECT *
FROM relations
WHERE m1_id = %s OR m2_id = %s
"""

while True:
    while True:
        cur.execute(select_random_morph_query)
        morph = cur.fetchall()[0]

        cur.execute(select_all_patterns_morphs, (morph[1],))
        patterns_morphs = cur.fetchall()

        cur.execute(select_clusters_of_word_query, (morph[0],))
        clusters = cur.fetchall()

        cur.execute(select_themes_of_word_query, (morph[0],))
        themes = cur.fetchall()
        break
        if clusters:
            break

    pn_series = pd.DataFrame(data=patterns_morphs, columns=["pattern", "morph"]).groupby("morph").size().rename("pn")
    tn_series = pd.DataFrame(data=themes, columns=["theme", "morph"]).groupby("morph").size().rename("tn")
    cn_series = pd.DataFrame(data=clusters, columns=["cluster", "morph"]).groupby("morph").size().rename("cn")

    summary_df = pd.concat([pn_series, cn_series, tn_series], axis=1).fillna(0).astype(int)

    # Assuming 'morph_name' is your target word (the variable x)
    # and 'summary_df' is the dataframe you just created with columns [pn, cn, tn]

    target_morph = morph[1]  # The center of your star

    rows = []

    # reset_index() so 'morph' becomes a column we can read
    for index_morph, data in summary_df.iterrows():
        
        # Skip self-loop if the target word is in the summary
        if index_morph == target_morph:
            continue

        # Extract counts
        pn = int(data['pn'])
        tn = int(data['tn'])
        cn = int(data['cn'])
        sn = 0

        if (pn + tn + cn + sn) > 0:
            # Format: (Source, Target, sn, tn, pn, cn)
            rows.append((target_morph, index_morph, sn, tn, pn, cn))


    initiation = input(f"---\n{target_morph} | \n---")

    if initiation == "q":
        break


    inputs = []
    printed_inputs = []
    did_print = False
    while True:
        input_morph = input("")
        if input_morph in ("n", "q"): break
        elif input_morph == "p":
            print(f"--- {tuple(item[1] for item in patterns_morphs if item[1] not in inputs)}")
            print(f"--- {tuple(item[1] for item in clusters if item[1] not in inputs)}")
            print(f"--- {tuple(item[1] for item in themes if item[1] not in inputs)}")
            did_print = True
        elif input_morph == "z": input(f"--- Paused")
        elif len(input_morph) < 2: continue
        else:
            inputs.append(input_morph)
            if did_print:
                printed_inputs.append(input_morph)  

    # inputs = tuple(dict.fromkeys(x for x in inputs if x not in printed_inputs))

    target_relations = [item[1] for collection in [patterns_morphs, clusters, themes] for item in collection]

    append_words("krilius", [target_morph] + inputs)