# X-Reach X調査特化最適化計画

Agent-Reach由来の汎用的な「マルチチャネル調査フレームワーク」構造を、X/Twitter単一チャネルに最適化したシャープなツールへ変革する。

## 現状の分析結果

### 定量データ
| 項目 | 値 |
|---|---|
| 総Pythonコード行数 | ~6,500行 (agent_reach内) |
| CLI (cli.py) | 1,622行 |
| 結果スキーマ (results.py) | 529行 |
| チャネル/アダプタ基底クラス | 207行 (使われ方は1つだけ) |
| テスト | 129件 全パス |
| 登録チャネル | **1つ** (twitter) |

### 特定した冗長・ノイズ箇所

#### 1. パッケージ名の混乱 (影響: 大)
- コアロジックが `agent_reach/` に残り、`x_reach/` は薄いラッパー
- `AgentReachClient` が主クラス名、`XReachClient` はエイリアス
- `agent-reach` CLI エイリアスが pyproject.toml に残存
- Legacy スキル名 `agent-reach-*` が7個定義

#### 2. 未使用の汎用抽象レイヤー (影響: 大)
- `channels/base.py`: `read`, `crawl`, `top`, `new`, `best` 等の汎用オペレーション定義 → Twitterでは `search`, `user`, `user_posts`, `tweet` の4つのみ
- `adapters/base.py`: 汎用 `BaseAdapter` に `crawl`, `top`, `new`, `best` メソッド定義
- `client.py`: `_Namespace` に `read()`, `crawl()`, `top()`, `new()`, `best()` メソッド → Twitter未使用
- `channels/__init__.py`: 動的チャネルレジストリ → チャネルは1つだけ

#### 3. results.py の他チャネル残骸 (影響: 中)
- `engagement` に `stars`, `forks` (GitHub固有), `points`, `descendants` (HN固有)
- `_normalize_identifiers` に `repo_full_name` (GitHub固有ロジック)
- `_HTML_ENTITY_RE` と web スクレイピング用のテキスト正規化
- `error.category` に `auth_expired`, `suspended` 等のX専用と、`paywall`, `robots_blocked` 等のweb専用が混在

#### 4. CLI の冗長 (影響: 中)
- `--channel twitter` を毎回指定する必要がある（チャネルは1つしかない）
- `--body-mode` (web channel用), `--query`/`crawl_query` (crawl用) 等の不要オプション
- `--page-size`, `--max-pages`, `--cursor`, `--page` → Twitter adapter は使わない
- doctor の `--require-channel` / `--require-channels` / `--require-all` → 1チャネルなので無意味

#### 5. scout.py の過剰設計 (影響: 小)
- 複数チャネルのcapabilityを比較する設計 → 1チャネルでは意味がない
- `PRESETS` の `social-pulse`, `timeline-check` → どちらも `("twitter",)` のみ

#### 6. 設定の冗長 (影響: 小)
- `FEATURE_REQUIREMENTS` マルチチャネル設定テーブル
- `.agent-reach` / `.x-reach` 二重パス対応
- コメント内の `# Agent Reach Configuration`

---

## User Review Required

> [!NOTE]
> **Phase 1 完了**: 汎用構造のX特化クリーンアップはすべて完了し、全テストおよびライブ収集テストも成功しました。

> [!IMPORTANT]
> **Phase 2 計画承認**:
> Phase 1が完了したため、ユーザーの要望に基づき Phase 2 に着手します。
> 以下の実装計画でよろしいかご確認ください。
> 
> 1. **ハッシュタグ検索の追加**: 新しいオペレーション `hashtag` を追加し、`x-reach collect --operation hashtag --input "#AI"` のように動作させます。
> 2. **エンゲージメントフィルタリング**: `--min-likes`, `--min-retweets`, `--min-views` などのオプションを追加し、バズっている投稿や質の高い情報を抽出しやすくします。
> 3. **パッケージ名統一**: `agent_reach` のソースコードを `x_reach` に移動させ、名実ともに単一の `x-reach` ツールとして完成させます。

---

## Proposed Changes

### Phase 1: 汎用構造のX特化クリーンアップ（完了 ✅）

---

### 1-A. results.py から他チャネル残骸を除去

#### [MODIFY] [results.py](file:///c:/x-reach/agent_reach/results.py)
- `engagement` スキーマからGitHub固有 (`stars`, `forks`)、HN固有 (`points`, `descendants`) フィールドを削除
- X専用engagement: `likes`, `retweets`, `replies`, `quotes`, `views`, `bookmarks` のみ保持
- `_normalize_identifiers` からGitHub `repo_full_name` ロジックを削除
- `_HTML_ENTITY_RE` 等のweb scraping用テキスト正規化を削除
- エラーカテゴリからweb固有 (`paywall`, `robots_blocked`, `geo_blocked`) を削除
- X専用に最適化されたURL正規化 (`x.com`, `twitter.com`) の強化

---

### 1-B. 基底クラスのスリム化

#### [MODIFY] [base.py (channels)](file:///c:/x-reach/agent_reach/channels/base.py)
- 汎用オペレーション (`read`, `crawl`, `top`, `new`, `best`) の定義を削除
- Twitter固有オペレーション (`search`, `user`, `user_posts`, `tweet`) のみ残す
- `KNOWN_OPERATIONS` をX専用セットに更新

