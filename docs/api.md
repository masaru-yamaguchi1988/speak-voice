# Python API・Web API

## Python API

### 音声を合成して再生する

```python
from speak_voice.engines import VoicevoxEngine
from speak_voice.player import play_wav

engine = VoicevoxEngine()

if engine.is_available():
    wav_bytes = engine.synthesize_wav(
        text="こんにちは、お元気ですか？",
        speaker_id="2",
        speed=1.1,
        pitch=0.05,
    )
    play_wav(wav_bytes)
```

### ストリーミング文章を読み上げる

`VoiceAgentBridge`は、句点、感嘆符、疑問符、改行を目安に文章を分割し、バックグラウンドで合成・再生します。

```python
from speak_voice import VoiceAgentBridge
from speak_voice.engines import VoicevoxEngine

bridge = VoiceAgentBridge(VoicevoxEngine(), speaker_id="2", speed=1.1)


def text_stream():
    yield "最初の文章です。"
    yield "続いて、二つ目の文章です。"


try:
    bridge.speak_stream(text_stream())
    bridge.wait_until_done()
finally:
    bridge.stop()
```

途中で止める場合は`bridge.cancel()`を使用します。

```python
bridge.cancel()
bridge.stop()
```

再生完了を待つ場合は、`bridge.stop()`の前に`bridge.wait_until_done()`を呼んでください。音声合成または再生に失敗した場合は`VoiceBridgeError`を送出します。

## Web API

| メソッド | パス | 用途 |
|---|---|---|
| GET | `/api/engines` | 音声エンジンと起動状態 |
| GET | `/api/speakers?engine=voicevox` | 話者一覧 |
| GET | `/api/engine-settings` | エンジン別の調声項目 |
| GET | `/api/models` | ローカルLLMのモデル一覧 |
| GET | `/api/diagnostics/voicepeak` | VOICEPEAKの診断イベント |
| POST | `/api/speak` | 音声合成・再生 |
| POST | `/api/hook/speak` | 外部アプリ向け読み上げ |
| POST | `/api/chat` | LLM回答のストリーミング表示・読み上げ |

`POST /api/chat`では、`system_prompt`へ固定指示、`messages`へ直近40件までの`user`／`assistant`履歴を指定できます。`auto_speak: false`にすると音声エンジンを起動せず、回答生成と表示だけを行います。

```json
{
  "engine": "voicevox",
  "speaker": "2",
  "prompt": "続きを教えて",
  "system_prompt": "日本語で簡潔に回答してください",
  "messages": [
    {"role": "user", "content": "最初の質問"},
    {"role": "assistant", "content": "最初の回答"}
  ],
  "api_provider": "ollama",
  "model_name": "gemma3",
  "disable_thinking": false,
  "auto_speak": true
}
```

Ollamaのthinking対応モデルでは、`disable_thinking: true`を指定するとネイティブAPIへ`think: false`を送信します。

Webコンソールの会話履歴と固定プロンプトはブラウザ内へ保存されます。APIキーは履歴へ含めません。

### フックAPI

```bash
curl http://127.0.0.1:8000/api/hook/speak \
  -H "Content-Type: application/json" \
  -d '{
    "engine": "voicevox",
    "speaker": "2",
    "text": "APIから読み上げます",
    "speed": 1.1,
    "wait": false
  }'
```

`wait: false`ではキュー投入後すぐに応答します。`wait: true`では再生完了まで待ち、合成・再生エラーをHTTPエラーとして返します。
