import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import os
import argparse
import shutil

def create_database_copy(db_path):
    """Create a copy of the database and WAL file to avoid modifying the original."""
    backup_db = db_path.replace(".db", "_backup.db")
    wal_path = db_path + "-wal"
    
    print(f"Creating backup: {backup_db}")
    shutil.copy2(db_path, backup_db)
    if os.path.exists(wal_path):
        shutil.copy2(wal_path, backup_db + "-wal")
    
    return backup_db

def fetch_app_names_from_file(adam_id_file_path):
    """Read app details from appID2app.txt and store them in a dictionary with AdamID as the key."""
    app_details = {}
    try:
        with open(adam_id_file_path, 'r') as file:
            for line in file:
                parts = line.strip().split(',')
                if len(parts) == 3:
                    bundle_id, app_id, app_name = parts  # Ensure correct order
                    app_details[app_id.strip()] = (app_name.strip(), bundle_id.strip())
    except Exception as e:
        print(f"Error reading AdamID2app.txt: {e}")
    return app_details

def parse_sqlite_db(db_path, adam_id_file_path, case_number):
    print(f"Parsing SQLite DB: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Ensure WAL mode is handled without writing
        cursor.execute("PRAGMA query_only = ON;")
        cursor.execute("PRAGMA journal_mode;")
        journal_mode = cursor.fetchone()[0]
        print(f"Journal mode: {journal_mode}")
        
        if journal_mode == "wal":
            print("Applying WAL checkpoint (PASSIVE) to ensure all data is visible...")
            try:
                cursor.execute("PRAGMA wal_checkpoint(PASSIVE);")
            except sqlite3.OperationalError:
                print("Read-only mode detected, unable to checkpoint WAL. Creating a backup copy...")
                db_path = create_database_copy(db_path)
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("PRAGMA query_only = ON;")
                cursor.execute("PRAGMA wal_checkpoint(PASSIVE);")
                print("WAL checkpoint applied on backup database.")
        
        # List all tables in the database
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"Tables in database: {tables}")
        
        # Check if ZAMDAPPEVENT table exists (case-insensitive check)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' COLLATE NOCASE AND name='ZAMDAPPEVENT';")
        if not cursor.fetchone():
            print("ZAMDAPPEVENT table not found! Check if the correct database is used and verify table names.")
            conn.close()
            return
        
        print("Fetching data from ZAMDAPPEVENT table...")
        cursor.execute("SELECT zadamid, ztime, zforegroundduration, zeventsubtype, ztype, zappversion FROM ZAMDAPPEVENT")
        rows = cursor.fetchall()
        print(f"Fetched {len(rows)} rows from the database.")
        
        app_details = fetch_app_names_from_file(adam_id_file_path)
        
        # Process the fetched data
        data = []
        for row in rows:
            zadamid, ztime, zforegroundduration, zeventsubtype, ztype, zappversion = row
            start_time = datetime.utcfromtimestamp(ztime / 1000)
            end_time = start_time + timedelta(seconds=zforegroundduration) if zforegroundduration else start_time
            
            # Ensure AdamID lookup matches exact format
            app_name, bundle_id = app_details.get(str(zadamid).strip(), ("Unknown App", "Unknown Bundle ID"))
            
            data.append({
                "Timestamp": start_time.strftime("%m/%d/%Y %H:%M:%S"),
                "Foreground": "App in Foreground",
                "Details": f"{app_name} (Bundle ID: {bundle_id}, AdamID: {zadamid}) v{zappversion}\nType: {ztype}, Subtype: {zeventsubtype} {'(Install)' if zeventsubtype == 3 else ''}\nDuration: {zforegroundduration} seconds"
            })
            data.append({
                "Timestamp": end_time.strftime("%m/%d/%Y %H:%M:%S"),
                "Foreground": "App moved to background",
                "Details": f"{app_name} (Bundle ID: {bundle_id}, AdamID: {zadamid}) v{zappversion}\nType: {ztype}, Subtype: {zeventsubtype} {'(Install)' if zeventsubtype == 3 else ''}\nDuration: {zforegroundduration} seconds"
            })
        
        conn.close()
        
        # Save to CSV
        df = pd.DataFrame(data)
        output_dir = os.path.dirname(db_path)
        output_filename = os.path.join(output_dir, f"{case_number}-recommendation_v9-StoreUser.db-parsed.csv")
        df.to_csv(output_filename, index=False)
        print(f"Data has been written to {output_filename}")
    
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse the ZAMDAPPEVENT table from an SQLite database.")
    parser.add_argument("db_path", help="Path to the SQLite database file")
    parser.add_argument("adam_id_file_path", help="Path to the AdamID2app.txt file")
    args = parser.parse_args()
    
    case_number = input("Please enter the case number: ")
    
    print(f"Starting script with db_path: {args.db_path} and adam_id_file_path: {args.adam_id_file_path}")
    parse_sqlite_db(args.db_path, args.adam_id_file_path, case_number)
    print("Script completed.")
