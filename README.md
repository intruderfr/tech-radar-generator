# tech-radar-generator

A small, single-file Python tool that turns a **YAML/JSON** description of your
organization's technology choices into a **static, interactive HTML
Technology Radar** — the ThoughtWorks-style chart with four quadrants
(Techniques / Tools / Platforms / Languages & Frameworks) and four rings
(Adopt / Trial / Assess / Hold).

The output is a single self-contained `radar.html` file with no external
runtime dependencies — drop it on any web server, Confluence page, or
internal portal.

## Why this exists

If you're a CIO, CTO, Head of IT, or platform engineering lead, a Tech Radar
is one of the most useful artefacts you can publish:

- It makes the implicit "what do we use here?" knowledge explicit.
- It gives engineers a fast answer to "is X approved?".
- It signals strategy: what's coming, what's going, and what's stable.

Most existing tooling either depends on a Google Sheet, a heavy SPA build,
or a SaaS account. This generator is **one Python file plus a YAML config**
that anyone on the team can edit through a pull request.

## Features

- Single-file Python CLI (`tech_radar.py`), no framework dependencies.
- Reads YAML or JSON — keep your radar in version control.
- Deterministic blip placement (same config → same layout, every run).
- Four status markers: **No Change**, **New**, **Moved In**, **Moved Out**.
- Interactive HTML output: click a blip or legend item to highlight it,
  double-click the radar to clear.
- Accessible: SVG `role="img"`, focusable blips, keyboard-friendly legend.
- Validates the config before rendering; clear errors if a quadrant or ring
  name is wrong.
- Works offline: no CDNs, no fonts, no JS frameworks.

## Quick start

```bash
git clone https://github.com/intruderfr/tech-radar-generator.git
cd tech-radar-generator
pip install -r requirements.txt
python tech_radar.py example-radar.yaml -o radar.html
open radar.html  # or xdg-open / start
```

## Configuring your radar

Edit `example-radar.yaml` (or copy it). The file has three sections:
**quadrants**, **rings**, and **entries**.

```yaml
title: "Acme Corp Technology Radar"
date: "2026-04-28"
organization: "CIO Office"

quadrants:
  - { id: techniques,  name: Techniques,                position: top-left }
  - { id: tools,       name: Tools,                     position: top-right }
  - { id: platforms,   name: Platforms,                 position: bottom-right }
  - { id: languages,   name: Languages & Frameworks,    position: bottom-left }

rings: [Adopt, Trial, Assess, Hold]

entries:
  - name: Kubernetes
    quadrant: platforms
    ring: Adopt
    status: no-change
    description: Container orchestration de facto standard.
  - name: Rust
    quadrant: languages
    ring: Assess
    status: new
    description: Pilot for hot-path services.
```

### Allowed `position` values

`top-left`, `top-right`, `bottom-left`, `bottom-right` — exactly one
quadrant must be assigned to each.

### Allowed `status` values

| Status      | Meaning                                  | Marker            |
|-------------|------------------------------------------|-------------------|
| `no-change` | Stayed in the same ring since last issue | filled circle     |
| `new`       | First appearance on the radar            | upward triangle   |
| `moved-in`  | Moved closer to the centre               | upward triangle   |
| `moved-out` | Moved further from the centre            | downward triangle |

## CLI usage

```text
usage: tech_radar [-h] [-o OUTPUT] [--validate-only] config

Generate a static Technology Radar HTML from a YAML/JSON config.

positional arguments:
  config                Path to YAML or JSON config file.

options:
  -h, --help            show this help message and exit
  -o OUTPUT, --output OUTPUT
                        Path to write the HTML output (default: radar.html).
  --validate-only       Only validate the config; do not render output.
```

## Running tests

```bash
python test_tech_radar.py        # standalone (no pytest needed)
# or
python -m pytest test_tech_radar.py -v
```

The tests cover config validation, deterministic layout, blip-position
geometry (every blip falls inside its expected ring and quadrant),
HTML completeness, and YAML/JSON round-trips.

## CI suggestion

Drop this snippet in `.github/workflows/radar.yml` to publish your radar
to GitHub Pages on every push:

```yaml
name: Publish radar
on:
  push:
    branches: [main]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements.txt
      - run: python tech_radar.py example-radar.yaml -o site/index.html
      - uses: actions/upload-pages-artifact@v3
        with: { path: site }
  deploy:
    needs: build
    permissions: { pages: write, id-token: write }
    environment: github-pages
    runs-on: ubuntu-latest
    steps:
      - uses: actions/deploy-pages@v4
```

## Roadmap

- Diff mode: compare two radar configs and emit a "what changed" report.
- Theming: light/dark, custom palettes per quadrant.
- Export: PNG and PDF output for printing the quarterly readout.
- Hosted dashboards: optional small static site with multiple historical radars.

PRs welcome.

## License

[MIT](LICENSE).

## Author

**Aslam Ahamed** — Head of IT @ Prestige One Developments, Dubai.
[LinkedIn](https://www.linkedin.com/in/aslam-ahamed/) ·
[GitHub](https://github.com/intruderfr).
