#!/usr/bin/env python3
"""minimal-blog local admin. Python 3 stdlib only.

Usage:
  python3 scripts/admin.py              # http://127.0.0.1:8765/
  python3 scripts/admin.py --port 9000
  python3 scripts/admin.py --no-open    # ブラウザ自動起動なし
"""
import argparse
import html
import http.server
import re
import socketserver
import urllib.parse
import webbrowser
from datetime import datetime, timezone, timedelta
from pathlib import Path

JST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "posts"
SITE_BASE = "https://example.com"
SLUG_RE = r"[a-z0-9][a-z0-9-]*"
DATE_RE = r"\d{4}-\d{2}-\d{2}"

POST_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t} — サイト名</title>
<link rel="stylesheet" href="../style.css">
<link rel="alternate" type="application/rss+xml" title="RSS" href="../feed.xml">
</head>
<body>
<header>
<nav>
<a href="../index.html">Home</a>
<a href="../posts/index.html">Posts</a>
<a href="../about.html">About</a>
</nav>
</header>
<main>
<article>
<h1>{t}</h1>
<p class="meta"><time datetime="{d}">{d}</time></p>

{b}
</article>
</main>
<footer>
<p>© 2026 / <a href="../feed.xml">RSS</a> / contact: you@example.com</p>
</footer>
</body>
</html>
"""

# ---- body <-> HTML conversion (plain text, blank line = paragraph break) ----

def body_to_html(text: str) -> str:
    text = text.strip().replace("\r\n", "\n")
    paras = re.split(r"\n\s*\n", text)
    return "\n\n".join(
        f"<p>{html.escape(p.strip())}</p>" for p in paras if p.strip()
    )

def html_to_body(content: str) -> str:
    m = re.search(r"<article>(.*?)</article>", content, re.S)
    if not m:
        return ""
    article = m.group(1)
    article = re.sub(r"<h1>.*?</h1>", "", article, count=1, flags=re.S)
    article = re.sub(r'<p class="meta">.*?</p>', "", article, count=1, flags=re.S)
    paras = re.findall(r"<p>(.*?)</p>", article, re.S)
    return "\n\n".join(html.unescape(p.strip()) for p in paras)

# ---- post discovery ----

def parse_filename(name: str):
    m = re.match(rf"^({DATE_RE})-({SLUG_RE})\.html$", name)
    return (m.group(1), m.group(2)) if m else None

def extract_title(content: str, fallback: str) -> str:
    m = re.search(r"<h1>(.*?)</h1>", content, re.S)
    return html.unescape(m.group(1).strip()) if m else fallback

def list_posts():
    out = []
    for p in POSTS_DIR.glob("*.html"):
        if p.name == "index.html":
            continue
        parsed = parse_filename(p.name)
        if not parsed:
            continue
        d, s = parsed
        title = extract_title(p.read_text(), s)
        out.append({"date": d, "slug": s, "title": title,
                    "filename": p.name, "path": p})
    out.sort(key=lambda x: (x["date"], x["slug"]), reverse=True)
    return out

def find_post(slug: str):
    for p in list_posts():
        if p["slug"] == slug:
            return p
    return None

def load_post(slug: str):
    p = find_post(slug)
    if not p:
        return None
    p["body"] = html_to_body(p["path"].read_text())
    return p

# ---- index rebuilds ----

def rebuild_posts_index(posts):
    by_year: dict = {}
    for p in posts:
        by_year.setdefault(p["date"][:4], []).append(p)
    sections = []
    for year in sorted(by_year.keys(), reverse=True):
        items = sorted(by_year[year], key=lambda x: x["date"], reverse=True)
        lis = "\n".join(
            f'<li><time datetime="{p["date"]}">{p["date"]}</time>'
            f'<a href="{p["filename"]}">{html.escape(p["title"])}</a></li>'
            for p in items
        )
        sections.append(f'<h2>{year}</h2>\n<ul class="posts-list">\n{lis}\n</ul>')
    block = "\n\n".join(sections) if sections else ""
    target = POSTS_DIR / "index.html"
    src = target.read_text()
    new = re.sub(
        r"(<h1>Posts</h1>)(.*?)(</main>)",
        lambda m: f"{m.group(1)}\n\n{block}\n{m.group(3)}",
        src, count=1, flags=re.S,
    )
    target.write_text(new)

def rebuild_home_latest(posts):
    top = posts[:3]
    if top:
        lis = "\n".join(
            f'<li><time datetime="{p["date"]}">{p["date"]}</time>'
            f'<a href="posts/{p["filename"]}">{html.escape(p["title"])}</a></li>'
            for p in top
        )
        ul = f'<ul class="posts-list">\n{lis}\n</ul>'
    else:
        ul = '<ul class="posts-list">\n</ul>'
    target = ROOT / "index.html"
    src = target.read_text()
    new = re.sub(r'<ul class="posts-list">.*?</ul>', ul, src, count=1, flags=re.S)
    target.write_text(new)

def rebuild_feed(posts):
    now = datetime.now(JST).strftime("%a, %d %b %Y %H:%M:%S +0900")
    items = []
    for p in posts[:20]:
        d = datetime.strptime(p["date"], "%Y-%m-%d").replace(tzinfo=JST)
        rss_d = d.strftime("%a, %d %b %Y %H:%M:%S +0900")
        link = f"{SITE_BASE}/posts/{p['filename']}"
        t = html.escape(p["title"])
        items.append(
            f"<item>\n<title>{t}</title>\n<link>{link}</link>\n"
            f"<guid>{link}</guid>\n<pubDate>{rss_d}</pubDate>\n"
            f"<description>{t}</description>\n</item>"
        )
    items_block = "\n".join(items)
    target = ROOT / "feed.xml"
    src = target.read_text()
    src = re.sub(
        r"<lastBuildDate>.*?</lastBuildDate>",
        f"<lastBuildDate>{now}</lastBuildDate>",
        src, count=1,
    )
    new = re.sub(
        r"(</lastBuildDate>)(.*?)(</channel>)",
        lambda m: f"{m.group(1)}\n{items_block}\n{m.group(3)}",
        src, count=1, flags=re.S,
    )
    target.write_text(new)

def write_post(date: str, slug: str, title: str, body: str):
    out = POST_TEMPLATE.format(
        t=html.escape(title), d=date, b=body_to_html(body),
    )
    (POSTS_DIR / f"{date}-{slug}.html").write_text(out)

def rebuild_all():
    posts = list_posts()
    rebuild_posts_index(posts)
    rebuild_home_latest(posts)
    rebuild_feed(posts)

# ---- HTTP layer ----

LAYOUT = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="/style.css">
<style>
body {{ max-width: 52em; }}
nav a {{ margin-right: 1em; }}
form label {{ display: block; margin-top: 1em; }}
form input[type=text], form textarea {{
  width: 100%; padding: 0.4em; box-sizing: border-box;
  font-family: inherit; font-size: 1em;
}}
form textarea {{
  min-height: 24em;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}}
button {{ font: inherit; padding: 0.4em 1em; margin-right: 0.4em; }}
table {{ border-collapse: collapse; width: 100%; }}
td {{ padding: 0.4em 0.6em 0.4em 0; vertical-align: top; }}
td.actions a {{ margin-right: 0.8em; }}
.flash {{ padding: 0.6em 0.8em; background: rgba(127,127,127,0.14);
          margin-bottom: 1em; }}
.note {{ color: var(--muted); font-size: 0.9em; }}
</style>
</head>
<body>
<header>
<nav>
<a href="/">Admin</a>
<a href="/new">+ New post</a>
<a href="/index.html" target="_blank">View site</a>
</nav>
</header>
<main>
{flash}
{content}
</main>
</body>
</html>
"""

