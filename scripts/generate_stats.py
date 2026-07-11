#!/usr/bin/env python3
"""Generate self-hosted GitHub stats SVG cards (onedark theme).

Fetches data from the GitHub API and renders two SVGs into assets/:
  - top-langs.svg : language composition bar + legend
  - stats.svg     : stat tiles (stars / commits / PRs / issues)

Requires: GITHUB_TOKEN env var. Stdlib only.
"""

import json
import os
import urllib.request

USERNAME = "hiroky1983"
EXCLUDE_REPOS = {"MAMP", "fullstack-webdev"}
TOP_N = 6
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")

TOKEN = os.environ["GITHUB_TOKEN"]
API = "https://api.github.com"

# onedark
BG = "#282c34"
BORDER = "#3e4451"
TITLE = "#61afef"
TEXT = "#abb2bf"
MUTED = "#8b929e"
VALUE = "#dcdfe4"

# GitHub linguist colors for the languages that appear in this account
LANG_COLORS = {
    "Dart": "#00B4AB",
    "TypeScript": "#3178c6",
    "Go": "#00ADD8",
    "Swift": "#F05138",
    "Python": "#3572A5",
    # linguist PHP (#4F5D95) is CVD-indistinguishable from Python blue when
    # adjacent in the bar; use a lighter indigo that keeps ΔE >= 8 (protan/deutan)
    "PHP": "#9FA8DA",
    "JavaScript": "#f1e05a",
    "HTML": "#e34c26",
    "CSS": "#663399",
    "C++": "#f34b7d",
    "Shell": "#89e051",
    "Ruby": "#701516",
    "Rust": "#dea584",
    "Kotlin": "#A97BFF",
    "Java": "#b07219",
}
OTHER_COLOR = "#5c6370"


def api_get(path):
    req = urllib.request.Request(
        API + path,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "User-Agent": USERNAME,
        },
    )
    with urllib.request.urlopen(req) as res:
        return json.loads(res.read())


def graphql(query):
    req = urllib.request.Request(
        API + "/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "User-Agent": USERNAME,
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as res:
        return json.loads(res.read())


def fetch_repos():
    repos, page = [], 1
    while True:
        batch = api_get(f"/users/{USERNAME}/repos?per_page=100&type=owner&page={page}")
        repos.extend(batch)
        if len(batch) < 100:
            return repos
        page += 1


def fetch_data():
    repos = [
        r for r in fetch_repos()
        if not r["fork"] and r["name"] not in EXCLUDE_REPOS
    ]
    langs = {}
    for r in repos:
        for lang, size in api_get(f"/repos/{USERNAME}/{r['name']}/languages").items():
            langs[lang] = langs.get(lang, 0) + size

    stars = sum(r["stargazers_count"] for r in repos)
    commits = graphql(
        f'{{ user(login: "{USERNAME}") {{ contributionsCollection {{ totalCommitContributions }} }} }}'
    )["data"]["user"]["contributionsCollection"]["totalCommitContributions"]
    prs = api_get(f"/search/issues?q=author:{USERNAME}+type:pr")["total_count"]
    issues = api_get(f"/search/issues?q=author:{USERNAME}+type:issue")["total_count"]
    return langs, {"stars": stars, "commits": commits, "prs": prs, "issues": issues}


def top_langs(langs):
    total = sum(langs.values())
    ranked = sorted(langs.items(), key=lambda kv: -kv[1])
    top = [(name, size / total) for name, size in ranked[:TOP_N]]
    rest = 1.0 - sum(share for _, share in top)
    if rest > 0.005:
        top.append(("Other", rest))
    return top


def card(width, height, title, body):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{title}">
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="8" fill="{BG}" stroke="{BORDER}"/>
  <text x="20" y="30" font-family="'Segoe UI', Ubuntu, sans-serif" font-size="15" font-weight="600" fill="{TITLE}">{title}</text>
{body}
</svg>
"""


def render_top_langs(shares):
    w, h = 320, 165
    bar_x, bar_y, bar_w, bar_h, gap = 20, 46, w - 40, 10, 2
    gaps_total = gap * (len(shares) - 1)
    body = [
        f'  <clipPath id="bar"><rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="{bar_h / 2}"/></clipPath>',
        '  <g clip-path="url(#bar)">',
    ]
    x = float(bar_x)
    for name, share in shares:
        seg_w = share * (bar_w - gaps_total)
        color = LANG_COLORS.get(name, OTHER_COLOR)
        body.append(
            f'    <rect x="{x:.1f}" y="{bar_y}" width="{seg_w:.1f}" height="{bar_h}" fill="{color}"/>'
        )
        x += seg_w + gap
    body.append("  </g>")

    for i, (name, share) in enumerate(shares):
        col, row = i % 2, i // 2
        lx = 20 + col * 150
        ly = 84 + row * 24
        color = LANG_COLORS.get(name, OTHER_COLOR)
        body.append(f'  <circle cx="{lx + 4}" cy="{ly - 4}" r="4" fill="{color}"/>')
        body.append(
            f'  <text x="{lx + 14}" y="{ly}" font-family="\'Segoe UI\', Ubuntu, sans-serif" font-size="12" fill="{TEXT}">{name} <tspan fill="{MUTED}">{share * 100:.1f}%</tspan></text>'
        )
    return card(w, h, "Top Languages", "\n".join(body))


def render_stats(stats):
    w, h = 320, 165
    tiles = [
        ("Total Stars", stats["stars"], "#e5c07b"),
        ("Commits (past year)", stats["commits"], "#c678dd"),
        ("Pull Requests", stats["prs"], "#61afef"),
        ("Issues", stats["issues"], "#98c379"),
    ]
    body = []
    for i, (label, value, accent) in enumerate(tiles):
        col, row = i % 2, i // 2
        tx = 20 + col * 150
        ty = 62 + row * 52
        body.append(
            f'  <rect x="{tx}" y="{ty - 16}" width="3" height="34" rx="1.5" fill="{accent}"/>'
        )
        body.append(
            f'  <text x="{tx + 12}" y="{ty}" font-family="\'Segoe UI\', Ubuntu, sans-serif" font-size="20" font-weight="700" fill="{VALUE}">{value:,}</text>'
        )
        body.append(
            f'  <text x="{tx + 12}" y="{ty + 16}" font-family="\'Segoe UI\', Ubuntu, sans-serif" font-size="11" fill="{MUTED}">{label}</text>'
        )
    return card(w, h, "GitHub Stats", "\n".join(body))


def main():
    langs, stats = fetch_data()
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "top-langs.svg"), "w") as f:
        f.write(render_top_langs(top_langs(langs)))
    with open(os.path.join(OUT_DIR, "stats.svg"), "w") as f:
        f.write(render_stats(stats))
    print("generated:", stats, "| top langs:", [n for n, _ in top_langs(langs)])


if __name__ == "__main__":
    main()
