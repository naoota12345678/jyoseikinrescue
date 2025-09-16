# デプロイメントガイド

## Cloud Runデプロイの正しい方法 🚀

### 重要な注意事項 ⚠️
**`gcloud run deploy --source`コマンドは使用禁止**
- Container import failedエラーが発生する既知の問題
- 必ず2段階デプロイ方式を使用すること

### 正しいデプロイ手順 ✅

#### STEP 1: ビルド実行
```bash
gcloud builds submit --tag asia-northeast1-docker.pkg.dev/jyoseikinrescue/jyoseikinrescue/IMAGE_NAME .
```

#### STEP 2: ビルド結果から正確なイメージタグ取得
```bash
gcloud builds list --limit=1 --format="value(images)"
```
または
```bash
gcloud builds list --limit=2
```
で最新のビルドのIMAGESカラムを確認

#### STEP 3: 確認したイメージタグでデプロイ
```bash
gcloud run services update jyoseikinrescue --region=asia-northeast1 --image=EXACT_IMAGE_FROM_STEP2
```

### よくある失敗パターン ❌
- `--tag`で指定した名前をそのまま使用（タイムスタンプが異なる）
- 推測でイメージ名を使用
- `gcloud builds list`を確認せずにデプロイ

### 成功パターン ✅
- `gcloud builds list`で実際に作成されたイメージ名を確認
- IMAGESカラムの値をそのまま使用
- 一文字も変更せずに正確にコピー

---

## Container import failed対処法

### 1. イメージパス確認
正しいArtifact Registryパスか？
```
asia-northeast1-docker.pkg.dev/jyoseikinrescue/jyoseikinrescue/IMAGE_NAME
```

### 2. サービスアカウント権限
Artifact Registry Reader権限があるか確認

### 3. 2段階デプロイで回避
`gcloud builds submit` → `gcloud run deploy --image`の順で実行

---

## 環境変数設定

### GitHub Secrets設定済み変数名（絶対に変更しない）
- `CLAUDE_API_KEY` ← **メインのAPI KEY**
- `FIREBASE_CLIENT_EMAIL`
- `FIREBASE_CLIENT_ID`
- `FIREBASE_PRIVATE_KEY`
- `FIREBASE_PRIVATE_KEY_ID`
- `FIREBASE_PROJECT_ID`
- `GCP_PROJECT_ID`
- `GCP_SA_KEY`
- `SECRET_KEY`
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`

### 重要な注意事項
- **CLAUDE_API_KEYを使用**（ANTHROPIC_API_KEYではない！）
- 新しい環境変数を追加する際は、上記のGitHub Secrets変数名と完全に一致させること
- 新しい変数名を勝手に作成せず、既存の変数名を必ず使用すること

### Cloud Run環境変数更新
```bash
gcloud run services update jyoseikinrescue --region=asia-northeast1 \
  --update-env-vars CLAUDE_API_KEY=<API_KEY>
```

---

## Cloud Run設定

### 現在のスペック
- **メモリ**: 2GB
- **最大インスタンス**: 100
- **リージョン**: asia-northeast1
- **処理能力**: 10,000-16,000人対応可能

### スペック変更方法
```bash
gcloud run services update jyoseikinrescue \
  --region=asia-northeast1 \
  --memory=2Gi \
  --max-instances=100
```

---

## Dockerfileの重要な設定

### fileフォルダのコピー（必須）
```dockerfile
# 要綱ファイルをコピー
COPY file/ ./file/
```
これがないと専門エージェントが動作しません。

---

## トラブルシューティング

### Container import failed
1. 環境変数の確認（CLAUDE_API_KEY設定されているか）
2. 2段階デプロイ方式を使用
3. ビルド成功を確認してからデプロイ

### 専門エージェントが動作しない
1. fileフォルダがDockerイメージに含まれているか確認
2. Cloud Runのメモリが十分か確認（推奨2GB以上）

### デプロイ後の動作確認
```bash
# ログ確認
gcloud run logs read --service=jyoseikinrescue --region=asia-northeast1

# サービス状態確認
gcloud run services describe jyoseikinrescue --region=asia-northeast1
```