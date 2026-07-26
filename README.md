# speak-voice

`speak-voice` は、日本の主要な音声合成ソフト（VOICEVOX、COEIROINK、Voicepeak、A.I.VOICE 2、VoiSona Talk）をPythonライブラリおよびCLIから統一されたコードで操作できるようにする、クロスプラットフォーム（Mac / Windows）対応の音声合成ラッパーです。

AIエージェントの会話テキストの自動読み上げや、リアルタイムなストリーミング発話に最適化されています。

## 特徴
- **マルチエンジン対応**: 同一のAPI（`BaseEngine`）から複数の異なる音声合成ソフトを同じ方法で呼び出せます。
- **クロスプラットフォーム再生機能**: `afplay` (Mac) や `winsound` (Windows) などのOS標準機能を利用するため、ビルドエラーになりがちな重いサウンド関係の依存ライブラリなしで即座に音声を再生できます。
- **自動発話ブリッジ (`VoiceAgentBridge`)**: AIのストリーミング応答を逐次受け取り、文単位に自動分割しながらバックグラウンドで非同期的に再生・読み上げが可能です。
- **将来的なWindows対応とCI完備**: macOSおよびWindows双方のネイティブAPI/コマンドラインに配慮した設計となっており、GitHub Actionsでの自動テストCIが構成されています。

## インストール

```bash
pip install .
```

開発者モードでインストールする場合（テストやコードの書き換えを行う場合）：
```bash
pip install -e ".[dev]"
```

## 各エンジンの準備と設定

各エンジンクラスをインスタンス化する際、接続設定を指定できます。

| エンジン名 | キー名 | 接続方式 / デフォルト値 | 必要な事前準備 |
| :--- | :--- | :--- | :--- |
| **VOICEVOX** | `voicevox` | HTTP API (`127.0.0.1:50021`) | VOICEVOX エディタまたはエンジンを起動しておく |
| **COEIROINK** | `coeiroink` | HTTP API (`127.0.0.1:50032`) | COEIROINK エディタを起動しておく |
| **Voicepeak** | `voicepeak` | CLI 実行ファイル | パスが通っているか、`/Applications/voicepeak.app` にインストールされていること |
| **A.I.VOICE 2** | `aivoice` | Windows COM API | A.I.VOICE 2 Editor がインストールされていること（Windows専用） |
| **VoiSona Talk** | `voisona` | スタブ（将来対応用） | - |

---

## 1. ライブラリとしての使用方法 (Python API)

### 基本的な音声合成と再生
```python
from speak_voice.engines import VoicevoxEngine
from speak_voice.player import play_wav

# VOICEVOXエンジンの初期化 (デフォルトでは 127.0.0.1:50021)
engine = VoicevoxEngine()

# 起動状態のチェック
if engine.is_available():
    # 利用可能なキャラクター一覧の取得
    speakers = engine.get_speakers()
    for speaker in speakers:
        print(f"ID: {speaker.id} - 名前: {speaker.name}")

    # 音声の合成（話速1.2倍、音高少し高めに設定）
    # speaker_id には get_speakers() で取得した ID (例: VOICEVOXなら "1", COEIROINKなら "uuid:style_id") を渡します
    wav_bytes = engine.synthesize_wav(
        text="こんにちは、お元気ですか？",
        speaker_id="1",
        speed=1.2,
        pitch=0.05
    )

    # 音声の再生
    play_wav(wav_bytes)
```

---

## 2. AIエージェント（LLM）との詳細な連携方法

AIエージェントのテキスト応答は、トークン単位で少しずつ生成（ストリーミング出力）されるのが一般的です。
`VoiceAgentBridge` を使用すると、画面上にAIの返答文字を出力させつつ、裏側で自然な文章単位（`。`や改行）に自動分割して順番に喋らせることができます。

