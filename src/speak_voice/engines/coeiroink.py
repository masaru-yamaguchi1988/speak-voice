from typing import List, Optional

import requests

from speak_voice.base import BaseEngine, Speaker


class CoeiroinkEngine(BaseEngine):
    """ローカルで稼働する COEIROINK (v2) の HTTP API を利用する音声合成エンジン実装クラス。"""

    def __init__(self, host: str = "127.0.0.1", port: int = 50032):
        self.base_url = f"http://{host}:{port}"

    @property
    def engine_name(self) -> str:
        return "COEIROINK"

    def is_available(self) -> bool:
        try:
            # v1/speakers エンドポイントを叩いて稼働中かチェック
            response = requests.get(f"{self.base_url}/v1/speakers", timeout=1.0)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def get_speakers(self) -> List[Speaker]:
        try:
            # COEIROINK v2 話者一覧API呼び出し
            response = requests.get(f"{self.base_url}/v1/speakers", timeout=2.0)
            response.raise_for_status()
            speakers_data = response.json()

            speakers = []
            for item in speakers_data:
                name = item.get("speakerName", "")
                uuid = item.get("speakerUuid", "")
                styles = [s.get("styleName", "") for s in item.get("styles", [])]
                for s in item.get("styles", []):
                    style_id = str(s.get("styleId"))
                    style_name = s.get("styleName", "")
                    # COEIROINK v2 では speakerUuid と styleId のペアが必要なため、"uuid:style_id" 形式でID化
                    composite_id = f"{uuid}:{style_id}"
                    speakers.append(
                        Speaker(
                            id=composite_id,
                            name=f"{name} ({style_name})",
                            styles=styles,
                            raw_info={
                                "speakerUuid": uuid,
                                "styleId": style_id,
                                "speakerName": name,
                                "styleName": style_name,
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
        # 複合ID (uuid:style_id) のパース
        if ":" in speaker_id:
            speaker_uuid, style_id = speaker_id.split(":", 1)
            style_id_int = int(style_id)
        else:
            # 万が一複合IDになっていない場合のフォールバック
            speaker_uuid = speaker_id
            style_id_int = 0

        # ステップ 1: 音声クエリ (audio_query) の予測生成
        query_payload = {"text": text, "speakerUuid": speaker_uuid, "styleId": style_id_int}
        query_resp = requests.post(
            f"{self.base_url}/v1/predict_audio_query", json=query_payload, timeout=5.0
        )
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

        # ステップ 3: 音声合成の実行
        synth_payload = {
            "speakerUuid": speaker_uuid,
            "styleId": style_id_int,
            "audioQuery": query_data,
        }
        synth_resp = requests.post(
            f"{self.base_url}/v1/predict_synthesis", json=synth_payload, timeout=15.0
        )
        synth_resp.raise_for_status()
        return synth_resp.content
