# 業務改善助成金レスキュー - セットアップガイド

## 🔧 必要な設定

### 1. Firebase設定

1. [Firebase Console](https://console.firebase.google.com/) でプロジェクトを作成
2. Authentication を有効化し、Google プロバイダーを追加
3. Firestore データベースを作成
4. サービスアカウントキーを生成し、`.env` ファイルに設定

### 2. Stripe設定

1. [Stripe Dashboard](https://dashboard.stripe.com/) でアカウント作成
2. APIキーを取得し、`.env` ファイルに設定
3. Webhookエンドポイントを設定: `https://your-domain.com/api/stripe/webhook`

### 3. 環境変数設定

`.env` ファイルを作成し、以下の内容を設定:

```bash
# Firebase Configuration
FIREBASE_PROJECT_ID=your-firebase-project-id
FIREBASE_PRIVATE_KEY_ID=your-firebase-private-key-id
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nyour-firebase-private-key\n-----END PRIVATE KEY-----"
FIREBASE_CLIENT_EMAIL=your-firebase-client-email
FIREBASE_CLIENT_ID=your-firebase-client-id

# Stripe Configuration
STRIPE_SECRET_KEY=sk_test_your_stripe_secret_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret

# Claude API Configuration  
ANTHROPIC_API_KEY=your_anthropic_api_key

# Flask設定
SECRET_KEY=your_secret_key_here
FLASK_ENV=production
PORT=8080
```

### 4. フロントエンド設定

`templates/auth_index.html` 内のFirebase設定を更新:

```javascript
const firebaseConfig = {
    apiKey: "your-api-key",
    authDomain: "your-project.firebaseapp.com",
    projectId: "your-project-id",
    storageBucket: "your-project.appspot.com",
    messagingSenderId: "123456789",
    appId: "your-app-id"
};
```

## 🚀 実装完了内容

### ✅ バックエンド機能

- **Firebase認証**: `src/firebase_config.py`
  - Firebase Admin SDK初期化
  - IDトークン検証機能

- **ユーザー管理**: `src/models/user.py`  
  - 新規ユーザー作成（トライアル5質問付き）
  - Stripe顧客ID連携

- **サブスクリプション管理**: `src/models/subscription.py`
  - 使用量カウンター（質問数追跡）
  - プラン管理（trial/basic/additional_pack）
  - 使用制限チェック

- **Stripe決済**: `src/stripe_service.py`
  - 基本プラン（月額3,000円）
  - 追加パック（2,000円）  
  - Webhook処理

- **認証ミドルウェア**: `src/auth_middleware.py`
  - `@require_auth`: Firebase認証必須
  - `@check_usage_limit`: 使用量制限チェック

### ✅ APIエンドポイント

- `POST /api/chat` - AI相談（認証・使用量制限あり）
- `GET /api/auth/user` - ユーザー情報取得
- `POST /api/auth/register` - 新規ユーザー登録
- `POST /api/payment/basic-plan` - 基本プラン決済
- `POST /api/payment/additional-pack` - 追加パック決済  
- `POST /api/stripe/webhook` - Stripe webhook処理

### ✅ フロントエンド機能

- **認証UI**: Google OAuth2 ログイン
- **使用状況表示**: 残り質問数・プラン情報
- **決済UI**: アップグレード・追加パック購入ボタン
- **制限処理**: 使用上限到達時の案内

## 💳 料金体系

- **トライアル**: 5質問無料
- **基本プラン**: 月額3,000円（50質問/月）
- **追加パック**: 2,000円（50質問追加）

## 📊 ビジネスモデル

- **顧客LTV**: 45,000円（5ヶ月平均利用）
- **利益率**: 78.3%（基本プラン）、67.5%（追加パック）
- **顧客価値**: 90,000円節約（従来手数料12万円 → AI 3万円）

## 🔄 次のステップ

1. Firebase プロジェクトの作成と設定
2. Stripe アカウントの設定  
3. 環境変数の設定
4. 本番環境でのテスト
5. ドメイン設定とSSL証明書
6. Google Analytics設定（オプション）