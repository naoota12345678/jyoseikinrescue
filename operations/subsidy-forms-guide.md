# 申請書類ダウンロード機能について ⚠️

## 実装方法
**現在の方式**: `templates/subsidy_memo.html`の1504-1526行目に助成金リンクを**直接HTML記述**

## 表示される助成金（2つのみ）
1. **業務改善助成金** - 厚労省公式ページリンク
2. **キャリアアップ助成金** - 厚労省公式ページリンク

## 新しい助成金の追加方法
`templates/subsidy_memo.html`の1526行目の`</div>`直前に以下を追加：

```html
<!-- 新しい助成金 -->
<div style="border: 1px solid #e5e7eb; border-radius: 8px; padding: 1.5rem;">
    <h3 style="color: #667eea; margin-bottom: 1rem;">🏢 助成金名</h3>
    <p style="color: #6b7280; margin-bottom: 1.5rem; font-size: 0.9rem;">助成金の説明</p>

    <a href="https://リンクURL" target="_blank" style="display: block; padding: 1rem; background: #f0f9ff; border: 1px solid #0ea5e9; border-radius: 8px; text-decoration: none; color: #0c4a6e; text-align: center; font-weight: 600;">
        📋 申請書類・制度詳細<br>
        <span style="font-size: 0.8rem; font-weight: normal;">（厚生労働省公式サイト）</span>
    </a>
</div>
```

## 重要な注意事項
- **APIやJSONファイルは使用しない**（過去に複雑化して失敗）
- **シンプルな静的HTML記述のみ**
- **各助成金につき1つのリンクのみ**（個別申請書類は表示しない）
- **厚労省公式ページへの直接リンク**