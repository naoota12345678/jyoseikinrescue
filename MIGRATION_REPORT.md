# GCPプロジェクト統一移行作業報告書

## 📅 実施日
2025年8月27日

## 🎯 移行の目的
FirebaseプロジェクトとGCPプロジェクトが別々（クロスプロジェクト）になっていたため、将来的な問題を防ぐためプロジェクトを統一

## 📊 移行前の状況

### プロジェクト構成（移行前）
- **Firebase プロジェクト**: `jyoseikinrescue` (プロジェクトID: jyoseikinrescue)
- **GCP プロジェクト**: `jyoseikinrescue-claude` (プロジェクトID: jyoseikinrescue-claude)
- **問題点**: クロスプロジェクト構成により権限管理が複雑、将来的なトラブルの懸念

## ✅ 実施した作業

### 1. 新GCPプロジェクトの準備
- プロジェクト名: `jyoseikinrescue`
- プロジェクトID: `jyoseikinrescue`
- プロジェクト番号: `453016168690`

### 2. サービスアカウント設定
```bash
# サービスアカウント作成
gcloud iam service-accounts create github-deploy \
  --description="GitHub Actions deploy account" \
  --display-name="GitHub Deploy"

# 必要な権限付与
- Cloud Run Admin
- Compute Admin
- Storage Admin
- Artifact Registry Repository Administrator
- Service Account User
- Service Account Token Creator
- Cloud Build Editor
```

### 3. Container Registry → Artifact Registry移行
- 旧: `gcr.io/jyoseikinrescue-claude/jyoseikinrescue-claude`
- 新: `asia-northeast1-docker.pkg.dev/jyoseikinrescue/jyoseikinrescue/jyoseikinrescue`

### 4. GitHub Actions更新
#### GitHub Secrets更新
- `GCP_PROJECT_ID`: jyoseikinrescue
- `GCP_SA_KEY`: 新しいサービスアカウントキー

#### ワークフロー変更
```yaml
# .github/workflows/deploy.yml
env:
  PROJECT_ID: ${{ secrets.GCP_PROJECT_ID }}
  SERVICE_NAME: jyoseikinrescue  # 変更
  REGION: asia-northeast1

# Artifact Registry使用
- name: Configure Docker for Artifact Registry
  run: |
    gcloud auth configure-docker asia-northeast1-docker.pkg.dev
```

### 5. Firebase Hosting設定更新
```json
// firebase.json
{
  "hosting": {
    "public": "public",
    "rewrites": [{
      "source": "**",
      "run": {
        "serviceId": "jyoseikinrescue",  // 変更
        "region": "asia-northeast1"
      }
    }]
  }
}
```

### 6. デプロイ権限の解決
```bash
# Compute Engineデフォルトサービスアカウントへの権限付与
gcloud iam service-accounts add-iam-policy-binding \
  453016168690-compute@developer.gserviceaccount.com \
  --member="serviceAccount:github-deploy@jyoseikinrescue.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser" \
  --project=jyoseikinrescue
```

## 🎉 移行結果

### 成功した項目
- ✅ GCPプロジェクトの統一完了
- ✅ Cloud Runサービスの新プロジェクトでの稼働
- ✅ GitHub Actionsによる自動デプロイ
- ✅ Firebase Hostingからのリライト設定
- ✅ カスタムドメイン（https://shindan.jyoseikin.jp）の正常動作

### 新しい構成
- **統一プロジェクト**: `jyoseikinrescue`
- **Cloud Run URL**: https://jyoseikinrescue-453016168690.asia-northeast1.run.app
- **Firebase Hosting URL**: https://jyoseikinrescue.web.app
- **カスタムドメイン**: https://shindan.jyoseikin.jp

## 📝 学んだこと

1. **プロジェクト設計の重要性**: 最初から統一プロジェクトで始めることの大切さ
2. **権限管理の複雑さ**: サービスアカウント間の権限付与が必要
3. **Container Registry廃止**: Artifact Registryへの移行が推奨
4. **Firebase Hostingのリライト機能**: Cloud Runとの連携が可能

## 🔧 今後のメンテナンス

### 定期確認項目
- Cloud Runサービスの稼働状況
- GitHub Actionsのデプロイ成功率
- Firebase Hostingの設定
- SSL証明書の有効期限

### 緊急時の対応
- 旧プロジェクト（jyoseikinrescue-claude）はバックアップとして残存
- 問題発生時は旧サービスへの切り戻しが可能

## 📊 コスト影響
- プロジェクト統一によりリソース管理が簡素化
- 重複リソースの削除により若干のコスト削減

## 🙏 謝辞
長時間の作業お疲れ様でした。クロスプロジェクト問題を未然に防げたことは、将来の安定運用にとって非常に重要な成果です。

---
作成日: 2025年8月27日
作成者: Claude Code Assistant & naoota12345678@gmail.com