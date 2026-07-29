# speak-voice

`speak-voice`は、複数の日本語音声合成ソフトをCLI・Webコンソール・Pythonから共通の操作で利用するためのラッパーです。

LLMの回答をストリーミング表示しながら読み上げるほか、ブラウザで選択した文章や、他のアプリでコピーした文章も音声化できます。

## 主な機能

- VOICEVOX、COEIROINK、VOICEPEAK、VoiSona Talkに対応
- OpenAI、Gemini、Ollama、OpenAI互換ローカルLLMとのチャット
- キャラクター／スタイル選択とエンジン別の調声スライダー
- 回答生成、再生中の音声、待機中の読み上げをまとめて停止
- ブラウザ、クリップボード、Raycast、Alfredなどから読み上げ

## 対応エンジン

| 音声エンジン | キー | 接続方式 |
|---|---|---|
| VOICEVOX | `voicevox` | HTTP API `127.0.0.1:50021` |
| COEIROINK v2 | `coeiroink` | HTTP API `127.0.0.1:50032` |
| VOICEPEAK | `voicepeak` | 公式CLI |
| VoiSona Talk | `voisona` | REST API `127.0.0.1:32766` |

Python 3.10以上と、使用する音声合成ソフトが必要です。音声エンジンやローカルLLMの設定は[接続・設定ガイド](docs/configuration.md)を参照してください。

## クイックスタート

### 1. インストール

リポジトリのディレクトリで、Webコンソールを含めてインストールします。

```bash
python -m pip install -e ".[web]"
```

### 2. 音声合成エンジンを起動

使用する音声合成ソフトを起動します。たとえばVOICEVOXを使う場合は、VOICEVOXエディタまたはエンジンを起動してください。

接続状態と話者を確認できます。

```bash
speak-voice list-engines
speak-voice list-speakers --engine voicevox
```

### 3. Webコンソールを起動

```bash
speak-voice-web
```

ブラウザで[http://127.0.0.1:8000](http://127.0.0.1:8000)を開きます。

## Webコンソールの使い方

1. LLMプロバイダーを選択
2. 必要に応じてBase URLやAPIキーを入力
3. ローカルLLMの場合は「再取得」からモデルを選択
4. 音声合成エンジンとキャラクター／スタイルを選択
5. 話速、音高、抑揚、音量などをスライダーで調整
6. テスト再生またはチャットを実行

文章入力欄ではEnterで改行し、Shift + Enterで送信します。「停止」を押すと、回答生成、再生中の音声、待機中の読み上げをまとめて中断できます。

VoiSona Talkを選択した場合は、画面に表示される接続設定へAPI URL、ユーザー名、API用パスワードを入力してください。詳細は[VoiSona Talkの設定](docs/configuration.md#voisona-talk)を参照してください。

## CLIで読み上げる

話者を確認して、文章を再生します。

```bash
speak-voice list-speakers --engine voicevox
speak-voice speak "こんにちは" --engine voicevox --speaker 2
```

調声パラメータや保存先も指定できます。

```bash
speak-voice speak "少し早口で読み上げます" \
  --engine voicevox \
  --speaker 2 \
  --speed 1.2 \
  --pitch 0.05 \
  --intonation 1.1 \
  --volume 1.0 \
  --out output.wav
```

## 他のアプリから読み上げる

Webコンソールの「選択テキストを読み上げ」をブックマークバーへ登録すると、Webページで選択した文章を送信できます。

クリップボードの文章を読み上げる場合：

```bash
speak-voice-clip --wait
```

テキストを直接送る場合：

```bash
speak-voice hook "読み上げたい文章" --engine voicevox --speaker 2
```

Raycast、Alfred、macOSショートカットなどへの登録方法は[外部アプリ連携](docs/external-apps.md)を参照してください。

## 詳細ドキュメント

- [音声エンジンとLLMの接続・設定](docs/configuration.md)
- [ブラウザ・クリップボード・外部アプリ連携](docs/external-apps.md)
- [Python API・Web API](docs/api.md)
- [トラブルシューティング](docs/troubleshooting.md)
- [開発・テスト・依存関係管理](docs/development.md)

## ライセンス

MIT
