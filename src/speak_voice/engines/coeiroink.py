from typing import List, Optional

import requests

from speak_voice.base import BaseEngine, Speaker


class CoeiroinkEngine(BaseEngine):
    """ローカルで稼働する COEIROINK (v2) の HTTP API を利用する音声合成エンジン実装クラス。"""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 50032,
        output_sampling_rate: int = 44100,
    ):
        self.base_url = f"http://{host}:{port}"
        self.output_sampling_rate = output_sampling_rate

    @property
    def engine_name(self) -> str:
        return "COEIROINK"

    def is_available(self) -> bool:
        try:
            # 画像を含む話者一覧は非常に大きいため、軽量なエンジン情報で確認する
            response = requests.get(f"{self.base_url}/v1/engine_info", timeout=1.0)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def get_speakers(self) -> List[Speaker]:
        try:
            # path variantはbase64画像を含まないため、通常のspeakersより大幅に軽量
            response = requests.get(f"{self.base_url}/v1/speakers_path_variant", timeout=5.0)
            if response.status_code == 404:
                response = requests.get(f"{self.base_url}/v1/speakers", timeout=10.0)
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
                                "version": item.get("version"),
                                "pathIcon": s.get("pathIcon"),
                                "pathPortrait": s.get("pathPortrait"),
                            },
                        )
                    )
            return speakers
        except (requests.RequestException, ValueError, TypeError):
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

        if not text.strip():
            raise ValueError("合成するテキストが空です。")

        # COEIROINK v2のsynthesisは予測と音声処理を一度に実行する
        synth_payload = {
            "speakerUuid": speaker_uuid,
            "styleId": style_id_int,
            "text": text,
            "speedScale": speed if speed is not None else 1.0,
            "pitchScale": pitch if pitch is not None else 0.0,
            "intonationScale": intonation if intonation is not None else 1.0,
            "volumeScale": volume if volume is not None else 1.0,
            "prePhonemeLength": kwargs.get("pre_phoneme_length", 0.1),
            "postPhonemeLength": kwargs.get("post_phoneme_length", 0.1),
            "outputSamplingRate": kwargs.get("output_sampling_rate", self.output_sampling_rate),
        }
        synth_resp = requests.post(
            f"{self.base_url}/v1/synthesis",
            json=synth_payload,
            headers={"Accept": "audio/wav"},
            timeout=60.0,
        )
        try:
            synth_resp.raise_for_status()
        except requests.HTTPError as error:
            try:
                detail = synth_resp.json().get("detail")
            except (ValueError, AttributeError):
                detail = synth_resp.text
            raise RuntimeError(f"COEIROINK音声合成に失敗しました: {detail}") from error
        return synth_resp.content
