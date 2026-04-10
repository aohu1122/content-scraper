#!/usr/bin/env python3
"""
content_scraper.py — AI 内容素材采集工具

通过 ScraperAPI 从多来源采集指定话题的相关内容，AI 去重筛选总结。

Usage:
  # 采集话题素材
  python3 content_scraper.py --topic "AI Agent 最新动态"
  python3 content_scraper.py --topic "AI Agent 最新动态" --sources hackernews,reddit,web
  python3 content_scraper.py --topic "AI Agent 最新动态" --limit 10
  python3 content_scraper.py --topic "AI Agent 最新动态" --no-ai  # 不用 AI 总结

需要环境变量:
  SCRAPERAPI_KEY — ScraperAPI 的 API key（免费层 1000 次/月）
  OPENAI_API_KEY — AI 总结需要（可选）
  OPENAI_BASE_URL — API 地址（可选，默认 OpenAI）
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path


# ── 推荐链接 ──
AFFILIATE_URL = "https://www.scraperapi.com/?via=KHAZIX"  # 替换为你的推荐链接


# ── 简单 HTML → 纯文本提取 ──

class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._text = []
        self._skip = False
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "footer", "header"):
            self._skip = True
    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "footer", "header"):
            self._skip = False
        if tag in ("p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr"):
            self._text.append("\n")
    def handle_data(self, data):
        if not self._skip:
            self._text.append(data.strip())
    def get_text(self):
        raw = " ".join(self._text)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()

def html_to_text(html: str) -> str:
    e = _TextExtractor()
    e.feed(html)
    return e.get_text()


# ── ScraperAPI 请求 ──

def scraperapi_get(url: str, api_key: str, params: dict = None) -> str:
    """通过 ScraperAPI 代理请求网页，返回 HTML。"""
    payload = {
        "api_key": api_key,
        "url": url,
        "render": "true",
    }
    if params:
        payload.update(params)
    qs = urllib.parse.urlencode(payload)
    req_url = f"http://api.scraperapi.com?{qs}"
    try:
        req = urllib.request.Request(req_url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=30)
        return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  ⚠️  采集失败 [{url[:50]}...]: {e}")
        return ""


# ── 数据源采集 ──

SOURCES = {
    "hackernews": {
        "name": "HackerNews",
        "search_url": "https://hn.algolia.com/api/v1/search?query={topic}&tags=story&hitsPerPage={limit}",
        "type": "api",  # 直接用 HN API，不需要 ScraperAPI
    },
    "reddit": {
        "name": "Reddit",
        "search_url": "https://www.reddit.com/search/?q={topic}&sort=relevance&t=month&limit={limit}",
        "type": "scrape",
    },
    "web": {
        "name": "Web 搜索",
        "search_url": "https://www.google.com/search?q={topic}&num={limit}",
        "type": "scrape",
    },
    "github": {
        "name": "GitHub Trending",
        "search_url": "https://github.com/search?q={topic}&type=repositories&s=stars&o=desc",
        "type": "scrape",
    },
    "producthunt": {
        "name": "Product Hunt",
        "search_url": "https://www.producthunt.com/search?q={topic}",
        "type": "scrape",
    },
}


def fetch_hackernews(topic: str, limit: int) -> list:
    """直接用 HN Algolia API（免费，不需要 ScraperAPI）。"""
    items = []
    url = SOURCES["hackernews"]["search_url"].format(topic=urllib.parse.quote(topic), limit=limit)
    try:
        resp = urllib.request.urlopen(url, timeout=15)
        data = json.loads(resp.read())
        for hit in data.get("hits", []):
            items.append({
                "title": hit.get("title", ""),
                "url": hit.get("url", "") or f"https://news.ycombinator.com/item?id={hit.get('objectID','')}",
                "source": "HackerNews",
                "points": hit.get("points", 0),
                "author": hit.get("author", ""),
                "created": hit.get("created_at", "")[:10],
                "snippet": (hit.get("title", "") + ". Points: " + str(hit.get("points", 0))),
            })
    except Exception as e:
        print(f"  ⚠️ HackerNews 采集失败: {e}")
    return items


def fetch_google(topic: str, limit: int, api_key: str) -> list:
    """通过 ScraperAPI 爬取 Google 搜索结果。"""
    items = []
    url = SOURCES["web"]["search_url"].format(topic=urllib.parse.quote(topic), limit=limit)
    print(f"  🌐 采集 Web 搜索...")
    html = scraperapi_get(url, api_key)
    if not html:
        return items
    text = html_to_text(html)
    # 简单提取搜索结果（标题+链接的模式）
    pattern = re.findall(r'(https?://[^\s]+)', text)
    seen = set()
    for link in pattern[:limit * 3]:
        clean = link.rstrip(".,;)")
        if clean not in seen and not any(x in clean for x in ["google.com", "youtube.com/results"]):
            seen.add(clean)
            items.append({
                "title": clean.split("//")[-1][:60],
                "url": clean,
                "source": "Google",
                "points": 0,
                "author": "",
                "created": "",
                "snippet": clean,
            })
    return items[:limit]


def fetch_reddit(topic: str, limit: int, api_key: str) -> list:
    """通过 ScraperAPI 爬取 Reddit 搜索结果。"""
    items = []
    url = SOURCES["reddit"]["search_url"].format(topic=urllib.parse.quote(topic), limit=limit)
    print(f"  📱 采集 Reddit...")
    html = scraperapi_get(url, api_key)
    if not html:
        return items
    # Reddit 搜索页面提取帖子
    pattern = re.findall(r'"title":"([^"]+)"[^}]*"url":"(https?://www\.reddit\.com/r/[^"]+)"', html)
    if not pattern:
        # 备用模式
        pattern = re.findall(r'<a[^>]*href="(https://www\.reddit\.com/r/[^"]+)"[^>]*>([^<]+)</a>', html)
        pattern = [(t, u) for u, t in pattern]
    for title, url in pattern[:limit]:
        items.append({
            "title": title,
            "url": url,
            "source": "Reddit",
            "points": 0,
            "author": "",
            "created": "",
            "snippet": title,
        })
    return items


def fetch_github(topic: str, limit: int, api_key: str) -> list:
    """通过 ScraperAPI 爬取 GitHub 搜索结果。"""
    items = []
    url = SOURCES["github"]["search_url"].format(topic=urllib.parse.quote(topic), limit=limit)
    print(f"  🐙 采集 GitHub...")
    html = scraperapi_get(url, api_key)
    if not html:
        return items
    pattern = re.findall(r'<a[^>]*href="(/[^"]+)"[^>]*class="[^"]*Link[^"]*"[^>]*>\s*(.*?)\s*</a>', html, re.DOTALL)
    for path, title in pattern[:limit * 2]:
        title = re.sub(r"<[^>]+>", "", title).strip()
        if title and path.startswith("/") and not path.startswith("/search") and "/" in path[1:]:
            items.append({
                "title": title,
                "url": f"https://github.com{path}",
                "source": "GitHub",
                "points": 0,
                "author": path.split("/")[1] if len(path.split("/")) > 1 else "",
                "created": "",
                "snippet": title,
            })
    # 去重
    seen = set()
    unique = []
    for item in items:
        if item["url"] not in seen:
            seen.add(item["url"])
            unique.append(item)
    return unique[:limit]


def fetch_producthunt(topic: str, limit: int, api_key: str) -> list:
    """通过 ScraperAPI 爬取 Product Hunt 搜索结果。"""
    items = []
    url = SOURCES["producthunt"]["search_url"].format(topic=urllib.parse.quote(topic), limit=limit)
    print(f"  🚀 采集 Product Hunt...")
    html = scraperapi_get(url, api_key)
    if not html:
        return items
    # Product Hunt 搜索结果提取
    pattern = re.findall(r'<a[^>]*href="(/posts/[^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL)
    for path, title in pattern[:limit * 2]:
        title = re.sub(r"<[^>]+>", "", title).strip()
        if title:
            items.append({
                "title": title,
                "url": f"https://www.producthunt.com{path}",
                "source": "ProductHunt",
                "points": 0,
                "author": "",
                "created": "",
                "snippet": title,
            })
    seen = set()
    unique = []
    for item in items:
        if item["url"] not in seen:
            seen.add(item["url"])
            unique.append(item)
    return unique[:limit]


# ── AI 总结 ──

def ai_summarize(items: list, topic: str, api_key: str, base_url: str, model: str = "gpt-4o-mini") -> str:
    """用 AI 对采集结果进行去重筛选和总结。"""
    if not api_key:
        return ""

    items_text = ""
    for i, item in enumerate(items[:20], 1):
        items_text += f"{i}. [{item['source']}] {item['title']}\n   链接: {item['url']}\n\n"

    system_prompt = """你是一个内容素材分析专家。用户采集了一批关于某个话题的内容素材，你需要：
