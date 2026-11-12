import os
import threading
import queue
import time
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.robotparser import RobotFileParser
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from openpyxl import Workbook
from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import StringProperty, NumericProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.utils import platform

KV = r"""
<RootUI>:
    orientation: "vertical"
    padding: "12dp"
    spacing: "8dp"
    canvas.before:
        Color:
            rgba: (0.055, 0.075, 0.12, 1)
        Rectangle:
            pos: self.pos
            size: self.size
    Label:
        text: "[b]MOVIE CRAWLER[/b]"
        markup: True
        font_size: "23sp"
        size_hint_y: None
        height: "42dp"
        color: (0.95, 0.97, 1, 1)
    Label:
        text: "Public movie metadata • Excel + CSV export"
        font_size: "12sp"
        size_hint_y: None
        height: "22dp"
        color: (0.68, 0.74, 0.84, 1)
    TextInput:
        id: urls
        hint_text: "Enter website URLs, one per line\\nhttps://example.com/movies/"
        multiline: True
        size_hint_y: 0.23
        background_color: (0.12, 0.15, 0.22, 1)
        foreground_color: (1, 1, 1, 1)
        cursor_color: (0.3, 0.7, 1, 1)
        padding: "10dp"
    BoxLayout:
        size_hint_y: None
        height: "42dp"
        spacing: "8dp"
        Label:
            text: "Max pages"
            size_hint_x: 0.38
            color: (0.9, 0.92, 0.97, 1)
        TextInput:
            id: max_pages
            text: "100"
            input_filter: "int"
            multiline: False
            size_hint_x: 0.62
            background_color: (0.12, 0.15, 0.22, 1)
            foreground_color: (1, 1, 1, 1)
    BoxLayout:
        size_hint_y: None
        height: "42dp"
        spacing: "8dp"
        Label:
            text: "Delay (seconds)"
            size_hint_x: 0.38
            color: (0.9, 0.92, 0.97, 1)
        TextInput:
            id: delay
            text: "2"
            input_filter: "float"
            multiline: False
            size_hint_x: 0.62
            background_color: (0.12, 0.15, 0.22, 1)
            foreground_color: (1, 1, 1, 1)
    BoxLayout:
        size_hint_y: None
        height: "46dp"
        spacing: "8dp"
        Button:
            text: "START"
            background_color: (0.12, 0.55, 0.35, 1)
            on_release: app.start_crawl()
        Button:
            text: "STOP"
            background_color: (0.68, 0.22, 0.2, 1)
            on_release: app.stop_crawl()
        Button:
            text: "EXPORT"
            background_color: (0.15, 0.38, 0.72, 1)
            on_release: app.export_data()
    ProgressBar:
        id: progress
        max: 100
        value: 0
        size_hint_y: None
        height: "12dp"
    Label:
        id: status
        text: "Ready"
        size_hint_y: None
        height: "25dp"
        color: (0.75, 0.85, 1, 1)
    Label:
        text: "ACTIVITY LOG"
        size_hint_y: None
        height: "24dp"
        color: (0.8, 0.85, 0.95, 1)
        bold: True
    TextInput:
        id: log
        readonly: True
        multiline: True
        background_color: (0.08, 0.10, 0.16, 1)
        foreground_color: (0.82, 0.9, 0.96, 1)
        font_size: "12sp"
        size_hint_y: 1
    Label:
        text: "Only crawl sites you are authorized to access. No access-control bypass."
        size_hint_y: None
        height: "30dp"
        font_size: "10sp"
        color: (0.85, 0.68, 0.38, 1)
"""

def norm_url(url, base=""):
    url = urldefrag(urljoin(base, (url or "").strip()))[0]
    p = urlparse(url)
    return url if p.scheme in ("http", "https") and p.netloc else ""

def txt(v):
    if v is None: return ""
    if isinstance(v, list): return ", ".join(txt(x) for x in v)
    if isinstance(v, dict): return txt(v.get("name") or v.get("url") or "")
    return " ".join(str(v).split())

def get_meta(soup, *names):
    for n in names:
        tag = soup.find("meta", attrs={"property": n}) or soup.find("meta", attrs={"name": n})
        if tag and tag.get("content"): return txt(tag["content"])
    return ""

def walk_ld(obj, found):
    if isinstance(obj, list):
        for x in obj: walk_ld(x, found)
    elif isinstance(obj, dict):
        typ = obj.get("@type", [])
        typ = typ if isinstance(typ, list) else [typ]
        if any(str(t).lower() in ("movie", "tvseries", "creativework") for t in typ):
            found.append(obj)
        if "@graph" in obj: walk_ld(obj["@graph"], found)

