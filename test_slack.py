#!/usr/bin/env python3
"""
Slack通知テストスクリプト
"""
import requests
import json
from datetime import datetime

def test_slack_notification():
    """Slack通知のテスト"""

    # Webhook URL
    webhook_url = "https://hooks.slack.com/services/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"

    # テストメッセージ
    test_message = f"""
🧪 **助成金レスキュー Slack通知テスト**

テスト時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

✅ Webhook接続テスト成功
📱 モバイル通知確認用

このメッセージが表示されれば、Slack通知システムは正常に動作しています。
"""

    # Slackペイロード（リッチフォーマット）
    payload = {
        "attachments": [
            {
                "color": "good",  # 緑色
                "title": "🧪 助成金レスキュー システムテスト",
                "text": test_message,
                "footer": "助成金レスキュー不正検知システム",
                "ts": int(datetime.now().timestamp())
            }
        ]
    }

    try:
        print("Slack通知を送信中...")

        response = requests.post(
            webhook_url,
            json=payload,
            timeout=10
        )

        if response.status_code == 200:
            print("OK Slack通知送信成功！")
            print("Slackアプリでメッセージを確認してください。")
            return True
        else:
            print(f"NG Slack通知送信失敗: {response.status_code}")
            print(f"エラー内容: {response.text}")
            return False

    except Exception as e:
        print(f"ERROR エラーが発生しました: {str(e)}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("Slack 通知テスト開始")
    print("=" * 50)

    success = test_slack_notification()

    if success:
        print("\nOK テスト完了！Slackで通知を確認してください。")
    else:
        print("\nNG テスト失敗。設定を確認してください。")