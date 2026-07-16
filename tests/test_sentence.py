from app.domain.voice.sentence import SentenceSplitter


def test_splits_on_sentence_end():
    splitter = SentenceSplitter()
    assert splitter.feed("거실 조명을 껐어요. 또 필요") == ["거실 조명을 껐어요."]
    assert splitter.feed("한 게 있나요?") == ["또 필요한 게 있나요?"]
    assert splitter.flush() is None


def test_flush_returns_remainder():
    splitter = SentenceSplitter()
    assert splitter.feed("네 알겠어") == []
    assert splitter.flush() == "네 알겠어"


def test_streaming_fragments_accumulate():
    splitter = SentenceSplitter()
    out: list[str] = []
    for piece in ["거", "실 불을 ", "켰어요", ". 온도", "는 이십이 도예요."]:
        out.extend(splitter.feed(piece))
    assert out == ["거실 불을 켰어요.", "온도는 이십이 도예요."]
