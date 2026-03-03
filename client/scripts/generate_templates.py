"""Generate pre-rendered OCR templates and save them as shipped assets.

Renders skill name, rank name, and digit templates for the default
font size / render mode combination using the licensed font file.
The output is committed to client/assets/rendered_templates/ so the
font file is not needed at runtime.

Usage:
    python -m client.scripts.generate_templates
"""

import json
import sys
from pathlib import Path

# Resolve paths relative to client/
CLIENT_DIR = Path(__file__).parent.parent
DATA_DIR = CLIENT_DIR / "data"
ASSETS_TEMPLATES_DIR = CLIENT_DIR / "assets" / "rendered_templates"

# Default rendering settings (matches FontMatcher.pre_initialize defaults)
DEFAULT_FONT_SIZE = 13
DEFAULT_RENDER_MODE = "native"


def load_skill_names() -> list[str]:
    path = DATA_DIR / "skill_reference.json"
    with open(path) as f:
        skills = json.load(f)
    return [s["name"] for s in skills]


def load_rank_names() -> list[str]:
    path = DATA_DIR / "skill_ranks.json"
    with open(path) as f:
        ranks = json.load(f)
    return [r["name"] for r in ranks]


def main():
    skill_names = load_skill_names()
    rank_names = load_rank_names()
    print(f"Loaded {len(skill_names)} skills, {len(rank_names)} ranks")

    # Import FontMatcher (needs opencv + Pillow)
    from client.ocr.font_matcher import FontMatcher, FONT_PATH

    font_path = str(FONT_PATH)
    if not Path(font_path).exists():
        print(f"ERROR: Font file not found at {font_path}")
        print("The font file is required to generate templates.")
        sys.exit(1)

    matcher = FontMatcher(skill_names, rank_names, font_path=font_path)

    size = DEFAULT_FONT_SIZE
    mode = DEFAULT_RENDER_MODE
    cache_key = f"s{size}_{mode}"
    output_dir = ASSETS_TEMPLATES_DIR / cache_key

    print(f"Rendering templates: size={size}, mode={mode}")

    # Load font and render
    matcher._font_size = size
    matcher._render_mode = mode
    matcher._load_font(size)

    # Clear any existing output
    if output_dir.exists():
        import shutil
        shutil.rmtree(output_dir)

    # Render templates (bypasses cache so we always regenerate)
    matcher._skill_templates.clear()
    matcher._skill_width_index.clear()
    for name in skill_names:
        tpl = matcher._render_template(name)
        if tpl is not None:
            tpl = matcher._to_binary(tpl)
            matcher._skill_templates[name] = tpl

    matcher._rank_templates.clear()
    matcher._rank_width_index.clear()
    for name in rank_names:
        tpl = matcher._render_template(name)
        if tpl is not None:
            tpl = matcher._to_binary(tpl)
            matcher._rank_templates[name] = tpl

    matcher._digit_templates.clear()
    for ch in "0123456789":
        tpl = matcher._render_template(ch)
        if tpl is not None:
            matcher._digit_templates[ch] = matcher._to_binary(tpl)

    # Save to assets directory
    matcher._save_rendered_cache(output_dir)

    total = (len(matcher._skill_templates) +
             len(matcher._rank_templates) +
             len(matcher._digit_templates))
    print(f"Saved {total} templates to {output_dir}")
    print(f"  Skills: {len(matcher._skill_templates)}")
    print(f"  Ranks:  {len(matcher._rank_templates)}")
    print(f"  Digits: {len(matcher._digit_templates)}")


if __name__ == "__main__":
    main()
