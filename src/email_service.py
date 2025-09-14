import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.smtp_server = "www516.sakura.ne.jp"
        self.smtp_port = 587
        self.username = "rescue@jyoseikin.jp"
        self.password = os.getenv('EMAIL_PASSWORD', 'rescue3737')  # 環境変数から取得、なければデフォルト

    def send_welcome_email(self, user_email: str, user_name: str = "") -> bool:
        """新規登録時のウェルカムメールを送信"""
        try:
            # メール内容作成
            msg = MIMEMultipart('alternative')
            msg['From'] = self.username
            msg['To'] = user_email
            msg['Subject'] = "【助成金レスキュー】ご登録ありがとうございます"

            # テキスト版
            text_content = f"""
{user_name if user_name else ""}様

この度は助成金レスキューにご登録いただき、誠にありがとうございます。

■ 5回無料お試しが開始されました
今すぐ専門エージェントで助成金相談をお試しください。
各助成金に特化したAIエージェントが、あなたの会社に最適なアドバイスを提供します。

■ ご利用方法
1. ログイン後、ダッシュボードから専門エージェントを選択
2. 業務改善助成金、キャリアアップ助成金など、目的に応じて選択
3. 具体的な相談内容を入力してご質問ください

■ サービスURL
https://shindan.jyoseikin.jp/dashboard

■ 主な対応助成金
・業務改善助成金
・キャリアアップ助成金（8コース対応）
・人材開発支援助成金
・65歳超雇用推進助成金

何かご不明な点やご質問がございましたら、お気軽にお問い合わせください。
助成金活用で、あなたの会社の発展をサポートいたします。

助成金レスキュー運営チーム
社会保険労務士監修
https://shindan.jyoseikin.jp/
rescue@jyoseikin.jp
"""

            # HTML版
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: 'Hiragino Sans', 'Yu Gothic', sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
        .content {{ background: white; padding: 30px; border: 1px solid #e5e7eb; }}
        .feature {{ background: #f8fafc; padding: 15px; margin: 15px 0; border-radius: 8px; border-left: 4px solid #667eea; }}
        .cta {{ background: #667eea; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; display: inline-block; margin: 20px 0; }}
        .footer {{ background: #f9fafb; padding: 20px; text-align: center; color: #6b7280; border-radius: 0 0 8px 8px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏢 助成金レスキュー</h1>
            <p>ご登録ありがとうございます！</p>
        </div>

        <div class="content">
            <p>{user_name if user_name else ""}様</p>

            <p>この度は助成金レスキューにご登録いただき、誠にありがとうございます。</p>

            <div class="feature">
                <h3>🎯 5回無料お試し開始</h3>
                <p>今すぐ専門エージェントで助成金相談をお試しください。<br>
                各助成金に特化したAIエージェントが、あなたの会社に最適なアドバイスを提供します。</p>
            </div>

            <a href="https://shindan.jyoseikin.jp/dashboard" class="cta">📊 ダッシュボードを開く</a>

            <div class="feature">
                <h3>💡 主な対応助成金</h3>
                <ul>
                    <li>✅ 業務改善助成金</li>
                    <li>✅ キャリアアップ助成金（8コース対応）</li>
                    <li>✅ 人材開発支援助成金</li>
                    <li>✅ 65歳超雇用推進助成金</li>
                </ul>
            </div>

            <div class="feature">
                <h3>🚀 ご利用方法</h3>
                <ol>
                    <li>ダッシュボードから専門エージェントを選択</li>
                    <li>目的に応じた助成金カテゴリを選択</li>
                    <li>具体的な相談内容を入力してご質問</li>
                </ol>
            </div>

            <p>何かご不明な点やご質問がございましたら、お気軽にお問い合わせください。<br>
            助成金活用で、あなたの会社の発展をサポートいたします。</p>
        </div>

        <div class="footer">
            <strong>助成金レスキュー運営チーム</strong><br>
            <em>社会保険労務士監修</em><br>
            <a href="https://shindan.jyoseikin.jp/">https://shindan.jyoseikin.jp/</a><br>
            rescue@jyoseikin.jp
        </div>
    </div>
</body>
</html>
"""

            # テキストとHTML両方を添付
            text_part = MIMEText(text_content, 'plain', 'utf-8')
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(text_part)
            msg.attach(html_part)

            # SMTP接続・送信
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()  # TLS暗号化開始
                server.login(self.username, self.password)
                server.send_message(msg)

            logger.info(f"Welcome email sent successfully to: {user_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send welcome email to {user_email}: {str(e)}")
            return False

    def send_test_email(self, test_email: str) -> bool:
        """テスト用メール送信"""
        try:
            msg = MIMEText("助成金レスキューのメール送信テストです。", 'plain', 'utf-8')
            msg['From'] = self.username
            msg['To'] = test_email
            msg['Subject'] = "【テスト】助成金レスキュー メール送信確認"

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)

            logger.info(f"Test email sent successfully to: {test_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send test email to {test_email}: {str(e)}")
            return False

# サービスインスタンス
_email_service = None

def get_email_service():
    """EmailServiceのシングルトンインスタンスを取得"""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service