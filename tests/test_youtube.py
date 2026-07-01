from yt_notion_digest.youtube import parse_channel_identity


def test_parse_handle_url_with_query() -> None:
    assert parse_channel_identity("https://youtube.com/@macamp0817?si=abc") == (
        "handle",
        "@macamp0817",
    )


def test_parse_channel_id_url() -> None:
    assert parse_channel_identity("https://www.youtube.com/channel/UCabc1234567890123456789") == (
        "id",
        "UCabc1234567890123456789",
    )


def test_parse_custom_url_falls_back_to_search() -> None:
    assert parse_channel_identity("https://www.youtube.com/c/SomeChannel") == ("search", "SomeChannel")