#### [MODIFY] [base.py (adapters)](file:///c:/x-reach/agent_reach/adapters/base.py)
- 汎用メソッド (`crawl`, `top`, `new`, `best`) を削除
- Twitter adapter用のインターフェースに最適化

#### [MODIFY] [client.py](file:///c:/x-reach/agent_reach/client.py)
- `_Namespace` から未使用メソッド (`read()`, `crawl()`, `top()`, `new()`, `best()`) を削除
- `collect()` に `channel` のデフォルト値として `"twitter"` を設定
- X調査に特化したヘルパーメソッドの追加（`search()`, `user()`, `user_posts()`, `tweet()` の直接呼び出し）

---

### 1-C. CLI の最適化

#### [MODIFY] [cli.py](file:///c:/x-reach/agent_reach/cli.py)
- `--channel` のデフォルト値を `"twitter"` に変更（明示指定も引き続き可能）
- 未使用オプション群を削除:
  - `--body-mode` (web channel用)
  - `--query` / crawl_query (crawl operation用)
  - `--page-size`, `--max-pages`, `--cursor`, `--page` (Twitter未使用)
- doctor の `--require-channel` / `--require-channels` / `--require-all` を簡素化（1チャネルなので `--probe` のみで十分）
- ショートカットサブコマンド追加:
  - `x-reach search "query"` → `x-reach collect --channel twitter --operation search --input "query"` 相当
  - `x-reach user "username"` → user操作のショートカット
  - `x-reach posts "username"` → user_posts のショートカット
  - `x-reach tweet "url"` → tweet操作のショートカット
- コマンド出力のヘッダを "Agent Reach" → "X Reach" に統一（一部残っている箇所）

---

### 1-D. 設定のクリーンアップ

#### [MODIFY] [config.py](file:///c:/x-reach/agent_reach/config.py)
- `FEATURE_REQUIREMENTS` のマルチチャネル設計を削除、X専用に
- コメントと変数名の "Agent Reach" → "X Reach" 統一

#### [MODIFY] [.env](file:///c:/x-reach/.env) / [.env.example](file:///c:/x-reach/.env.example)
- コメントの "Agent Reach" → "X Reach" 統一

---

### 1-E. scout.py のX特化

#### [MODIFY] [scout.py](file:///c:/x-reach/agent_reach/scout.py)
- マルチチャネルcapabilityスキャン → X単一チャネルの状態確認に簡素化
- 不要な `PRESETS`, `BUDGETS` の整理
- `build_scout_plan` をX調査に特化した形に

---

### 1-F. candidates.py からの他チャネル残骸除去

#### [MODIFY] [candidates.py](file:///c:/x-reach/agent_reach/candidates.py)
- dedupe モード `domain`, `repo` を削除（X専用では不要）
- X投稿に最適化したdedupeロジック（ツイートID基準を主軸に）

---

### 1-G. チャネル/アダプタレジストリの簡素化

#### [MODIFY] [channels/__init__.py](file:///c:/x-reach/agent_reach/channels/__init__.py)
- 動的チャネルレジストリのオーバーヘッドを削減
- 直接 `TwitterChannel` を返す最適化

#### [MODIFY] [adapters/__init__.py](file:///c:/x-reach/agent_reach/adapters/__init__.py)
- 動的アダプタ解決のオーバーヘッドを削減

---

### Phase 2: X調査機能拡充とパッケージ名統一（Next Phase）

#### 2-A. X/Twitter 特化機能の実装
- `channels/twitter.py` および `adapters/twitter.py` に `hashtag` オペレーションを追加。
- `cli.py` に `--min-likes`, `--min-retweets`, `--min-views` などのフィルタリングオプションを追加。
- フィルターオプションを `adapters/twitter.py` 内で実装し、条件を満たさないアイテムをドロップまたはAPI側でフィルタ処理する。

#### 2-B. パッケージ名の完全移行
- `agent_reach/` ディレクトリ内の全ファイルを `x_reach/` に移動または統合。
- インポートパス (`from agent_reach...`) をすべて `from x_reach...` に置換。
- `pyproject.toml` やテスト内の参照を一括更新。

---

## Open Questions

特にありません。Phase 2の実行に進むため、承認をお願いします。

---

## Verification Plan

### Automated Tests
```powershell
# 既存テスト全通過確認
uv run pytest tests/ -x -q --tb=short

# ライブ動作確認
uv run x-reach channels --json
uv run x-reach doctor --json --probe
uv run x-reach collect --channel twitter --operation search --input "OpenAI" --limit 3 --json
uv run x-reach collect --operation search --input "OpenAI" --limit 3 --json  # channel省略テスト
uv run x-reach search "OpenAI" --limit 3 --json  # ショートカットテスト

# 既存互換性確認
uv run x-reach collect --channel twitter --operation user --input "openai" --json
uv run x-reach collect --channel twitter --operation user_posts --input "openai" --limit 5 --json
```

### Manual Verification
- 各CLIコマンドのヘルプ出力確認
- JSON出力スキーマの整合性確認
- 既存スクリプト/ワークフローとの後方互換性確認
