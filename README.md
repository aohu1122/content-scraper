# Content Scraper — AI Content Collection Skill

> Multi-source content collector for AI agents. Scrape HackerNews, Reddit, Google, GitHub, Product Hunt with AI-powered dedup and summarization.

## Features

- 🔄 **Multi-source scraping** — 5 data sources with one command
- 🤖 **AI dedup & summary** — Automatically removes duplicates and generates structured summaries
- 📄 **Dual output** — JSON for programs + Markdown for humans
- 🔑 **Zero-config start** — HackerNews works out of the box, no keys needed
- 🧩 **OpenClaw / Claude Code / Codex compatible** — Standard `SKILL.md` format

## Quick Start

```bash
# HackerNews only (free, no keys)
python3 scripts/content_scraper.py --topic "AI Agent latest news"

# All sources (requires ScraperAPI key)
SCRAPERAPI_KEY=your_key python3 scripts/content_scraper.py --topic "AI Agent"

# Specific sources
python3 scripts/content_scraper.py --topic "AI Agent" --sources hackernews,reddit,github

# With AI summary
SCRAPERAPI_KEY=your_key OPENAI_API_KEY=your_key \
  python3 scripts/content_scraper.py --topic "AI Agent"
```

## Data Sources

| Source | Requires Key | Description |
|--------|:---:|------|
| HackerNews | ❌ | Free via Algolia API |
| Reddit | ✅ | Community discussions and opinions |
| Google Search | ✅ | General web search |
| GitHub | ✅ | Open source projects |
| Product Hunt | ✅ | New product discovery |

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|:---:|------|
| `SCRAPERAPI_KEY` | Partial | Free tier: 1,000 requests/month |
| `OPENAI_API_KEY` | No | For AI summarization |
| `OPENAI_BASE_URL` | No | Default: OpenAI, supports compatible APIs |

### Get ScraperAPI Key

HackerNews is free. Other sources require [ScraperAPI](https://www.scraperapi.com/?fp_ref=harel38):

- Free tier: 1,000 requests/month
- Auto proxy rotation, anti-bot, CAPTCHA handling
- Pay-as-you-go

```bash
export SCRAPERAPI_KEY="your_key"
```

## Output

Each run produces two files:
- **JSON** — Structured data for programmatic use
- **Markdown** — Human-readable list with AI summary

## Installation as AI Agent Skill

### OpenClaw
```bash
clawhub install content-scraper
```

### Claude Code / Codex CLI
Clone this repo into your `.claude/skills/` or `.codex/skills/` directory. The `SKILL.md` file is auto-detected.

### Manual
```bash
git clone https://github.com/aohu1122/content-scraper.git
```

## Requirements

- Python 3.8+
- No external dependencies (pure stdlib)

## License

MIT
