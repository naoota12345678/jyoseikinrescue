import os
import smtplib
import logging
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        # さくらサーバー経由での送信に切り替え
        self.use_php_relay = True  # PHPリレー使用フラグ
        self.php_endpoint = "https://h-office.sakura.ne.jp/api/send_mail.php"
        self.api_key = "jyoseikin_rescue_2024_secure_key_xyz789"  # PHPスクリプトと同じキー

        # SMTP設定（フォールバック用）
        self.smtp_server = "h-office.sakura.ne.jp"
        self.smtp_port = 587
        self.username = "rescue@jyoseikin.jp"
        self.password = os.getenv('EMAIL_PASSWORD', 'rescue3737')

    def _send_via_php(self, to: str, subject: str, body: str, is_html: bool = False) -> bool:
        """PHPスクリプト経由でメール送信"""
        try:
            # デバッグ用に本文の内容をログ出力
            logger.info(f"Sending email via PHP relay - Subject: {subject}")
            logger.info(f"Email body length: {len(body)} characters")
            logger.info(f"Email body preview: {body[:100]}...")

            response = requests.post(
                self.php_endpoint,
                json={
                    'to': to,
                    'subject': subject,
                    'body': body,
                    'is_html': is_html
                },
                headers={
                    'X-API-Key': self.api_key,
                    'Content-Type': 'application/json'
                },
                timeout=30
            )

            if response.status_code == 200:
                logger.info(f"Email sent via PHP relay to: {to}")
                return True
            else:
                logger.error(f"PHP relay failed: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"PHP relay error: {str(e)}")
            return False

    def send_welcome_email(self, user_email: str, user_name: str = "") -> bool:
        """新規登録時のウェルカムメールを送信"""
        try:
            subject = "【助成金レスキュー】ご登録ありがとうございます"

            # シンプルなテキスト版（明確な文字列連結）
            greeting = f"{user_name}様" if user_name else "お客様"
            text_content = greeting + "\n\n"
            text_content += "ご登録ありがとうございます。助成金レスキューで自分に合う助成金の申請をはじめてください。\n\n"
            text_content += "サービスURL\n"
            text_content += "https://shindan.jyoseikin.jp/dashboard\n\n"
            text_content += "助成金レスキュー運営チーム\n"
            text_content += "rescue@jyoseikin.jp"

            # PHPリレー経由で送信
            if self.use_php_relay:
                # テキスト版を送信
                return self._send_via_php(user_email, subject, text_content, is_html=False)

            # 以下はフォールバック用（SMTPが復旧した場合）
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
            subject = "【テスト】助成金レスキュー メール送信確認"
            body = "助成金レスキューのメール送信テストです。"

            # PHPリレー経由で送信
            if self.use_php_relay:
                return self._send_via_php(test_email, subject, body, is_html=False)

            # 以下はフォールバック用（SMTP直接送信）
            msg = MIMEText(body, 'plain', 'utf-8')
            msg['From'] = self.username
            msg['To'] = test_email
            msg['Subject'] = subject

            logger.info(f"SMTP接続開始: {self.smtp_server}:{self.smtp_port}")

            server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30)
            try:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self.username, self.password)
                server.send_message(msg)
            finally:
                server.quit()

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