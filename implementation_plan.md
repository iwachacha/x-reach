# X-Reach X調査特化最適化計画

Agent-Reach由来の汎用的な「マルチチャネル調査フレームワーク」構造を、X/Twitter単一チャネルに最適化したシャープなツールへ変革する。

## 現状の分析結果

2026-04-15 時点で、runtime 本体は `x_reach/` へ移行済みです。`agent_reach/` は後方互換のための shim レイヤーとして維持しています。

### 定量データ
| 項目 | 値 |
|---|---|
| 総Pythonコード行数 | ~6,500行 (runtime本体は `x_reach/` に移行済み) |
| CLI (cli.py) | 1,622行 |
| 結果スキーマ (results.py) | 529行 |
| チャネル/アダプタ基底クラス | 207行 (使われ方は1つだけ) |
| テスト | 149件 全パス |
| 登録チャネル | **1つ** (twitter) |

### 特定した冗長・ノイズ箇所

#### 1. パッケージ名の混乱 (影響: 大)
- 対応済み: コアロジックは `x_reach/` に移行し、`agent_reach/` は互換 shim 化
- `XReachClient` を主クラスとして扱い、`AgentReachClient` は legacy alias として維持
- Legacy スキル名 `agent-reach-*` は cleanup / uninstall 互換のために残存

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

## Progress Update

> [!NOTE]
> **Phase 1 完了**: 汎用構造のX特化クリーンアップは完了済みです。

> [!NOTE]
> **Phase 2-A 完了**:
> `hashtag` オペレーション、`--min-likes` / `--min-retweets` / `--min-views`、`search|hashtag|user|posts|tweet` ショートカット、`user_posts --originals-only` を実装済みです。

> [!IMPORTANT]
> **Phase 2-B 進行中**:
> runtime 実装を `x_reach/` へ移し、`agent_reach/` は compatibility shim に切り替えました。
> この段階で `pytest` 141 件と live 収集テストはすべて成功しています。

> [!IMPORTANT]
> **Phase 2-C 完了**:
> `quality_profile`、broad op の compact default shaping、deterministic noise filtering、ledger/candidates の large-scale 向け診断を実装しました。
> `pytest` 149 件と live の `doctor / search / posts / batch -> merge -> summarize -> plan candidates` まで成功しています。

> [!IMPORTANT]
> **Phase 2-D 完了**:
> `x-reach collect --spec mission.json` を mission-driven runtime として追加しました。
> spec から batch plan を固定し、`raw.jsonl` / `canonical.jsonl` / `ranked.jsonl` / `summary.md` / `mission-result.json` を出力します。
> Agent は戦略・レビューに寄せ、x-reach が deterministic executor になる方針を採用しました。

> [!IMPORTANT]
> **Phase 2-E 完了**:
> レビュー案を参考にしつつ live probe で不足を再確認し、LLM ではなく deterministic な候補品質改善を追加しました。
> `quality_profile` の drop 集計に dropped sample を持たせ、候補化では薄い引用投稿を `low_content` として落とせるようにしました。

> [!IMPORTANT]
> **Phase 2-F 完了**:
> mission runtime に opt-in の coverage gap fill を追加しました。
> `coverage.enabled=true` の場合、初回 ranked 候補を deterministic topic terms で検査し、不足 topic に対して明示クエリまたは `objective + label` の追加 search を1ラウンドだけ実行します。

---

## Proposed Changes

### Phase 1: 汎用構造のX特化クリーンアップ（完了 ✅）

---

### 1-A. results.py から他チャネル残骸を除去

#### [MODIFY] [results.py](file:///c:/x-reach/x_reach/results.py)
- `engagement` スキーマからGitHub固有 (`stars`, `forks`)、HN固有 (`points`, `descendants`) フィールドを削除
- X専用engagement: `likes`, `retweets`, `replies`, `quotes`, `views`, `bookmarks` のみ保持
- `_normalize_identifiers` からGitHub `repo_full_name` ロジックを削除
- `_HTML_ENTITY_RE` 等のweb scraping用テキスト正規化を削除
- エラーカテゴリからweb固有 (`paywall`, `robots_blocked`, `geo_blocked`) を削除
- X専用に最適化されたURL正規化 (`x.com`, `twitter.com`) の強化

---

### 1-B. 基底クラスのスリム化

#### [MODIFY] [base.py (channels)](file:///c:/x-reach/x_reach/channels/base.py)
- 汎用オペレーション (`read`, `crawl`, `top`, `new`, `best`) の定義を削除
- Twitter固有オペレーション (`search`, `user`, `user_posts`, `tweet`) のみ残す
- `KNOWN_OPERATIONS` をX専用セットに更新

