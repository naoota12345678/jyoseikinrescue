# Claude開発メモ

## 重要な注意事項 ⚠️

### 絶対にやってはいけないこと
1. **勝手にファイルを全面的に書き換えない**
   - ユーザーが明確に依頼していない限り、既存のファイルの構造を大幅に変更しない
   - 特に動作している機能を「改善」しようとして壊さない

2. **要求されていない機能追加・変更をしない**
   - ユーザーの具体的な指示のみに従う
   - 「より良くしよう」という判断で勝手な変更をしない

3. **動作しているシステムを触らない**
   - 「問題ない部分」は絶対に変更しない
   - 小さな修正でも影響範囲を慎重に考える

### 正しいアプローチ
1. **最小限の変更のみ** - 要求された部分のみを正確に修正
2. **変更前に確認** - 既存のコードがなぜそうなっているかを理解してから修正
3. **段階的な修正** - 一度に多くを変更せず、一つずつ確認しながら進める

## システム概要 📋

### ⚠️ 重要: アプリケーション構成（絶対に忘れるな！）
**アプリ**: Python Flask (Cloud Runで動作)
**Cloud Run サービス名**: `jyoseikinrescue`
**Cloud Run URL**: `https://jyoseikinrescue-453016168690.asia-northeast1.run.app`
**Firebase Hosting**: `jyoseikinrescue.web.app` (Cloud Runにプロキシ)
**カスタムドメイン**: `shindan.jyoseikin.jp` → `jyoseikinrescue.web.app` → Cloud Run

### 🔑 重要：Googleワークスペース連携構成（2025-09-18追加）
**アカウント関係（必須暗記）**:
- **親アカウント**: hasebe.sr.office@gmail.com（Google Cloud権限あり）
- **ワークスペース**: info@hasebe-sr-office.com（カレンダー＋Meet管理）
- **デプロイ用**: naoota12345678@gmail.com（Cloud Run管理）

**Google Cloudプロジェクト**:
- **メインアプリ**: `jyoseikinrescue`（naoota12345678@gmail.com）
- **カレンダーAPI**: `jyoseikin-calender`（hasebe.sr.office@gmail.com）

**重要な連携情報**:
- **サービスアカウント**: `calendar-system@jyoseikin-calender.iam.gserviceaccount.com`
- **カレンダーID**: `info@hasebe-sr-office.com`
- **機能**: CalendlyからGoogle Meet直接連携に移行完了

### プロジェクト構成
- **メインデプロイ**: Google Cloud Run
- **アプリケーション**: Python Flask + HTML/CSS/JavaScript
- **バックエンド**: Python Flask + Firebase
- **AI**: Claude 3.5 Sonnet API
- **認証**: Firebase Auth
- **決済**: Stripe

### 主要機能
1. **無料診断システム**: 助成金の適用可能性を診断
2. **AI専門エージェント**: 9つの助成金専門エージェント
3. **メモ機能**: 相談内容の保存・管理
4. **申請書類リンク**: 厚労省公式書類への直接リンク
5. **料金プラン**: Light/Regular/Heavy（¥1,480～¥5,500）
6. **専門家相談システム**: Google Meet直接連携で30分¥14,300

## エージェントID管理 🏷️

### 現在のエージェント（9つ）
- `gyoumukaizen` - 業務改善助成金
- `career-up_seishain` - 正社員化コース
- `career-up_chingin` - 賃金規定等改定コース
- `career-up_shogaisha` - 障害者正社員化コース
- `career-up_kyotsu` - 賃金規定等共通化コース
- `career-up_shoyo` - 賞与・退職金制度導入コース
- `career-up_shahoken` - 社会保険適用時処遇改善コース
- `career-up_tanshuku` - 短時間労働者労働時間延長支援コース
- `jinzai-kaihatsu_teigaku` - 人材開発支援助成金

### エージェント追加時のチェックリスト
- [ ] dashboard.htmlのagentNamesマッピング更新
- [ ] app.pyのagent_info辞書更新
- [ ] claude_service.pyの対応確認
- [ ] fileフォルダにデータファイル配置

## 環境変数・デプロイ 🚀

