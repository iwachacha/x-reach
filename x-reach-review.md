前回の方針文書との一致度は高く、x_reach はもう単なる「X を叩ける CLI」ではなく、**mission spec・raw/canonical/ranked・candidate planning・quality profile・coverage/judge 契約**まで持つ、かなり明確な **X 調査ランタイム寄り** の形になっています。README でも x_reach は Agent-Reach の X/Twitter 専用 split とされ、`x-reach collect --spec`、`plan candidates`、ledger、`x_reach` SDK を安定面として前に出しています。リポジトリ構成も `mission.py`、`high_signal.py`、`candidates.py`、`ledger.py`、`operation_contracts.py`、`scout.py` など、方針で重視した責務に対応した形です。 ([GitHub][1])

まず、**特に良いところ**です。
一番大きいのは、方針文書にある「Mission Spec First」「Raw / Canonical / Curated」「Deterministic First, LLM Second」「3 つの quality profile」が、文書だけでなく README と実装の両方に反映されていることです。`collect --spec` は raw/canonical/ranked と resumable handoff を前提にしており、`docs/project-principles.md` でも同じ思想が明文化されています。 ([GitHub][1])

次に、**caller-control の思想がかなり良い**です。
README では、x_reach は最終 scope・final selection・synthesis・publishing を勝手に決めず、topic-agnostic を維持しつつ、`collect --json` を薄い既定インターフェースにし、`batch` と `scout` は opt-in に留めています。さらに broad discovery で `quality_profile=balanced`、`raw_mode=none`、`item_text_mode=snippet` を既定にして artifacts を無駄に重くしない設計も、かなり実務的です。これは「広く使えるが薄すぎない」という方針にかなり合っています。 ([GitHub][1])

また、**ノイズ処理の初期基盤はすでにある**のも良いです。
`high_signal.py` には `precision / balanced / recall` の quality profile、engagement gate、retweet/reply 除外、構造ノイズ、promo phrase、low-content 判定があり、`candidates.py` 側でも `max_per_author`、`prefer_originals`、`drop_noise`、`drop_title_duplicates`、`require_query_match`、`min_seen_in` といった後段フィルタが入っています。README でも large-scale research では compact discovery の後に `plan candidates --max-per-author 2 --prefer-originals --drop-noise` を挟む二段構えを推しています。 ([GitHub][2])

さらに、**安定面への意識も強い**です。
`operation_contracts.py` は channel/operation ごとの contract を読み、unsupported option や invalid input を明示的に弾く実装になっていて、`TwitterChannel` でも operations と options がかなり明文化されています。テスト群も `test_candidates.py`、`test_channel_contracts.py`、`test_mission.py`、`test_results.py`、`test_twitter_channel.py` などが揃っていて、薄い CLI ツールではなく「壊れにくい基盤」にしようとしているのが見えます。 ([GitHub][3])

そのうえで、**まだ方針と少しズレている部分 / もっと強化したい部分**もかなりあります。

いちばん大きいのは、**リネームと境界整理がまだ中途半端**な点です。
README では `x_reach` を primary Python SDK surface としていますが、実際の wheel は `agent_reach` と `x_reach` を両方含み、リポジトリ直下にも両パッケージが残っています。しかも `tests/test_mission.py` では `agent_reach.mission` と `agent_reach.results` から import しつつ `x_reach.cli` を使っています。互換性維持としては理解できますが、今のままだと「どちらが本体か」がやや曖昧です。 ([GitHub][1])

次に、**quality / ranking はまだ v1 感が強い**です。
今ある quality 判定は、retweet/reply、query match、structural noise、promo phrase、low-content、engagement gate といった前処理としては十分有用です。ですが、`docs/project-principles.md` が目標にしている「テーマ関連性・情報量・具体性・一次体験性・新規性・多様性への寄与」まで見るにはまだ浅いです。現状の公開コードから強く見えるのは、まず候補化して、ノイズを落として、diversity 制約を当てる流れであり、**“調査目的に照らした証拠価値” を評価する層**はまだ薄いです。 ([GitHub][4])

**ノイズ除去も、まだ伸びしろが大きい**です。
promo phrase は現状かなり小さめの固定語群で、low-content も「明らかに薄い quote を落とす」には効きますが、多言語・多テーマ・長期運用のスパム対策としてはまだ軽めです。`docs/project-principles.md` が想定する「明らかな宣伝」「同一アカウントの偏り」「同一スレッド内の過剰冗長」まで本気で抑えるなら、author 単位のスパム傾向、近似重複、同一テンプレ連投、quote-shell 的な薄い投稿、thread collapse をもう一段強くしたいです。 ([GitHub][2])

**多様性も “入口はあるが完成していない” 印象**です。
`plan candidates` には `max_per_author` や `min_seen_in` があり、mission spec の diversity にも `max_posts_per_author`、`max_posts_per_url`、`min_seen_in`、`require_topic_spread` があります。ですが、公開されている curated path では `build_candidates_payload` → `_rank_candidates` → `_apply_diversity_constraints` → coverage annotation という流れが見え、`require_topic_spread` は正規化されている一方で、その名前に対応する別の明示的ステージは少なくとも私が確認した範囲では見当たりませんでした。つまり、多様性は「author/url 方向」は進んでいるが、「topic spread」まではまだ本実装が薄そうです。 ([GitHub][5])