def extract(soup, url):
    ld = []
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            import json
            walk_ld(json.loads(s.string or s.get_text()), ld)
        except Exception:
            pass
    d = ld[0] if ld else {}
    title = txt(d.get("name")) or get_meta(soup, "og:title", "twitter:title") or txt(soup.title.string if soup.title else "")
    desc = txt(d.get("description")) or get_meta(soup, "og:description", "description")
    genre = txt(d.get("genre")) or txt([x.get_text(" ", strip=True) for x in soup.select('[itemprop="genre"], .genre, .genres')][:10])
    ar = d.get("aggregateRating") or {}
    rating = txt(ar.get("ratingValue")) if isinstance(ar, dict) else ""
    if not rating: rating = get_meta(soup, "rating")
    year = txt(d.get("datePublished"))[:4] or get_meta(soup, "release_date")[:4]
    poster = d.get("image") or get_meta(soup, "og:image", "twitter:image")
    if isinstance(poster, list): poster = poster[0] if poster else ""
    if isinstance(poster, dict): poster = poster.get("url") or poster.get("contentUrl", "")
    poster = norm_url(txt(poster), url)
    images, downloads = [], []
    for im in soup.find_all("img"):
        src = im.get("data-src") or im.get("src")
        u = norm_url(src, url)
        if u and u not in images: images.append(u)
    if poster and poster not in images: images.insert(0, poster)
    keys = ("download", "1080p", "720p", "480p", "watch", "magnet")
    for a in soup.find_all("a", href=True):
        u = norm_url(a["href"], url)
        label = txt(a.get_text(" ", strip=True)).lower()
        if u and (any(k in label for k in keys) or any(k in u.lower() for k in ("download", "magnet:"))):
            if u not in downloads: downloads.append(u)
    return {
        "movie_id": str(abs(hash(url))), "title": title, "genre": genre, "rating": rating,
        "release_year": year, "language": txt(d.get("inLanguage")),
        "duration": txt(d.get("duration")), "description": desc,
        "director": txt(d.get("director")), "cast": txt(d.get("actor")),
        "poster_url": poster, "banner_url": get_meta(soup, "og:image") and norm_url(get_meta(soup, "og:image"), url) or poster,
        "image_urls": " | ".join(images[:30]), "download_urls": " | ".join(downloads[:30]),
        "source_url": url, "source_domain": urlparse(url).netloc,
        "crawl_date": datetime.now(timezone.utc).isoformat()
    }, downloads

class RootUI(BoxLayout):
    pass

