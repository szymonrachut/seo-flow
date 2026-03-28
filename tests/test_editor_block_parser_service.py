from __future__ import annotations

from app.services.editor_block_parser_service import parse_html_document_into_blocks


def test_parse_html_document_into_blocks_preserves_order_keys_and_context() -> None:
    html_content = """
    <article>
      <h1>Guide to Local SEO</h1>
      <p>Start with the homepage summary.</p>
      <section>
        <h2>Service Pages</h2>
        <p>Service pages should match search intent <strong>clearly</strong>.</p>
        <ul>
          <li>Describe the core service.</li>
        </ul>
      </section>
    </article>
    """

    blocks = parse_html_document_into_blocks(html_content)

    assert [block.block_key for block in blocks] == [
        "H1-001",
        "P-002",
        "H2-003",
        "P-004",
        "LI-005",
    ]
    assert [block.position_index for block in blocks] == [1, 2, 3, 4, 5]
    assert [block.block_type for block in blocks] == [
        "heading",
        "paragraph",
        "heading",
        "paragraph",
        "list_item",
    ]
    assert blocks[0].text_content == "Guide to Local SEO"
    assert blocks[1].text_content == "Start with the homepage summary."
    assert blocks[2].text_content == "Service Pages"
    assert blocks[3].text_content == "Service pages should match search intent clearly."
    assert blocks[4].text_content == "Describe the core service."
    assert blocks[2].parent_block_key == "H1-001"
    assert blocks[3].parent_block_key == "H2-003"
    assert blocks[4].parent_block_key == "H2-003"
    assert blocks[0].context_path == "Guide to Local SEO"
    assert blocks[2].context_path == "Guide to Local SEO > Service Pages"
    assert blocks[3].context_path == "Guide to Local SEO > Service Pages"
    assert blocks[3].html_content is not None
    assert blocks[3].content_hash


def test_parse_html_document_into_blocks_is_deterministic() -> None:
    html_content = "<h1>FAQ</h1><p>Short answer.</p><li>One bullet</li>"

    first_run = parse_html_document_into_blocks(html_content)
    second_run = parse_html_document_into_blocks(html_content)

    assert first_run == second_run
