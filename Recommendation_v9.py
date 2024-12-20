import sqlite3
import requests
import pandas as pd
from datetime import datetime, timedelta
import threading

def fetch_app_names(bundle_ids):
    url = f"https://itunes.apple.com/lookup?bundleId={','.join(bundle_ids)}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx and 5xx)
        data = response.json()
        if 'results' in data:
            return {app['bundleId']: app['trackName'] for app in data['results']}
        else:
            print("Unexpected response format from iTunes API")
            return {}
    except requests.exceptions.RequestException as e:
        print(f"Error querying iTunes API: {e}")
        return {}

def parse_sqlite_db(db_path):
    try:
        # Connect to the SQLite database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Fetch data from ZAMDAPPEVENT table
        cursor.execute("SELECT zadamid, ztime, zforegroundduration, zeventsubtype, ztype, zappversion FROM ZAMDAPPEVENT")
        rows = cursor.fetchall()

        # Close the connection
        conn.close()

        # Process the fetched data
        bundle_ids = list(set(row[0] for row in rows))
        app_names = fetch_app_names(bundle_ids)

        data = []
        for row in rows:
            zadamid, ztime, zforegroundduration, zeventsubtype, ztype, zappversion = row
            start_time = datetime.utcfromtimestamp(ztime / 1000)
            end_time = start_time + timedelta(seconds=zforegroundduration)
            app_name = app_names.get(zadamid, "Unknown App")

            data.append({
                "Timestamp": start_time.strftime("%m/%d/%Y %H:%M:%S"),
                "Foreground": "App in Foreground",
                "Details": f"{app_name} v{zappversion}\nType: {ztype}, Subtype: {zeventsubtype} {'(Install)' if zeventsubtype == 3 else ''}\nDuration: {zforegroundduration} seconds"
            })
            data.append({
                "Timestamp": end_time.strftime("%m/%d/%Y %H:%M:%S"),
                "Foreground": "App moved to background",
                "Details": f"{app_name} v{zappversion}\nType: {ztype}, Subtype: {zeventsubtype} {'(Install)' if zeventsubtype == 3 else ''}\nDuration: {zforegroundduration} seconds"
            })

        # Create a DataFrame and save to Excel
        df = pd.DataFrame(data)
        df.to_excel("output.xlsx", index=False)
        print("Data has been written to output.xlsx")
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")

def start_parsing_thread(db_path):
    parsing_thread = threading.Thread(target=parse_sqlite_db, args=(db_path,))
    parsing_thread.start()
    return parsing_thread

# Example usage
if __name__ == "__main__":
    db_path = "recommendation_v9.sqlite"
    thread = start_parsing_thread(db_path)
    thread.join()  # Wait for the thread to complete

