# 助成金レスキュー - Claude AI助成金相談サービス

Claude AIを活用した高精度な助成金相談サービスです。業務改善助成金の専門知識により、企業に最適な助成金提案を行います。

## 🚀 特徴

- **Claude AI搭載**: 最新のAI技術による高精度な助成金相談
- **即座に回答**: 24時間365日いつでも専門的なアドバイス
- **個別最適化**: 企業状況に合わせたカスタマイズされた提案
- **業務改善助成金専門**: 特化した知識による的確なサポート

## 🛠 技術スタック

- **Backend**: Flask (Python)
- **AI**: Claude API (Anthropic)
- **Frontend**: HTML/CSS/JavaScript
- **Deployment**: Google Cloud Run
- **CI/CD**: GitHub Actions

## 📦 セットアップ

### 1. 環境変数の設定

`.env.example`をコピーして`.env`ファイルを作成:

```bash
cp .env.example .env
```

`.env`ファイルに必要な値を設定:

```
CLAUDE_API_KEY=your_claude_api_key_here
SECRET_KEY=your_secret_key_here
FLASK_ENV=development
PORT=8080
```

### 2. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 3. アプリケーションの実行

```bash
python src/app.py
```

アプリケーションは http://localhost:8080 で利用できます。

## 🚀 デプロイ

### Google Cloud Run

1. GitHubシークレットを設定:
   - `GCP_PROJECT_ID`: Google CloudプロジェクトID
   - `GCP_SA_KEY`: サービスアカウントキー (JSON)
   - `CLAUDE_API_KEY`: Claude APIキー
   - `SECRET_KEY`: Flaskシークレットキー

2. mainブランチにプッシュすると自動デプロイされます

## 📁 プロジェクト構成

```
jyoseikinrescue-claude/
├── .github/
│   └── workflows/
│       └── deploy.yml          # CI/CDパイプライン
├── src/
│   ├── app.py                  # Flaskメインアプリケーション
│   └── claude_service.py       # Claude APIサービス
├── templates/
│   └── index.html              # フロントエンドUI
├── static/                     # 静的ファイル
├── requirements.txt            # Python依存関係
├── Dockerfile                  # Dockerコンテナ設定
├── .env.example               # 環境変数テンプレート
├── .gitignore                 # Git除外ファイル
└── README.md                  # このファイル
```

## 💬 使用方法

1. **会社情報入力**: 会社名、業種、従業員数などの基本情報を入力
2. **助成金チェック**: 利用可能な助成金の適用可能性を確認
3. **AI相談**: 具体的な質問をして専門的なアドバイスを受ける

## 🔧 API エンドポイント

- `POST /api/chat`: AI助成金相談
- `POST /api/grant-check`: 助成金適用可能性チェック
- `GET /health`: ヘルスチェック

## 📄 ライセンス

このプロジェクトは MIT ライセンスの下で公開されています。

## 🤝 サポート

質問や問題がある場合は、GitHubのIssueをご利用ください。