class MovieCrawlerAndroid(App):
    def build(self):
        self.title = "Movie Crawler"
        self.stop_flag = threading.Event()
        self.events = queue.Queue()
        self.movies, self.links, self.errors, self.logs = [], [], [], []
        Builder.load_string(KV)
        self.ui = RootUI()
        Clock.schedule_interval(self.poll, 0.2)
        return self.ui

    def log(self, message):
        self.events.put(("log", str(message)))

    def start_crawl(self):
        if hasattr(self, "worker") and self.worker and self.worker.is_alive():
            self.log("A crawl is already running.")
            return
        urls = [norm_url(x) for x in self.ui.ids.urls.text.splitlines() if x.strip()]
        urls = list(dict.fromkeys(x for x in urls if x))
        if not urls:
            self.log("Please enter at least one valid http(s) URL.")
            return
        self.stop_flag.clear()
        self.movies, self.links, self.errors, self.logs = [], [], [], []
        try: max_pages = max(1, min(5000, int(self.ui.ids.max_pages.text or "100")))
        except ValueError: max_pages = 100
        try: delay = max(1.0, min(60.0, float(self.ui.ids.delay.text or "2")))
        except ValueError: delay = 2.0
        self.ui.ids.progress.max = max_pages
        self.ui.ids.progress.value = 0
        self.ui.ids.status.text = "Crawling…"
        self.worker = threading.Thread(target=self.crawl_worker, args=(urls, max_pages, delay), daemon=True)
        self.worker.start()

    def stop_crawl(self):
        self.stop_flag.set()
        self.log("Stop requested; finishing current request.")

    def crawl_worker(self, starts, max_pages, delay):
        session = requests.Session()
        session.headers.update({"User-Agent": "MovieMetadataResearchCrawler/1.0"})
        seen, queue_urls, domain_last, robots = set(), [(u, u) for u in starts], {}, {}
        while queue_urls and len(seen) < max_pages and not self.stop_flag.is_set():
            url, root = queue_urls.pop(0)
            if url in seen or urlparse(url).netloc != urlparse(root).netloc: continue
            seen.add(url)
            try:
                host = urlparse(url)
                robots_url = f"{host.scheme}://{host.netloc}/robots.txt"
                if robots_url not in robots:
                    rp = RobotFileParser(); rp.set_url(robots_url)
                    try:
                        rr = session.get(robots_url, timeout=8)
                        if rr.status_code == 404: robots[robots_url] = None
                        elif rr.ok: rp.parse(rr.text.splitlines()); robots[robots_url] = rp
                        else: robots[robots_url] = False
                    except Exception: robots[robots_url] = False
                rp = robots[robots_url]
                if rp is False or (rp is not None and not rp.can_fetch(session.headers["User-Agent"], url)):
                    self.log(f"robots.txt disallows or cannot be checked: {url}")
                    continue
                wait = delay - (time.time() - domain_last.get(host.netloc, 0))
                if wait > 0: time.sleep(wait)
                domain_last[host.netloc] = time.time()
                r = session.get(url, timeout=20); r.raise_for_status()
                soup = BeautifulSoup(r.text, "html.parser")
                movie, downloads = extract(soup, url)
                self.logs.append({"url": url, "status": r.status_code, "visited_at": datetime.now(timezone.utc).isoformat()})
                if movie["title"] and any(movie[k] for k in ("description", "poster_url", "genre", "rating")):
                    self.movies.append(movie)
                    self.log("Found: " + movie["title"])
                    for link in downloads:
                        status, code, ctype, final = self.validate(session, link)
                        self.links.append({"movie_title": movie["title"], "source_page": url, "url": link,
                                           "validation_status": status, "http_status": code,
                                           "content_type": ctype, "final_url": final})
                for a in soup.find_all("a", href=True):
                    candidate = norm_url(a["href"], url)
                    if candidate and urlparse(candidate).netloc == urlparse(root).netloc and candidate not in seen:
                        path = urlparse(candidate).path.lower()
                        label = txt(a.get_text(" ", strip=True)).lower()
                        if any(x in path for x in ("movie", "film", "watch", "title", "series", "page")) or label in ("next", "older", "next page", "»", "›"):
                            queue_urls.append((candidate, root))
            except Exception as e:
                self.errors.append({"url": url, "error": str(e), "time": datetime.now(timezone.utc).isoformat()})
                self.log(f"Error: {url} — {e}")
            self.events.put(("progress", (len(seen), max_pages)))
        self.events.put(("finished", None))

    def validate(self, session, url):
        try:
            r = session.head(url, allow_redirects=True, timeout=8)
            if r.status_code in (405, 501) or r.status_code >= 500:
                r.close()
                r = session.get(url, headers={"Range": "bytes=0-0"}, allow_redirects=True, timeout=8, stream=True)
            code, ctype, final = str(r.status_code), r.headers.get("Content-Type", ""), r.url
            status = "reachable" if 200 <= r.status_code < 400 else ("blocked_or_unknown" if r.status_code in (401,403,429) else "http_error")
            r.close()
            return status, code, ctype, final
        except Exception:
            return "unreachable_or_timeout", "", "", url

    def poll(self, _dt):
        while not self.events.empty():
            kind, data = self.events.get()
            if kind == "log":
                self.ui.ids.log.text += data + "\n"
            elif kind == "progress":
                done, total = data
                self.ui.ids.progress.value = done
                self.ui.ids.status.text = f"Visited {done}/{total} pages • {len(self.movies)} movie pages"
            elif kind == "finished":
                self.ui.ids.status.text = f"Finished • {len(self.movies)} movie pages found"
                self.log("Crawl finished. Use EXPORT to save your files.")

    def export_data(self):
        if not (self.movies or self.links or self.errors or self.logs):
            self.log("Nothing to export yet.")
            return
        try:
            out = os.path.join(self.user_data_dir, "exports")
            os.makedirs(out, exist_ok=True)
            self.write_csv(os.path.join(out, "movies.csv"), self.movies)
            self.write_csv(os.path.join(out, "download_links.csv"), self.links)
            wb = Workbook()
            for idx, (name, rows) in enumerate([
                ("Movies", self.movies), ("Download Links", self.links),
                ("Errors", self.errors), ("Crawl Log", self.logs)
            ]):
                ws = wb.active if idx == 0 else wb.create_sheet()
                ws.title = name
                if rows:
                    headers = list(rows[0].keys())
                    ws.append(headers)
                    for row in rows: ws.append([row.get(h, "") for h in headers])
                    ws.freeze_panes = "A2"
                    ws.auto_filter.ref = ws.dimensions
                else:
                    ws.append(["No records"])
            xlsx = os.path.join(out, "movie_catalog.xlsx")
            wb.save(xlsx)
            self.log(f"Exported files to app storage: {out}")
            self.log("Use Android Files > Internal storage > Android > data > " + self.get_package_name() + " > files > exports (device access varies).")
        except Exception as e:
            self.log("Export error: " + str(e))

    def write_csv(self, path, rows):
        import csv
        if not rows:
            with open(path, "w", encoding="utf-8-sig") as f: f.write("")
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

if __name__ == "__main__":
    MovieCrawlerAndroid().run()
