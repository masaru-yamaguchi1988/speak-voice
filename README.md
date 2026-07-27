# speak-voice

`speak-voice`は、VOICEVOX、COEIROINK、Voicepeakなどの日本語音声合成ソフトを、Python API・CLI・Webコンソールから共通の操作で利用するためのラッパーです。

LLMのストリーミング回答を文章単位で順番に読み上げるほか、ブラウザで選択した文章や、他のアプリからコピーした文章をすぐに音声化できます。

## 主な機能

- 複数の音声合成エンジンを共通APIで操作
- OpenAI、Gemini、Ollama、OpenAI互換ローカルLLMとのチャット
- Ollama／ローカルLLMの利用可能モデルを自動取得して選択
- LLMの回答を画面へストリーミング表示しながら文単位で読み上げ
- 停止ボタンやブラウザ切断に連動して、回答生成・再生中の音声・待機キューを停止
- ブラウザの選択テキストを送るブックマークレット
- クリップボード、Raycast、Alfred、macOSショートカットなどからの読み上げ
- macOS、Windows、Linuxの標準機能を利用した音声再生

## 対応状況

| 音声エンジン | キー | 接続方式 | 状況 |
|---|---|---|---|
| VOICEVOX | `voicevox` | HTTP API `127.0.0.1:50021` | 対応 |
| COEIROINK v2 | `coeiroink` | HTTP API `127.0.0.1:50032` | 対応 |
| Voicepeak | `voicepeak` | 公式CLI | 対応 |
| A.I.VOICE 2 | `aivoice` | Windows COM API | 試験的実装・実機検証が必要 |
| VoiSona Talk | `voisona` | － | 未実装 |

| LLMプロバイダー | 用途 | モデル選択 |
|---|---|---|
| Ollama | ローカルLLM | `/api/tags`から自動取得 |
| Local OpenAI | LM Studio、vLLMなど | `/v1/models`から自動取得 |
| OpenAI | OpenAI API | アプリの既定モデル |
| Gemini | Google Gemini API | APIから利用可能モデルを探索 |
| Mock | 接続確認 | APIキー不要 |

## 必要環境

- Python 3.10以上
- 使用する音声合成ソフト
- Webコンソールを使う場合はWeb用の追加依存関係
- ローカルLLMを使う場合はOllama、LM Studioなど

音声再生には次のOS標準機能または一般的なコマンドを使用します。

- macOS: `afplay`
- Windows: `winsound`
- Linux: `aplay`、`paplay`、`play`のいずれか

## クイックスタート

### 1. インストール

Webコンソールを含めて開発モードでインストールします。

```bash
python -m pip install -e ".[web]"
```

テスト・整形ツールも入れる場合：

```bash
python -m pip install -e ".[web,dev]"
```

### 2. 音声合成エンジンを起動

たとえばVOICEVOXを使用する場合は、VOICEVOXエディタまたはエンジンを起動します。

接続状態はCLIから確認できます。

```bash
speak-voice list-engines
speak-voice list-speakers --engine voicevox
```

### 3. Webコンソールを起動

```bash
speak-voice-web
```