1. 去除重复和低质量的内容
2. 筛选出最有价值的 5-10 条
3. 用中文为每条写一段简短的价值描述（为什么值得看）
4. 最后给出一个话题趋势观察（2-3句话）

输出格式：
## 精选素材

### 1. 标题
- 来源: xxx
- 链接: xxx
- 价值: 为什么值得看

### 2. ...

## 趋势观察
xxx"""

    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"话题: {topic}\n\n采集到的素材:\n{items_text}"}
        ],
        "temperature": 0.3,
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    })

    try:
        resp = urllib.request.urlopen(req, timeout=60)
        result = json.loads(resp.read())
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"  ⚠️ AI 总结失败: {e}")
        return ""


# ── 输出 ──

def save_results(items: list, summary: str, topic: str, output_dir: str):
    """保存采集结果为 JSON 和 Markdown。"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    slug = re.sub(r"[^\w]", "-", topic.lower())[:30]
    base = f"{output_dir}/{date_str}-{slug}"

    # JSON
    json_path = f"{base}.json"
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "date": date_str,
            "topic": topic,
            "items": items,
            "summary": summary,
            "total": len(items),
        }, f, ensure_ascii=False, indent=2)
    print(f"  📄 JSON: {json_path}")

    # Markdown
    md_path = f"{base}.md"
    md = f"# 素材采集: {topic}\n> {date_str}\n\n"
    md += f"共采集 {len(items)} 条素材\n\n"
    for i, item in enumerate(items, 1):
        md += f"### {i}. {item['title']}\n"
        md += f"- 来源: {item['source']}\n"
        md += f"- 链接: {item['url']}\n"
        if item.get("author"):
            md += f"- 作者: {item['author']}\n"
        if item.get("points"):
            md += f"- 热度: {item['points']}\n"
        md += f"- 摘要: {item.get('snippet', '')}\n\n"
    if summary:
        md += "---\n\n" + summary + "\n"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"  📝 Markdown: {md_path}")

    return json_path, md_path


