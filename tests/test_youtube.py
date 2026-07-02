from yt_notion_digest.youtube import parse_channel_identity, parse_playlist_id


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


def test_parse_playlist_id() -> None:
    url = "https://youtube.com/playlist?list=PL0pHg9WQBbWZqnTu9vqMUdwsxRaZIB0Ja&si=abc"
    assert parse_playlist_id(url) == "PL0pHg9WQBbWZqnTu9vqMUdwsxRaZIB0Ja"


def test_parse_playlist_id_from_watch_url() -> None:
    url = "https://www.youtube.com/watch?v=abc123&list=PLxyz"
    assert parse_playlist_id(url) == "PLxyz"
