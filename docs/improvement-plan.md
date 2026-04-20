## 1. 改善計画書

### 目的

`x-reach` を、今の設計思想を崩さずに、
**「壊しにくい・レビューしやすい・CI で信頼できる・運用しやすい」状態へ引き上げる**。

### 守るべき原則

1. `x_reach` を主系として扱う。
2. `agent_reach` はこの改善パスでは削除しない。薄い互換 shim として維持する。
3. 既存公開 CLI / SDK / schema は壊さない。
4. 変更は additive を優先し、診断・観測・テストを先に強くする。
5. hidden model judgment や open-ended expansion は入れない。
6. 1 回の変更量は小さくし、PR 単位で安全に前進する。 ([GitHub][3])

### 非目標

* `agent_reach` の削除
* LLM/VLM judge の先行導入
* hidden な query expansion
* `summary.md` の最終研究レポート化
* 大規模な機能追加を一気にやること ([GitHub][3])

---

### フェーズ1: 境界整理と契約保全

**狙い**
`x_reach` 主系化を実態としても固める。互換層は残すが、本体実装・テスト・ドキュメントの主語を `x_reach` に寄せる。

**やること**

* `tests/` で `agent_reach` 直参照している箇所を棚卸しし、主系テストを `x_reach` ベースへ移す。
* `agent_reach` 側は「wrapper-only / alias-only」であることを確認するテストに縮小する。
* README / examples / skills / docs で `x_reach` が第一面であることを再点検する。
* schema mirror / compatibility shim の役割を `docs/compatibility-policy.md` か同等文書に明文化する。

**完了条件**

* 新規テスト追加時、主系 import は `x_reach` が原則になる。
* `agent_reach` は機能実装の置き場ではなく、互換境界としてのみ残る。
* 公開 docs のサンプルが `x_reach` に統一される。

**優先度**
最優先。ここを曖昧にしたままリファクタリングを進めると、以後の変更コストが上がる。 ([GitHub][3])

---

### フェーズ2: 巨大モジュールの分割

**狙い**
`cli.py` と `mission.py` の変更容易性とレビュー性を上げる。

**やること**

* `x_reach/cli.py` を少なくとも以下に分割する。
  `cli/main.py`, `cli/parser.py`, `cli/commands/*.py`, `cli/renderers/*.py`
* `_build_parser()` の単一巨大関数を、コマンドごとの parser registration に分離する。
* `mission.py` 相当の責務を、spec 解釈、実行 orchestration、ranking、summary rendering に分ける。
* 共通 dataclass / typed dict / helper を専用モジュールへ抽出する。

**完了条件**

* 1 ファイル 500〜800 行超の集中を緩和する。
* parser 定義変更が 1 コマンド 1 ファイル内で完結しやすくなる。
* 既存 CLI 出力と schema が変わらないことを回帰テストで確認する。

**優先度**
高。構造改善の核。 ([GitHub][4])

---

### フェーズ3: CI を「回る」から「守る」へ強化

**狙い**
今ある静的解析設定を CI に接続し、壊れ方を早期検出する。

**やること**

* `pytest.yml` に `ruff check` を追加する。
* `mypy` を少なくとも `x_reach/` の主要モジュールに対して走らせる。
* 契約テストを追加する。
  例: `x-reach --help`, `schema` 出力, `channels --json`, `doctor --json`, `plan candidates` の snapshot / golden test
* smoke workflow を「観測用」に位置づけ直す。
  `collect` 失敗許容は残すとしても、何が optional 失敗で何が hard failure かを明確化する。
* 任意で nightly / manual / required を分離する。

**完了条件**

* PR 時に lint / type / test の最低 3 本柱が回る。
* CLI 契約破壊が CI で検出できる。
* smoke artifact の意味が文書化される。

**優先度**
高。構造分割と並走可能。 ([GitHub][2])

---

### フェーズ4: 認証・設定の堅牢化

**狙い**
cookie / token を扱うツールとして、ローカル保存の安全性と診断性を上げる。

**やること**

* config backend を `file | env | keyring` のように抽象化する設計案を作る。
* まずは file backend を維持しつつ、doctor に
  `config file exists`, `owner-only perms attempted`, `fallback write path used`, `env override active`
  などの診断を足す。
* 機密値の masking ルールを整理する。
* 将来的な keyring 対応を見据えて config interface を分離する。

**完了条件**

* 現状の平文 YAML 保存と env fallback の挙動が docs に明記される。
* doctor が「動く」だけでなく「安全状態に近いか」を返せる。
* 既存ユーザーの設定ファイル互換は壊さない。

**優先度**
中高。実運用信頼性に直結。 ([GitHub][5])

---

### フェーズ5: スコア調整・診断の監査しやすさ向上

**狙い**
すでに入っている deterministic scoring / topic-fit / topic spread を、より説明可能・検証可能にする。

**やること**

* thin / promo / quote-shell / non-English の代表ケースを fixture 化する。
* `quality_score` と `quality_reasons` の重み調整テストを増やす。
* representative artifact に対する calibration 用の fixture を整備する。
* `summary.md` は synthesis ではなく diagnostic として維持する。

**完了条件**

* 高エンゲージだが薄い投稿より、低エンゲージでも情報量が高い投稿が上位になるケースをテストで保証する。
* スコア変化の理由が機械可読と人間可読の両方で追える。
* non-English / promo / quote-shell の退行が検出できる。

**優先度**
中。機能追加ではなく品質安定化の仕上げ。 ([GitHub][3])

---

### フェーズ6: OSS と配布の外装整備

**狙い**
中身に見合う公開信頼性を作る。

**やること**

* GitHub Releases を開始する。
* repository description / topics / homepage を設定する。
* CHANGELOG 運用を release と連動させる。
* issue template / bug report / feature request / security policy を整備する。
* README に「典型ワークフロー」「mission spec gallery」「CI 状態」の導線を追加する。

**完了条件**

* 新規利用者が README と Releases だけで導入・変更点把握・不具合報告に進める。
* リポジトリの成熟度シグナルが改善する。

**優先度**
中。コード改善と並行で進められる。 ([GitHub][1])

---

[1]: https://github.com/iwachacha/x-reach "GitHub - iwachacha/x-reach · GitHub"
[2]: https://github.com/iwachacha/x-reach/blob/main/pyproject.toml "x-reach/pyproject.toml at main · iwachacha/x-reach · GitHub"
[3]: https://github.com/iwachacha/x-reach/blob/main/docs/improvement-plan.md "x-reach/docs/improvement-plan.md at main · iwachacha/x-reach · GitHub"
[4]: https://github.com/iwachacha/x-reach/blob/main/x_reach/cli.py "x-reach/x_reach/cli.py at main · iwachacha/x-reach · GitHub"
[5]: https://github.com/iwachacha/x-reach/blob/main/x_reach/config.py "x-reach/x_reach/config.py at main · iwachacha/x-reach · GitHub"
