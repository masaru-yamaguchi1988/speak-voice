from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Speaker:
    """音声合成エンジンにおける話者/キャラクターを表すクラス。"""

    id: str  # 話者を識別するユニークなID
    name: str  # 話者の表示名
    styles: List[str] = field(
        default_factory=list
    )  # 利用可能なスタイル（例: 喜、怒、哀、楽）のリスト
    raw_info: dict = field(default_factory=dict)  # エンジン固有の生のメタデータ情報


class BaseEngine(ABC):
    """すべての音声合成エンジンを統括する抽象基底クラス。"""

    @property
    @abstractmethod
    def engine_name(self) -> str:
        """エンジンの名前を返します。"""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """エンジン（またはバックエンドのHTTPサービス/CLI等）が実行可能・利用可能か確認します。"""
        pass

    @abstractmethod
    def get_speakers(self) -> List[Speaker]:
        """利用可能な話者/キャラクターの一覧を取得します。"""
        pass

    @abstractmethod
    def synthesize_wav(
        self,
        text: str,
        speaker_id: str,
        speed: Optional[float] = None,
        pitch: Optional[float] = None,
        intonation: Optional[float] = None,
        volume: Optional[float] = None,
        style: Optional[str] = None,
        **kwargs,
    ) -> bytes:
        """入力テキストを音声合成し、生のWAVバイトデータを返します。

        引数:
            text: 合成する日本語テキスト。
            speaker_id: 使用する話者のID。
            speed: 話速の倍率（デフォルト値や範囲はエンジンに依存）。
            pitch: ピッチ/音高の倍率（デフォルト値や範囲はエンジンに依存）。
            intonation: 抑揚の倍率（デフォルト値や範囲はエンジンに依存）。
            volume: 音量の倍率（デフォルト値や範囲はエンジンに依存）。
            style: 特定の感情スタイル（例: happy, sad など、対応している場合のみ）。
            **kwargs: その他エンジン固有の追加パラメータ。

        戻り値:
            bytes: 合成されたWAV形式の音声データバイナリ。
        """
        pass
