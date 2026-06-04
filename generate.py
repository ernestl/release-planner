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


def parse_args() -> argparse.Namespace:
    root = Path(__file__).parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        default=str(root / "data" / "snapd-2026-h1.yaml"),
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


def compute_window(cycle: str) -> dict[str, Any]:
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


def resolve_event_start(event: dict[str, Any], year: int) -> date | None:
    kind = str(event.get("kind", "")).strip()
    if kind == "by-week":
        return week_start_date(year, int(event.get("week")))
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

        duration_weeks = int(raw.get("duration", 1))
        if duration_weeks <= 0:
            raise ValueError(f"{section} '{name}' must have duration > 0.")

        start = resolve_event_start(raw, year)
        if start is None:
            continue

        if constrain_to_window and not within_window(start, duration_weeks, window_start, window_end):
            continue

        end = event_end_date(start, duration_weeks)

        normalized.append(
            {
                "id": sanitize_id(f"{section.lower()}_{index}_{name}"),
                "name": name,
                "label": f"{name}{suffix}",
                "range_label": f"{start.strftime('%d-%m')} to {end.strftime('%d-%m')}",
                "section": section,
                "start": start,
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
    event_ends = [event_end_date(event["start"], int(event["duration_weeks"])) for event in events]

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

        kind = str(raw.get("kind", "by-week")).strip()
        start: date | None = None
        if kind == "by-week":
            if "week" in raw:
                start = week_start_date(year, int(raw.get("week")))
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

        start = resolve_event_start(raw, year)
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

    window = compute_window(cycle)
    year = int(window["year"])
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
        constrain_to_window=False,
    )
    window = stretch_window_to_events(window, sprints)
    window_start = window["window_start"]
    window_end = window["window_end"]

    releases = normalize_releases(
        releases_raw,
        year=year,
        window_start=window_start,
        window_end=window_end,
    )
    window = stretch_window_to_events(window, releases)
    window_start = window["window_start"]
    window_end = window["window_end"]

    release_sets = build_release_sets(releases)
    deadlines = normalize_deadlines(
        deadlines_raw,
        year=year,
        window_start=window_start,
        window_end=window_end,
    )

    # Sprints are already guaranteed to fit in the stretched window.
    holidays = normalize_named_events(
        holidays_raw,
        section="Holidays",
        year=year,
        window_start=window_start,
        window_end=window_end,
    )

    title = f"{plan.get('project', 'Project')} {cycle} Release Plan"

    return {
        "title": title,
        "window": window,
        "releases": releases,
        "release_sets": release_sets,
        "deadlines": deadlines,
        "sprints": sprints,
        "holidays": holidays,
        "pulse_range": {
            "start_week": pulse_start_week,
            "end_week": pulse_end_week,
        },
    }


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
    
    # Calculate cycle window info
    cycle_window_start = window_start
    cycle_window_end = window_end
    cycle_duration_weeks = window["base_weeks"]
    cycle_duration_days = window["exact_days"]
    
    # Find next major release (first release after reference_date)
    next_major_release = None
    for release in releases:
        if release["start"] >= reference_date:
            next_major_release = release
            break
    
    if next_major_release is None and releases:
        # If no future releases, show the last one
        next_major_release = releases[-1]
    
    # Find upcoming deadline (closest deadline after reference_date)
    upcoming_deadline = None
    for deadline in deadlines:
        if deadline["start"] >= reference_date:
            upcoming_deadline = deadline
            break
    
    # Find active sprint (sprint that contains reference_date or next one)
    active_sprint = None
    for sprint in sprints:
        sprint_start = sprint["start"]
        sprint_end = event_end_date(sprint_start, sprint["duration_weeks"])
        if sprint_start <= reference_date <= sprint_end:
            active_sprint = sprint
            break
    
    if active_sprint is None and sprints:
        # If no current sprint, show the next one
        for sprint in sprints:
            sprint_start = sprint["start"]
            sprint_end = event_end_date(sprint_start, sprint["duration_weeks"])
            if sprint_start >= reference_date:
                active_sprint = sprint
                break
    
    if active_sprint is None and sprints:
        # If no future sprints, show the last one
        active_sprint = sprints[-1]
    
    # Format dates for display
    def format_date_range(start_date: date, end_date: date) -> str:
        if start_date.month == end_date.month and start_date.year == end_date.year:
            return f"{start_date.strftime('%b %d')} - {end_date.strftime('%d, %Y')}"
        else:
            return f"{start_date.strftime('%b %d, %Y')} - {end_date.strftime('%b %d, %Y')}"
    
    def format_date_simple(date_obj: date) -> str:
        return date_obj.strftime("%b %d, %Y")
    
    # Helper to get end date from start and duration
    def get_end_date(start_date: date, duration_weeks: int) -> date:
        return event_end_date(start_date, duration_weeks)
    
    metrics = {
        "cycle_window": {
            "start": format_date_simple(cycle_window_start),
            "end": format_date_simple(cycle_window_end),
            "duration_weeks": cycle_duration_weeks,
            "duration_days": cycle_duration_days,
            "text": f"{format_date_simple(cycle_window_start)} – {format_date_simple(cycle_window_end)}",
        },
        "next_major_release": {
            "version": next_major_release["name"] if next_major_release else "None",
            "purpose": next_major_release.get("purpose", "") if next_major_release else "",
            "start": format_date_simple(next_major_release["start"]) if next_major_release else "",
            "end": format_date_simple(get_end_date(next_major_release["start"], next_major_release["duration_weeks"])) if next_major_release else "",
            "date_range": (
                format_date_range(
                    next_major_release["start"],
                    get_end_date(next_major_release["start"], next_major_release["duration_weeks"])
                )
                if next_major_release
                else ""
            ),
        },
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
            "end": format_date_simple(get_end_date(active_sprint["start"], active_sprint["duration_weeks"])) if active_sprint else "",
            "date_range": (
                format_date_range(active_sprint["start"], get_end_date(active_sprint["start"], active_sprint["duration_weeks"]))
                if active_sprint
                else ""
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
        all_ends.append(event_end_date(release["start"], release["duration_weeks"]))
    
    for sprint in sprints:
        sprint_start = sprint["start"]
        sprint_end = event_end_date(sprint_start, sprint["duration_weeks"])
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

    pulse_anchor = first_monday_of_year(int(window["year"]))

    weeks: list[dict[str, Any]] = []
    for index in range(weeks_count):
        week_start = window_start + timedelta(days=index * 7)
        week_end = week_start + timedelta(days=6)
        business_week = ((week_start - pulse_anchor).days // 7) + 1
        weeks.append(
            {
                "index": index,
                "start": week_start,
                "end": week_end,
                "start_label": week_start.strftime("%Y-%m-%d"),
                "business_week": int(business_week),
                "week_label": f"W{business_week}",
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
            duration_weeks = int(event["duration_weeks"])
            event_end = event_end_date(event_start, duration_weeks)

            clipped = clip_event_to_window(event_start, event_end, window_start, window_end)
            if clipped is None:
                continue

            clipped_start, clipped_end = clipped
            start_index = (clipped_start - window_start).days // 7
            end_index = (clipped_end - window_start).days // 7
            span_weeks = end_index - start_index + 1

            width = span_weeks * layout["week_width"]
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
            duration_weeks = int(event["duration_weeks"])
            event_end = event_end_date(event_start, duration_weeks)

            clipped = clip_event_to_window(event_start, event_end, window_start, window_end)
            if clipped is None:
                continue

            clipped_start, clipped_end = clipped
            start_index = (clipped_start - window_start).days // 7
            end_index = (clipped_end - window_start).days // 7
            span_weeks = end_index - start_index + 1

            x = grid_x + start_index * layout["week_width"]
            width = span_weeks * layout["week_width"]
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
                shade_t = 0.0 if release_rows <= 1 else row_index / (release_rows - 1)
                fill_color = interpolate_color("#5b21b6", "#8b5cf6", shade_t)
                stroke_color = interpolate_color("#4c1d95", "#6d28d9", shade_t)
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
                    line_class = "item-label-inside item-label-centered deadline-label"
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
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
