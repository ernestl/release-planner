#!/usr/bin/env python3
"""Generate an HTML release-plan diagram from YAML input."""

from __future__ import annotations

import argparse
import calendar
import shutil
from datetime import date, datetime, timedelta
import math
from pathlib import Path
import re
import textwrap
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

# One hue per release pack, in first-seen order. Bugfix and security use lighter steps.
RELEASE_PACK_PALETTE = [
    ("#5b21b6", "#4c1d95"),
    ("#1d4ed8", "#1e40af"),
    ("#0f766e", "#115e59"),
    ("#be185d", "#9d174d"),
    ("#b45309", "#92400e"),
    ("#047857", "#065f46"),
]


def parse_args() -> argparse.Namespace:
    root = Path(__file__).parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        default=str(root / "data" / "snapd-27.04.yaml"),
        help="Path to release-plan YAML file.",
    )
    parser.add_argument(
        "--template",
        default=str(root / "templates" / "plan.html.j2"),
        help="Path to Jinja2 HTML template.",
    )
    parser.add_argument(
        "--output",
        default=str(root / "output" / "plan.html"),
        help="Path to generated HTML output.",
    )
    parser.add_argument(
        "--svg",
        default=str(root / "output" / "plan.svg"),
        help="Path to generated standalone SVG output.",
    )
    parser.add_argument(
        "--svg-template",
        default=str(root / "templates" / "plan.svg.j2"),
        help="Path to Jinja2 SVG template.",
    )
    parser.add_argument(
        "--reference-date",
        default=date.today().isoformat(),
        help="Reference date for calculating metrics (YYYY-MM-DD, default: today)",
    )
    return parser.parse_args()


def read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("YAML top-level value must be an object.")
    return data


def sanitize_id(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]", "_", value.strip())
    if not normalized:
        raise ValueError("Milestone id cannot be empty.")
    if not re.match(r"^[A-Za-z_]", normalized):
        normalized = f"m_{normalized}"
    return normalized


def parse_cycle(cycle: str) -> tuple[int, int]:
    match = re.match(r"^(\d{2})\.(\d{2})$", cycle.strip())
    if not match:
        raise ValueError("cycle must match yy.mm, for example '26.10'.")

    year = 2000 + int(match.group(1))
    month = int(match.group(2))
    if month < 1 or month > 12:
        raise ValueError("cycle month must be between 01 and 12.")
    return year, month


