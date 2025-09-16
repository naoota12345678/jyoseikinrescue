#!/usr/bin/env python3
"""
不正検知レポート統合テストスクリプト
"""
import os
import sys
sys.path.append('src')

from email_service import get_email_service

def test_fraud_report():
    """不正検知レポートの統合テスト"""

    print("=" * 50)
    print("不正検知レポートシステム 統合テスト")
    print("=" * 50)

    # 1. EmailServiceの通知テスト
    print("\n1. Slack通知テスト")
    email_service = get_email_service()

    test_message = """
📊 **不正検知システム統合テスト**

テスト時刻: 2025-09-16 19:00:00

✅ システム正常稼働確認
🔐 環境変数設定確認
📱 Slack通知機能確認

このメッセージが表示されれば、不正検知システムは正常に動作しています。
"""

    slack_result = email_service.send_slack_notification(test_message, urgent=False)
    print(f"Slack通知テスト結果: {'OK' if slack_result else 'NG'}")

    # 2. 不正検知レポート形式のテスト
    print("\n2. 不正検知レポート形式テスト")
    sample_report_message = """
📊 **不正検知日次レポート** (2025-09-16)

━━━━━━━━━━━━━━━━━━━━━━━━━━━
**📈 本日のサマリー**
• メール送信失敗: 5件
• 使い捨てメール登録試行: 3件
• 同一IP複数登録: 2件

━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ **要注意ユーザー**

• 192.168.1.1 → 3回失敗: test1@example.com, test2@example.com
• 10.0.0.1 → 2回失敗: fake@disposable.com

━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔧 **アクション方法**
Firebase Console: https://console.firebase.google.com/project/jyoseikinrescue/firestore/data/~2Fusers

該当ユーザーの status を 'blocked' に設定してください。
"""

    report_result = email_service.send_slack_notification(sample_report_message, urgent=False)
    print(f"不正検知レポート送信結果: {'OK' if report_result else 'NG'}")

    # 3. 緊急アラートテスト
    print("\n3. 緊急アラートテスト")
    alert_message = "🚨 緊急アラート: 同一IPから10回以上の不正登録を検出しました (IP: 192.168.1.100)"
    alert_result = email_service.send_slack_notification(alert_message, urgent=True)
    print(f"緊急アラート送信結果: {'OK' if alert_result else 'NG'}")

    print("\n" + "=" * 50)

    # 結果まとめ
    all_success = slack_result and report_result and alert_result
    if all_success:
        print("OK 統合テスト完了: 全ての機能が正常に動作しています")
        print("不正検知システムの本格稼働準備完了です。")
    else:
        print("NG 統合テスト失敗: 一部機能に問題があります")
        print("設定を確認してください。")

    return all_success

if __name__ == "__main__":
    # 環境変数の確認
    slack_url = os.getenv('SLACK_WEBHOOK_URL')
    if slack_url:
        print(f"SLACK_WEBHOOK_URL: 設定済み")
    else:
        print("WARNING: SLACK_WEBHOOK_URL が設定されていません")
        print("export SLACK_WEBHOOK_URL='https://hooks.slack.com/services/...' を実行してください")

    success = test_fraud_report()
    exit(0 if success else 1)