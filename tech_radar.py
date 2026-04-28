#!/usr/bin/env python3
"""
tech-radar-generator
====================

Generate a static, interactive ThoughtWorks-style Technology Radar
from a YAML/JSON config file.

Author: Aslam Ahamed - Head of IT @ Prestige One Developments, Dubai
License: MIT
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import sys
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - handled at runtime
    yaml = None  # noqa: N816

# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------

QUADRANT_POSITIONS = {
    "top-right": (0, 90),
    "top-left": (90, 180),
    "bottom-left": (180, 270),
    "bottom-right": (270, 360),
}

DEFAULT_RINGS = ["Adopt", "Trial", "Assess", "Hold"]
RING_OUTER_RADII = [120, 220, 310, 400]  # in SVG user units

STATUS_CHOICES = {
    "new": "New",
    "moved-in": "Moved In",
    "moved-out": "Moved Out",
    "no-change": "No Change",
}

RING_FILLS = ["#bae6fd", "#bbf7d0", "#fde68a", "#fecaca"]
RING_TEXT = ["#075985", "#166534", "#92400e", "#991b1b"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hash_floats(seed: str, n: int = 4) -> list[float]:
    """Deterministic [0,1) floats derived from seed."""
    digest = hashlib.md5(seed.encode("utf-8")).digest()
    return [digest[i] / 255.0 for i in range(min(n, len(digest)))]


def _polar_to_cartesian(radius: float, angle_deg: float) -> tuple[float, float]:
    """Convert polar coords (degrees, 0=east, ccw) to SVG cartesian (y down)."""
    a = math.radians(angle_deg)
    return radius * math.cos(a), -radius * math.sin(a)


def _validate_config(cfg: dict[str, Any]) -> None:
    if "quadrants" not in cfg or len(cfg["quadrants"]) != 4:
        raise ValueError("config must define exactly 4 quadrants")
    positions = {q["position"] for q in cfg["quadrants"]}
    if positions != set(QUADRANT_POSITIONS):
        raise ValueError(
            "quadrants must use positions: "
            + ", ".join(sorted(QUADRANT_POSITIONS))
        )
    rings = cfg.get("rings", DEFAULT_RINGS)
    if len(rings) != 4:
        raise ValueError("config must define exactly 4 rings")
    quadrant_ids = {q["id"] for q in cfg["quadrants"]}
    for entry in cfg.get("entries", []):
        if entry.get("quadrant") not in quadrant_ids:
            raise ValueError(f"entry {entry.get('name')!r} has unknown quadrant")
        if entry.get("ring") not in rings:
            raise ValueError(f"entry {entry.get('name')!r} has unknown ring")
        status = entry.get("status", "no-change")
        if status not in STATUS_CHOICES:
            raise ValueError(
                f"entry {entry.get('name')!r} has invalid status {status!r}"
            )


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def compute_blips(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    rings = cfg.get("rings", DEFAULT_RINGS)
    pos_by_id = {q["id"]: q["position"] for q in cfg["quadrants"]}
    blips: list[dict[str, Any]] = []

    # Group entries per (quadrant_id, ring) so we can spread them out.
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for entry in cfg.get("entries", []):
        key = (entry["quadrant"], entry["ring"])
        grouped.setdefault(key, []).append(entry)

    blip_id = 0
    for (qid, ring_name), entries in grouped.items():
        position = pos_by_id[qid]
        a_start, a_end = QUADRANT_POSITIONS[position]
        ring_idx = rings.index(ring_name)
        r_inner = 0 if ring_idx == 0 else RING_OUTER_RADII[ring_idx - 1]
        r_outer = RING_OUTER_RADII[ring_idx]

        # Margins so blips don't sit on borders.
        ang_margin = 6
        rad_margin = 18
        a_lo, a_hi = a_start + ang_margin, a_end - ang_margin
        r_lo, r_hi = r_inner + rad_margin, r_outer - rad_margin

        for entry in entries:
            blip_id += 1
            seed = f"{entry['name']}|{qid}|{ring_name}"
            f1, f2, *_ = _hash_floats(seed)
            angle = a_lo + (a_hi - a_lo) * f1
            radius = r_lo + (r_hi - r_lo) * f2
            x, y = _polar_to_cartesian(radius, angle)
            blips.append({
                "id": blip_id,
                "name": entry["name"],
                "quadrant": qid,
                "ring": ring_name,
                "ring_index": ring_idx,
                "status": entry.get("status", "no-change"),
                "description": entry.get("description", ""),
                "x": round(x, 2),
                "y": round(y, 2),
            })
    return blips


# ---------------------------------------------------------------------------
# SVG / HTML generation
# ---------------------------------------------------------------------------

SVG_SIZE = 900  # full SVG viewbox is -SVG_SIZE/2 .. SVG_SIZE/2

QUADRANT_LABEL_OFFSET = 30


def _quadrant_label_xy(position: str) -> tuple[float, float, str]:
    """Return (x, y, text-anchor) for the quadrant label."""
    half = SVG_SIZE / 2
    pad = QUADRANT_LABEL_OFFSET
    if position == "top-right":
        return half - pad, -half + pad, "end"
    if position == "top-left":
        return -half + pad, -half + pad, "start"
    if position == "bottom-left":
        return -half + pad, half - pad, "start"
    return half - pad, half - pad, "end"  # bottom-right


def render_svg(cfg: dict[str, Any], blips: list[dict[str, Any]]) -> str:
    rings = cfg.get("rings", DEFAULT_RINGS)
    half = SVG_SIZE // 2
    parts: list[str] = []
    parts.append(
        f'<svg viewBox="{-half} {-half} {SVG_SIZE} {SVG_SIZE}" '
        f'xmlns="http://www.w3.org/2000/svg" class="radar-svg" '
        f'role="img" aria-label="Technology Radar">'
    )

    # Concentric rings (drawn outermost first so inner rings sit on top).
    for i in range(len(rings) - 1, -1, -1):
        parts.append(
            f'<circle cx="0" cy="0" r="{RING_OUTER_RADII[i]}" '
            f'fill="{RING_FILLS[i]}" stroke="#94a3b8" '
            f'stroke-width="1" opacity="0.55"/>'
        )

    # Quadrant separator lines.
    parts.append(
        f'<line x1="{-half}" y1="0" x2="{half}" y2="0" '
        f'stroke="#475569" stroke-width="1.5"/>'
    )
    parts.append(
        f'<line x1="0" y1="{-half}" x2="0" y2="{half}" '
        f'stroke="#475569" stroke-width="1.5"/>'
    )

    # Ring labels (offset slightly above the +X axis).
    for i, ring_name in enumerate(rings):
        r_inner = 0 if i == 0 else RING_OUTER_RADII[i - 1]
        label_r = (r_inner + RING_OUTER_RADII[i]) / 2
        parts.append(
            f'<text x="{label_r}" y="-6" text-anchor="middle" '
            f'class="ring-label" fill="{RING_TEXT[i]}">'
            f'{html.escape(ring_name)}</text>'
        )

    # Quadrant labels.
    for q in cfg["quadrants"]:
        x, y, anchor = _quadrant_label_xy(q["position"])
        parts.append(
            f'<text x="{x}" y="{y}" text-anchor="{anchor}" '
            f'class="quadrant-label">{html.escape(q["name"])}</text>'
        )

    # Blips.
    for blip in blips:
        marker = _blip_marker(blip)
        parts.append(marker)

    parts.append("</svg>")
    return "\n".join(parts)


def _blip_marker(blip: dict[str, Any]) -> str:
    x, y = blip["x"], blip["y"]
    label = str(blip["id"])
    status = blip["status"]
    title = (
        f'{html.escape(blip["name"])} - {html.escape(blip["ring"])}'
    )
    g_open = (
        f'<g class="blip" data-id="{blip["id"]}" '
        f'data-quadrant="{html.escape(blip["quadrant"])}" '
        f'data-ring="{html.escape(blip["ring"])}" '
        f'data-status="{status}" tabindex="0" role="button">'
        f'<title>{title}</title>'
    )
    if status == "new":
        # Triangle pointing up
        size = 14
        pts = (
            f"{x},{y - size} "
            f"{x - size}, {y + size * 0.7} "
            f"{x + size}, {y + size * 0.7}"
        )
        marker = (
            f'<polygon points="{pts}" fill="#1d4ed8" '
            f'stroke="white" stroke-width="1.5"/>'
        )
    elif status == "moved-in":
        size = 13
        pts = f"{x - size},{y + size * 0.6} {x + size},{y + size * 0.6} {x},{y - size}"
        marker = (
            f'<polygon points="{pts}" fill="#15803d" '
            f'stroke="white" stroke-width="1.5"/>'
        )
    elif status == "moved-out":
        size = 13
        pts = f"{x - size},{y - size * 0.6} {x + size},{y - size * 0.6} {x},{y + size}"
        marker = (
            f'<polygon points="{pts}" fill="#b91c1c" '
            f'stroke="white" stroke-width="1.5"/>'
        )
    else:
        marker = (
            f'<circle cx="{x}" cy="{y}" r="11" fill="#0f172a" '
            f'stroke="white" stroke-width="1.5"/>'
        )
    label_el = (
        f'<text x="{x}" y="{y + 4}" text-anchor="middle" '
        f'class="blip-label">{label}</text>'
    )
    return g_open + marker + label_el + "</g>"


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{
  --bg: #f8fafc;
  --panel: #ffffff;
  --ink: #0f172a;
  --muted: #475569;
  --accent: #1d4ed8;
  --border: #e2e8f0;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
    Roboto, "Helvetica Neue", Arial, sans-serif;
  background: var(--bg); color: var(--ink);
}}
header {{
  padding: 24px 32px; border-bottom: 1px solid var(--border);
  background: var(--panel);
}}
header h1 {{ margin: 0 0 4px; font-size: 24px; }}
header .meta {{ color: var(--muted); font-size: 14px; }}
main {{ display: grid; grid-template-columns: minmax(0,1fr) 360px; gap: 24px;
        padding: 24px 32px; align-items: start; }}
@media (max-width: 1024px) {{ main {{ grid-template-columns: 1fr; }} }}
.radar-card {{ background: var(--panel); border: 1px solid var(--border);
        border-radius: 12px; padding: 16px; }}
.radar-svg {{ width: 100%; height: auto; }}
.legend {{ background: var(--panel); border: 1px solid var(--border);
        border-radius: 12px; padding: 16px 20px; max-height: 80vh; overflow:auto; }}
.legend h2 {{ font-size: 16px; margin: 0 0 8px; }}
.legend section {{ margin-bottom: 18px; }}
.legend section h3 {{ font-size: 13px; margin: 8px 0 6px;
        color: var(--accent); text-transform: uppercase; letter-spacing: 0.04em; }}
.legend ol {{ margin: 0; padding-left: 22px; }}
.legend li {{ margin: 2px 0; cursor: pointer; }}
.legend li:hover {{ color: var(--accent); }}
.legend .ring-group h4 {{ font-size: 12px; color: var(--muted);
        margin: 4px 0; text-transform: uppercase; }}
.blip {{ cursor: pointer; }}
.blip text.blip-label {{ fill: white; font-size: 11px; font-weight: 600;
        pointer-events: none; }}
.blip:hover circle, .blip:hover polygon {{ stroke: var(--accent);
        stroke-width: 3; }}
.blip.dimmed {{ opacity: 0.18; }}
.blip.highlight circle, .blip.highlight polygon {{
        stroke: var(--accent); stroke-width: 4; }}
.ring-label {{ font-size: 13px; font-weight: 600; }}
.quadrant-label {{ font-size: 18px; font-weight: 700; fill: #1e293b; }}
.status-key {{ display: flex; gap: 14px; flex-wrap: wrap;
        margin-top: 8px; font-size: 12px; color: var(--muted); }}
.status-key span::before {{ content: ""; display: inline-block;
        width: 10px; height: 10px; margin-right: 6px; vertical-align: middle;
        border-radius: 50%; background: var(--ink); }}
.status-key span.new::before {{ background: #1d4ed8; border-radius: 0;
        clip-path: polygon(50% 0, 100% 100%, 0 100%); }}
.status-key span.moved-in::before {{ background: #15803d; border-radius: 0;
        clip-path: polygon(50% 0, 100% 100%, 0 100%); }}
.status-key span.moved-out::before {{ background: #b91c1c; border-radius: 0;
        clip-path: polygon(0 0, 100% 0, 50% 100%); }}
footer {{ text-align: center; padding: 16px; color: var(--muted);
        font-size: 12px; }}
footer a {{ color: var(--accent); }}
</style>
</head>
<body>
<header>
  <h1>{title}</h1>
  <div class="meta">{subtitle}</div>
  <div class="status-key" aria-label="Status legend">
    <span class="no-change">No change</span>
    <span class="new">New</span>
    <span class="moved-in">Moved in</span>
    <span class="moved-out">Moved out</span>
  </div>
</header>
<main>
  <div class="radar-card">
    {svg}
  </div>
  <aside class="legend">
    <h2>Entries</h2>
    {legend}
  </aside>
</main>
<footer>
  Generated with <a href="https://github.com/intruderfr/tech-radar-generator">
    tech-radar-generator</a> &middot; Aslam Ahamed
</footer>
<script>
(function () {{
  const blips = document.querySelectorAll('.blip');
  const legendItems = document.querySelectorAll('.legend li[data-id]');
  function clear() {{
    blips.forEach(b => b.classList.remove('dimmed', 'highlight'));
  }}
  function highlight(id) {{
    blips.forEach(b => {{
      if (b.dataset.id === id) {{
        b.classList.add('highlight');
        b.classList.remove('dimmed');
      }} else {{
        b.classList.add('dimmed');
        b.classList.remove('highlight');
      }}
    }});
  }}
  legendItems.forEach(li => {{
    li.addEventListener('click', () => highlight(li.dataset.id));
  }});
  blips.forEach(b => {{
    b.addEventListener('click', () => highlight(b.dataset.id));
  }});
  document.querySelector('.radar-card').addEventListener('dblclick', clear);
}})();
</script>
</body>
</html>
"""


