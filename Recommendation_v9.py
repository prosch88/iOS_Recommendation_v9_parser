import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import threading
import os
import argparse

def fetch_app_names_from_storeuser(storeuser_db_path):
    print("Fetching app names from storeUser.db...")
    conn = sqlite3.connect(storeuser_db_path)
    cursor = conn.cursor()

    # Fetch app names and bundle IDs from purchase_history_apps
    cursor.execute('''
    SELECT store_item_ID, long_title, bundle_id
    FROM purchase_history_apps
    ''')

    all_rows = cursor.fetchall()
    app_details = {str(row[0]): (row[1], row[2]) for row in all_rows}

    conn.close()
    print(f"Extracted app details: {app_details}")
    return app_details

def parse_sqlite_db(db_path, storeuser_db_path):
    print(f"Parsing SQLite DB: {db_path}")
    try:
        # Ensure the .wal and .shm files are in the same directory
        wal_path = db_path + '-wal'
        shm_path = db_path + '-shm'
        if os.path.exists(wal_path) and os.path.exists(shm_path):
            # Connect to the SQLite database with WAL mode
            conn = sqlite3.connect(db_path, isolation_level=None)
            cursor = conn.cursor()
            cursor.execute('PRAGMA journal_mode=WAL;')
        else:
            # Connect to the SQLite database
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

        # Fetch data from ZAMDAPPEVENT table
        cursor.execute("SELECT zadamid, ztime, zforegroundduration, zeventsubtype, ztype, zappversion FROM ZAMDAPPEVENT")
        rows = cursor.fetchall()
        print(f"Fetched {len(rows)} rows from the database.")

        # Close the connection
        conn.close()

        # Fetch app details from storeUser.db
        app_details = fetch_app_names_from_storeuser(storeuser_db_path)

        # Process the fetched data
        data = []
        for row in rows:
            zadamid, ztime, zforegroundduration, zeventsubtype, ztype, zappversion = row
            start_time = datetime.utcfromtimestamp(ztime / 1000)
            if zforegroundduration is not None:
                end_time = start_time + timedelta(seconds=zforegroundduration)
            else:
                end_time = start_time
            app_name, bundle_id = app_details.get(str(zadamid), ("Unknown App", "Unknown Bundle ID"))
            print(f"Mapping AdamID {zadamid} to app name {app_name} and bundle ID {bundle_id}")

            data.append({
                "Timestamp": start_time.strftime("%m/%d/%Y %H:%M:%S"),
                "Foreground": "App in Foreground",
                "Details": f"{app_name} (Bundle ID: {bundle_id}) v{zappversion}\nType: {ztype}, Subtype: {zeventsubtype} {'(Install)' if zeventsubtype == 3 else ''}\nDuration: {zforegroundduration} seconds"
            })
            data.append({
                "Timestamp": end_time.strftime("%m/%d/%Y %H:%M:%S"),
                "Foreground": "App moved to background",
                "Details": f"{app_name} (Bundle ID: {bundle_id}) v{zappversion}\nType: {ztype}, Subtype: {zeventsubtype} {'(Install)' if zeventsubtype == 3 else ''}\nDuration: {zforegroundduration} seconds"
            })

        # Create a DataFrame and save to CSV
        df = pd.DataFrame(data)
        print("DataFrame created, writing to CSV...")
        df.to_csv("output.csv", index=False)
        print("Data has been written to output.csv")
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def start_parsing_thread(db_path, storeuser_db_path):
    print("Starting parsing thread...")
    parsing_thread = threading.Thread(target=parse_sqlite_db, args=(db_path, storeuser_db_path))
    parsing_thread.start()
    return parsing_thread

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse the ZAMDAPPEVENT table from an SQLite database.")
    parser.add_argument("db_path", help="Path to the SQLite database file")
    parser.add_argument("storeuser_db_path", help="Path to the storeUser.db file")
    args = parser.parse_args()

    print(f"Starting script with db_path: {args.db_path} and storeuser_db_path: {args.storeuser_db_path}")
    thread = start_parsing_thread(args.db_path, args.storeuser_db_path)
    thread.join()  # Wait for the thread to complete
    print("Script completed.")

