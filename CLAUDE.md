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

### プロジェクト構成
- **フロントエンド**: Flask + HTML/CSS/JavaScript
- **バックエンド**: Python Flask + Firebase
- **AI**: Claude 3.5 Sonnet API
- **デプロイ**: Google Cloud Run
- **認証**: Firebase Auth
- **決済**: Stripe

### 主要機能
1. **無料診断システム**: 助成金の適用可能性を診断
2. **AI専門エージェント**: 9つの助成金専門エージェント
3. **メモ機能**: 相談内容の保存・管理
4. **申請書類リンク**: 厚労省公式書類への直接リンク
5. **料金プラン**: Light/Regular/Heavy（¥1,480～¥5,500）

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

### デプロイ手順（必須）
```bash
# 1. ビルド
gcloud builds submit --tag asia-northeast1-docker.pkg.dev/jyoseikinrescue/jyoseikinrescue/IMAGE_NAME .

# 2. ビルド結果確認
gcloud builds list --limit=1 --format="value(images)"

# 3. デプロイ
gcloud run services update jyoseikinrescue --region=asia-northeast1 --image=EXACT_IMAGE_FROM_STEP2
```

**⚠️ 重要**: `--source`オプションは使用禁止

## 詳細ドキュメント 📚

- **セッション履歴**:
  - `sessions/2025-08-sessions.md` - 8月の開発履歴
  - `sessions/2025-09-sessions.md` - 9月の開発履歴
- **運用ガイド**:
  - `operations/deployment-guide.md` - デプロイ詳細
  - `operations/troubleshooting.md` - トラブルシューティング

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

### 2025-08-30 助成金申請フォーム管理システム構築セッション ✅
**要求内容**: 
- AIが間違ったURLを返す問題の修正（特にキャリアアップ助成金）
- ランディングページのロゴ表示修正・デザイン改善
