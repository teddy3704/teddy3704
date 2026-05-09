#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET


REPO_ROOT = Path(__file__).resolve().parents[1]
SVG_PATH = REPO_ROOT / "assets" / "profile-overview-live.svg"
GRAPHQL_URL = "https://api.github.com/graphql"
SVG_NS = "http://www.w3.org/2000/svg"
BAR_WIDTH = 320

GRAPHQL_QUERY = """
query ProfileOverview($login: String!) {
  user(login: $login) {
    repositories(
      first: 100
      ownerAffiliations: OWNER
      privacy: PUBLIC
      isFork: false
      orderBy: {field: PUSHED_AT, direction: DESC}
    ) {
      totalCount
      nodes {
        name
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges {
            size
            node {
              name
            }
          }
        }
      }
    }
    pinnedItems(first: 6, types: REPOSITORY) {
      totalCount
    }
    contributionsCollection {
      totalCommitContributions
    }
  }
}
"""

LANGUAGE_BUCKETS = {
    "typescript": {
        "label": "TypeScript",
        "names": {"TypeScript"},
    },
    "python": {
        "label": "Python",
        "names": {"Python"},
    },
    "htmlcss": {
        "label": "HTML / CSS",
        "names": {"HTML", "CSS", "SCSS", "Sass", "Less"},
    },
    "java": {
        "label": "Java",
        "names": {"Java"},
    },
}

SAMPLE_DATA = {
    "public_repos": 20,
    "curated_pins": 4,
    "total_commits": 75,
    "language_percentages": {
        "typescript": 91,
        "python": 83,
        "htmlcss": 74,
        "java": 66,
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update the profile overview SVG from GitHub data.")
    parser.add_argument("--login", default=os.environ.get("GITHUB_REPOSITORY_OWNER") or os.environ.get("GITHUB_ACTOR") or "teddy3704")
    parser.add_argument("--svg-path", default=str(SVG_PATH))
    parser.add_argument("--source", choices=("live", "sample"), default="live")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def github_graphql_request(login: str, token: str) -> dict[str, Any]:
    payload = json.dumps({"query": GRAPHQL_QUERY, "variables": {"login": login}}).encode("utf-8")
    request = urllib.request.Request(
        GRAPHQL_URL,
        data=payload,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "teddy3704-profile-overview-updater",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"GitHub GraphQL request failed with HTTP {exc.code}.") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"GitHub GraphQL request failed: {exc.reason}") from exc

    payload_data = json.loads(body)
    if payload_data.get("errors"):
        messages = "; ".join(error.get("message", "Unknown GraphQL error") for error in payload_data["errors"])
        raise SystemExit(f"GitHub GraphQL returned errors: {messages}")

    return payload_data["data"]


def normalize_language_footprint(repositories: list[dict[str, Any]]) -> dict[str, int]:
    sizes = {bucket: 0 for bucket in LANGUAGE_BUCKETS}

    for repository in repositories:
        languages = repository.get("languages") or {}
        for edge in languages.get("edges") or []:
            language_name = edge["node"]["name"]
            language_size = edge.get("size", 0)
            for bucket, metadata in LANGUAGE_BUCKETS.items():
                if language_name in metadata["names"]:
                    sizes[bucket] += language_size
                    break

    total_size = sum(sizes.values())
    if total_size == 0:
        return dict(SAMPLE_DATA["language_percentages"])

    percentages = {
        bucket: max(0, min(100, round((size / total_size) * 100)))
        for bucket, size in sizes.items()
    }

    if percentages and sum(percentages.values()) == 0:
        return dict(SAMPLE_DATA["language_percentages"])

    return percentages


def fetch_live_data(login: str) -> dict[str, Any]:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("Set GH_TOKEN or GITHUB_TOKEN before running with --source live.")

    response = github_graphql_request(login, token)
    user = response.get("user")
    if not user:
        raise SystemExit(f"Unable to find GitHub user '{login}'.")

    repositories = user["repositories"]
    language_percentages = normalize_language_footprint(repositories.get("nodes") or [])
    tracked_language_count = sum(1 for value in language_percentages.values() if value > 0)

    return {
        "public_repos": repositories["totalCount"],
        "curated_pins": user["pinnedItems"]["totalCount"],
        "total_commits": user["contributionsCollection"]["totalCommitContributions"],
        "language_percentages": language_percentages,
        "tracked_language_count": tracked_language_count,
    }


def compact_number(value: int) -> str:
    if value < 1000:
        return str(value)
    if value < 1000000:
        return f"{value / 1000:.1f}k".rstrip("0").rstrip(".")
    return f"{value / 1000000:.1f}m".rstrip("0").rstrip(".")


def update_text(root: ET.Element, element_id: str, text: str) -> None:
    node = root.find(f".//svg:text[@id='{element_id}']", {"svg": SVG_NS})
    if node is None:
        raise SystemExit(f"SVG text node '{element_id}' was not found.")
    node.text = text


def update_rect_width(root: ET.Element, element_id: str, width: int) -> None:
    node = root.find(f".//svg:rect[@id='{element_id}']", {"svg": SVG_NS})
    if node is None:
        raise SystemExit(f"SVG rect node '{element_id}' was not found.")
    node.set("width", str(width))


def update_svg(svg_path: Path, login: str, stats: dict[str, Any]) -> None:
    ET.register_namespace("", SVG_NS)
    tree = ET.parse(svg_path)
    root = tree.getroot()

    tracked_language_count = stats.get("tracked_language_count")
    if tracked_language_count is None:
        tracked_language_count = sum(1 for value in stats["language_percentages"].values() if value > 0)

    description = root.find(".//svg:desc", {"svg": SVG_NS})
    if description is not None:
        description.text = (
            f"A self-hosted overview card showing live public GitHub metrics and language footprint for {login}."
        )

    update_text(root, "metric-public-repos", compact_number(stats["public_repos"]))
    update_text(root, "metric-curated-pins", compact_number(stats["curated_pins"]))
    update_text(root, "metric-last-12m-commits", compact_number(stats["total_commits"]))
    update_text(root, "metric-primary-languages", compact_number(tracked_language_count))

    for bucket in LANGUAGE_BUCKETS:
        percentage = max(0, min(100, int(stats["language_percentages"].get(bucket, 0))))
        update_rect_width(root, f"lang-bar-{bucket}", round((percentage / 100) * BAR_WIDTH))
        update_text(root, f"lang-pct-{bucket}", f"{percentage}%")

    ET.indent(tree, space="  ")
    tree.write(svg_path, encoding="utf-8", xml_declaration=False)


def main() -> int:
    args = parse_args()
    svg_path = Path(args.svg_path)

    if args.source == "sample":
        stats = {
            **SAMPLE_DATA,
            "tracked_language_count": sum(
                1 for value in SAMPLE_DATA["language_percentages"].values() if value > 0
            ),
        }
    else:
        stats = fetch_live_data(args.login)

    if not args.dry_run:
        update_svg(svg_path, args.login, stats)

    print(
        json.dumps(
            {
                "login": args.login,
                "svg_path": str(svg_path),
                "source": args.source,
                "dry_run": args.dry_run,
                "stats": stats,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())