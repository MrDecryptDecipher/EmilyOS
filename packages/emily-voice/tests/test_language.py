"""Language detection sticky state tests."""

from __future__ import annotations

from emily.voice.language import LanguageDetector


def test_detect_devanagari_hindi() -> None:
    det = LanguageDetector()
    state = det.detect("नमस्ते मेरा नाम एमिली है")
    assert state.dominant == "hi"
    assert state.confidence > 0.5


def test_detect_telugu_and_tamil() -> None:
    det = LanguageDetector()
    assert det.detect("నమస్కారం").dominant == "te"
    assert det.detect("வணக்கம்").dominant == "ta"


def test_detect_indic_script_matrix() -> None:
    det = LanguageDetector()
    samples = {
        "te": "తెలుగు భాష",
        "or": "ଓଡ଼ିଆ ଭାଷା",
        "bn": "বাংলা ভাষা",
        "ta": "தமிழ் மொழி",
        "kn": "ಕನ್ನಡ ಭಾಷೆ",
        "ml": "മലയാളം ഭാഷ",
        "gu": "ગુજરાતી ભાષા",
        "pa": "ਪੰਜਾਬੀ ਭਾਸ਼ਾ",
    }
    for lang, text in samples.items():
        state = det.detect(text)
        assert state.dominant == lang, f"{lang}: got {state.dominant}"
        assert state.sticky is True


def test_language_state_sticky_field() -> None:
    det = LanguageDetector()
    state = det.update("Hello there friend")
    assert state.sticky is True


def test_hinglish_latin() -> None:
    det = LanguageDetector()
    state = det.detect("Yaar yeh kya hai, theek hai na?")
    assert state.dominant == "hi"
    assert state.code_switching is True


def test_is_romanized_hinglish() -> None:
    from emily.voice.language import has_devanagari, is_romanized_hinglish

    assert is_romanized_hinglish("Haan, bas yahin hoon, aap se baat kar rahi hoon.")
    assert not is_romanized_hinglish("Hello, how are you?")
    assert not is_romanized_hinglish("नमस्ते आप कैसे हैं")
    assert has_devanagari("क्या कर रही हो")


def test_sticky_does_not_flip_randomly() -> None:
    det = LanguageDetector()
    det.update("Hello, how are you doing today?")
    assert det.state.dominant == "en"
    # Short mixed noise should not flip
    det.update("ok")
    assert det.state.dominant == "en"
    # Strong Hindi should flip
    det.update("नमस्ते आप कैसे हैं धन्यवाद")
    assert det.state.dominant == "hi"