def layout(title: str, content: str, flash: str = "") -> str:
    flash_html = f'<div class="flash">{html.escape(flash)}</div>' if flash else ""
    return LAYOUT.format(title=html.escape(title), content=content, flash=flash_html)

def page_list(flash: str = "") -> str:
    posts = list_posts()
    if not posts:
        body = '<p>記事がありません。<a href="/new">新規作成</a>から始めてください。</p>'
    else:
        rows = "\n".join(
            f"<tr>"
            f"<td><time>{p['date']}</time></td>"
            f"<td>{html.escape(p['title'])}</td>"
            f'<td class="actions">'
            f'<a href="/edit/{p["slug"]}">編集</a>'
            f'<a href="/preview/{p["slug"]}" target="_blank">プレビュー</a>'
            f'<a href="/delete/{p["slug"]}">削除</a>'
            f"</td></tr>"
            for p in posts
        )
        body = f"<table>{rows}</table>"
    content = f'<h1>記事一覧</h1>\n<p><a href="/new">+ 新規記事</a></p>\n{body}'
    return layout("Admin — minimal-blog", content, flash)

def page_new(flash: str = "") -> str:
    today = datetime.now(JST).strftime("%Y-%m-%d")
    content = f"""
<h1>新規記事</h1>
<form method="post" action="/new">
<label>日付 <input type="text" name="date" value="{today}" required pattern="\\d{{4}}-\\d{{2}}-\\d{{2}}"></label>
<label>スラッグ（半角小文字・数字・ハイフン）<input type="text" name="slug" required pattern="[a-z0-9][a-z0-9-]*"></label>
<label>タイトル <input type="text" name="title" required></label>
<label>本文（空行で段落区切り）<textarea name="body" placeholder="ここに本文。空行で段落が分かれます。"></textarea></label>
<p>
<button type="submit" name="action" value="save">作成</button>
<button type="submit" name="action" value="save-preview">作成してプレビュー</button>
</p>
</form>
"""
    return layout("新規記事", content, flash)

