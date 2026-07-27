from typing import List, Optional

import requests

from speak_voice.base import BaseEngine, Speaker


class VoicevoxEngine(BaseEngine):
    """ローカルで稼働する VOICEVOX の HTTP API を利用する音声合成エンジン実装クラス。"""

    def __init__(self, host: str = "127.0.0.1", port: int = 50021):
        self.base_url = f"http://{host}:{port}"

    @property
    def engine_name(self) -> str:
        return "VOICEVOX"

    def is_available(self) -> bool:
        try:
            # VOICEVOXが起動しているか確認するためにバージョン情報を取得
            response = requests.get(f"{self.base_url}/version", timeout=1.0)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def get_speakers(self) -> List[Speaker]:
        try:
            # 利用可能なキャラクター（話者）の一覧を取得
            response = requests.get(f"{self.base_url}/speakers", timeout=2.0)
            response.raise_for_status()
            speakers_data = response.json()

            speakers = []
            for item in speakers_data:
                name = item.get("name", "")
                # 利用可能なスタイルの名前リスト
                styles = [s.get("name", "") for s in item.get("styles", [])]
                # 各スタイルIDごとに話者オブジェクトを生成
                for s in item.get("styles", []):
                    style_id = str(s.get("id"))
                    style_name = s.get("name", "")
                    speakers.append(
                        Speaker(
                            id=style_id,
                            name=f"{name} ({style_name})",
                            styles=styles,
                            raw_info={
                                "speakerName": name,
                                "styleName": style_name,
                                "speakerUuid": item.get("speaker_uuid"),
                                "styleId": style_id,
                                "styleType": s.get("type"),
                            },
                        )
                    )
            return speakers
        except requests.RequestException:
            return []

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
        # ステップ 1: 音声クエリ（パラメータ構成情報）の生成
        query_params = {"text": text, "speaker": int(speaker_id)}
        query_resp = requests.post(f"{self.base_url}/audio_query", params=query_params, timeout=5.0)
        query_resp.raise_for_status()
        query_data = query_resp.json()

        # ステップ 2: 調声用パラメータの適用
        if speed is not None:
            query_data["speedScale"] = speed
        if pitch is not None:
            query_data["pitchScale"] = pitch
        if intonation is not None:
            query_data["intonationScale"] = intonation
        if volume is not None:
            query_data["volumeScale"] = volume

        # ステップ 3: 音声データの合成実行
        synth_params = {"speaker": int(speaker_id)}
        synth_resp = requests.post(
            f"{self.base_url}/synthesis", params=synth_params, json=query_data, timeout=15.0
        )
        synth_resp.raise_for_status()
        return synth_resp.content