#### [MODIFY] [base.py (adapters)](file:///c:/x-reach/x_reach/adapters/base.py)
- 汎用メソッド (`crawl`, `top`, `new`, `best`) を削除
- Twitter adapter用のインターフェースに最適化

#### [MODIFY] [client.py](file:///c:/x-reach/x_reach/client.py)
- `_Namespace` から未使用メソッド (`read()`, `crawl()`, `top()`, `new()`, `best()`) を削除
- `collect()` に `channel` のデフォルト値として `"twitter"` を設定
- X調査に特化したヘルパーメソッドの追加（`search()`, `user()`, `user_posts()`, `tweet()` の直接呼び出し）

---

### 1-C. CLI の最適化

#### [MODIFY] [cli.py](file:///c:/x-reach/x_reach/cli.py)
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

#### [MODIFY] [config.py](file:///c:/x-reach/x_reach/config.py)
- `FEATURE_REQUIREMENTS` のマルチチャネル設計を削除、X専用に
- コメントと変数名の "Agent Reach" → "X Reach" 統一

#### [MODIFY] [.env](file:///c:/x-reach/.env) / [.env.example](file:///c:/x-reach/.env.example)
- コメントの "Agent Reach" → "X Reach" 統一

---

### 1-E. scout.py のX特化

#### [MODIFY] [scout.py](file:///c:/x-reach/x_reach/scout.py)
- マルチチャネルcapabilityスキャン → X単一チャネルの状態確認に簡素化
- 不要な `PRESETS`, `BUDGETS` の整理
- `build_scout_plan` をX調査に特化した形に

---

### 1-F. candidates.py からの他チャネル残骸除去

#### [MODIFY] [candidates.py](file:///c:/x-reach/x_reach/candidates.py)
- dedupe モード `domain`, `repo` を削除（X専用では不要）
- X投稿に最適化したdedupeロジック（ツイートID基準を主軸に）

---

### 1-G. チャネル/アダプタレジストリの簡素化

#### [MODIFY] [channels/__init__.py](file:///c:/x-reach/x_reach/channels/__init__.py)
- 動的チャネルレジストリのオーバーヘッドを削減
- 直接 `TwitterChannel` を返す最適化

#### [MODIFY] [adapters/__init__.py](file:///c:/x-reach/x_reach/adapters/__init__.py)
- 動的アダプタ解決のオーバーヘッドを削減

---

### Phase 2: X調査機能拡充とパッケージ名統一

#### 2-A. X/Twitter 特化機能の実装（完了 ✅）
- `channels/twitter.py` および `adapters/twitter.py` に `hashtag` オペレーションを追加。
- `cli.py` に `--min-likes`, `--min-retweets`, `--min-views` などのフィルタリングオプションを追加。
- `posts --originals-only` と `client.twitter.user_posts(..., originals_only=True)` を追加し、retweet を除外したタイムライン調査を可能にした。
- フィルターオプションを `adapters/twitter.py` 内で実装し、条件を満たさないアイテムをドロップまたはAPI側でフィルタ処理する。

#### 2-B. パッケージ名の完全移行（進行中 🚧）
- 完了: runtime 実装 (`cli`, `config`, `doctor`, `results`, `ledger`, `adapters`, `channels`, `integrations` など) を `x_reach/` に配置。
- 完了: `x_reach/` 側の内部 import を `x_reach...` に反転。
- 完了: `agent_reach/` の Python モジュール群を `x_reach/` を参照する compatibility shim に変更。
- 完了: `x_reach.schema_files` を schema 読み込み元に切り替え、`X_REACH_RUN_ID` を優先しつつ `AGENT_REACH_RUN_ID` を後方互換で維持。
- 残作業: テスト・ドキュメント・skills 内の参照を段階的に `x_reach` 優先へ寄せ、どこまで legacy import を残すかを決める。

