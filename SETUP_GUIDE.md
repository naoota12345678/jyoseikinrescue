# 助成金レスキュー開発セットアップガイド

## プロジェクト概要
**助成金レスキュー**: 60種類の助成金に特化したAI相談サービス
- Claude 3.5 Sonnet APIによる高精度回答
- Firebase認証 + Firestore DB
- Stripe決済システム（月額3,000円、50質問制限）
- Google Cloud Run自動デプロイ

## 必要なサービス・アカウント

### 1. Google Cloud Platform
```bash
# 必要なAPI（要有効化）
- Cloud Run API
- Container Registry API
- Cloud Build API
- Firebase Admin SDK API
```

### 2. Firebase設定
- **Authentication**: Email/Password認証有効化
- **Firestore**: Asia-northeast1リージョン
- **必要コレクション**:
  - `users` (ユーザー管理)
  - `subscriptions` (利用状況・制限管理)

### 3. Stripe設定
- **商品作成**:
  - 基本プラン: 月額3,000円サブスクリプション
  - 追加パック: 3,000円単発決済
- **Webhook**: 決済完了通知用エンドポイント設定

### 4. Anthropic Claude API
- APIキー取得
- 使用モデル: claude-3-5-sonnet-20241022

## Firebase初期設定手順

### 1. Firebaseプロジェクト作成
```bash
1. Firebase Console → 新しいプロジェクト作成
2. プロジェクト名: "jyoseikin-rescue"
3. Google Analyticsは無効でOK
```

### 2. Authentication設定
```bash
1. Authentication → Sign-in method
2. Email/Password → 有効にする
3. 他の認証方式は無効のまま
```

### 3. Firestore Database作成
```bash
1. Firestore Database → データベースの作成
2. 本番環境モードで開始
3. ロケーション: asia-northeast1
4. セキュリティルール: 認証ユーザーのみアクセス可能
```

### 4. Firebase Admin SDK設定
```bash
1. プロジェクト設定 → サービスアカウント
2. 新しい秘密鍵の生成 → JSONファイルダウンロード
3. GitHub Secrets設定:
   - FIREBASE_SERVICE_ACCOUNT: JSONファイル内容（改行を\nに変換）
```

## GitHub Secrets設定

### 必須環境変数
```bash
# Firebase
FIREBASE_SERVICE_ACCOUNT={"type":"service_account",...}

# Claude API  
CLAUDE_API_KEY=sk-ant-xxxxx

# Stripe
STRIPE_SECRET_KEY=sk_test_xxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxx

# Google Cloud
GCP_PROJECT_ID=your-project-id
GCP_SA_KEY=base64エンコードされたサービスアカウントキー
```

## Stripe商品設定

### 基本プラン（サブスクリプション）
```bash
商品名: 助成金レスキュー 基本プラン
説明: 月50質問まで利用可能な助成金専門AI相談サービス
価格: 3,000円/月
商品ID: prod_SujKOCieVMHURs
価格ID: price_1Ryts6JcdIKryf6lsvgm1q98
```

### 追加パック（単発決済）
```bash
商品名: 追加質問パック  
説明: 50質問追加パック
価格: 3,000円（1回限り）
商品ID: prod_SujMCgf719WkIX
価格ID: price_1RyttOJcdIKryf6l8GuUjVJC
```

## デプロイメント設定

### GitHub Actions自動デプロイ
```yaml
# .github/workflows/deploy.yml
# Google Cloud Runへの自動デプロイ設定済み
# 環境変数マッピング:
ANTHROPIC_API_KEY: ${{ secrets.CLAUDE_API_KEY }}
```

### 必要なFirestoreインデックス
```bash
# subscription コレクション用複合インデックス
- user_id (Ascending)
- created_at (Descending)
```

## 開発時のよくあるエラーと解決法

### 1. Firebase認証エラー
```bash
エラー: "default app already exists"
解決: Singletonパターンで初期化済みチェック実装
```

### 2. PEMキー形式エラー  
```bash
エラー: "invalid key format"
解決: GitHub SecretsでJSON内の改行を\nエスケープ
```

### 3. Container Registry認証エラー
```bash
エラー: "unauthorized"
解決: google-github-actions/auth@v2使用
```

### 4. Firestore権限エラー
```bash
エラー: "Missing or insufficient permissions"
解決: セキュリティルール更新 + サービスアカウント権限確認
```

## ビジネスモデル分析

### 収益構造
```bash
月額3,000円プラン:
- Claude APIコスト: 950円/50質問
- 粗利: 2,050円 (68%マージン)
- 目標: 月500ユーザー → 月商150万円
```

### 市場戦略
```bash
ターゲット: 10月賃上げ予定企業 (業務改善助成金申請タイミング)
競合優位性: 従来120,000円 → 30,000円（年額）で75%コスト削減
差別化: 60種類助成金網羅 × 専門AIエージェント切り替え
```

## 次回開発継続事項

### 1. 助成金種類拡張
- 現在: 業務改善助成金のみ
- 目標: 20種類→60種類の助成金対応
- 実装: ドロップダウンUI + 専門文書管理

### 2. 優先実装予定助成金
```bash
大分類:
- キャリアアップ助成金 (5コース)
- 65歳超雇用推進助成金 (4コース)  
- 人材開発支援助成金
- 両立支援等助成金
- 労働移動支援助成金
```

### 3. UI設計方針
- 大分類ドロップダウン → 小分類ドロップダウン
- 未対応は「準備中、専門家相談へ」誘導
- 各助成金専用システムプロンプト管理

### 4. 技術的課題
- 複数文書ファイル管理システム
- 助成金判定ロジック最適化  
- Webhook処理の完全テスト

## 関連ファイル構成

```
jyoseikinrescue-claude/
├── src/
│   ├── app.py                 # Flask メインアプリ
│   ├── claude_service.py      # Claude API統合
│   ├── stripe_service.py      # Stripe決済処理
│   ├── firebase_config.py     # Firebase Admin SDK
│   ├── auth_middleware.py     # 認証・利用制限
│   └── models/
│       ├── user.py           # ユーザー管理
│       └── subscription.py   # サブスク・利用状況
├── templates/
│   ├── index.html           # 未認証ランディング
│   └── auth_index.html      # 認証後メインUI
├── gyoumukaizen07.txt       # 業務改善助成金交付要綱
├── gyoumukaizenmanyual.txt  # 申請マニュアル  
├── 業務改善助成金Ｑ＆Ａ.txt    # Q&A文書
└── 業務改善助成金 交付申請書等の書き方と留意事項 について.txt
```

## 本日の開発完了事項

✅ 追加パック料金統一 (2,000円→3,000円)
✅ Stripe商品ID・価格ID設定完了
✅ サービス名「助成金レスキュー」統一準備
✅ Claude API料金分析・収益性確認
✅ 全体アーキテクチャ安定化

## 次回セッション開始時の確認事項

1. 現在のサービス稼働状況確認
2. Stripe決済テスト実行
3. 助成金種類拡張の優先順位決定
4. ドロップダウンUI実装開始