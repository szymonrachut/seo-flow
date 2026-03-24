from __future__ import annotations

from scrapy.http import Response


def extract_image_metrics(response: Response) -> tuple[int, int]:
    images = response.xpath("//img")
    images_count = len(images)
    images_missing_alt_count = sum(
        1
        for image in images
        if image.xpath("@alt").get() is None or not image.xpath("normalize-space(@alt)").get()
    )
    return images_count, images_missing_alt_count
