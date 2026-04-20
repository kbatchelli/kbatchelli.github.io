#!/usr/bin/env python3
"""Static blog generator. Converts markdown posts into HTML."""

import os
import re
import shutil
from datetime import datetime
from pathlib import Path

SITE_TITLE = "Blog"
SITE_SUBTITLE = ""
BASE_URL = ""

POSTS_DIR = Path("posts")
STATIC_DIR = Path("static")
OUTPUT_DIR = Path("_site")


def parse_post(filepath):
    """Parse a markdown file with YAML-ish frontmatter."""
    text = filepath.read_text()
    meta = {}
    body = text

    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().splitlines():
                if ":" in line:
                    key, val = line.split(":", 1)
                    meta[key.strip()] = val.strip()
            body = parts[2].strip()

    slug = filepath.stem
    meta.setdefault("title", slug.replace("-", " ").title())
    meta.setdefault("date", datetime.fromtimestamp(filepath.stat().st_mtime).strftime("%Y-%m-%d"))
    meta["slug"] = slug

    # Extract first paragraph as summary
    first_para = ""
    for line in body.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            first_para = line
            break
    meta["summary"] = meta.get("summary", first_para[:200])

    meta.setdefault("category", "uncategorized")
    meta["body_html"] = markdown_to_html(body)
    return meta


def markdown_to_html(md):
    """Minimal markdown to HTML converter."""
    lines = md.split("\n")
    html_parts = []
    in_code_block = False
    in_list = False
    list_type = None
    code_block_lines = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # Fenced code blocks
        if line.strip().startswith("```"):
            if in_code_block:
                html_parts.append("<pre><code>" + escape_html("\n".join(code_block_lines)) + "</code></pre>")
                code_block_lines = []
                in_code_block = False
            else:
                if in_list:
                    html_parts.append(f"</{list_type}>")
                    in_list = False
                in_code_block = True
            i += 1
            continue

        if in_code_block:
            code_block_lines.append(line)
            i += 1
            continue

        stripped = line.strip()

        # Blank line
        if not stripped:
            if in_list:
                html_parts.append(f"</{list_type}>")
                in_list = False
            i += 1
            continue

        # Headings
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading_match:
            if in_list:
                html_parts.append(f"</{list_type}>")
                in_list = False
            level = len(heading_match.group(1))
            text = inline_format(heading_match.group(2))
            html_parts.append(f"<h{level}>{text}</h{level}>")
            i += 1
            continue

        # Horizontal rule
        if re.match(r"^[-*_]{3,}$", stripped):
            if in_list:
                html_parts.append(f"</{list_type}>")
                in_list = False
            html_parts.append("<hr>")
            i += 1
            continue

        # Blockquote
        if stripped.startswith(">"):
            if in_list:
                html_parts.append(f"</{list_type}>")
                in_list = False
            quote_lines = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote_lines.append(re.sub(r"^>\s?", "", lines[i].strip()))
                i += 1
            html_parts.append(f"<blockquote><p>{inline_format(' '.join(quote_lines))}</p></blockquote>")
            continue

        # Unordered list
        ul_match = re.match(r"^[-*+]\s+(.+)$", stripped)
        if ul_match:
            if not in_list or list_type != "ul":
                if in_list:
                    html_parts.append(f"</{list_type}>")
                html_parts.append("<ul>")
                in_list = True
                list_type = "ul"
            html_parts.append(f"<li>{inline_format(ul_match.group(1))}</li>")
            i += 1
            continue

        # Ordered list
        ol_match = re.match(r"^\d+\.\s+(.+)$", stripped)
        if ol_match:
            if not in_list or list_type != "ol":
                if in_list:
                    html_parts.append(f"</{list_type}>")
                html_parts.append("<ol>")
                in_list = True
                list_type = "ol"
            html_parts.append(f"<li>{inline_format(ol_match.group(1))}</li>")
            i += 1
            continue

        # Paragraph
        if in_list:
            html_parts.append(f"</{list_type}>")
            in_list = False
        para_lines = []
        while i < len(lines) and lines[i].strip() and not lines[i].strip().startswith(("#", "```", ">", "---", "***", "___")):
            if re.match(r"^[-*+]\s+", lines[i].strip()) or re.match(r"^\d+\.\s+", lines[i].strip()):
                break
            para_lines.append(lines[i].strip())
            i += 1
        if para_lines:
            html_parts.append(f"<p>{inline_format(' '.join(para_lines))}</p>")
        continue

        i += 1

    if in_list:
        html_parts.append(f"</{list_type}>")
    if in_code_block:
        html_parts.append("<pre><code>" + escape_html("\n".join(code_block_lines)) + "</code></pre>")

    return "\n".join(html_parts)