def shift_months(input_date: date, months: int) -> date:
    month_index = input_date.year * 12 + (input_date.month - 1) + months
    year = month_index // 12
    month = month_index % 12 + 1
    day = min(input_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def compute_window(cycle: str, plan: dict[str, Any] | None = None) -> dict[str, Any]:
    explicit = (plan or {}).get("window")
    if isinstance(explicit, dict) and explicit.get("start") and explicit.get("end"):
        return _explicit_window(cycle, explicit)

    year, month = parse_cycle(cycle)
    month_last_day = calendar.monthrange(year, month)[1]
    cycle_end = date(year, month, month_last_day)

    six_month_start = shift_months(cycle_end, -6)
    exact_days = (cycle_end - six_month_start).days + 1

    # Weekly grid is Monday-based to align by-week YAML semantics.
    rounded_start = six_month_start - timedelta(days=six_month_start.weekday())
    days_from_rounded_start = (cycle_end - rounded_start).days + 1
    rounded_weeks = math.ceil(days_from_rounded_start / 7)
    rounded_end = rounded_start + timedelta(days=rounded_weeks * 7 - 1)

    return {
        "cycle": cycle,
        "year": year,
        "month": month,
        "window_start": rounded_start,
        "window_end": rounded_end,
        "cycle_end": cycle_end,
        "exact_start": six_month_start,
        "base_weeks": rounded_weeks,
        "exact_days": exact_days,
        "explicit": False,
    }


def _explicit_window(cycle: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Chart a declared cycle, with optional whole weeks of padding on each side."""
    year, month = parse_cycle(cycle)
    cycle_start = parse_date_value(str(raw.get("start", "")))
    cycle_end = parse_date_value(str(raw.get("end", "")))
    if cycle_start.weekday() != 0:
        raise ValueError("window.start must be a Monday.")
    if cycle_end < cycle_start:
        raise ValueError("window.end must be on or after window.start.")

    pad_before = int(raw.get("pad_before_weeks", 0))
    pad_after = int(raw.get("pad_after_weeks", 0))
    if pad_before < 0 or pad_after < 0:
        raise ValueError("window padding must be >= 0.")

    cycle_last_monday = cycle_end - timedelta(days=cycle_end.weekday())
    cycle_weeks = ((cycle_last_monday - cycle_start).days // 7) + 1
    window_start = cycle_start - timedelta(days=pad_before * 7)
    # Include the week that contains cycle_end, then pad_after further weeks.
    window_end = cycle_last_monday + timedelta(days=(1 + pad_after) * 7 - 1)
    chart_weeks = ((window_end - window_start).days + 1) // 7

    return {
        "cycle": cycle,
        "year": year,
        "month": month,
        "window_start": window_start,
        "window_end": window_end,
        "cycle_start": cycle_start,
        "cycle_end": cycle_end,
        "cycle_weeks": cycle_weeks,
        "exact_start": cycle_start,
        "base_weeks": chart_weeks,
        "exact_days": (cycle_end - cycle_start).days + 1,
        "explicit": True,
    }


def week_start_date(year: int, week: int) -> date:
    if week < 1 or week > 53:
        raise ValueError(f"Week must be in range 1..53, got {week}.")

    # Week 1 is anchored to the first Monday of the calendar year.
    anchor = first_monday_of_year(year)
    return anchor + timedelta(days=(week - 1) * 7)


def month_final_week_start(year: int, month: int) -> date:
    if month < 1 or month > 12:
        raise ValueError(f"Month must be in range 1..12, got {month}.")
    last_day = date(year, month, calendar.monthrange(year, month)[1])
    return last_day - timedelta(days=last_day.weekday())


def first_monday_of_year(year: int) -> date:
    jan1 = date(year, 1, 1)
    return jan1 + timedelta(days=(7 - jan1.weekday()) % 7)


def resolve_week_start(week: int, year: int, cycle_start: date | None = None) -> date:
    """Calendar business week, or a cycle week counted from cycle_start."""
    if cycle_start is not None:
        if week < 1:
            raise ValueError(f"Cycle week must be >= 1, got {week}.")
        return cycle_start + timedelta(days=(week - 1) * 7)
    return week_start_date(year, week)


def resolve_event_start(
    event: dict[str, Any],
    year: int,
    cycle_start: date | None = None,
) -> date | None:
    kind = str(event.get("kind", "")).strip()
    if kind == "by-week":
        return resolve_week_start(int(event.get("week")), year, cycle_start)
    if kind == "by-month-final-week":
        return month_final_week_start(year, int(event.get("month")))
    if kind == "by-date":
        value = str(event.get("date", "")).strip()
        return parse_date_value(value)
    if kind == "by-lookup":
        return None
    raise ValueError(f"Unsupported event kind: {kind}")


def parse_date_value(value: str) -> date:
    text = value.strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unsupported date format: {value}. Use YYYY-MM-DD or DD-MM-YYYY.")


def normalize_ref_text(value: str) -> str:
    # Normalize loose human references like "24.04.5 content freeze".
    return " ".join(value.replace(":", " ").lower().split())


def within_window(start: date, duration_weeks: int, window_start: date, window_end: date) -> bool:
    end = start + timedelta(days=duration_weeks * 7 - 1)
    return end >= window_start and start <= window_end


def normalize_named_events(
    events: list[dict[str, Any]],
    section: str,
    year: int,
    window_start: date,
    window_end: date,
    constrain_to_window: bool = True,
    cycle_start: date | None = None,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    section_lower = section.lower()
    suffix_by_section = {
        "sprints": " sprint",
        "holidays": " holiday",
    }
    suffix = suffix_by_section.get(section_lower, "")

    for index, raw in enumerate(events, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"Each {section.lower()} entry must be an object.")

        name = str(raw.get("name", "")).strip()
        if not name:
            raise ValueError(f"Each {section.lower()} entry must include a non-empty name.")

        start = resolve_event_start(raw, year, cycle_start)
        if start is None:
            continue

        end_text = str(raw.get("end", "")).strip()
        if end_text:
            end = parse_date_value(end_text)
            if end < start:
                raise ValueError(f"{section} '{name}' end date is before its start date.")
            span_days = (end - start).days + 1
            duration_weeks = max(1, (span_days + 6) // 7)
        else:
            duration_weeks = int(raw.get("duration", 1))
            if duration_weeks <= 0:
                raise ValueError(f"{section} '{name}' must have duration > 0.")
            end = event_end_date(start, duration_weeks)

        if constrain_to_window and (end < window_start or start > window_end):
            continue

        normalized.append(
            {
                "id": sanitize_id(f"{section.lower()}_{index}_{name}"),
                "name": name,
                "label": f"{name}{suffix}",
                "range_label": f"{start.strftime('%d-%m')} to {end.strftime('%d-%m')}",
                "section": section,
                "start": start,
                "end": end,
                "duration_weeks": duration_weeks,
            }
        )
    return normalized


def stretch_window_to_events(window: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    if not events:
        return window

    start_bound = window["window_start"]
    end_bound = window["window_end"]

    event_starts = [event["start"] for event in events]
    event_ends = [resolve_event_end(event) for event in events]

    stretched_start = min([start_bound, *event_starts])
    stretched_end = max([end_bound, *event_ends])

    stretched_weeks = ((stretched_end - stretched_start).days + 1) // 7

    updated = dict(window)
    updated["window_start"] = stretched_start
    updated["window_end"] = stretched_end
    updated["base_weeks"] = stretched_weeks
    return updated


def normalize_releases(
    releases: list[dict[str, Any]],
    year: int,
    window_start: date,
    window_end: date,
    cycle_start: date | None = None,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    previous_start: date | None = None
    set_child_counts: dict[str, int] = {}

    def release_set_key(name: str) -> str:
        # Treat major.minor as a release set (e.g. 2.76, 2.76.1, 2.76.2 -> 2.76).
        match = re.match(r"^(\d+\.\d+)", name)
        if match:
            return match.group(1)
        fallback = re.match(r"^(\d+)", name)
        if fallback:
            return fallback.group(1)
        return name

    for index, raw in enumerate(releases, start=1):
        if not isinstance(raw, dict):
            raise ValueError("Each releases entry must be an object.")

        name = str(raw.get("name", "")).strip()
        if not name:
            raise ValueError("Each releases entry must include a non-empty name.")

        duration_weeks = int(raw.get("duration", 1))
        if duration_weeks <= 0:
            raise ValueError(f"Release '{name}' must have duration > 0.")
        extend_days = int(raw.get("extend_days", 0))
        if extend_days < 0:
            raise ValueError(f"Release '{name}' extend_days must be >= 0.")
        shift_days = int(raw.get("shift_days", 0))

        kind = str(raw.get("kind", "by-week")).strip()
        start: date | None = None
        if kind == "by-week":
            if "week" in raw:
                start = resolve_week_start(int(raw.get("week")), year, cycle_start)
            elif "offset" in raw:
                if previous_start is None:
                    raise ValueError(
                        f"Release '{name}' uses offset but no previous release exists."
                    )
                start = previous_start + timedelta(days=int(raw.get("offset")) * 7)
            else:
                raise ValueError(
                    f"Release '{name}' must define either week or offset for kind by-week."
                )
        elif kind == "by-date":
            start = date.fromisoformat(str(raw.get("date", "")).strip())
        elif kind == "by-month-final-week":
            start = month_final_week_start(year, int(raw.get("month")))
        elif kind == "by-lookup":
            start = None
        else:
            raise ValueError(f"Unsupported release kind: {kind}")

        if start is None:
            continue

        start += timedelta(days=shift_days)
        previous_start = start

        purpose = str(raw.get("purpose", "")).strip()
        label = f"{name} release"
        if purpose:
            label = f"{name} release: {purpose}"

        raw_linkto = raw.get("links_to")
        if raw_linkto is None:
            raw_linkto = raw.get("linkto", "")
        linkto_values: list[str]
        if isinstance(raw_linkto, list):
            linkto_values = [str(value).strip() for value in raw_linkto if str(value).strip()]
        elif isinstance(raw_linkto, str):
            linkto_values = [raw_linkto.strip()] if raw_linkto.strip() else []
        elif raw_linkto is None:
            linkto_values = []
        else:
            raise ValueError(
                f"Release '{name}' links_to/linkto must be string or list of strings."
            )

        linkto_refs = [normalize_ref_text(value) for value in linkto_values]

        set_key = release_set_key(name)
        set_child_index = set_child_counts.get(set_key, 0)
        set_child_counts[set_key] = set_child_index + 1

        normalized.append(
            {
                "id": sanitize_id(f"release_{index}_{name}"),
                "name": name,
                "label": label,
                "purpose": purpose,
                "linkto": linkto_values,
                "linkto_refs": linkto_refs,
                "section": "Releases",
                "set_key": set_key,
                "set_child_index": set_child_index,
                "start": start,
                "end": event_end_date(start, duration_weeks) + timedelta(days=extend_days),
                "duration_weeks": duration_weeks,
            }
        )

    return normalized


def build_release_sets(releases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sets_by_key: dict[str, dict[str, Any]] = {}
    ordered_keys: list[str] = []

    for release in releases:
        key = str(release.get("set_key", "unknown"))
        if key not in sets_by_key:
            sets_by_key[key] = {"key": key, "children": []}
            ordered_keys.append(key)
        sets_by_key[key]["children"].append(release)

    return [sets_by_key[key] for key in ordered_keys]


def normalize_deadlines(
    deadlines: list[dict[str, Any]],
    year: int,
    window_start: date,
    window_end: date,
    cycle_start: date | None = None,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    group_row_index: dict[str, int] = {}

    for index, raw in enumerate(deadlines, start=1):
        if not isinstance(raw, dict):
            raise ValueError("Each deadlines entry must be an object.")

        release = str(raw.get("release", "")).strip()
        purpose = str(raw.get("purpose", "")).strip()
        if not release and not purpose:
            raise ValueError("Each deadlines entry must include release and/or purpose.")

        start = resolve_event_start(raw, year, cycle_start)
        if start is None:
            continue

        if not within_window(start, 1, window_start, window_end):
            continue

        label = release
        if purpose:
            label = f"{release}: {purpose}" if release else purpose

        deadline_ref = normalize_ref_text(f"{release} {purpose}".strip())

        # Same release values share a horizontal milestone row.
        group_key = release if release else f"__deadline_{index}"
        if group_key not in group_row_index:
            group_row_index[group_key] = len(group_row_index)
        row_index = group_row_index[group_key]

        normalized.append(
            {
                "id": sanitize_id(f"deadline_{index}_{label}"),
                "name": label,
                "label": label,
                "release": release,
                "purpose": purpose,
                "deadline_group_key": group_key,
                "deadline_group_index": row_index,
                "deadline_ref": deadline_ref,
                "section": "Deadlines",
                "start": start,
                "duration_weeks": 1,
            }
        )

    return normalized


def normalize_sources(plan: dict[str, Any]) -> list[dict[str, str]]:
    raw = plan.get("sources", [])
    if not raw:
        return []
    if not isinstance(raw, list):
        raise ValueError("'sources' must be a list.")
    sources: list[dict[str, str]] = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Source {index} must be an object.")
        name = str(item.get("name", "")).strip()
        release = str(item.get("release", "")).strip()
        url = str(item.get("url", "")).strip()
        if not name or not url:
            raise ValueError(f"Source {index} needs a name and a url.")
        sources.append({"name": name, "release": release, "url": url})
    return sources


def parse_pulse_range(plan: dict[str, Any]) -> tuple[int, int]:
    pulses = plan.get("pulses", {})
    if not isinstance(pulses, dict):
        return (1, 53)

    start = pulses.get("start", {})
    end = pulses.get("end", {})
    if not isinstance(start, dict) or not isinstance(end, dict):
        return (1, 53)

    start_week = int(start.get("week", 1))
    end_week = int(end.get("week", 53))
    if start_week < 1 or start_week > 53:
        raise ValueError("pulses.start.week must be in range 1..53")
    if end_week < 1 or end_week > 53:
        raise ValueError("pulses.end.week must be in range 1..53")
    if start_week > end_week:
        raise ValueError("pulses.start.week must be <= pulses.end.week")
    return (start_week, end_week)


def build_plan(plan: dict[str, Any]) -> dict[str, Any]:
    cycle = str(plan.get("cycle", "")).strip()
    if not cycle:
        raise ValueError("YAML must define a cycle, for example '26.10'.")

    window = compute_window(cycle, plan)
    year = int(window["year"])
    explicit = bool(window.get("explicit"))
    cycle_start = window.get("cycle_start") if explicit else None
    window_start = window["window_start"]
    window_end = window["window_end"]

    releases_raw = plan.get("snapd_releases")
    if releases_raw is None:
        releases_raw = plan.get("snapd-releases")
    if releases_raw is None:
        releases_raw = plan.get("releases", [])
    deadlines_raw = plan.get("deadlines", [])
    sprints_raw = plan.get("sprints", [])
    holidays_raw = plan.get("holidays", [])

    if not isinstance(releases_raw, list):
        raise ValueError("'snapd_releases' (or legacy releases keys) must be a list.")
    if not isinstance(deadlines_raw, list):
        raise ValueError("'deadlines' must be a list.")
    if not isinstance(sprints_raw, list):
        raise ValueError("'sprints' must be a list.")
    if not isinstance(holidays_raw, list):
        raise ValueError("'holidays' must be a list.")

    pulse_start_week, pulse_end_week = parse_pulse_range(plan)

    sprints = normalize_named_events(
        sprints_raw,
        section="Sprints",
        year=year,
        window_start=window_start,
        window_end=window_end,
        constrain_to_window=explicit,
        cycle_start=cycle_start,
    )
    if not explicit:
        window = stretch_window_to_events(window, sprints)
        window_start = window["window_start"]
        window_end = window["window_end"]

    releases = normalize_releases(
        releases_raw,
        year=year,
        window_start=window_start,
        window_end=window_end,
        cycle_start=cycle_start,
    )
    if explicit:
        releases = [
            release
            for release in releases
            if release["start"] <= window_end and resolve_event_end(release) >= window_start
        ]
    else:
        window = stretch_window_to_events(window, releases)
        window_start = window["window_start"]
        window_end = window["window_end"]

    release_sets = build_release_sets(releases)
    deadlines = normalize_deadlines(
        deadlines_raw,
        year=year,
        window_start=window_start,
        window_end=window_end,
        cycle_start=cycle_start,
    )

    # An explicit window stays put. Otherwise holidays use the stretched bounds.
    holidays = normalize_named_events(
        holidays_raw,
        section="Holidays",
        year=year,
        window_start=window_start,
        window_end=window_end,
        cycle_start=cycle_start,
    )

    project_name = str(plan.get("project", "Project")).strip() or "Project"
    titled_project = project_name[:1].upper() + project_name[1:]
    title = f"{cycle} {titled_project} Release Plan"

    return {
        "title": title,
        "window": window,
        "releases": releases,
        "release_sets": release_sets,
        "deadlines": deadlines,
        "sprints": sprints,
        "holidays": holidays,
        "sources": normalize_sources(plan),
        "pulse_range": {
            "start_week": pulse_start_week,
            "end_week": pulse_end_week,
        },
    }


def _determine_sprint_status(sprint: dict[str, Any] | None, reference_date: date) -> str:
    """Return active, upcoming, completed, or none relative to reference_date."""
    if not sprint:
        return "none"

    sprint_start = sprint["start"]
    sprint_end = resolve_event_end(sprint)

    if sprint_start <= reference_date <= sprint_end:
        return "active"
    if sprint_start > reference_date:
        return "upcoming"
    return "completed"


def _select_sprint(
    sprints: list[dict[str, Any]], reference_date: date
) -> tuple[dict[str, Any] | None, str]:
    """Pick the in-progress sprint, otherwise the next one that has not started."""
    ordered = sorted(sprints, key=lambda sprint: (sprint["start"], str(sprint.get("name", ""))))
    for sprint in ordered:
        status = _determine_sprint_status(sprint, reference_date)
        if status in {"active", "upcoming"}:
            return sprint, status
    return None, "none"


def calculate_sidebar_metrics(
    built_plan: dict[str, Any], reference_date: date
) -> dict[str, Any]:
    """Calculate metrics for sidebar display."""
    window = built_plan["window"]
    window_start = window["window_start"]
    window_end = window["window_end"]
    releases = built_plan["releases"]
    deadlines = built_plan["deadlines"]
    sprints = built_plan["sprints"]
    
    # The sidebar shows the development cycle, not the padded chart.
    if window.get("explicit"):
        cycle_window_start = window["cycle_start"]
        cycle_window_end = window["cycle_end"]
        cycle_duration_weeks = int(window["cycle_weeks"])
        cycle_duration_days = int(window["exact_days"])
    else:
        cycle_window_start = window_start
        cycle_window_end = window_end
        cycle_duration_weeks = window["base_weeks"]
        cycle_duration_days = window["exact_days"]
    
    # The major in progress today. Bugfix and security bars are not majors.
    current_major_release = None
    for release in releases:
        if int(release.get("set_child_index", 0)) != 0:
            continue
        release_end = resolve_event_end(release)
        if release["start"] <= reference_date <= release_end:
            current_major_release = release
            break

    # The next major that has not started. Bugfix and security bars are minors.
    next_major_release = None
    for release in releases:
        if int(release.get("set_child_index", 0)) != 0:
            continue
        if release["start"] > reference_date:
            next_major_release = release
            break
    
    # Find upcoming deadline (closest deadline after reference_date)
    upcoming_deadline = None
    for deadline in deadlines:
        if deadline["start"] >= reference_date:
            upcoming_deadline = deadline
            break
    
    active_sprint, sprint_status = _select_sprint(sprints, reference_date)
    
    # Format dates for display
    def format_date_range(start_date: date, end_date: date) -> str:
        if start_date.month == end_date.month and start_date.year == end_date.year:
            return f"{start_date.strftime('%b %d')} - {end_date.strftime('%d, %Y')}"
        else:
            return f"{start_date.strftime('%b %d, %Y')} - {end_date.strftime('%b %d, %Y')}"
    
    def format_date_simple(date_obj: date) -> str:
        return date_obj.strftime("%b %d, %Y")
    
    def release_card(release: dict[str, Any] | None, countdown_to: str | None = None) -> dict[str, Any]:
        if not release:
            return {
                "version": "None",
                "purpose": "",
                "start": "",
                "end": "",
                "date_range": "",
                "days_until": None,
            }
        end = resolve_event_end(release)
        color, color_end = release_pack_gradient(releases, release)
        if countdown_to == "end":
            days_until = (end - reference_date).days
        elif countdown_to == "start":
            days_until = (release["start"] - reference_date).days
        else:
            days_until = None
        return {
            "version": release["name"],
            "purpose": str(release.get("purpose", "")).strip(),
            "start": format_date_simple(release["start"]),
            "end": format_date_simple(end),
            "date_range": format_date_range(release["start"], end),
            "color": color,
            "color_end": color_end,
            "days_until": days_until,
        }
    
    metrics = {
        "cycle_window": {
            "start": format_date_simple(cycle_window_start),
            "end": format_date_simple(cycle_window_end),
            "duration_weeks": cycle_duration_weeks,
            "duration_days": cycle_duration_days,
            "text": f"{format_date_simple(cycle_window_start)} – {format_date_simple(cycle_window_end)}",
        },
        "current_major_release": release_card(current_major_release, "end"),
        "next_major_release": release_card(next_major_release, "start"),
        "upcoming_deadline": {
            "name": upcoming_deadline["label"] if upcoming_deadline else "None",
            "date": format_date_simple(upcoming_deadline["start"]) if upcoming_deadline else "",
            "days_until": (
                (upcoming_deadline["start"] - reference_date).days
                if upcoming_deadline
                else None
            ),
        },
        "active_sprint": {
            "name": active_sprint["label"] if active_sprint else "None",
            "start": format_date_simple(active_sprint["start"]) if active_sprint else "",
            "end": format_date_simple(resolve_event_end(active_sprint)) if active_sprint else "",
            "date_range": (
                format_date_range(active_sprint["start"], resolve_event_end(active_sprint))
                if active_sprint
                else ""
            ),
            "status": sprint_status,
            "is_active": sprint_status == "active",
            "is_upcoming": sprint_status == "upcoming",
            "is_completed": sprint_status == "completed",
            "days_until": (
                (active_sprint["start"] - reference_date).days
                if sprint_status == "upcoming" and active_sprint
                else None
            ),
        },
    }
    
    return metrics


def calculate_zoom_levels(
    window: dict[str, Any],
    releases: list[dict[str, Any]],
    sprints: list[dict[str, Any]],
    reference_date: date,
) -> dict[str, Any]:
    """Calculate data for different zoom levels."""
    window_start = window["window_start"]
    window_end = window["window_end"]
    
    # Find overall bounds from all events
    all_starts = [window_start]
    all_ends = [window_end]
    
    for release in releases:
        all_starts.append(release["start"])
        all_ends.append(resolve_event_end(release))
    
    for sprint in sprints:
        sprint_start = sprint["start"]
        sprint_end = resolve_event_end(sprint)
        all_starts.append(sprint_start)
        all_ends.append(sprint_end)
    
    overall_start = min(all_starts)
    overall_end = max(all_ends)
    
    # Calculate different zoom levels
    zoom_levels = {
        "fit": {
            "window_start": window_start,
            "window_end": window_end,
            "label": "Fit",
        },
        "3m": {
            "window_start": reference_date,
            "window_end": reference_date + timedelta(days=3 * 30),  # Approximate 3 months
            "label": "3M",
        },
        "6m": {
            "window_start": reference_date,
            "window_end": reference_date + timedelta(days=6 * 30),  # Approximate 6 months
            "label": "6M",
        },
        "12m": {
            "window_start": reference_date,
            "window_end": reference_date + timedelta(days=12 * 30),  # Approximate 12 months
            "label": "12M",
        },
        "all": {
            "window_start": overall_start,
            "window_end": overall_end,
            "label": "All",
        },
    }
    
    return zoom_levels


def event_end_date(start: date, duration_weeks: int) -> date:
    return start + timedelta(days=duration_weeks * 7 - 1)


def resolve_event_end(event: dict[str, Any]) -> date:
    stored = event.get("end")
    if isinstance(stored, date):
        return stored
    return event_end_date(event["start"], int(event["duration_weeks"]))


def event_bar_geometry(
    event_start: date,
    event_end: date,
    window_start: date,
    window_end: date,
    grid_x: float,
    week_width: float,
) -> tuple[float, float] | None:
    """Place a bar by calendar day. Whole weeks stay on the week grid."""
    clipped = clip_event_to_window(event_start, event_end, window_start, window_end)
    if clipped is None:
        return None
    clipped_start, clipped_end = clipped
    day_width = week_width / 7
    offset_days = (clipped_start - window_start).days
    span_days = (clipped_end - clipped_start).days + 1
    return grid_x + offset_days * day_width, span_days * day_width


def clip_event_to_window(
    event_start: date,
    event_end: date,
    window_start: date,
    window_end: date,
) -> tuple[date, date] | None:
    clipped_start = max(event_start, window_start)
    clipped_end = min(event_end, window_end)
    if clipped_end < clipped_start:
        return None
    return clipped_start, clipped_end


def wrap_label_lines(label: str, max_chars: int) -> list[str]:
    wrapped = textwrap.wrap(
        label,
        width=max_chars,
        break_long_words=True,
        break_on_hyphens=False,
    )
    return wrapped or [label]


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip("#")
    if len(value) != 6:
        raise ValueError(f"Invalid hex color: {hex_color}")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def interpolate_color(start_hex: str, end_hex: str, t: float) -> str:
    start_rgb = hex_to_rgb(start_hex)
    end_rgb = hex_to_rgb(end_hex)
    out = (
        int(round(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * t)),
        int(round(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * t)),
        int(round(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * t)),
    )
    return rgb_to_hex(out)


def release_pack_gradient(releases: list[dict[str, Any]], release: dict[str, Any]) -> tuple[str, str]:
    """Match a major release card to the same hue as its chart bar."""
    pack_keys = list(dict.fromkeys(item["set_key"] for item in releases))
    pack_index = pack_keys.index(release["set_key"]) % len(RELEASE_PACK_PALETTE)
    base_fill, _stroke = RELEASE_PACK_PALETTE[pack_index]
    return base_fill, interpolate_color(base_fill, "#ffffff", 0.22)


def build_render_model(built_plan: dict[str, Any]) -> dict[str, Any]:
    window = built_plan["window"]
    window_start: date = window["window_start"]
    window_end: date = window["window_end"]
    weeks_count = int(window["base_weeks"])

    layout = {
        "left_label_width": 170,
        "grid_left_gap": 12,
        "right_padding": 24,
        "top_padding": 18,
        "month_row_height": 38,
        "week_row_height": 44,
        "pulse_row_height": 40,
        "rows_to_lanes_gap": 14,
        "lane_height": 54,
        "lane_inner_padding": 10,
        "lane_gap": 12,
        "item_stack_gap": 8,
        "item_height": 30,
        "week_width": 86,
        "line_height": 14,
        "line_baseline_offset": 11,
        "item_horizontal_padding": 8,
        "char_px": 7,
    }

    grid_x = layout["left_label_width"] + layout["grid_left_gap"]
    grid_width = weeks_count * layout["week_width"]

    explicit = bool(window.get("explicit"))
    cycle_start: date | None = window.get("cycle_start") if explicit else None
    cycle_weeks = int(window.get("cycle_weeks") or 0)

    weeks: list[dict[str, Any]] = []
    for index in range(weeks_count):
        week_start = window_start + timedelta(days=index * 7)
        week_end = week_start + timedelta(days=6)
        # Pulses restart each calendar year, paired from that year's first Monday.
        pulse_anchor = first_monday_of_year(week_start.year)
        business_week = ((week_start - pulse_anchor).days // 7) + 1
        if explicit and cycle_start is not None:
            cycle_week = ((week_start - cycle_start).days // 7) + 1
            week_label = str(cycle_week) if 1 <= cycle_week <= cycle_weeks else ""
        else:
            cycle_week = None
            week_label = f"W{business_week}"
        weeks.append(
            {
                "index": index,
                "start": week_start,
                "end": week_end,
                "start_label": week_start.strftime("%Y-%m-%d"),
                "business_week": int(business_week),
                "cycle_week": cycle_week,
                "week_label": week_label,
                "range_label": (
                    f"{week_start.strftime('%d-%m')} to {week_end.strftime('%d-%m')}"
                ),
                "x": grid_x + index * layout["week_width"],
                "width": layout["week_width"],
            }
        )

    months: list[dict[str, Any]] = []
    if weeks:
        start_idx = 0
        current_key = (weeks[0]["start"].year, weeks[0]["start"].month)
        for idx, week in enumerate(weeks[1:], start=1):
            week_key = (week["start"].year, week["start"].month)
            if week_key != current_key:
                span = idx - start_idx
                month_start = weeks[start_idx]["start"]
                months.append(
                    {
                        "year": current_key[0],
                        "month": current_key[1],
                        "label": month_start.strftime("%b %Y"),
                        "start_index": start_idx,
                        "span_weeks": span,
                        "x": grid_x + start_idx * layout["week_width"],
                        "width": span * layout["week_width"],
                    }
                )
                start_idx = idx
                current_key = week_key

        span = len(weeks) - start_idx
        month_start = weeks[start_idx]["start"]
        months.append(
            {
                "year": current_key[0],
                "month": current_key[1],
                "label": month_start.strftime("%b %Y"),
                "start_index": start_idx,
                "span_weeks": span,
                "x": grid_x + start_idx * layout["week_width"],
                "width": span * layout["week_width"],
            }
        )

    pulse_range = built_plan["pulse_range"]
    pulse_start_week = int(pulse_range["start_week"])
    pulse_end_week = int(pulse_range["end_week"])
    pulses: list[dict[str, Any]] = []
    for week in weeks:
        business_week = int(week["business_week"])
        if business_week < pulse_start_week or business_week > pulse_end_week:
            continue

        pulse_number = ((business_week - pulse_start_week) // 2) + 1
        if pulses and pulses[-1]["number"] == pulse_number:
            pulses[-1]["end_index"] = week["index"]
        else:
            pulses.append(
                {
                    "number": pulse_number,
                    "label": f"P{pulse_number}",
                    "start_index": week["index"],
                    "end_index": week["index"],
                }
            )

    for pulse in pulses:
        pulse_span = pulse["end_index"] - pulse["start_index"] + 1
        pulse["span_weeks"] = pulse_span
        pulse["x"] = grid_x + pulse["start_index"] * layout["week_width"]
        pulse["width"] = pulse_span * layout["week_width"]

    month_y = layout["top_padding"]
    week_y = month_y + layout["month_row_height"]
    pulse_y = week_y + layout["week_row_height"]
    lanes_start_y = pulse_y + layout["pulse_row_height"] + layout["rows_to_lanes_gap"]

    lane_defs: list[dict[str, Any]] = []
    if built_plan["releases"]:
        lane_defs.append(
            {
                "name": "Releases",
                "class_name": "release",
                "events": built_plan["releases"],
            }
        )
    if built_plan["deadlines"]:
        lane_defs.append(
            {
                "name": "Deadlines",
                "class_name": "deadline",
                "events": built_plan["deadlines"],
            }
        )
    if built_plan["holidays"]:
        lane_defs.append(
            {
                "name": "Holidays",
                "class_name": "holiday",
                "events": built_plan["holidays"],
            }
        )
    if built_plan["sprints"]:
        lane_defs.append(
            {
                "name": "Sprints",
                "class_name": "sprint",
                "events": built_plan["sprints"],
            }
        )

    # Keep sprint/holiday item boxes visually consistent by using one shared height.
    uniform_work_item_height = layout["item_height"]
    for lane in lane_defs:
        if lane["class_name"] not in {"sprint", "holiday"}:
            continue

        for event in lane["events"]:
            event_start = event["start"]
            event_end = resolve_event_end(event)

            geometry = event_bar_geometry(
                event_start,
                event_end,
                window_start,
                window_end,
                grid_x,
                layout["week_width"],
            )
            if geometry is None:
                continue
            _x, width = geometry
            max_chars = max(
                3,
                (width - 2 * layout["item_horizontal_padding"]) // layout["char_px"],
            )
            range_line = f"{event_start.strftime('%d-%m')} to {event_end.strftime('%d-%m')}"
            label_lines = []
            for line in (str(event["label"]), range_line):
                label_lines.extend(wrap_label_lines(line, max_chars))
            required_height = max(
                layout["item_height"],
                len(label_lines) * layout["line_height"] + 10,
            )
            uniform_work_item_height = max(uniform_work_item_height, required_height)

    lanes: list[dict[str, Any]] = []
    chart_width = grid_x + grid_width + layout["right_padding"]
    current_lane_y = lanes_start_y

    deadline_group_palette = [
        ("#be123c", "#9f1239"),
        ("#0369a1", "#075985"),
        ("#15803d", "#166534"),
        ("#7c3aed", "#6d28d9"),
        ("#c2410c", "#9a3412"),
        ("#0f766e", "#115e59"),
    ]

    for lane in lane_defs:
        pre_items: list[dict[str, Any]] = []
        lane_max_item_height = layout["item_height"]

        for event in lane["events"]:
            event_start = event["start"]
            event_end = resolve_event_end(event)

            clipped = clip_event_to_window(event_start, event_end, window_start, window_end)
            if clipped is None:
                continue

            clipped_start, clipped_end = clipped
            start_index = (clipped_start - window_start).days // 7
            if lane["class_name"] == "deadline":
                end_index = (clipped_end - window_start).days // 7
                span_weeks = end_index - start_index + 1
                x = grid_x + start_index * layout["week_width"]
                width = span_weeks * layout["week_width"]
            else:
                geometry = event_bar_geometry(
                    event_start,
                    event_end,
                    window_start,
                    window_end,
                    grid_x,
                    layout["week_width"],
                )
                if geometry is None:
                    continue
                x, width = geometry
            label = str(event["label"])
            deadline_center_x: float | None = None

            max_chars = max(
                3,
                (width - 2 * layout["item_horizontal_padding"]) // layout["char_px"],
            )
            label_lines = wrap_label_lines(label, max_chars)
            label_line_count = max(1, len(label_lines))
            required_height = max(
                layout["item_height"],
                label_line_count * layout["line_height"] + 10,
            )
            if lane["class_name"] == "release":
                purpose_value = str(event.get("purpose", "")).strip()
                title_line = f"{event['name']} release"
                if purpose_value:
                    title_line = f"{title_line}: {purpose_value}"
                range_line = (
                    f"{event_start.strftime('%d-%m')} to {event_end.strftime('%d-%m')}"
                )

                label_lines = []
                for line in (title_line, range_line):
                    label_lines.extend(wrap_label_lines(line, max_chars))

                label_line_count = len(label_lines)
                required_height = max(
                    layout["item_height"],
                    label_line_count * layout["line_height"] + 10,
                )
                item_height = required_height
            elif lane["class_name"] == "deadline":
                # Position deadline marker by day slot: each week is split into 5 equal weekday slots.
                week_left = grid_x + start_index * layout["week_width"]
                weekday_slot = min(max(event_start.weekday(), 0), 4)
                day_width = layout["week_width"] / 5
                deadline_center_x = week_left + (weekday_slot + 0.5) * day_width

                marker_size = 16
                title_line = str(event["label"])
                date_line = event_start.strftime("%d-%m-%Y")
                label_lines = []
                for line in (title_line, date_line):
                    label_lines.extend(wrap_label_lines(line, max_chars))
                item_height = max(
                    layout["item_height"],
                    marker_size + 6 + len(label_lines) * layout["line_height"] + 6,
                )
            elif lane["class_name"] in {"sprint", "holiday"}:
                range_line = (
                    f"{event_start.strftime('%d-%m')} to {event_end.strftime('%d-%m')}"
                )
                label_lines = []
                for line in (label, range_line):
                    label_lines.extend(wrap_label_lines(line, max_chars))
                item_height = uniform_work_item_height
            else:
                item_height = required_height
            lane_max_item_height = max(lane_max_item_height, item_height)

            pre_items.append(
                {
                    "id": event["id"],
                    "label": label,
                    "start": event_start.isoformat(),
                    "end": event_end.isoformat(),
                    "set_key": event.get("set_key"),
                    "set_child_index": int(event.get("set_child_index", 0)),
                    "linkto_refs": [
                        str(value).strip()
                        for value in event.get("linkto_refs", [])
                        if str(value).strip()
                    ],
                    "deadline_group_index": int(event.get("deadline_group_index", 0)),
                    "deadline_ref": str(event.get("deadline_ref", "")).strip(),
                    "x": x,
                    "width": width,
                    "height": item_height,
                    "shape": "diamond" if lane["class_name"] == "deadline" else "box",
                    "marker_size": 16 if lane["class_name"] == "deadline" else None,
                    "marker_center_x": deadline_center_x,
                    "label_lines": label_lines,
                }
            )

        lane_height = max(
            layout["lane_height"],
            lane_max_item_height + 2 * layout["lane_inner_padding"],
        )

        if lane["class_name"] == "release" and pre_items:
            release_rows = max(item["set_child_index"] for item in pre_items) + 1
            lane_height = max(
                lane_height,
                (
                    2 * layout["lane_inner_padding"]
                    + release_rows * lane_max_item_height
                    + (release_rows - 1) * layout["item_stack_gap"]
                ),
            )
        if lane["class_name"] == "deadline" and pre_items:
            deadline_rows = max(item["deadline_group_index"] for item in pre_items) + 1
            lane_height = max(
                lane_height,
                (
                    2 * layout["lane_inner_padding"]
                    + deadline_rows * lane_max_item_height
                    + (deadline_rows - 1) * layout["item_stack_gap"]
                ),
            )

        lane_y = current_lane_y
        label_y = lane_y + lane_height // 2 + 5

        items: list[dict[str, Any]] = []
        release_rows = max((item["set_child_index"] for item in pre_items), default=0) + 1
        release_pack_keys = list(dict.fromkeys(item["set_key"] for item in pre_items))
        for item_index, pre_item in enumerate(pre_items):
            if lane["class_name"] == "release":
                row_index = pre_item["set_child_index"]
                row_y = (
                    lane_y
                    + layout["lane_inner_padding"]
                    + row_index * (lane_max_item_height + layout["item_stack_gap"])
                )
                item_y = row_y + (lane_max_item_height - pre_item["height"]) // 2
            elif lane["class_name"] == "deadline":
                row_index = pre_item["deadline_group_index"]
                row_y = (
                    lane_y
                    + layout["lane_inner_padding"]
                    + row_index * (lane_max_item_height + layout["item_stack_gap"])
                )
                item_y = row_y + (lane_max_item_height - pre_item["height"]) // 2
            else:
                item_y = lane_y + (lane_height - pre_item["height"]) // 2

            fill_color: str | None = None
            stroke_color: str | None = None
            if lane["class_name"] == "release":
                pack_index = release_pack_keys.index(pre_item["set_key"]) % len(RELEASE_PACK_PALETTE)
                base_fill, base_stroke = RELEASE_PACK_PALETTE[pack_index]
                shade_t = min(pre_item["set_child_index"], 2) * 0.16
                fill_color = interpolate_color(base_fill, "#ffffff", shade_t)
                stroke_color = interpolate_color(base_stroke, "#ffffff", shade_t)
            elif lane["class_name"] == "deadline":
                palette_idx = pre_item["deadline_group_index"] % len(deadline_group_palette)
                fill_color, stroke_color = deadline_group_palette[palette_idx]

            if pre_item["shape"] == "diamond":
                marker_size = int(pre_item["marker_size"])
                text_top = item_y + marker_size + 6
                center_x = float(pre_item["marker_center_x"])
                half = marker_size / 2
                diamond_points = (
                    f"{center_x},{item_y} "
                    f"{center_x + half},{item_y + half} "
                    f"{center_x},{item_y + marker_size} "
                    f"{center_x - half},{item_y + half}"
                )
            else:
                text_top = item_y + (pre_item["height"] - len(pre_item["label_lines"]) * layout["line_height"]) // 2
                diamond_points = None

            text_lines = []
            for line_index, line_text in enumerate(pre_item["label_lines"]):
                if lane["class_name"] in {"release", "sprint", "holiday"}:
                    line_x = pre_item["x"] + pre_item["width"] / 2
                    line_class = "item-label-inside item-label-centered"
                elif lane["class_name"] == "deadline":
                    line_x = float(pre_item["marker_center_x"])
                    date_line = bool(re.fullmatch(r"\d{2}-\d{2}-\d{4}", line_text))
                    label_class = "deadline-label-date" if date_line else "deadline-label"
                    line_class = f"item-label-inside item-label-centered {label_class}"
                else:
                    line_x = pre_item["x"] + layout["item_horizontal_padding"]
                    line_class = "item-label-inside"

                text_lines.append(
                    {
                        "text": line_text,
                        "x": line_x,
                        "y": (
                            text_top
                            + line_index * layout["line_height"]
                            + layout["line_baseline_offset"]
                        ),
                        "class_name": line_class,
                    }
                )

            items.append(
                {
                    "id": pre_item["id"],
                    "label": pre_item["label"],
                    "start": pre_item["start"],
                    "end": pre_item["end"],
                    "lane_class": lane["class_name"],
                    "set_key": pre_item["set_key"],
                    "linkto_refs": pre_item["linkto_refs"],
                    "deadline_ref": pre_item["deadline_ref"],
                    "x": pre_item["x"],
                    "y": item_y,
                    "width": pre_item["width"],
                    "height": pre_item["height"],
                    "shape": pre_item["shape"],
                    "marker_center_x": pre_item["marker_center_x"],
                    "diamond_points": diamond_points,
                    "fill_color": fill_color,
                    "stroke_color": stroke_color,
                    "text_lines": text_lines,
                }
            )

        lanes.append(
            {
                "name": lane["name"],
                "class_name": lane["class_name"],
                "y": lane_y,
                "height": lane_height,
                "label_y": label_y,
                "items": items,
            }
        )
        current_lane_y += lane_height + layout["lane_gap"]

    if lanes:
        chart_height = lanes[-1]["y"] + lanes[-1]["height"] + 14
    else:
        chart_height = lanes_start_y + 14

    # Build simple release->deadline links from links_to references.
    deadline_targets: dict[str, tuple[float, float]] = {}
    release_sources: list[dict[str, Any]] = []
    for lane in lanes:
        for item in lane["items"]:
            if item["lane_class"] == "deadline" and item["deadline_ref"]:
                target_x = float(item["marker_center_x"])
                target_y = float(item["y"]) + 8.0
                deadline_targets[item["deadline_ref"]] = (target_x, target_y)
            elif item["lane_class"] == "release" and item["linkto_refs"]:
                release_sources.append(item)

    links: list[dict[str, Any]] = []
    for source in release_sources:
        source_x = float(source["x"]) + float(source["width"])
        source_y = float(source["y"]) + float(source["height"]) / 2.0
        link_color = (
            str(source.get("stroke_color") or source.get("fill_color") or "#475569")
        )
        for ref in source["linkto_refs"]:
            target = deadline_targets.get(ref)
            if not target:
                continue
            links.append(
                {
                    "x1": source_x,
                    "y1": source_y,
                    "x2": target[0],
                    "y2": target[1],
                    "color": link_color,
                }
            )

    return {
        "width": chart_width,
        "height": chart_height,
        "grid_x": grid_x,
        "grid_width": grid_width,
        "left_label_width": layout["left_label_width"],
        "month_y": month_y,
        "week_y": week_y,
        "pulse_y": pulse_y,
        "month_row_height": layout["month_row_height"],
        "week_row_height": layout["week_row_height"],
        "pulse_row_height": layout["pulse_row_height"],
        "lanes_start_y": lanes_start_y,
        "week_width": layout["week_width"],
        "weeks": [
            {
                "index": w["index"],
                "start": w["start"].isoformat(),
                "end": w["end"].isoformat(),
                "start_label": w["start_label"],
                "business_week": w["business_week"],
                "week_label": w["week_label"],
                "range_label": w["range_label"],
                "x": w["x"],
                "width": w["width"],
            }
            for w in weeks
        ],
        "months": months,
        "pulses": pulses,
        "lanes": lanes,
        "links": links,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
    }


def render_html(template_file: Path, context: dict[str, Any]) -> str:
    env = Environment(
        loader=FileSystemLoader(str(template_file.parent)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template(template_file.name)
    return template.render(**context)


def main() -> None:
    args = parse_args()
    input_file = Path(args.input)
    template_file = Path(args.template)
    output_file = Path(args.output)

    plan = read_yaml(input_file)
    built_plan = build_plan(plan)
    render_model = build_render_model(built_plan)
    
    # Parse reference date
    try:
        reference_date = datetime.fromisoformat(args.reference_date).date()
    except ValueError:
        print(f"Warning: Invalid reference date '{args.reference_date}', using today")
        reference_date = date.today()
    
    # Calculate sidebar metrics
    sidebar_metrics = calculate_sidebar_metrics(built_plan, reference_date)
    
    # Calculate zoom levels
    zoom_levels = calculate_zoom_levels(
        built_plan["window"],
        built_plan["releases"],
        built_plan["sprints"],
        reference_date,
    )

    context = {
        "project": plan.get("project", "unknown"),
        "plan_name": built_plan["title"],
        "owner": plan.get("owner", "unknown"),
        "window": built_plan["window"],
        "releases": built_plan["releases"],
        "deadlines": built_plan["deadlines"],
        "sprints": built_plan["sprints"],
        "holidays": built_plan["holidays"],
        "render_model": render_model,
        "sidebar_metrics": sidebar_metrics,
        "zoom_levels": zoom_levels,
        "reference_date": reference_date.isoformat(),
        "generated_at": datetime.now().strftime("%Y-%m-%d"),
        "plan_source": plan,
        "sources": built_plan["sources"],
    }
    html = render_html(template_file, context)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(html, encoding="utf-8")
    print(f"Generated release plan: {output_file}")

    # Copy static assets to output directory
    static_src = Path(__file__).parent / "static"
    static_dst = output_file.parent / "static"
    if static_src.exists():
        shutil.copytree(static_src, static_dst, dirs_exist_ok=True)

    svg_template_file = Path(args.svg_template)
    svg_output_file = Path(args.svg)
    if svg_template_file.exists():
        svg = render_html(svg_template_file, context)
        svg_output_file.parent.mkdir(parents=True, exist_ok=True)
        svg_output_file.write_text(svg, encoding="utf-8")
        print(f"Generated SVG diagram: {svg_output_file}")


if __name__ == "__main__":
    main()
