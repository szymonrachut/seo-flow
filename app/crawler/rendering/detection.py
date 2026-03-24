from __future__ import annotations

from dataclasses import dataclass

from scrapy.http import Response


FRAMEWORK_MARKERS: tuple[tuple[str, str], ...] = (
    ("__NEXT_DATA__", "next_data"),
    ('id="__next"', "next_root"),
    ('id="__nuxt"', "nuxt_root"),
    ("data-reactroot", "react_root"),
    ("ng-version", "angular"),
    ("astro-island", "astro"),
    ("window.__NUXT__", "nuxt_state"),
    ("sveltekit", "sveltekit"),
)


@dataclass(slots=True)
class RenderDetectionResult:
    js_heavy_like: bool
    reason: str | None


def detect_js_heavy_page(
    response: Response,
    *,
    title: str | None,
    meta_description: str | None,
    canonical_url: str | None,
    h1: str | None,
    visible_text: str,
    link_count: int,
) -> RenderDetectionResult:
    if not response.text:
        return RenderDetectionResult(js_heavy_like=False, reason=None)

    text_word_count = len(visible_text.split()) if visible_text else 0
    text_char_count = len(visible_text)
    script_count = len(response.css("script"))
    missing_core_count = sum(
        1
        for value in (title, meta_description, canonical_url, h1)
        if value is None or str(value).strip() == ""
    )
    html_lower = response.text.lower()
    framework_marker = next(
        (
            label
            for marker, label in FRAMEWORK_MARKERS
            if marker.lower() in html_lower
        ),
        None,
    )

    if text_word_count <= 20 and script_count >= 6 and link_count <= 2:
        return RenderDetectionResult(
            js_heavy_like=True,
            reason=f"low_text_many_scripts(words={text_word_count},scripts={script_count},links={link_count})",
        )

    if text_char_count <= 180 and missing_core_count >= 3 and script_count >= 4:
        return RenderDetectionResult(
            js_heavy_like=True,
            reason=(
                "shell_html_missing_core("
                f"chars={text_char_count},missing_core={missing_core_count},scripts={script_count})"
            ),
        )

    if framework_marker and text_word_count <= 50 and script_count >= 4 and link_count <= 3:
        return RenderDetectionResult(
            js_heavy_like=True,
            reason=(
                "framework_shell("
                f"marker={framework_marker},words={text_word_count},scripts={script_count},links={link_count})"
            ),
        )

    return RenderDetectionResult(js_heavy_like=False, reason=None)
