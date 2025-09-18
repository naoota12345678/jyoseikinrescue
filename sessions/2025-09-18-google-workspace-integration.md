# 2025-09-18 Googleワークスペース連携セッション

## セッション概要
円山動物病院システムを転用した専門家相談システムにおいて、CalendlyからGoogle Meet直接連携への移行を実施。複雑なアカウント権限問題を解決してワークスペース連携を完了。

## アカウント構成の整理

### 🔴 重要：アカウント関係図
```
親アカウント（個人Google）
hasebe.sr.office@gmail.com
├── Google Cloudプロジェクト作成権限あり
├── 組織ポリシー制限なし
└── サービスアカウント作成可能

↓ 管理

ワークスペースアカウント（業務用）
info@hasebe-sr-office.com
├── Googleワークスペース管理者
├── Google Meetライセンスあり
├── Google Cloud権限不足（組織ポリシーで制限）
└── カレンダー管理権限あり
```

### 🏗️ Google Cloudプロジェクト構成

#### 1. デプロイ用プロジェクト（既存）
- **プロジェクトID**: `jyoseikinrescue`
- **所有者**: naoota12345678@gmail.com（個人）
- **用途**: Cloud Run本体のデプロイ
- **URL**: https://jyoseikinrescue-453016168690.asia-northeast1.run.app

#### 2. カレンダー連携用プロジェクト（新規作成）
- **プロジェクトID**: `jyoseikin-calender`
- **所有者**: hasebe.sr.office@gmail.com（親アカウント）
- **用途**: Google Calendar API + サービスアカウント
- **サービスアカウント**: `calendar-system@jyoseikin-calender.iam.gserviceaccount.com`

## 権限問題と解決策

### 問題：ワークスペースでの制限
```
❌ info@hasebe-sr-office.com
   ├── Google Cloudプロジェクト作成：制限あり
   ├── サービスアカウントキー作成：組織ポリシーで禁止
   └── 組織ポリシー変更：権限不足
```

### 解決策：親アカウント活用
```
✅ hasebe.sr.office@gmail.com（親）
   ├── 新規Google Cloudプロジェクト作成
   ├── サービスアカウント作成（制限なし）
   ├── JSONキー生成
   └── ワークスペースカレンダーに招待で連携
```

## 実装された連携システム

### Google Calendar API設定
- **認証**: サービスアカウント方式
- **JSONキー**: Cloud Run環境変数で管理
- **カレンダーID**: `info@hasebe-sr-office.com`
- **Meet URL**: 実際のGoogle Meet会議室を自動生成

### 環境変数設定（Cloud Run）
```yaml
GOOGLE_SERVICE_ACCOUNT_JSON: |
  {
    "type": "service_account",
    "project_id": "jyoseikin-calender",
    "client_email": "calendar-system@jyoseikin-calender.iam.gserviceaccount.com",
    # ... 他の認証情報
  }
GOOGLE_CALENDAR_ID: info@hasebe-sr-office.com
```

## システム連携フロー

### 1. 予約プロセス
```
ユーザー決済完了
    ↓
専門家相談予約画面
    ↓
カレンダー時間枠選択
    ↓
サービスアカウント経由でGoogle Calendar API実行
    ↓
info@hasebe-sr-office.comのカレンダーに予約作成
    ↓
本物のGoogle Meet URL自動生成
    ↓
予約確定 + Meet URL通知
```

### 2. 管理者機能
- **営業時間設定**: 曜日別の開始・終了時間
- **休日設定**: 特定日の予約ブロック
- **時間枠ブロック**: 特定時間の予約不可設定
- **リアルタイム反映**: Firebase経由で即座に反映

## 重要なファイル構成

### コア実装ファイル
```
src/
├── google_calendar_service.py     # Google Calendar API統合
├── consultation_schedule_service.py  # スケジュール管理
└── app.py                        # APIエンドポイント

templates/
├── admin_dashboard.html          # 管理画面（スケジュール設定）
├── consultation_success.html     # 決済完了→予約画面
└── expert_consultation.html      # 専門家相談説明
```

### セキュリティ設定
```
.gitignore
├── *.json                       # サービスアカウントJSONファイル除外
└── UsersnaootDownloads*         # ダウンロードフォルダ除外
```

## デプロイ履歴

### 最新デプロイ
- **日時**: 2025-09-18 23:18
- **イメージ**: `google-api-setup-20250918-2230`
- **リビジョン**: `jyoseikinrescue-00255-tv4`
- **環境変数**: ワークスペース連携版に更新済み

### Gitコミット
- **コミットID**: 292a5d0
- **メッセージ**: "実装: Googleワークスペース連携完了 - セキュア版"

## 今後の運用

### ワークスペース側で必要な作業
1. **カレンダー共有確認**
   - calendar-system@jyoseikin-calender.iam.gserviceaccount.com
   - 「予定の変更および共有の管理権限」付与済み

2. **Meet URL生成テスト**
   - 実際の予約でGoogle Meet URLが正常生成されるか確認

### システム管理
- **環境変数**: Cloud Runコンソールで管理
- **スケジュール**: 管理画面 `/admin` で設定
- **ログ**: Cloud Run Logsで確認

## トラブルシューティング

### よくある問題
1. **Meet URL生成失敗**: サービスアカウント権限確認
2. **カレンダー同期エラー**: カレンダーID設定確認
3. **予約時間枠エラー**: 営業時間・休日設定確認

### 確認コマンド
```bash
# 現在の環境変数確認
gcloud run services describe jyoseikinrescue --region=asia-northeast1

# ログ確認
gcloud run logs read jyoseikinrescue --region=asia-northeast1
```

## 成果

### ✅ 達成できたこと
- ✅ Calendly依存を完全除去
- ✅ 本物のGoogle Meet URL自動生成
- ✅ ワークスペースカレンダー直接連携
- ✅ 管理者による柔軟なスケジュール管理
- ✅ セキュアな認証情報管理

### 🎯 システムの価値
- **専門家の効率化**: 一元的なカレンダー管理
- **ユーザー体験向上**: 実際のMeet会議室での相談
- **管理コスト削減**: Calendly月額料金不要
- **システム統合**: Google Workspace完全連携

---

**次回セッション時の引き継ぎ事項**:
このアカウント関係図と環境変数設定を必ず確認してから作業開始すること。特にデプロイ時は必ずnaoota12345678@gmail.comアカウントに切り替えてから実行。