### 重要な環境変数
- `CLAUDE_API_KEY` ← **これを使用（ANTHROPIC_API_KEYではない！）**
- Firebase認証設定（FIREBASE_*）
- Stripe決済設定（STRIPE_*）

### デプロイ手順（必須・厳守）
```bash
# 1. ビルド（IMAGE_NAMEは具体的な名前を指定）
gcloud builds submit --tag asia-northeast1-docker.pkg.dev/jyoseikinrescue/jyoseikinrescue/IMAGE_NAME .

# 2. ビルド結果確認
gcloud builds list --limit=1 --format="value(images)"

# 3. デプロイ（必ずサービス名jyoseikinrescue指定）
gcloud run services update jyoseikinrescue --region=asia-northeast1 --image=EXACT_IMAGE_FROM_STEP2

# 4. 🚨 重要：トラフィックを最新リビジョンに向ける（忘れると変更が反映されない）
gcloud run services update-traffic jyoseikinrescue --region=asia-northeast1 --to-latest
```

**🚨 絶対に守ること**:
- **IMAGE_NAMEには具体的な名前を使用**（例：gyomukaizen-fix-20250917）
- **`jyoseikinrescue`固定は絶対禁止**
- **サービス名は必ず`jyoseikinrescue`を指定**
- **`--source`オプションは使用禁止**
- **この手順以外のデプロイ方法は禁止**

**🔥 重大問題事例（2025-09-17）**:
Claude自身がルールを破り、`jyoseikinrescue`でビルド実行。
バックグラウンドプロセスが修正版を上書きし、大問題発生。

**💀 絶対禁止コマンド**:
```bash
# これは絶対に実行禁止
gcloud builds submit --tag asia-northeast1-docker.pkg.dev/jyoseikinrescue/jyoseikinrescue/jyoseikinrescue .
```

**✅ 正しい手順**:
```bash
# 1. バックグラウンドプロセス確認（必須）
ps aux | grep "gcloud builds" || echo "No background builds"

# 2. 具体的な名前でビルド（YYYY-MM-DD-HHMM形式推奨）
gcloud builds submit --tag asia-northeast1-docker.pkg.dev/jyoseikinrescue/jyoseikinrescue/fix-YYYYMMDD-HHMM .

# 3. 完了確認後デプロイ
gcloud run services update jyoseikinrescue --region=asia-northeast1 --image=EXACT_IMAGE_FROM_STEP2

# 4. 🚨 最重要：トラフィックを最新リビジョンに向ける
gcloud run services update-traffic jyoseikinrescue --region=asia-northeast1 --to-latest

# 5. 🔍 デプロイ後検証（必須）
gcloud run services describe jyoseikinrescue --region=asia-northeast1 --format="value(status.latestCreatedRevisionName)"
gcloud run revisions list --service=jyoseikinrescue --region=asia-northeast1 --limit=3 --format="table(metadata.name,status.conditions[0].status,spec.containers[0].image)"
```

### 🚨 重要：バックグラウンドプロセス対策（2025-09-21追加）
**問題**: 別のビルドプロセスが並行して動作し、修正版を上書きする
**対策**:
1. **必ずps auxでバックグラウンドプロセスチェック**
2. **`--to-latest`使用禁止、具体的リビジョン指定必須**
3. **デプロイ後に即座にリビジョン確認**

```bash
# ❌ 危険な方法（--to-latestは上書きされるリスク）
gcloud run services update-traffic jyoseikinrescue --region=asia-northeast1 --to-latest

# ✅ 安全な方法（具体的リビジョン指定）
gcloud run services update-traffic jyoseikinrescue --region=asia-northeast1 --to-revisions=SPECIFIC_REVISION_NAME=100
```

## 詳細ドキュメント 📚

- **セッション履歴**:
  - `sessions/2025-08-sessions.md` - 8月の開発履歴
  - `sessions/2025-09-sessions.md` - 9月の開発履歴
- **運用ガイド**:
  - `operations/deployment-guide.md` - デプロイ詳細
  - `operations/troubleshooting.md` - トラブルシューティング

## 🚨 重要な失敗例と教訓