def page_edit(slug: str, flash: str = ""):
    post = load_post(slug)
    if not post:
        return None
    t = html.escape(post["title"])
    b = html.escape(post["body"])
    content = f"""
<h1>編集</h1>
<p class="note">日付: {post['date']} / スラッグ: {post['slug']}（変更不可）</p>
<form method="post" action="/edit/{post['slug']}">
<label>タイトル <input type="text" name="title" required value="{t}"></label>
<label>本文 <textarea name="body">{b}</textarea></label>
<p>
<button type="submit" name="action" value="save">保存</button>
<button type="submit" name="action" value="save-preview">保存してプレビュー</button>
<a href="/preview/{post['slug']}" target="_blank">現状をプレビュー</a>
</p>
</form>
"""
    return layout(f"編集: {post['title']}", content, flash)

def page_delete_confirm(slug: str):
    post = find_post(slug)
    if not post:
        return None
    content = f"""
<h1>削除確認</h1>
<p>「{html.escape(post['title'])}」（{post['date']}）を削除します。よろしいですか？</p>
<form method="post" action="/delete/{post['slug']}">
<button type="submit">削除する</button>
<a href="/">キャンセル</a>
</form>
<p class="note">git で管理していれば <code>git checkout</code> で復元できます。</p>
"""
    return layout("削除確認", content)


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):
        return  # quiet

    def _html(self, body: str, status: int = 200):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self, location: str):
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()

    @staticmethod
    def _flash(msg: str) -> str:
        return urllib.parse.quote(msg)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        q = urllib.parse.parse_qs(parsed.query)
        flash = q.get("m", [""])[0]

        if path in ("/", "/admin"):
            return self._html(page_list(flash))
        if path == "/new":
            return self._html(page_new(flash))
        m = re.match(rf"^/edit/({SLUG_RE})$", path)
        if m:
            out = page_edit(m.group(1), flash)
            return self._html(out) if out else self.send_error(404)
        m = re.match(rf"^/delete/({SLUG_RE})$", path)
        if m:
            out = page_delete_confirm(m.group(1))
            return self._html(out) if out else self.send_error(404)
        m = re.match(rf"^/preview/({SLUG_RE})$", path)
        if m:
            post = find_post(m.group(1))
            if not post:
                return self.send_error(404)
            return self._redirect(f"/posts/{post['filename']}")
        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length else ""
        form = {
            k: v[0]
            for k, v in urllib.parse.parse_qs(raw, keep_blank_values=True).items()
        }
        action = form.get("action", "save")

        if path == "/new":
            date = form.get("date", "").strip()
            slug = form.get("slug", "").strip()
            title = form.get("title", "").strip()
            body = form.get("body", "")
            if not (re.match(rf"^{DATE_RE}$", date)
                    and re.match(rf"^{SLUG_RE}$", slug) and title):
                return self._redirect(f"/new?m={self._flash('入力エラー')}")
            target = POSTS_DIR / f"{date}-{slug}.html"
            if target.exists():
                return self._redirect(f"/new?m={self._flash('既存: ' + target.name)}")
            write_post(date, slug, title, body)
            rebuild_all()
            if action == "save-preview":
                return self._redirect(f"/preview/{slug}")
            return self._redirect(f"/?m={self._flash('作成: ' + title)}")

        m = re.match(rf"^/edit/({SLUG_RE})$", path)
        if m:
            slug = m.group(1)
            post = find_post(slug)
            if not post:
                return self.send_error(404)
            title = form.get("title", "").strip()
            body = form.get("body", "")
            if not title:
                return self._redirect(f"/edit/{slug}?m={self._flash('タイトル必須')}")
            write_post(post["date"], slug, title, body)
            rebuild_all()
            if action == "save-preview":
                return self._redirect(f"/preview/{slug}")
            return self._redirect(f"/?m={self._flash('保存: ' + title)}")

        m = re.match(rf"^/delete/({SLUG_RE})$", path)
        if m:
            slug = m.group(1)
            post = find_post(slug)
            if not post:
                return self.send_error(404)
            post["path"].unlink()
            rebuild_all()
            return self._redirect(f"/?m={self._flash('削除: ' + post['title'])}")

        return self.send_error(404)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args()

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", args.port), Handler) as srv:
        url = f"http://127.0.0.1:{args.port}/"
        print(f"Admin: {url}")
        print("Ctrl+C で終了")
        if not args.no_open:
            try:
                webbrowser.open(url)
            except Exception:
                pass
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print()


if __name__ == "__main__":
    main()