ブラウザで[http://127.0.0.1:8000](http://127.0.0.1:8000)を開きます。

## Webコンソール

Webコンソールでは、次の順番で設定します。

1. LLMプロバイダーを選択
2. 必要に応じて接続先やAPIキーを入力
3. ローカルLLMの場合は取得されたモデルをプルダウンから選択
4. 音声合成エンジンとキャラクター／スタイルを選択
5. 選択したエンジンに対応する調声スライダーを調整
6. テスト再生またはチャットを実行

VOICEVOXとCOEIROINKでは、スタイルをキャラクター単位でグループ表示します。調声項目・設定範囲・初期値はエンジンに合わせて自動的に切り替わります。

- VOICEVOX: 話速、音高、抑揚、音量
- COEIROINK: 話速、音高、抑揚、音量
- Voicepeak: 話速、音高、音量、利用可能な感情
- A.I.VOICE 2: 話速、音高、抑揚、音量

Voicepeakでナレーター固有の感情を取得できる場合は、感情ごとの強さも0～100のスライダーで指定できます。

### Ollamaを使用する

Ollamaを起動し、少なくとも1つモデルを取得しておきます。

```bash
ollama list
ollama pull gemma3
```

Web画面で次を選択します。

- AIプロバイダー: `Ollama`
- Base URL: `http://localhost:11434/v1`
- モデル: 自動取得されたモデルから選択

一覧が更新されない場合は「再取得」を押してください。

### LM Studioなどを使用する

OpenAI互換サーバーを起動し、Web画面で次を選択します。

- AIプロバイダー: `Local OpenAI`
- Base URL: 例 `http://localhost:1234/v1`
- モデル: `/v1/models`から取得されたモデル

### 回答と音声を停止する

チャット中に「停止」を押すと、次の処理をまとめて中断します。

- ブラウザでの回答受信
- サーバー側の回答処理
- 現在再生中の音声
- 待機中の読み上げ文章

タブを閉じるなどブラウザとの接続が切れた場合も、サーバー側で検知して停止します。音声合成APIへの実行中リクエストだけは、接続先の処理が戻るまで短時間残ることがあります。

## ブラウザや他のアプリから読み上げる

### ブックマークレット

Webコンソールで音声エンジンと話者を選択し、「選択テキストを読み上げ」をブラウザのブックマークバーへドラッグします。

任意のWebページで文章を選択してブックマークを押すと、ローカルの`speak-voice`へ文章が送られます。文章を選択していない場合は入力ダイアログが表示されます。

Webコンソールは`127.0.0.1`だけで待ち受けますが、ブックマークレット利用のため外部ページからローカルのフックAPIへのPOSTを許可しています。

### クリップボード

文章をコピーしてから実行します。

```bash
speak-voice-clip --wait
```

エンジンや話者も指定できます。

```bash
speak-voice-clip \
  --engine voicevox \
  --speaker 2 \
  --speed 1.1 \
  --wait
```

クリップボード取得には次のコマンドを使用します。

- macOS: `pbpaste`
- Windows: PowerShell `Get-Clipboard`
- Linux: `wl-paste`、`xclip`、`xsel`のいずれか

このコマンドはRaycast、Alfred、macOSショートカットなどのシェルコマンドとして登録できます。

### テキストを直接送る

```bash
speak-voice hook "読み上げたい文章" \
  --engine voicevox \
  --speaker 2
```

通常はWebサーバーの`POST /api/hook/speak`へ送信します。Webサーバーへ接続できない場合は、指定した音声エンジンをCLIから直接呼び出して再生を試みます。

## CLI

### エンジンの状態を確認

```bash
speak-voice list-engines
```

### 話者を確認

```bash
speak-voice list-speakers --engine voicevox
```

### 合成して再生

```bash
speak-voice speak "こんにちは" \
  --engine voicevox \
  --speaker 2
```

調声パラメータを指定できます。

```bash
speak-voice speak "少し早口で読み上げます" \
  --engine voicevox \
  --speaker 2 \
  --speed 1.2 \
  --pitch 0.05 \
  --intonation 1.1 \
  --volume 1.0
```

Voicepeakでは感情パラメータも指定できます。

```bash
speak-voice speak "とても嬉しいです" \
  --engine voicepeak \
  --speaker "Female 1" \
  --style "happy=100"
```

### WAVファイルへ保存

```bash
speak-voice speak "保存する音声です" \
  --engine voicevox \
  --speaker 2 \
  --out output.wav
```

## セキュリティと依存関係の管理

このリポジトリでは、依存関係の脆弱性を検知するために GitHub Actions 上で `pip-audit` を実行します。

- プッシュまたは PR 時に自動的に脆弱性スキャンを実行
- 毎週 1 回、定期的に依存関係を確認
- Dependabot により Python パッケージと GitHub Actions の更新候補を自動的に提案

ローカルでも次のコマンドで確認できます。

```bash
python -m pip install -e ".[dev]"
pip-audit -r <(python -m pip freeze)
```

## Python API

### 音声を合成して再生

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

### ストリーミング文章を順番に読み上げる

`VoiceAgentBridge`は、`。`、`！`、`？`、改行を目安に文章を分割し、バックグラウンドで合成・再生します。

```python
from speak_voice import VoiceAgentBridge
from speak_voice.engines import VoicevoxEngine

engine = VoicevoxEngine()
bridge = VoiceAgentBridge(engine, speaker_id="2", speed=1.1)


def text_stream():
    yield "最初の文章です。"
    yield "続いて、二つ目の文章です。"


try:
    bridge.speak_stream(text_stream())
    bridge.wait_until_done()
finally:
    bridge.stop()
```

再生完了を待つ場合は、`bridge.stop()`の前に`bridge.wait_until_done()`を呼んでください。途中で止める場合は`bridge.cancel()`を使用できます。

```python
bridge.cancel()
bridge.stop()
```

音声合成または再生に失敗した場合、`wait_until_done()`は`VoiceBridgeError`を送出します。

## Web API

主なエンドポイント：

| メソッド | パス | 用途 |
|---|---|---|
| GET | `/api/engines` | 音声エンジンと起動状態 |
| GET | `/api/speakers?engine=voicevox` | 話者一覧 |
| GET | `/api/models` | ローカルLLMのモデル一覧 |
| POST | `/api/speak` | 音声合成・再生 |
| POST | `/api/hook/speak` | 外部アプリ向け読み上げ |
| POST | `/api/chat` | LLM回答のストリーミング表示・読み上げ |

フックAPIの例：

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

## トラブルシューティング

### Ollamaで404になる

Ollamaが起動していても、指定モデルが未取得の場合は404になります。

```bash
ollama list
ollama pull gemma3
```

Base URLは通常`http://localhost:11434/v1`です。Web画面の「再取得」でモデルが表示されることを確認してください。

### 音声エンジンが「無効」と表示される

- VOICEVOXまたはCOEIROINKのエディタ／エンジンが起動しているか確認
- 使用ポートが既定値と異なっていないか確認
- Voicepeakは実行ファイルの場所を確認
- Voicepeakの場所を変更する場合は`VOICEPEAK_PATH`環境変数を設定

COEIROINKは軽量な`/v1/engine_info`で起動確認し、画像データを含まない`/v1/speakers_path_variant`から話者一覧を取得します。音声合成にはCOEIROINK v2の`/v1/synthesis`を使用します。

### Linuxで音声が再生されない

`aplay`、`paplay`、`play`のいずれかをインストールしてください。

### クリップボードを取得できない

Linuxでは環境に合わせて`wl-paste`、`xclip`、`xsel`のいずれかをインストールしてください。

### Python APIの読み上げが途中で切れる

`bridge.stop()`の前に`bridge.wait_until_done()`を呼び出してください。

```python
bridge.wait_until_done()
bridge.stop()
```

## 開発

### テスト

```bash
pytest
```

### CIと整形

CIはLinux、macOS、Windows上のPython 3.10～3.12で次を確認します。

```bash
black --check src tests
isort --check src tests
pytest
```

ローカルで整形する場合：

```bash
black src tests
isort src tests
```

## ライセンス

MIT
