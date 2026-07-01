from yt_notion_digest.notion import MAX_RICH_TEXT, markdown_to_blocks


def test_markdown_to_blocks_splits_long_lines() -> None:
    blocks = markdown_to_blocks("# Heading\n" + "a" * (MAX_RICH_TEXT + 100))
    assert blocks[0]["type"] == "heading_1"
    assert len(blocks) >= 3
    for block in blocks:
        block_type = block["type"]
        rich_text = block[block_type]["rich_text"]
        if rich_text:
            assert len(rich_text[0]["text"]["content"]) <= MAX_RICH_TEXT
