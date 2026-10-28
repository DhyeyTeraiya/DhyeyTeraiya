"""Regenerate the figures rendered in ``milestone_stats.svg``.

``milestone_stats.svg`` is a static asset: the artwork is hand-drawn, but the
numbers inside it must come from an API rather than from memory. This script
rewrites exactly two values, in place:

    * public repository count          — REST ``/users/{login}``
    * contributions in the last year   — GraphQL ``contributionsCollection``,
      falling back to the public contribution calendar page when the token in
      use cannot read that field (the Actions ``GITHUB_TOKEN`` cannot query
      another user, so the fallback is the normal path in CI)

Design rules:
    * every substitution must match exactly once, so a silent no-op (which is
      how the previous version of this script failed — its regexes matched
      nothing for months) raises instead of passing quietly;
    * the file is only rewritten when a value actually changed, so the daily
      workflow does not create empty commits;
    * failures exit non-zero, so the Actions run goes red instead of printing
      an error into a green build.

Usage::

    GITHUB_TOKEN=... python scripts/update_stats.py
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import requests

USERNAME = "DhyeyTeraiya"
REPO_ROOT = Path(__file__).resolve().parents[1]
SVG_PATH = REPO_ROOT / "milestone_stats.svg"
USER_AGENT = "dhyey-profile-stats/2.0"

CONTRIBUTION_QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
      }
    }
  }
}
"""


def _token() -> str:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN is not set")
    return token


def public_repository_count(token: str) -> int:
    response = requests.get(
        f"https://api.github.com/users/{USERNAME}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
        },
        timeout=30,
    )
    response.raise_for_status()
    return int(response.json()["public_repos"])


def contributions_last_year(token: str) -> int:
    """GraphQL first; fall back to the public calendar when the token is denied."""
    try:
        response = requests.post(
            "https://api.github.com/graphql",
            json={"query": CONTRIBUTION_QUERY, "variables": {"login": USERNAME}},
            headers={"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("errors"):
            calendar = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]
            if calendar and calendar.get("totalContributions") is not None:
                return int(calendar["totalContributions"])
        print("GraphQL did not expose the calendar; using the public page", file=sys.stderr)
    except (requests.RequestException, KeyError, TypeError) as exc:
        print(f"GraphQL contributions unavailable ({exc}); using the public page", file=sys.stderr)

    return _contributions_from_public_page()


def _contributions_from_public_page() -> int:
    response = requests.get(
        f"https://github.com/users/{USERNAME}/contributions",
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    response.raise_for_status()
    match = re.search(r"([\d,]+)\s+contributions?\s+in\s+the\s+last\s+year", response.text)
    if not match:
        raise RuntimeError("could not read the contribution total from the public calendar page")
    return int(match.group(1).replace(",", ""))


def _replace_once(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text)
    if count != 1:
        raise RuntimeError(f"expected exactly one {label} in the SVG, matched {count}")
    return updated


def render(svg: str, repositories: int, contributions: int) -> str:
    svg = _replace_once(
        svg, r">[^<]*Public Repositories<", f">{repositories} Public Repositories<", "repository count"
    )
    svg = _replace_once(
        svg, r">[^<]*Contributions<", f">{contributions:,} Contributions<", "contribution count"
    )
    return svg


def main() -> int:
    token = _token()
    repositories = public_repository_count(token)
    contributions = contributions_last_year(token)
    print(f"public repos: {repositories}  contributions (last year): {contributions}")

    current = SVG_PATH.read_text(encoding="utf-8")
    updated = render(current, repositories, contributions)

    if updated == current:
        print("milestone_stats.svg is already current")
        return 0

    SVG_PATH.write_text(updated, encoding="utf-8")
    print(f"updated {SVG_PATH.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