def render_legend(cfg: dict[str, Any], blips: list[dict[str, Any]]) -> str:
    rings = cfg.get("rings", DEFAULT_RINGS)
    by_quadrant: dict[str, list[dict[str, Any]]] = {}
    for blip in blips:
        by_quadrant.setdefault(blip["quadrant"], []).append(blip)

    sections: list[str] = []
    for q in cfg["quadrants"]:
        qid = q["id"]
        section = [f'<section><h3>{html.escape(q["name"])}</h3>']
        for ring_name in rings:
            ring_blips = [
                b for b in by_quadrant.get(qid, []) if b["ring"] == ring_name
            ]
            if not ring_blips:
                continue
            section.append(
                f'<div class="ring-group"><h4>{html.escape(ring_name)}</h4><ol>'
            )
            for b in sorted(ring_blips, key=lambda x: x["id"]):
                tooltip = html.escape(b["description"]) if b["description"] else ""
                section.append(
                    f'<li data-id="{b["id"]}" value="{b["id"]}" '
                    f'title="{tooltip}">{html.escape(b["name"])}</li>'
                )
            section.append("</ol></div>")
        section.append("</section>")
        sections.append("".join(section))
    return "\n".join(sections)


def render_html(cfg: dict[str, Any]) -> str:
    blips = compute_blips(cfg)
    svg = render_svg(cfg, blips)
    legend = render_legend(cfg, blips)
    title = cfg.get("title", "Technology Radar")
    subtitle_parts: list[str] = []
    if cfg.get("date"):
        subtitle_parts.append(f"As of {cfg['date']}")
    if cfg.get("organization"):
        subtitle_parts.append(cfg["organization"])
    subtitle = " &middot; ".join(subtitle_parts) or f"{len(blips)} entries"
    return HTML_TEMPLATE.format(
        title=html.escape(title),
        subtitle=html.escape(subtitle),
        svg=svg,
        legend=legend,
    )


# ---------------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------------

def load_config(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        if yaml is None:
            raise SystemExit(
                "PyYAML is required for YAML input. "
                "Install with: pip install PyYAML"
            )
        return yaml.safe_load(text)
    if path.suffix.lower() == ".json":
        return json.loads(text)
    raise SystemExit(f"unsupported config extension: {path.suffix}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tech-radar",
        description="Generate a static Technology Radar HTML from a YAML/JSON config.",
    )
    parser.add_argument("config", type=Path, help="Path to YAML or JSON config file.")
    parser.add_argument(
        "-o", "--output", type=Path, default=Path("radar.html"),
        help="Path to write the HTML output (default: radar.html).",
    )
    parser.add_argument(
        "--validate-only", action="store_true",
        help="Only validate the config; do not render output.",
    )
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    _validate_config(cfg)
    if args.validate_only:
        print(f"OK: {len(cfg.get('entries', []))} entries validated.")
        return 0

    html_out = render_html(cfg)
    args.output.write_text(html_out, encoding="utf-8")
    print(f"Wrote {args.output} ({len(cfg.get('entries', []))} entries).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
