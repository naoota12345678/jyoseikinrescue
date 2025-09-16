# デプロイ検証ガイド - 意図しないイメージ配備防止

## 問題の教訓 ⚠️

### **2025-09-16に発生した問題**
- **症状**: プロンプト改修が適用されない
- **原因**: 正しいイメージがデプロイされていなかった
- **稼働中**: 古いイメージ `sha256:68232ddb9465fc5fe691d9e436f85d278edc575537de00039ce654ae8ed81d6a`
- **期待される**: `prompt-improvement-20250916-2122`

## 必須の検証手順 ✅

### **STEP 1: ビルド後の即座確認**
```bash
# ビルド実行後、必ず以下を確認
gcloud builds list --limit=1 --format="table(images,status,createTime)"
```

### **STEP 2: デプロイ前の最終確認**
```bash
# ビルド結果から正確なイメージ名を取得
LATEST_IMAGE=$(gcloud builds list --limit=1 --format="value(images)")
echo "デプロイするイメージ: $LATEST_IMAGE"

# 確認後にデプロイ実行
gcloud run services update jyoseikinrescue --region=asia-northeast1 --image=$LATEST_IMAGE
```

### **STEP 3: デプロイ後の稼働確認**
```bash
# 現在稼働中のリビジョンとイメージを確認
gcloud run revisions describe $(gcloud run services describe jyoseikinrescue --region=asia-northeast1 --format="value(status.latestReadyRevisionName)") --region=asia-northeast1 --format="value(spec.template.spec.containers[0].image)"
```

## 絶対に避けるべきパターン ❌

### **1. 推測でのイメージ名使用**
```bash
❌ --image=asia-northeast1-docker.pkg.dev/jyoseikinrescue/jyoseikinrescue/latest
❌ --image=asia-northeast1-docker.pkg.dev/jyoseikinrescue/jyoseikinrescue/IMAGE_NAME
```

### **2. gcloud builds list の確認スキップ**
```bash
❌ gcloud builds submit --tag IMAGE_NAME .
❌ gcloud run services update jyoseikinrescue --image=IMAGE_NAME  # 確認なし
```

### **3. デプロイ後の検証スキップ**
- リビジョン確認なし
- 実際の動作テストなし

## 正しいワークフロー ✅

### **完全なデプロイ手順**
```bash
# 1. ビルド実行
echo "=== STEP 1: ビルド実行 ==="
gcloud builds submit --tag asia-northeast1-docker.pkg.dev/jyoseikinrescue/jyoseikinrescue/$(date +%Y%m%d-%H%M) .

# 2. ビルド結果確認（必須）
echo "=== STEP 2: ビルド結果確認 ==="
LATEST_IMAGE=$(gcloud builds list --limit=1 --format="value(images)")
echo "ビルド完了イメージ: $LATEST_IMAGE"

# 3. デプロイ実行
echo "=== STEP 3: デプロイ実行 ==="
gcloud run services update jyoseikinrescue --region=asia-northeast1 --image=$LATEST_IMAGE

# 4. 稼働確認（必須）
echo "=== STEP 4: 稼働確認 ==="
CURRENT_REVISION=$(gcloud run services describe jyoseikinrescue --region=asia-northeast1 --format="value(status.latestReadyRevisionName)")
CURRENT_IMAGE=$(gcloud run revisions describe $CURRENT_REVISION --region=asia-northeast1 --format="value(spec.template.spec.containers[0].image)")
echo "稼働中リビジョン: $CURRENT_REVISION"
echo "稼働中イメージ: $CURRENT_IMAGE"

# 5. 一致確認
if [[ "$LATEST_IMAGE" == "$CURRENT_IMAGE" ]]; then
    echo "✅ 正しいイメージが稼働中"
else
    echo "❌ イメージ不一致検出"
    echo "期待: $LATEST_IMAGE"
    echo "実際: $CURRENT_IMAGE"
    exit 1
fi
```

## 緊急時の対処法 🚨

### **意図しないイメージが稼働中の場合**
```bash
# 1. 正しいイメージを特定
gcloud builds list --limit=10 --format="table(images,status,createTime)"

# 2. 正しいイメージで緊急リデプロイ
gcloud run services update jyoseikinrescue --region=asia-northeast1 --image=CORRECT_IMAGE

# 3. 動作確認
# 実際のアプリケーション機能をテスト
```

## チェックリスト 📋

### **デプロイ前**
- [ ] `gcloud builds submit` でビルド成功を確認
- [ ] `gcloud builds list` で実際のイメージ名を確認
- [ ] イメージ名をコピー&ペーストで正確に使用

### **デプロイ後**
- [ ] `gcloud run revisions list` で新リビジョン確認
- [ ] 稼働中イメージがビルド結果と一致することを確認
- [ ] アプリケーションの実際の機能をテスト

### **機能テスト**
- [ ] 業務改善助成金エージェントで期限質問をテスト
- [ ] 「要綱と要領を確認いたします」から始まる回答を確認
- [ ] 専門エージェントの正常動作を確認

## 自動化スクリプト 🤖

上記の手順を自動化したスクリプトを `scripts/safe-deploy.sh` として作成することを推奨。

---

**重要**: この検証手順を必ず実行することで、プロンプト改修などの重要な変更が確実に本番環境に反映される。