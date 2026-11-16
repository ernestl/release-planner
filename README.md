# release-planner

A visual release-planning tool that generates HTML (and SVG) timeline diagrams from a YAML definition. Built for the snapd project but adaptable to any release cadence.

## Quick start

```bash
# 1. Set up the Python virtual environment and install dependencies
source setup_env.sh

# 2. Generate the plan (HTML + SVG)
python generate.py
```

Output is written to `output/plan.html` (open in a browser) and `output/plan.svg`.

## Requirements

- Python 3.10+
- Dependencies: `pyyaml`, `jinja2` (installed automatically by `setup_env.sh`)

## Usage

```
python generate.py [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--input` | `data/snapd-27.04.yaml` | Path to the release-plan YAML file |
| `--template` | `templates/plan.html.j2` | Jinja2 HTML template |
| `--output` | `output/plan.html` | Generated HTML output path |
| `--svg-template` | `templates/plan.svg.j2` | Jinja2 SVG template |
| `--svg` | `output/plan.svg` | Generated SVG output path |

## YAML data format

The input YAML file defines the full release plan. Top-level keys:

```yaml
project: snapd          # Project name
cycle: "26.10"          # Target cycle (yy.mm) — defines the 6-month window

timeline:
  resolution: week      # Timeline granularity

pulses:                 # Visual pulse markers (start/end of timeline)
  start:
    kind: "by-week"
    week: 1
  end:
    kind: "by-week"
    week: 52

releases:               # List of releases to plot
  - name: "2.76"
    purpose: "26.04 carry-over"
    kind: "by-week"
    week: 20            # Absolute week number in the year
    duration: 6         # Duration in weeks
  - name: "2.76.1"
    purpose: "bugfix"
    kind: "by-week"
    offset: 2           # Weeks after previous release start
    duration: 6

deadlines:              # External milestone dates
  - release: "26.10"
    purpose: "feature freeze"
    kind: "by-date"
    date: "20-08-2026"  # DD-MM-YYYY or YYYY-MM-DD

sprints:                # Team sprint periods
  - name: "May"
    kind: "by-week"
    week: 18
    duration: 2

holidays:               # Holiday / unavailability blocks
  - name: "Midyear"
    kind: "by-month-final-week"
    month: 7
    duration: 2
```

### Scheduling kinds

| Kind | Required fields | Meaning |
|------|----------------|---------|
| `by-week` | `week` or `offset` | Absolute ISO week, or offset from previous item |
| `by-date` | `date` | Exact date (DD-MM-YYYY or YYYY-MM-DD) |
| `by-month-final-week` | `month` | Last Monday of the given month |
| `by-lookup` | — | Resolved via external lookup (skipped if unresolvable) |

### Linking releases to deadlines

Releases can reference deadlines using `links_to` to draw dependency arrows:

```yaml
links_to: "26.10: beta freeze"
# or multiple:
links_to:
  - "24.04.5: content freeze"
  - "26.04.1: content freeze"
```

## Project structure

```
generate.py          # Main generator script
data/                # YAML plan definitions
templates/           # Jinja2 templates (HTML and SVG)
output/              # Generated output (git-ignored)
setup_env.sh         # One-step environment setup
requirements.txt     # Python dependencies
```

## Customisation

To plan a different cycle or project, create a new YAML file in `data/` following the format above, then run:

```bash
python generate.py --input data/my-plan.yaml
```