### 例1：OpenAI API（ストリーミング）との連携例
```python
import os
from openai import OpenAI
from speak_voice import VoiceAgentBridge
from speak_voice.engines import VoicevoxEngine

# OpenAIクライアントと音声合成エンジンの準備
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
engine = VoicevoxEngine()

# 話速やキャラクター（例: 四国めたん=2番など）を設定してブリッジを作成
bridge = VoiceAgentBridge(engine, speaker_id="2", speed=1.1)

# ユーザーからのチャット入力を模倣
prompt = "日本の美味しい食べ物について、3文で教えてください。"

# OpenAIにストリーミング形式でリクエストを投げる
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}],
    stream=True
)

# ストリーミングトークンを中継するジェネレータ関数を定義
def token_generator():
    for chunk in response:
        content = chunk.choices[0].delta.content
        if content:
            # 1. ターミナル等にリアルタイムでテキストを表示
            print(content, end="", flush=True)
            # 2. 音声ブリッジにテキストの断片を yield
            yield content
    print() # 最後に改行を入れる

try:
    # speak_streamを実行すると、ジェネレータから随時届く文字を日本語の「文」として
    # 切り出し、バックグラウンドのキューに溜めて順次発話してくれます。
    bridge.speak_stream(token_generator())

    # キュー内の音声合成・再生がすべて完了するまで待機
    bridge.wait_until_done()
finally:
    # バックグラウンド再生スレッドを安全に停止
    bridge.stop()
```

### 例2：Gemini API (`google-genai` SDK) との連携例
```python
import os
from google import genai
from speak_voice import VoiceAgentBridge
from speak_voice.engines import VoicevoxEngine

# Google GenAI クライアント (最新 SDK `google-genai` 推奨)
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
engine = VoicevoxEngine()

bridge = VoiceAgentBridge(engine, speaker_id="2", speed=1.1)

# 利用中のGemini APIで有効なモデル名を指定
stream = client.models.generate_content_stream(
    model=os.environ["GEMINI_MODEL"],
    contents='こんにちは、今日の天気はどうですか？'
)

def gemini_generator():
    for chunk in stream:
        if hasattr(chunk, "text") and chunk.text:
            print(chunk.text, end="", flush=True)
            yield chunk.text
    print()

try:
    bridge.speak_stream(gemini_generator())
    bridge.wait_until_done()  # 音声再生完了までしっかり待つ
finally:
    bridge.stop()
```

> [!TIP]
> **再生完了の同期についての注意点**  
> `speak_stream()` の呼び出し自体はテキスト出力ストリームが終了した時点で完了します。  
> 音声合成とスピーカー再生が最後まで途切れるのを防ぐため、`finally` ブロックで `bridge.stop()` を呼ぶ直前に **`bridge.wait_until_done()`** を必ず呼び出してください。

---

## 3. コマンドラインツール (CLI) としての使用方法

インストールが完了すると、`speak-voice` コマンドが使用可能になります。

### 対応エンジンの一覧と起動確認
```bash
speak-voice list-engines
```
*出力例:*
```
Available Engines:
  - voicevox    : VOICEVOX (Available)
  - coeiroink   : COEIROINK (Not Installed/Running)
  - voicepeak   : Voicepeak (Available)
  ...
```

### 特定エンジンの話者一覧の取得
```bash
speak-voice list-speakers --engine voicevox
```
*出力例:*
```
Speakers for VOICEVOX:
  ID                             | Name
--------------------------------------------------
  2                              | 四国めたん (ノーマル)
  0                              | 四国めたん (あまあま)
  ...
```

### 合成と再生
指定したテキストを指定したエンジンと話者で喋らせます。
```bash
# VOICEVOXで喋らせる
speak-voice speak "こんにちは" --engine voicevox --speaker 2

# Voicepeakで感情を設定して喋らせる (※エモーショナル対応モデルのみ)
speak-voice speak "とても嬉しいです" --engine voicepeak --speaker "Female 1" --style "happy=100"

# 調声パラメータを指定する (話速 1.5倍)
speak-voice speak "早口で喋ります" --engine voicevox --speaker 2 --speed 1.5
```

