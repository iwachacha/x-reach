## 1. いちばん大きい課題は「ツール呼び出し」中心で、「調査ミッション」中心になっていないこと

Codex 系エージェントに大規模調査を任せるなら、
`twitter search を何回か叩く` では足りません。

必要なのは、エージェントがこういう単位で仕事できることです。

* 調査目的
* 対象テーマ
* 期間
* 言語
* 除外ノイズ
* 欲しい証拠の種類
* 収集件数の目安
* 品質優先か網羅優先か
* 途中停止 / 再開
* 最終出力形式

つまり **コマンド実行基盤** ではなく **mission-driven research runtime** が必要です。

### 強く推したい改善

`xreach collect --spec mission.json` を最上位 API にしてください。
Agent には細かい shell orchestration をさせず、**1つの宣言的 spec を渡す** 形に寄せたほうが圧倒的に安定します。

たとえば最低でもこんな spec を持たせるべきです。

```json
{
  "objective": "新機能Xに対する実利用者の不満と要望を把握する",
  "queries": ["機能X 不便", "機能X バグ", "\"機能X\" lang:ja"],
  "time_range": {"since": "2026-03-01", "until": "2026-04-15"},
  "languages": ["ja"],
  "target_posts": 500,
  "quality_profile": "research_high_precision",
  "exclude": {
    "keywords": ["宣伝", "抽選", "フォロー&RT"],
    "min_account_age_days": 30,
    "max_same_author_posts": 3,
    "drop_retweets": true,
    "drop_low_content_posts": true
  },
  "diversity": {
    "max_posts_per_thread": 4,
    "max_posts_per_author": 3,
    "require_topic_spread": true
  },
  "outputs": ["raw.jsonl", "ranked.jsonl", "summary.md"]
}
```

この形にすると、プロジェクトごとの柔軟性を保ちながら、共通基盤を強化できます。

---

## 2. x-reach は「収集器」だけでなく「評価器」を持つべきです

あなたの要件で重要なのは、**小規模〜大規模調査まで対応しつつ、明らかなノイズを落として質を上げる**ことです。
そのためには取得と評価を分ける必要があります。

### 推奨する 5 段階パイプライン

1. **Broad Recall**

   * 広めに収集
   * クエリ展開
   * 類義語 / 表記ゆれ / ハッシュタグ / 引用語を増やす

2. **Normalization**

   * 投稿、スレッド、ユーザー、URL、メディアを正規化
   * RT / quote / reply / thread root を関係づける

3. **Dedup / Collapse**

   * 同文、近似文、同じ thread 内の冗長投稿を束ねる
   * URL 共有だけの焼き直しも統合

4. **Quality Ranking**

   * 情報量
   * 具体性
   * 一次体験性
   * ノイズ度
   * アカウント信頼性
   * 多様性
     でスコアリング

5. **Coverage Gap Fill**

   * 足りない観点だけ再探索
   * すでに十分な観点は深掘り停止

この 5 段階を分けないと、
「たくさん集めたけど広告・bot・RT・薄い感想ばかり」という状態になります。

---

## 3. ノイズ削減は「ルール + 軽量モデル + LLM最終判定」の三層がよいです

ここは非常に重要です。
全部 LLM に投げるとコストもブレも大きいので、まずは前段を強くしてください。

### 第1層: ハードフィルタ

ここは deterministic に切るべきです。

* RT / repost 除外
* 極端に短い投稿除外
* URL だらけ・ハッシュタグだらけ除外
* 同一 author の連投制限
* 同一文面の重複除外
* フォロワー稼ぎ文言、懸賞文言、定型宣伝文言除外
* 投稿本文に実質的内容がないものを除外

### 第2層: heuristic scoring

ここで「質の高そうなもの」を上に持っていきます。

* 一次体験を示す語彙
  例: 「使ってみた」「導入した」「検証した」「障害出た」
* 具体性
  数値、手順、再現条件、スクショ参照、URL、固有名詞
* 投稿者属性
  新規捨て垢っぽさ、過剰宣伝比率、投稿履歴の偏り
* エンゲージメントは補助指標としてのみ使う
  伸びていても中身が薄い投稿は多い

### 第3層: LLM judging

上位候補だけ LLM に回す。

判定軸は固定してください。

* この投稿は調査目的に関連するか
* 一次情報 / 二次情報 / 雑談 / 宣伝 のどれか
* 具体的な主張や証拠があるか
* 既存収集群に対して新規性があるか
* 重要度は高いか

ここで大事なのは、**LLM に yes/no だけでなく理由も短く返させる**ことです。
後でデバッグできます。

---

## 4. 大規模調査に必要なのは「検索」より「ジョブ管理」です

上流は installer / doctor に強いですが、大規模収集ではそこが主戦場ではありません。
必要なのは次です。

### 必須機能

* job 単位の実行
* checkpoint / resume
* query shard 分割
* 進捗管理
* retry/backoff
* 失敗タスクの再投入
* 途中結果の保存
* 収集 budget 管理
* 終了条件管理

### 推奨する保存レイヤ

3層に分けると運用が安定します。

* **raw**

  * API / CLI から得た生データ
  * 後から再解釈できる

* **canonical**

  * 正規化済み投稿
  * thread / author / url 関係を整理

* **curated**

  * dedup 済み
  * スコア付き
  * 最終分析用

