import unicodedata


def has_speakable_text(text: str) -> bool:
    """文字・数字を1文字以上含み、音声として読み上げる内容があるか判定する。"""
    return any(unicodedata.category(character)[0] in {"L", "N"} for character in text)