# ── 主逻辑 ──

def main():
    parser = argparse.ArgumentParser(description="AI 内容素材采集工具")
    parser.add_argument("--topic", required=True, help="采集话题")
    parser.add_argument("--sources", default="hackernews,reddit,web", help="数据源，逗号分隔 (hackernews,reddit,web,github,producthunt)")
    parser.add_argument("--limit", type=int, default=10, help="每个来源最多采集条数")
    parser.add_argument("--output", default="scraped-material", help="输出目录")
    parser.add_argument("--no-ai", action="store_true", help="不使用 AI 总结")
    parser.add_argument("--model", default="gpt-4o-mini", help="AI 模型")
    args = parser.parse_args()

    scraper_key = os.environ.get("SCRAPERAPI_KEY", "")
    ai_key = os.environ.get("OPENAI_API_KEY", "")
    ai_base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

    topic = args.topic
    sources = [s.strip() for s in args.sources.split(",")]
    limit = args.limit

    print(f"🔍 采集话题: {topic}")
    print(f"📡 数据源: {', '.join(sources)}")
    print()

    all_items = []
    scraper_used = False

    # HackerNews 用免费 API，不需要 ScraperAPI
    if "hackernews" in sources:
        print("  🔶 采集 HackerNews（免费 API）...")
        items = fetch_hackernews(topic, limit)
        all_items.extend(items)
        print(f"  ✅ 获取 {len(items)} 条")

    # 其他源需要 ScraperAPI
    scrape_sources = [s for s in sources if s != "hackernews"]
    if scrape_sources and not scraper_key:
        print()
        print(f"⚠️  HackerNews 数据已采集完成（{len(all_items)} 条）")
        print(f"💡 要采集 {', '.join(scrape_sources)} 需要 ScraperAPI key")
        print(f"   免费层 1000 次/月，注册地址: {AFFILIATE_URL}")
        print(f"   设置: export SCRAPERAPI_KEY=你的key")
        print()
        if not all_items:
            print("没有采集到任何数据。")
            sys.exit(0)

    if scrape_sources and scraper_key:
        if "reddit" in sources:
            items = fetch_reddit(topic, limit, scraper_key)
            all_items.extend(items)
            print(f"  ✅ 获取 {len(items)} 条")
            scraper_used = True
            time.sleep(1)

        if "web" in sources:
            items = fetch_google(topic, limit, scraper_key)
            all_items.extend(items)
            print(f"  ✅ 获取 {len(items)} 条")
            scraper_used = True
            time.sleep(1)

        if "github" in sources:
            items = fetch_github(topic, limit, scraper_key)
            all_items.extend(items)
            print(f"  ✅ 获取 {len(items)} 条")
            scraper_used = True
            time.sleep(1)

        if "producthunt" in sources:
            items = fetch_producthunt(topic, limit, scraper_key)
            all_items.extend(items)
            print(f"  ✅ 获取 {len(items)} 条")
            scraper_used = True
            time.sleep(1)

    print()
    print(f"📊 共采集 {len(all_items)} 条素材")

    # AI 总结
    summary = ""
    if not args.no_ai and all_items:
        if ai_key:
            print("🤖 AI 正在分析筛选...")
            summary = ai_summarize(all_items, topic, ai_key, ai_base, args.model)
            if summary:
                print("✅ AI 总结完成")
        else:
            print("💡 加 AI 总结功能？设置 OPENAI_API_KEY 环境变量")

    # 保存
    json_path, md_path = save_results(all_items, summary, topic, args.output)
    print()
    print(f"🎉 采集完成！")

    # 提示 ScraperAPI
    if not scraper_used and scrape_sources:
        print()
        print(f"💡 解锁更多数据源（Reddit、Google、GitHub、Product Hunt），注册 ScraperAPI:")
        print(f"   {AFFILIATE_URL}")
        print(f"   免费层 1000 次/月 → 设置: export SCRAPERAPI_KEY=你的key")


if __name__ == "__main__":
    main()
