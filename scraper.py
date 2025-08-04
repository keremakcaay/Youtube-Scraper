import tkinter as tk
from tkinter import messagebox, ttk
from googleapiclient.discovery import build
import psycopg2
import re
import datetime
import webbrowser

# ---------------- YouTube API ----------------
API_KEY = ""
youtube = build("youtube", "v3", developerKey=API_KEY)

# ---------------- PostgreSQL Config ----------------
DB_HOST = "localhost"
DB_NAME = "youtubescrape"
DB_USER = ""
DB_PASS = ""
DB_PORT = ""

def connect_db():
    return psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT
    )

def extract_email(text):
    match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    return match.group(0) if match else None

def create_table():
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS youtube_channels (
            id SERIAL PRIMARY KEY,
            channel_id VARCHAR(255) UNIQUE,
            channel_title TEXT,
            channel_link TEXT,
            subscribers BIGINT,
            views BIGINT,
            videos BIGINT,
            country TEXT,
            business_email TEXT,
            scraped_at TIMESTAMP DEFAULT NOW()
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

def get_channel_details(channel_id):
    response = youtube.channels().list(
        part="snippet,statistics,brandingSettings",
        id=channel_id
    ).execute()

    if not response["items"]:
        return None

    info = response["items"][0]
    snippet = info.get("snippet", {})
    stats = info.get("statistics", {})

    try:
        subscriber_count = int(stats.get("subscriberCount", 0))
    except:
        subscriber_count = 0  

    return {
        "channel_id": channel_id,
        "channel_title": snippet.get("title", ""),
        "channel_link": f"https://www.youtube.com/channel/{channel_id}",
        "subscribers": subscriber_count,
        "views": int(stats.get("viewCount", 0)),
        "videos": int(stats.get("videoCount", 0)),
        "country": snippet.get("country", "Unknown"),
        "business_email": extract_email(snippet.get("description", "")),
        "scraped_at": datetime.datetime.now()
    }

def scrape_and_save(keyword):
    search_response = youtube.search().list(
        q=keyword,
        type="channel",
        part="snippet",
        maxResults=10
    ).execute()

    channels = []

    for item in search_response["items"]:
        channel_id = item["snippet"]["channelId"]
        details = get_channel_details(channel_id)
        if details and details["subscribers"] >= 1000:
            channels.append(details)

    conn = connect_db()
    cur = conn.cursor()

    for ch in channels:
        cur.execute("""
            INSERT INTO youtube_channels (
                channel_id, channel_title, channel_link,
                subscribers, views, videos, country,
                business_email, scraped_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (channel_id) DO UPDATE SET
                channel_title = EXCLUDED.channel_title,
                channel_link = EXCLUDED.channel_link,
                subscribers = EXCLUDED.subscribers,
                views = EXCLUDED.views,
                videos = EXCLUDED.videos,
                country = EXCLUDED.country,
                business_email = EXCLUDED.business_email,
                scraped_at = EXCLUDED.scraped_at;
        """, (
            ch["channel_id"],
            ch["channel_title"],
            ch["channel_link"],
            ch["subscribers"],
            ch["views"],
            ch["videos"],
            ch["country"],
            ch["business_email"],
            ch["scraped_at"]
        ))

    conn.commit()
    cur.close()
    conn.close()

    return channels

# ---------------- GUI ----------------
def start_scrape():
    keyword = keyword_entry.get().strip()
    if not keyword:
        messagebox.showwarning("Missing Input", "Please enter a keyword.")
        return

    try:
        create_table()
        channels = scrape_and_save(keyword)
        messagebox.showinfo("Done", f"✅ {len(channels)} channels saved/updated.")
        update_table()
    except Exception as e:
        messagebox.showerror("Error", str(e))

def update_table():
    for row in tree.get_children():
        tree.delete(row)

    conn = connect_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT channel_title, subscribers, views, videos, country,
               business_email, channel_link, scraped_at
        FROM youtube_channels
        ORDER BY scraped_at DESC LIMIT 100;
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    for row in rows:
        tree.insert("", "end", values=row)

def open_link(event):
    selected = tree.focus()
    if not selected:
        return
    values = tree.item(selected, "values")
    url = values[6]
    webbrowser.open(url)

# Build the GUI
app = tk.Tk()
app.title("YouTube Channel Scraper")
app.geometry("1100x600")

tk.Label(app, text="Enter keyword to search YouTube channels:").pack(pady=10)
keyword_entry = tk.Entry(app, width=50)
keyword_entry.pack(pady=5)

tk.Button(app, text="Scrape Now", command=start_scrape).pack(pady=10)

# Results Table
columns = ("Title", "Subscribers", "Views", "Videos", "Country", "Email", "Link", "Scraped At")
tree = ttk.Treeview(app, columns=columns, show="headings", height=20)
for col in columns:
    tree.heading(col, text=col)
    tree.column(col, width=140 if col != "Title" else 200)

tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
tree.bind("<Double-1>", open_link)

app.mainloop()


