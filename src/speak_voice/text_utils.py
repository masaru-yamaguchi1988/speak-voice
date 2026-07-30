import re
import unicodedata

_url_pattern = re.compile(r"https?://[^\s）)＞>]+")
_markdown_link_pattern = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_html_tag_pattern = re.compile(r"<[^>]+>")
_markdown_marks_pattern = re.compile(r"[*_~#>|]+")


def has_speakable_text(text: str) -> bool:
    """文字・数字を1文字以上含み、音声として読み上げる内容があるか判定する。"""
    return any(unicodedata.category(character)[0] in {"L", "N"} for character in text)


def prepare_text_for_speech(text: str) -> str:
    """URLやMarkdown装飾を除去し、画面表示とは別の読み上げ用文章を作る。"""
    text = _markdown_link_pattern.sub(r"\1", text)
    text = _url_pattern.sub(" URL ", text)
    text = _html_tag_pattern.sub(" ", text)
    text = _markdown_marks_pattern.sub("", text)
    return " ".join(text.split())


class StreamingSpeechFilter:
    """ストリームをまたぐMarkdownコード範囲を読み上げ対象から除外する。"""

    def __init__(self):
        self.in_code_block = False
        self.in_inline_code = False
        self.pending_backticks = 0

    def feed(self, chunk: str) -> str:
        output: list[str] = []
        for character in chunk:
            if character == "`":
                self.pending_backticks += 1
                continue
            if self.pending_backticks:
                self._consume_backticks()
            if not self.in_code_block and not self.in_inline_code:
                output.append(character)
        return "".join(output)

    def flush(self) -> str:
        if self.pending_backticks:
            self._consume_backticks()
        return ""

    def _consume_backticks(self) -> None:
        count = self.pending_backticks
        self.pending_backticks = 0
        while count >= 3:
            self.in_code_block = not self.in_code_block
            count -= 3
        if count and not self.in_code_block:
            self.in_inline_code = not self.in_inline_code