**coverage は良いが、まだ保守的です。**
これは思想としてはかなり良いです。README でも coverage は opt-in で、explicit topic gap だけ埋め、ranked-count gap では自動 query expansion しないと明記されています。実装でも `coverage.max_rounds` は現状 1 のみ、`min_posts_per_topic` や `max_queries` を持ちつつ、topic gap を分析して follow-up query を組む設計です。つまり「暴走しない gap fill」はできていますが、逆に言うと **大規模調査で recall を自動補強する層はまだかなり抑制的**です。 ([GitHub][1])

**judge はまだ“契約先行”です。**
README がはっきり書いている通り、judge は opt-in の forward-compatible contract で、judge runner 未設定時は fallback record を書き、`ranked.jsonl` は deterministic に維持します。実装も `judge_runner_not_configured` を理由に `not_run` / `unjudged` の fallback を返す形です。これは設計としては非常に誠実ですが、実運用としては「最終曖昧判定を外部 judge に渡す本体」がまだない、ということでもあります。 ([GitHub][1])

さらに、**mission 実行の探索面はまだ search 中心**です。
mission の batch plan 生成では query ごとに `channel: twitter`、`operation: search` を組み立てています。一方で公開 channel contract の operations は `search`、`hashtag`、`user`、`user_posts`、`tweet` の 5 つです。つまり今は broad recall を `search` 主体で回す設計で、**有望投稿を起点に thread / quote / replies / author history を二段目で掘る X 調査専用オーケストレーション**は、まだ本格実装の余地があります。 ([GitHub][6])

優先度順に言うと、次に効くのはこの順です。

**P0**

1. **境界整理**
   `x_reach` を本体、`agent_reach` を明示的 compatibility shim にするか、段階的 deprecation に寄せる。README・tests・wheel package の三者を揃える。 ([GitHub][1])

2. **調査品質 scoring v2**
   今のノイズ判定は活かしつつ、その上に「テーマ関連性」「具体性」「一次体験性」「証拠密度」「新規性」を短い deterministic reasons 付きで載せる。`docs/project-principles.md` の目標に一番近づく改善です。 ([GitHub][4])

3. **二段目の証拠拡張**
   broad search で拾った seed から、`tweet`・thread・quote・reply・author 近傍を掘る X 専用 research flow を mission に入れる。これは「X 一本化した価値」が最も出る部分です。 ([GitHub][6])

4. **`require_topic_spread` を本当に効かせる**
   今のままなら名前だけ先行しやすいので、topic bucket を作って最終選抜に diversity quota を入れるか、まだなら一度消す。 ([GitHub][6])

**P1**
5. **coverage を “暴走しない範囲で” もう一段だけ強くする**
今の explicit topic gap fill は良いので維持しつつ、query expansion は完全自動ではなく、bounded opt-in で追加する。 ([GitHub][1])

6. **judge runner の最小実装**
   最初は external command / JSONL in-out でも十分です。今の fallback は残しつつ、「外部 LLM/VLM 判定を接続できる」状態にすると mission の完成度が一気に上がります。 ([GitHub][1])

7. **observability 強化**
   今も dropped diagnostics はありますが、query ごとの yield、author/thread 偏り、topic coverage、time spread を summary に足すと改善ループが速くなります。README の caller-control と相性も良いです。 ([GitHub][1])

総評すると、
**x_reach はすでに方針から大きく外れていません。むしろかなり沿っています。**
いまの課題は「思想が弱い」ことではなく、**思想に対して実装がまだ 1 段浅い箇所がある**ことです。特に次の飛躍点は、`境界整理`、`quality scoring v2`、`X 専用の二段目証拠拡張` の 3 つです。そこまで入ると、かなり本格的な **AI エージェント向け X 調査実行基盤** になります。 ([GitHub][1])

[1]: https://github.com/iwachacha/x-reach "https://github.com/iwachacha/x-reach"
[2]: https://github.com/iwachacha/x-reach/blob/main/x_reach/high_signal.py "https://github.com/iwachacha/x-reach/blob/main/x_reach/high_signal.py"
[3]: https://github.com/iwachacha/x-reach/blob/main/x_reach/operation_contracts.py "x-reach/x_reach/operation_contracts.py at main · iwachacha/x-reach · GitHub"
[4]: https://github.com/iwachacha/x-reach/blob/main/docs/project-principles.md "https://github.com/iwachacha/x-reach/blob/main/docs/project-principles.md"
[5]: https://github.com/iwachacha/x-reach/blob/main/x_reach/candidates.py "https://github.com/iwachacha/x-reach/blob/main/x_reach/candidates.py"
[6]: https://github.com/iwachacha/x-reach/blob/main/x_reach/mission.py "x-reach/x_reach/mission.py at main · iwachacha/x-reach · GitHub"
