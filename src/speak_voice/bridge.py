import queue
import re
import threading
from typing import Generator

from speak_voice.base import BaseEngine
from speak_voice.player import play_wav
from speak_voice.text_utils import (
    StreamingSpeechFilter,
    has_speakable_text,
    prepare_text_for_speech,
)


class VoiceBridgeError(RuntimeError):
    """音声合成または再生に失敗したことを呼び出し元へ通知します。"""


class SentenceSplitter:
    """入力されたテキストのストリームを日本語の文単位（。！？改行など）に分割するクラス。"""

    def __init__(self):
        self.buffer = ""
        # 文の区切り文字となるパターン（。、！、？、改行）
        self.split_pat = re.compile(r"([^。！？\n]+[。！？\n]+)")

    def append(self, text_chunk: str) -> list[str]:
        """テキストの断片を追加し、完了した文のリストを返します。"""
        self.buffer += text_chunk
        sentences = []

        # パターンに一致する部分（文）を抽出
        matches = list(self.split_pat.finditer(self.buffer))
        if matches:
            last_end = 0
            for m in matches:
                sentences.append(m.group(1).strip())
                last_end = m.end()
            self.buffer = self.buffer[last_end:]

        return [s for s in sentences if s]

    def flush(self) -> list[str]:
        """バッファに残っているテキストを最後の文として強制的に出力します。"""
        remaining = self.buffer.strip()
        self.buffer = ""
        if remaining:
            return [remaining]
        return []


class VoiceAgentBridge:
    """AIエージェントのテキスト応答をバックグラウンドで非同期に音声合成・再生するブリッジクラス。"""

    def __init__(self, engine: BaseEngine, speaker_id: str, **kwargs):
        """初期化。

        引数:
            engine: 使用する音声合成エンジンインスタンス。
            speaker_id: 使用する話者ID。
            **kwargs: 共通の調声パラメータ（speed, pitch, volume など）。
        """
        self.engine = engine
        self.speaker_id = speaker_id
        self.synth_params = kwargs

        self.queue = queue.Queue()
        self.thread = None
        self.running = False
        self._errors: list[Exception] = []
        self._error_lock = threading.Lock()
        self._cancel_event = threading.Event()

    def start(self):
        """バックグラウンド再生スレッドを開始します。"""
        if self.running:
            return
        with self._error_lock:
            self._errors.clear()
        self._cancel_event.clear()
        self.running = True
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def stop(self):
        """再生スレッドを停止し、処理を終了します。"""
        self.cancel()
        self.running = False
        self.queue.put(None)  # 終了シグナル
        if self.thread:
            self.thread.join()

    def cancel(self):
        """現在の再生を止め、未再生の文章をキューから破棄します。"""
        self._cancel_event.set()
        while True:
            try:
                item = self.queue.get_nowait()
                self.queue.task_done()
                if item is None:
                    break
            except queue.Empty:
                break

    def wait_until_done(self):
        """キュー内のすべてのテキストの音声合成・再生が完了するまでブロック待機します。"""
        if self.running and self.thread:
            self.queue.join()
        with self._error_lock:
            if self._errors:
                first_error = self._errors[0]
                raise VoiceBridgeError(
                    f"音声合成または再生に失敗しました: {first_error}"
                ) from first_error

    def speak(self, text: str):
        """文またはテキスト全体を再生キューに追加します。"""
        clean_text = prepare_text_for_speech(text)
        if not has_speakable_text(clean_text):
            return
        if not self.running:
            self.start()

        max_length = getattr(self.engine, "max_text_length", None)
        if isinstance(max_length, int) and max_length > 0:
            for start in range(0, len(clean_text), max_length):
                segment = clean_text[start : start + max_length]
                if has_speakable_text(segment):
                    self.queue.put(segment)
        else:
            self.queue.put(clean_text)

    def speak_stream(self, text_generator: Generator[str, None, None]):
        """ジェネレータ（ストリーミング出力）から随時テキストを受け取り、文単位で切り出してキューに追加します。"""
        if not self.running:
            self.start()

        splitter = SentenceSplitter()
        speech_filter = StreamingSpeechFilter()
        for chunk in text_generator:
            if self._cancel_event.is_set():
                break
            sentences = splitter.append(speech_filter.feed(chunk))
            for sentence in sentences:
                self.speak(sentence)

        # 最後にバッファに残ったテキストをフラッシュして発話
        if not self._cancel_event.is_set():
            speech_filter.flush()
            for sentence in splitter.flush():
                self.speak(sentence)

    def _worker(self):
        """バックグラウンドでキューを監視し、合成と再生を行うワーカースレッド。"""
        while True:
            try:
                text = self.queue.get(timeout=0.5)
                if text is None:  # 終了シグナル
                    self.queue.task_done()
                    break

                try:
                    # 音声の合成
                    if self._cancel_event.is_set():
                        continue
                    wav_bytes = self.engine.synthesize_wav(
                        text=text, speaker_id=self.speaker_id, **self.synth_params
                    )
                    # 音声の再生
                    if not play_wav(wav_bytes, stop_event=self._cancel_event):
                        if self._cancel_event.is_set():
                            continue
                        raise RuntimeError("音声プレイヤーが再生に失敗しました。")
                except Exception as e:
                    import sys

                    with self._error_lock:
                        self._errors.append(e)
                    print(f"Bridge worker error during synthesis/playback: {e}", file=sys.stderr)
                finally:
                    self.queue.task_done()

            except queue.Empty:
                continue
