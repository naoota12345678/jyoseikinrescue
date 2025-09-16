# デプロイ前チェックリスト

**🚨 デプロイ実行前に必ず確認**

## 1. バックグラウンドプロセス確認
```bash
ps aux | grep "gcloud builds"
```
- [ ] バックグラウンドビルドが動いていないことを確認

## 2. イメージ名確認
- [ ] 具体的な名前を使用（例：`fix-20250917-0630`）
- [ ] **絶対に`jyoseikinrescue`は使わない**

## 3. 禁止コマンド確認
以下のコマンドは**絶対に実行禁止**：
```bash
gcloud builds submit --tag asia-northeast1-docker.pkg.dev/jyoseikinrescue/jyoseikinrescue/jyoseikinrescue .
```

## 4. 正しい手順
```bash
# 1. バックグラウンドプロセス確認
ps aux | grep "gcloud builds" || echo "No background builds"

# 2. 具体的な名前でビルド
gcloud builds submit --tag asia-northeast1-docker.pkg.dev/jyoseikinrescue/jyoseikinrescue/fix-YYYYMMDD-HHMM .

# 3. ビルド完了確認
gcloud builds list --limit=1 --format="value(images)"

# 4. デプロイ
gcloud run services update jyoseikinrescue --region=asia-northeast1 --image=EXACT_IMAGE_FROM_STEP3
```

## 5. 事例：2025-09-17の問題
Claude自身がルールを破り、`jyoseikinrescue`でビルドを実行。
バックグラウンドプロセスが修正版を上書きし、大問題となった。

**絶対に同じ間違いを繰り返さない**