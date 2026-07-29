# 開発・テスト・依存関係管理

## 開発環境

Web機能、テスト、整形ツールを含めてインストールします。

```bash
python -m pip install -e ".[web,dev]"
```

## テスト

```bash
PYTHONPATH=src pytest
```

## 整形と静的チェック

```bash
black --check src tests
isort --check-only src tests
python -m compileall -q src tests
```

ローカルで整形する場合：

```bash
black src tests
isort src tests
```

CIではLinux、macOS、Windows上のPython 3.10～3.12で整形とテストを確認します。

## 依存関係の管理

GitHub Actionsで`pip-audit`を実行します。

- プッシュまたはPull Request時に脆弱性をスキャン
- 毎週1回、定期的に依存関係を確認
- DependabotがPythonパッケージとGitHub Actionsの更新候補を提案

ローカルで確認する場合：

```bash
python -m pip install -e ".[dev]"
pip-audit -r <(python -m pip freeze)
```