これをやらないと、あとでルールや評価基準を変えた時に全取り直しになります。

---

## 5. X 専用最適化はしてよいが、抽象境界は汎用に保つべきです

あなたの方針は正しいです。
X 一本化で最適化しつつ、共通部分は強くするべきです。

そのためには、**X-specific と research-common を分離**してください。

### X-specific に置くもの

* 認証
* 検索クエリ表現
* 投稿 / thread / reply / quote の取得方法
* X 固有メタデータ
* rate / failure パターンへの対処
* URL / handle / post ID 解決

### common core に置くもの

* mission spec
* job runner
* result schema
* dedup
* scoring
* ranking
* export
* sample inspection
* observability
* resume / retry

この分離ができていれば、将来 Reddit 版や forum 版を作っても再利用できます。

---

## 6. 今の channel 設計は軽すぎるので、Capability ベースに拡張したほうがいいです

上流の `Channel` は `can_handle()` と `check()` が中心で、かなり薄いです。これは installer と doctor には合っていますが、調査基盤には足りません。 ([GitHub][3])

x-reach では、少なくとも X adapter に以下の capability を持たせるとよいです。

* `search_posts(query, options)`
* `read_post(url_or_id)`
* `read_thread(post_id)`
* `get_author(author_id)`
* `search_author_posts(author, options)`
* `search_replies(post_id, options)`
* `search_quotes(post_id, options)`
* `hydrate(posts)`
* `healthcheck()`

さらに返り値は必ず JSON schema 固定にしてください。
Agent に自然言語テキストを返すより、**構造化データ + 人間向け要約** の二系統が安定します。

---

## 7. Codex 前提なら、Agent に「自由に考えさせすぎない」ほうが強いです

上流は Claude Code / Cursor / OpenClaw / Codex など、shell 実行できる agent で使う想定です。 ([GitHub][4])

ただ、調査タスクでは agent の自由度が高すぎると、

* 無駄に検索を増やす
* 同じ観点を何度も回る
* ノイズ判定がぶれる
* 途中状態が壊れる
* 出力再現性がなくなる

という問題が出ます。

なので、Codex に対しては

* まず plan を作る
* 次に spec を固定する
* その spec を x-reach が実行する
* Agent は sample inspection と refinement だけやる

という分担が最適です。

要は
**Agent = strategist / reviewer**
**x-reach = deterministic executor**
に寄せるべきです。

---

## 8. 品質を上げるなら「多様性制約」が必須です

良い調査結果は「上位スコア順」だけでは出ません。
同じクラスタの似た投稿が上位を占めます。

そこで ranking の後に diversity constraint を入れてください。

### 入れるべき制約

* 同一 author 上限
* 同一 thread 上限
* 同一 URL 上限
* 同一 stance 上限
* 同一 subtopic 上限
* 同一時間帯上限

これにより、
「有名投稿の周辺ノイズだけ大量に取れる」問題をかなり抑えられます。

---

## 9. 観測性を入れないと改善が回りません

本気で強くするなら、最低限これを毎 job で残してください。

* 何 query 打ったか
* query ごとの hit 数
* dedup で何件落ちたか
* hard filter で何件落ちたか
* heuristic / LLM で何件採用されたか
* 最終件数
* author/thread の偏り
* サブトピックの偏り
* 代表サンプル
* 失敗理由内訳

これがないと、
「なぜ質が悪かったのか」が分からず、改善が勘になります。

---

## 10. 優先順位付きで言うと、先にやるべきはこの順番です

### 最優先

1. **Mission spec の導入**
2. **Canonical result schema の固定**
3. **Dedup / noise filter / ranking の三段構え**
4. **Job checkpoint / resume**
5. **JSON-first の stable API**

### 次点

6. Thread / quote / reply を束ねた evidence graph
7. Coverage gap fill
8. 調査プロファイル

   * high precision
   * balanced
   * broad recall
     の切り替え

### その後

9. LLM judge の自己改善
10. sample-based active refinement
11. analyst 向け export
12. cross-project preset library

---

## 11. いまの方針に対する私の最終評価

方向性はかなり良いです。
**「Agent-Reach の X 部分だけを切り出して、X 専用に最適化する」**のは正しいです。

ただし、真に価値が出るのは X 専用化そのものではなく、

* 調査ミッションを宣言的に記述できること
* ノイズを系統的に落とせること
* 大規模でも途中再開できること
* Agent が迷わず使えること
* 出力の再現性があること

この5点を揃えた時です。

逆に言うと、
**x-reach を「twitter-cli を便利に使う道具」で止めると限界が早い**です。
**「X 調査 OS」まで引き上げると、かなり強い基盤になります。**

[1]: https://github.com/Panniantong/Agent-Reach/tree/main/agent_reach "Agent-Reach/agent_reach at main · Panniantong/Agent-Reach · GitHub"
[2]: https://github.com/Panniantong/Agent-Reach/blob/main/agent_reach/channels/twitter.py "Agent-Reach/agent_reach/channels/twitter.py at main · Panniantong/Agent-Reach · GitHub"
[3]: https://github.com/Panniantong/Agent-Reach/blob/main/agent_reach/channels/base.py "Agent-Reach/agent_reach/channels/base.py at main · Panniantong/Agent-Reach · GitHub"