### 2025-09-17 デプロイ方法間違いによるURL変更問題
**問題**: `gcloud builds submit --tag asia-northeast1-docker.pkg.dev/jyoseikinrescue/jyoseikinrescue/jyoseikinrescue`を使用
**結果**: サービスURLが`jyoseikinrescue-453016168690`から`jyoseikinrescue-yuebabzoza-an`に変更
**影響**: カスタムドメイン`shindan.jyoseikin.jp`が古いURLを指したまま、サイト接続不可
**教訓**: **絶対にCLAUDE.mdの記載手順以外は使用しない**

## 最新セッション（直近3件）

### 2025-09-16 ナビゲーションUI実装 ✅
- デスクトップナビゲーションバー追加
- モバイルメニュー改善
- 心電図風ファビコン実装

### 2025-09-14 スケーラビリティ問題解決 ✅
- メモリ不足解決（512MB→2GB）
- ファイルキャッシュ実装
- 10,000人対応可能に

### 2025-09-14 モバイルUI大幅改善 ✅
- 会話履歴UI完全改善
- 診断結果保存問題解決

---
詳細は各分割ファイルを参照


---

## 申請書類ダウンロード機能
詳細は `operations/subsidy-forms-guide.md` を参照

## 開発セッション履歴
詳細は `sessions/` フォルダ内の各ファイルを参照

### 2025-09-21 Stripe決済後認証問題解決セッション ✅
**問題報告**:
- ユーザーがStripe決済画面から戻るボタンで戻ると「認証が必要です」エラーが発生
- 専門家相談の決済完了ページにアクセスできない状況

**根本原因特定**:
- `/expert-consultation/success/<consultation_id>`ルートが`@require_auth`デコレータを使用
- `@require_auth`はAPI用でHTML routes向けではない（Authorization headerが必要）
- Stripe checkout後のブラウザ直接アクセスではheaderが設定されない
- localStorageトークンの期限切れが併発

**実施した修正**:
1. **認証方式の変更** (`src/app.py:2541`):
   - `/expert-consultation/success/<consultation_id>`から`@require_auth`を削除
   - クライアント側Firebase認証に変更（ダッシュボードと同じ方式）

2. **新API endpoint追加** (`src/app.py:2552`):
   - `/api/expert-consultation/success/<consultation_id>`を作成
   - サーバーサイド認証とデータ取得を分離

3. **クライアント側認証強化** (`templates/consultation_success.html`):
   - Firebase認証ライブラリ追加
   - `user.getIdToken(true)`で強制トークン更新機能実装
   - 認証失敗時のダッシュボードリダイレクト機能

**技術的特徴**:
- **トークン自動更新**: Stripe戻り時に新しいFirebaseトークンを自動取得
- **認証フォールバック**: 認証失敗時の適切なエラーハンドリング
- **API分離設計**: HTML表示と認証データ取得を分離

**デプロイ情報**:
- ビルド: `stripe-auth-fix-20250921-2101`
- リビジョン: `jyoseikinrescue-00298-5gv`
- コミット: `0927971`

### 2025-09-19 専門家相談予約ボタン修正セッション ✅
**要求内容**:
- 専門家相談の予約ボタンが押せない問題の解決
- 認証フローの確認と修正
- ダッシュボードと専門家相談ページの認証方式統一

**実施内容**:
- `/expert-consultation`ページの認証設定確認（既に適切に設定済み）
- API呼び出しのBearer token送信確認（正常動作確認）
- 認証フローがダッシュボードと一致していることを確認
- デプロイ: `expert-consultation-fix-20250919-1555`
- リビジョン: `jyoseikinrescue-00273-dzq`

### 2025-09-18 Googleワークスペース連携完了セッション ✅
**要求内容**:
- CalendlyからGoogle Meet直接連携への移行
- 複雑なアカウント権限問題の解決
- ワークスペースカレンダーとの統合
- 本物のGoogle Meet URL自動生成システム構築

### 2025-08-30 助成金申請フォーム管理システム構築セッション ✅
**要求内容**:
- AIが間違ったURLを返す問題の修正（特にキャリアアップ助成金）
- ランディングページのロゴ表示修正・デザイン改善