### 音声データのファイル保存
`-o` または `--out` オプションを使用すると、再生する代わりにWAVファイルに保存します。
```bash
speak-voice speak "この音声を保存します" --engine voicevox --speaker 2 --out output.wav
```

### 他のアプリやブラウザから読み上げる

Webコンソールを起動した状態で、任意のテキストをフックAPIへ送れます。

```bash
speak-voice hook "読み上げたい文章"
```

クリップボードにコピーした文章を読み上げる場合：

```bash
speak-voice-clip --wait
```

`speak-voice-clip` はRaycast、Alfred、macOSショートカットなどのシェルコマンドとして登録できます。Webコンソールには、Webページ上で選択した文章を送信するブックマークレットも用意されています。音声エンジンと話者を選んだ後、「選択テキストを読み上げ」ボタンをブラウザのブックマークバーへドラッグしてください。

Webサーバーを起動していない場合、CLIの`hook`コマンドは指定した音声エンジンを直接呼び出して再生を試みます。

---

## 4. Webコンソール（GUI）の使用方法

Webコンソールを使用すると、ブラウザ上でエンジン選択・話者選択・調声パラメータ設定・AIエージェントとのチャットテストをすべてGUIで操作できます。

### 起動方法

Web用の依存関係をインストールしてから起動します：

```bash
pip install -e ".[web]"
speak-voice-web
```

または直接 Python モジュールとして起動：

```bash
python -m speak_voice.web.app
```

サーバーが `http://127.0.0.1:8000` で起動します。ブラウザでアクセスしてください。

### Webコンソールの機能

#### 左パネル: 連携設定 ＆ 音声調声
- **API Key 入力**: OpenAI / Gemini の API Key を入力すると、実際のLLMと連携してチャットできます。未入力の場合はモックエージェントで動作確認が可能です。
- **エンジン選択**: 対応している音声合成エンジン（VOICEVOX、COEIROINK、Voicepeak 等）をドロップダウンで切り替えられます。起動中のエンジンには「有効」と表示されます。
- **話者選択**: 選択中のエンジンに登録されているキャラクター/話者がドロップダウンに一覧表示されます。
- **調声スライダー**: 話速（Speed）、音高（Pitch）、抑揚（Intonation）、音量（Volume）をスライダーでリアルタイムに調整できます。
- **テスト再生ボタン**: 現在の設定パラメータでテスト用の定型文を即座に合成・再生します。

#### 右パネル: AIエージェント対話
- テキストを入力して送信すると、設定されたAPI（OpenAI / Gemini / Mock）を通じてAIが応答を生成します。
- 生成されたテキストは画面上に表示されると同時に、選択中のエンジン・話者・調声パラメータを使って自動的に音声再生されます。

---

## 5. 注意点・トラブルシューティング

> [!WARNING]
> **Gemini API のモデル名指定について**  
> 利用可能なモデル名はAPIや時期によって変わります。Webコンソールは、入力されたモデル名を優先し、未指定時はGemini APIから取得した利用可能なモデルを選びます。モデル一覧を取得できない場合は、利用中のAPIで有効なモデル名を画面から明示してください。

> [!NOTE]
> **Google SDK のバージョン互換性**  
> 現在 Google 公式から提供されている新しい `google-genai` SDK (`from google import genai`) の利用を推奨します。旧ライブラリ `google-generativeai` がインストールされていない環境でも問題なく動作します。

> [!IMPORTANT]
> **音声の読み上げが途中で切れる場合**  
> `VoiceAgentBridge` を Python スクリプトで使用する際は、AIのテキスト生成終了と音声再生完了のタイミングが異なります。`bridge.stop()` を呼ぶ前に必ず **`bridge.wait_until_done()`** を実行して発話キューの処理完了を待機させてください。

---

## テストの実行

```bash
pytest
```