#### 2-C. 高信号・大規模調査最適化（完了 ✅）
- `search` / `hashtag` / `user_posts` に `quality_profile=precision|balanced|recall` を追加し、broad op の既定を `balanced` にした。
- broad op の既定出力を `raw_mode=none`、`item_text_mode=snippet`、`item_text_max_chars=280` に変更し、CLI と SDK の両方で同じ shape を返すようにした。
- `balanced` / `precision` で oversampling、query token hit、retweet/reply 除外、構造ノイズ除去、promo/scam phrase 除去、engagement gate、fallback backfill を実装した。
- `user_posts` では `originals_only` を balanced/precision の既定にし、timeline ノイズを減らした。
- `ledger summarize|validate` に `raw_mode_counts`、`item_text_mode_counts`、`raw_payload_bytes_total`、`item_text_chars_total`、`unbounded_time_window_records`、`filter_drop_reason_counts`、`timeline_item_kind_counts`、`search_type_counts` を追加した。
- `plan candidates` に `--max-per-author`、`--prefer-originals`、`--drop-noise`、`--require-query-match` を追加した。
- `scout` に discovery / deep-read 推奨設定を返す `recommended_collection_settings` を追加した。

#### 2-D. Mission Spec Runtime（完了 ✅）
- 採用案: レビューの最優先案である `x-reach collect --spec mission.json` を実装対象にした。既存の `batch` / `ledger` / `candidates` / `quality_profile` を再利用し、薄い CLI 呼び出しではなく宣言的 spec を deterministic に実行する。
- `x_reach/mission.py` を追加し、spec 正規化、language/time range 展開、batch plan 生成、checkpoint/resume 付き実行、raw/canonical/curated artifact 生成を担当させた。
- `collect --spec` は `--dry-run`、`--output-dir`、`--resume`、`--concurrency`、`--checkpoint-every` を持つ。`--operation/--input` とは排他にした。
- 出力は `raw/` shard、`raw.jsonl`、`canonical.jsonl`、`ranked.jsonl`、`summary.md`、`mission-result.json`、`mission-state.json`。handoff/debug 用に batch plan と normalized spec も保存する。
- ranking は deterministic heuristic として `seen_in_count`、original/quote/reply/retweet、engagement、本文量、URL/media 有無を使う。LLM judge はまだ入れていない。
- diversity は author/thread/url cap を mission 側で適用し、`plan candidates` 側の post dedupe / title duplicate / query match と併用する。
- `x-reach schema mission-spec --json` と SDK の `XReachClient.mission_plan()` / `XReachClient.collect_spec()` を追加した。
- 残課題: LLM/VLM judge、stance/subtopic classification は未実装。coverage gap fill は Phase 2-F で opt-in の deterministic 実装に昇格した。

#### 2-E. 実調査フィードバックによる品質改善（完了 ✅）
- 2026-04-16 の live probe で `doctor --probe` / `channels` は正常、`search "OpenAI" --limit 5 --quality-profile balanced` では `structural_noise` の drop 集計と、単体では根拠として薄い引用投稿が確認された。
- 採用案: LLM judge 追加より先に、決定的に解ける品質改善を優先した。`quality_filter.dropped_samples` に最大5件の `id` / `author` / `text_preview` / `reasons` を残し、運用時に drop 理由を検証できるようにした。
- 採用案: `plan candidates --drop-noise` と mission の `exclude.drop_low_content_posts` で、短すぎる本文や「短い quote + コロン終端」の引用投稿を `low_content` として落とす。X投稿収集では候補品質に直結し、汎用性の毀損は小さい。
- 非採用/保留: LLM はまだ入れない。投入する場合も `ranked.jsonl` の上位候補など deterministic に絞った後の最終判定に限定し、provider/model は実装時点の低コストなクラウドモデルを公式情報で確認して選ぶ。

#### 2-F. Coverage Gap Fill（完了 ✅）
- 採用案: レビューの `Coverage gap fill` は、LLM や自律探索ではなく、mission spec で明示された `coverage.topics` を deterministic に検査する形で採用した。
- `coverage.enabled=true` の時だけ有効化し、初回 `ranked_candidates` に topic terms が不足していて、かつ新しい follow-up query を生成できる場合のみ、最大 `coverage.max_queries` 件の追加 search を1ラウンド実行する。
- `min_ranked_posts` / `target_gap` は件数不足の診断として残すが、それ単体では追加 search を走らせない。自動拡張は明示 topic gap に限定する。
- topic ごとに `label` / `terms` / `queries` / `min_posts` / `probe_limit` を指定できる。`queries` がない場合は `objective + label` から控えめに生成する。
- 追加 batch は `source_role=coverage_gap_fill` として raw ledger に追記し、`raw.jsonl` / `canonical.jsonl` / `ranked.jsonl` / `summary.md` / `mission-result.json` を再生成する。
- coverage topic に一致した ranked 候補には `coverage_topics` を付与し、後続レビューでどの観点を満たしているか確認しやすくした。
- manifest には `coverage.initial` / `coverage.final` / `coverage.gap_queries` / `coverage.batch_summary` を残すため、どの不足がどこまで埋まったかを次作業者が確認できる。
- 非採用/保留: 複数ラウンドの active refinement、LLM による意味的 topic 判定、画像/VLM coverage はまだ入れない。現段階ではコストと挙動予測性を優先した。

