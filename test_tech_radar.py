"""
Lightweight tests for tech_radar.py.

Run:
    python -m pytest test_tech_radar.py -v

Or without pytest:
    python test_tech_radar.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import tech_radar as tr


SAMPLE = {
    "title": "Test Radar",
    "date": "2026-01-01",
    "quadrants": [
        {"id": "techniques", "name": "Techniques", "position": "top-left"},
        {"id": "tools", "name": "Tools", "position": "top-right"},
        {"id": "platforms", "name": "Platforms", "position": "bottom-right"},
        {"id": "languages", "name": "Languages", "position": "bottom-left"},
    ],
    "rings": ["Adopt", "Trial", "Assess", "Hold"],
    "entries": [
        {"name": "TypeScript", "quadrant": "languages", "ring": "Adopt",
         "status": "no-change", "description": "Default web language."},
        {"name": "Rust", "quadrant": "languages", "ring": "Assess",
         "status": "new"},
        {"name": "Kubernetes", "quadrant": "platforms", "ring": "Adopt"},
        {"name": "GitHub Actions", "quadrant": "tools", "ring": "Adopt"},
        {"name": "Trunk-Based", "quadrant": "techniques", "ring": "Adopt"},
    ],
}


def test_validate_accepts_good_config():
    tr._validate_config(SAMPLE)  # should not raise


def test_validate_rejects_wrong_quadrant_count():
    cfg = json.loads(json.dumps(SAMPLE))
    cfg["quadrants"].pop()
    try:
        tr._validate_config(cfg)
    except ValueError as e:
        assert "exactly 4 quadrants" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_validate_rejects_bad_ring():
    cfg = json.loads(json.dumps(SAMPLE))
    cfg["entries"][0]["ring"] = "Maybe"
    try:
        tr._validate_config(cfg)
    except ValueError as e:
        assert "unknown ring" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_validate_rejects_bad_status():
    cfg = json.loads(json.dumps(SAMPLE))
    cfg["entries"][0]["status"] = "totally-new"
    try:
        tr._validate_config(cfg)
    except ValueError as e:
        assert "invalid status" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_blip_positions_inside_correct_ring_and_quadrant():
    blips = tr.compute_blips(SAMPLE)
    assert len(blips) == len(SAMPLE["entries"])
    pos_by_id = {q["id"]: q["position"] for q in SAMPLE["quadrants"]}
    for blip in blips:
        x, y = blip["x"], blip["y"]
        radius = math.hypot(x, y)
        ring_idx = blip["ring_index"]
        inner = 0 if ring_idx == 0 else tr.RING_OUTER_RADII[ring_idx - 1]
        outer = tr.RING_OUTER_RADII[ring_idx]
        assert inner <= radius <= outer, (
            f"blip {blip['name']} radius {radius} outside [{inner}, {outer}]"
        )
        position = pos_by_id[blip["quadrant"]]
        # Quadrant boundary checks (SVG y is flipped: up = negative).
        if position == "top-right":
            assert x >= 0 and y <= 0
        elif position == "top-left":
            assert x <= 0 and y <= 0
        elif position == "bottom-left":
            assert x <= 0 and y >= 0
        elif position == "bottom-right":
            assert x >= 0 and y >= 0


def test_deterministic_layout():
    """Same config -> same blip positions across runs."""
    a = tr.compute_blips(SAMPLE)
    b = tr.compute_blips(SAMPLE)
    assert [(x["name"], x["x"], x["y"]) for x in a] == [
        (x["name"], x["x"], x["y"]) for x in b
    ]


def test_render_html_produces_complete_document():
    html_doc = tr.render_html(SAMPLE)
    assert html_doc.startswith("<!doctype html>")
    assert "<svg" in html_doc and "</svg>" in html_doc
    for entry in SAMPLE["entries"]:
        assert entry["name"] in html_doc
    assert "Test Radar" in html_doc
    # Status legend present:
    for status in ("No change", "New", "Moved in", "Moved out"):
        assert status in html_doc


def test_load_config_yaml_round_trip(tmp_path: Path):
    if tr.yaml is None:
        return  # PyYAML not installed; skip.
    p = tmp_path / "r.yaml"
    p.write_text(tr.yaml.safe_dump(SAMPLE), encoding="utf-8")
    cfg = tr.load_config(p)
    assert cfg["title"] == "Test Radar"
    assert len(cfg["entries"]) == len(SAMPLE["entries"])


def test_load_config_json(tmp_path: Path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps(SAMPLE), encoding="utf-8")
    cfg = tr.load_config(p)
    assert cfg["title"] == "Test Radar"


if __name__ == "__main__":
    import sys
    failed = 0
    for name in sorted(globals()):
        if name.startswith("test_"):
            fn = globals()[name]
            try:
                # tmp_path tests need pytest; skip those in standalone mode.
                import inspect
                params = inspect.signature(fn).parameters
                if "tmp_path" in params:
                    import tempfile
                    with tempfile.TemporaryDirectory() as d:
                        fn(Path(d))
                else:
                    fn()
                print(f"  ok  {name}")
            except Exception as e:
                failed += 1
                print(f"  FAIL  {name}: {e}")
    sys.exit(failed)