def escape_html(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline_format(text):
    """Handle inline markdown: bold, italic, code, links, images."""
    # Code (do first to avoid processing inside code spans)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    # Images
    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img src="\2" alt="\1">', text)
    # Links
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    # Bold
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__(.+?)__", r"<strong>\1</strong>", text)
    # Italic
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"_(.+?)_", r"<em>\1</em>", text)
    return text


def render_page(title, content, is_home=False, categories=None):
    nav_links = '<a href="/">All</a>'
    if categories:
        for cat in sorted(categories):
            nav_links += f' <a href="/category/{cat}/">{cat.title()}</a>'
    subtitle_html = f'<p class="subtitle">{SITE_SUBTITLE}</p>' if SITE_SUBTITLE and is_home else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title}</title>
    <link rel="stylesheet" href="/style.css">
</head>
<body>
    <header>
        <h1><a href="/">{SITE_TITLE}</a></h1>
        {subtitle_html}
        <nav>{nav_links}</nav>
    </header>
    <main>
        {content}
    </main>
    <footer>&copy; {datetime.now().year}</footer>
</body>
</html>"""


def build():
    # Clean output
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir()

    # Tell GitHub Pages to skip Jekyll processing
    (OUTPUT_DIR / ".nojekyll").touch()

    # Copy static files
    if STATIC_DIR.exists():
        for f in STATIC_DIR.iterdir():
            shutil.copy2(f, OUTPUT_DIR / f.name)

    # Parse posts
    posts = []
    if POSTS_DIR.exists():
        for f in sorted(POSTS_DIR.glob("*.md")):
            posts.append(parse_post(f))

    # Sort by date descending
    posts.sort(key=lambda p: p.get("date", ""), reverse=True)

    # Collect all categories
    categories = sorted(set(p["category"] for p in posts)) if posts else []

    def render_post_list(post_list):
        if not post_list:
            return "<p>No posts yet.</p>"
        items = []
        for p in post_list:
            cat_link = f'<a href="/category/{p["category"]}/" class="post-category">{p["category"].title()}</a>'
            items.append(
                f'<li>'
                f'<div class="post-title"><a href="/{p["slug"]}/">{p["title"]}</a></div>'
                f'<div class="post-meta"><span class="post-date">{p["date"]}</span> {cat_link}</div>'
                f'<div class="post-summary">{p["summary"]}</div>'
                f'</li>'
            )
        return f'<ul class="post-list">{"".join(items)}</ul>'

    # Build index
    (OUTPUT_DIR / "index.html").write_text(
        render_page(SITE_TITLE, render_post_list(posts), is_home=True, categories=categories)
    )

    # Build category pages
    cat_base = OUTPUT_DIR / "category"
    cat_base.mkdir(exist_ok=True)
    for cat in categories:
        cat_posts = [p for p in posts if p["category"] == cat]
        cat_dir = cat_base / cat
        cat_dir.mkdir(exist_ok=True)
        heading = f'<h2 class="category-heading">{cat.title()}</h2>'
        (cat_dir / "index.html").write_text(
            render_page(f'{cat.title()} — {SITE_TITLE}', heading + render_post_list(cat_posts), categories=categories)
        )

    # Build individual posts
    for p in posts:
        post_dir = OUTPUT_DIR / p["slug"]
        post_dir.mkdir()
        cat_link = f'<a href="/category/{p["category"]}/" class="post-category">{p["category"].title()}</a>'
        content = (
            f'<article><h1>{p["title"]}</h1>'
            f'<div class="post-meta"><span class="post-date">{p["date"]}</span> {cat_link}</div>'
            f'{p["body_html"]}</article>'
        )
        (post_dir / "index.html").write_text(
            render_page(f'{p["title"]} — {SITE_TITLE}', content, categories=categories)
        )

    print(f"Built {len(posts)} post(s), {len(categories)} category page(s) → {OUTPUT_DIR}/")


if __name__ == "__main__":
    build()