---

## Open Questions

次の候補は以下です。

- coverage gap fill の次段として、topic terms だけでは拾えない意味的な不足を上位候補サンプルから検出するか。
- LLM judge / VLM judge を入れる場合、`ranked.jsonl` の上位候補だけに限定し、yes/no ではなく理由付き判定を残す方針がよい。モデル名は固定せず、作業時点で低コスト・十分なクラウドモデルを公式情報で確認して選ぶ。
- `agent_reach` 表記が残る docs / skills / tests の整理と、互換レイヤーの維持方針の明文化。

---

## Progress Log

| 日付 | 進捗 | 検証 |
|---|---|---|
| 2026-04-15 | `hashtag`、検索フィルタ、CLI ショートカット、`posts --originals-only` を追加 | `uv run pytest tests/ -q --tb=short`、`uv run x-reach doctor --json --probe`、`uv run x-reach hashtag "OpenAI" --limit 3 --json`、`uv run x-reach posts "openai" --limit 5 --originals-only --json` |
| 2026-04-15 | runtime 本体を `x_reach/` に移動し、`agent_reach/` を shim 化 | `uv run pytest tests/ -q --tb=short`、`uv run x-reach doctor --json --probe`、`uv run x-reach search "OpenAI" --limit 3 --json`、`uv run x-reach posts "openai" --limit 5 --originals-only --json` |
| 2026-04-15 | `quality_profile`、broad op の compact default、deterministic noise filtering、ledger/candidates の大規模調査向け診断を追加 | `uv run pytest tests/ -q --tb=short`、`uv run x-reach doctor --json --probe`、`uv run x-reach search "OpenAI" --limit 5 --json`、`uv run x-reach search "AI agent" --limit 5 --quality-profile precision --json`、`uv run x-reach posts "openai" --limit 5 --json`、`uv run x-reach batch --plan PLAN.json --save-dir SHARDS --json`、`uv run x-reach ledger merge --input SHARDS --output evidence.jsonl --json`、`uv run x-reach ledger summarize --input evidence.jsonl --json`、`uv run x-reach plan candidates --input evidence.jsonl --by post --max-per-author 2 --prefer-originals --drop-noise --json` |
| 2026-04-16 | `collect --spec` mission runtime、mission spec schema、raw/canonical/ranked artifact 出力、SDK helper を追加 | `uv run pytest tests/ -q --tb=short`、`uv run pytest tests/test_mission.py tests/test_cli.py tests/test_client.py -q --tb=short`、`uv run --extra dev ruff check x_reach\mission.py x_reach\batch.py x_reach\cli.py x_reach\client.py x_reach\schemas.py agent_reach\mission.py tests\test_mission.py`、`uv run x-reach schema mission-spec --json` |
| 2026-04-16 | live probe 結果から drop sample 診断と `low_content` 候補フィルタを追加 | `uv run x-reach doctor --json --probe`、`uv run x-reach channels --json`、`uv run x-reach search "OpenAI" --limit 5 --quality-profile balanced --json`、`uv run pytest tests/test_candidates.py tests/test_collect_adapters.py tests/test_mission.py -q --tb=short` |
| 2026-04-16 | mission runtime に opt-in coverage gap fill を追加し、target gap を report-only に固定 | `uv run pytest tests/test_mission.py -q --tb=short`、`uv run pytest tests/ -q --tb=short`、`uv run --extra dev ruff check x_reach\mission.py tests\test_mission.py`、`uv run x-reach schema mission-spec --json` |

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
uv run x-reach hashtag "OpenAI" --limit 3 --json
uv run x-reach posts "openai" --limit 5 --originals-only --json
uv run x-reach schema mission-spec --json
uv run x-reach collect --spec mission.json --output-dir .x-reach/missions/test --dry-run --json
uv run x-reach collect --spec mission.json --output-dir .x-reach/missions/test --json
uv run x-reach collect --spec mission.json --output-dir .x-reach/missions/test --resume --json

# 既存互換性確認
uv run x-reach collect --channel twitter --operation user --input "openai" --json
uv run x-reach collect --channel twitter --operation user_posts --input "openai" --limit 5 --json
```

### Manual Verification
- 各CLIコマンドのヘルプ出力確認
- JSON出力スキーマの整合性確認
- 既存スクリプト/ワークフローとの後方互換性確認

