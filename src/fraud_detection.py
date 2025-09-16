#!/usr/bin/env python3
"""
不正検知・レポート生成システム
"""
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any
from collections import defaultdict
from email_service import get_email_service

logger = logging.getLogger(__name__)

class FraudDetectionService:
    def __init__(self):
        self.email_service = get_email_service()

    def analyze_failed_emails(self, log_file_path: str) -> Dict[str, Any]:
        """メール送信失敗ログを分析"""
        try:
            if not os.path.exists(log_file_path):
                logger.warning(f"Log file not found: {log_file_path}")
                return {
                    'failed_emails': 0,
                    'duplicate_ips': 0,
                    'suspicious_users': '特になし'
                }

            failed_entries = []
            ip_counts = defaultdict(list)

            # ログファイルを読み込み
            with open(log_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        failed_entries.append(entry)
                        ip_counts[entry['ip']].append(entry)
                    except json.JSONDecodeError:
                        continue

            # 同一IPからの複数失敗を検出
            suspicious_ips = []
            for ip, entries in ip_counts.items():
                if len(entries) >= 2:  # 2回以上失敗
                    emails = [entry['email'] for entry in entries]
                    suspicious_ips.append(f"• {ip} → {len(entries)}回失敗: {', '.join(emails[:3])}{'...' if len(emails) > 3 else ''}")

            suspicious_users = '\n'.join(suspicious_ips) if suspicious_ips else '特になし'

            return {
                'failed_emails': len(failed_entries),
                'duplicate_ips': len([ip for ip, entries in ip_counts.items() if len(entries) >= 2]),
                'suspicious_users': suspicious_users
            }

        except Exception as e:
            logger.error(f"Failed to analyze email logs: {str(e)}")
            return {
                'failed_emails': 0,
                'duplicate_ips': 0,
                'suspicious_users': 'ログ分析エラー'
            }

    def analyze_app_logs(self) -> Dict[str, Any]:
        """アプリケーションログから使い捨てメール試行を分析"""
        try:
            # Cloud Runのログから使い捨てメール試行を検索
            # 実装は簡素化：ログファイルがある場合の処理
            disposable_attempts = 0

            # 実際の実装では gcloud logging read コマンドまたは
            # Cloud Logging API を使用してログを取得

            return {
                'disposable_attempts': disposable_attempts
            }

        except Exception as e:
            logger.error(f"Failed to analyze app logs: {str(e)}")
            return {
                'disposable_attempts': 0
            }

    def generate_daily_report(self) -> bool:
        """日次レポートを生成してSlackに送信"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')

            # メール失敗ログ分析
            log_file_path = '/path/to/logs/failed_emails.log'  # 実際のパスに変更
            email_analysis = self.analyze_failed_emails(log_file_path)

            # アプリログ分析
            app_analysis = self.analyze_app_logs()

            # レポートデータ作成
            report_data = {
                'date': today,
                **email_analysis,
                **app_analysis
            }

            # Slackに送信
            success = self.email_service.send_fraud_report_slack(report_data)

            if success:
                logger.info(f"Daily fraud report sent successfully for {today}")
            else:
                logger.error(f"Failed to send daily fraud report for {today}")

            return success

        except Exception as e:
            logger.error(f"Failed to generate daily report: {str(e)}")
            return False

    def send_emergency_alert(self, message: str) -> bool:
        """緊急アラートをSlackに送信"""
        try:
            return self.email_service.send_slack_notification(message, urgent=True)
        except Exception as e:
            logger.error(f"Failed to send emergency alert: {str(e)}")
            return False

def main():
    """メイン処理：日次レポート生成"""
    logging.basicConfig(level=logging.INFO)

    fraud_service = FraudDetectionService()
    success = fraud_service.generate_daily_report()

    if success:
        print("Daily fraud report sent successfully")
    else:
        print("Failed to send daily fraud report")
        exit(1)

if __name__ == "__main__":
    main()