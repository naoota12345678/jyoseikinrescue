# Firebase ストレージ制限とコスト最適化

## 保存上限の実装

### 1. ユーザーごとの保存上限
```javascript
// 無料プラン
const FREE_LIMITS = {
  ai_results: 10,      // AI診断結果は10件まで
  subsidies: 3,        // メモは3件まで
  total_size: 5        // 合計5MBまで
};

// 有料プラン
const PAID_LIMITS = {
  ai_results: 100,     // AI診断結果は100件まで
  subsidies: 50,       // メモは50件まで
  total_size: 50       // 合計50MBまで
};
```

### 2. 自動削除ポリシー
- 90日以上アクセスのないデータは自動削除
- AI診断結果は最新20件のみ保持（古いものから削除）
- 一時診断結果は24時間で自動削除

### 3. データ圧縮
- 長文のAI回答は要約版を保存
- 画像は使用しない
- JSONデータの最適化

## コスト削減施策

### 1. キャッシュ戦略
```javascript
// ブラウザキャッシュを活用
const CACHE_DURATION = {
  ai_results: 3600,    // 1時間
  subsidies: 1800,     // 30分
  user_data: 300       // 5分
};
```

### 2. バッチ処理
- 複数の書き込みを1回にまとめる
- リアルタイム同期は必要最小限に

### 3. インデックス最適化
- 必要最小限のインデックスのみ作成
- 複合インデックスは慎重に検討

## 実装コード例

### データ保存時の上限チェック
```python
def check_storage_limit(user_id, plan_type='free'):
    """ストレージ上限をチェック"""
    limits = FREE_LIMITS if plan_type == 'free' else PAID_LIMITS
    
    # 現在の使用量を取得
    ai_results_count = db.collection('users').document(user_id)\
        .collection('ai_results').count().get()
    
    subsidies_count = db.collection('users').document(user_id)\
        .collection('subsidies').count().get()
    
    if ai_results_count >= limits['ai_results']:
        # 古いデータを削除
        delete_oldest_ai_results(user_id, count=5)
    
    if subsidies_count >= limits['subsidies']:
        raise StorageLimitExceeded("メモの保存上限に達しました")
```

### 古いデータの自動削除
```python
def cleanup_old_data():
    """90日以上古いデータを削除"""
    cutoff_date = datetime.now() - timedelta(days=90)
    
    # バッチ削除処理
    batch = db.batch()
    old_docs = db.collection_group('ai_results')\
        .where('timestamp', '<', cutoff_date.isoformat())\
        .limit(500).get()
    
    for doc in old_docs:
        batch.delete(doc.reference)
    
    batch.commit()
```

## 月額コスト予測

### 1000人アクティブユーザー時
- **現状**: 約¥9,520/月
- **最適化後**: 約¥5,000/月（47%削減）

### スケーリング予測
- 100人: 約¥500/月
- 500人: 約¥2,500/月
- 1000人: 約¥5,000/月
- 5000人: 約¥25,000/月

## 推奨事項

1. **即座に実装すべき**
   - 保存上限の設定
   - 24時間での一時データ削除
   - 最新20件制限

2. **段階的に実装**
   - キャッシュ戦略
   - バッチ処理
   - 自動クリーンアップ

3. **モニタリング**
   - Firebase使用量ダッシュボードの定期確認
   - アラート設定（月額¥5,000超過時）
   - ユーザーごとの使用量追跡

## 収益性分析

### 1000人の場合
- 売上: ¥3,000 × 1000人 = ¥3,000,000/月
- Firebase費用: ¥5,000/月
- **粗利率: 99.8%**

Firebaseのコストは売上の0.2%以下で、十分に採算が取れます。