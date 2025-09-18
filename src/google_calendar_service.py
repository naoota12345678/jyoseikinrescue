"""
Google Calendar & Meet統合サービス
専門家相談の予約管理
"""

import os
import logging
from datetime import datetime, timedelta
from firebase_config import firebase_service

logger = logging.getLogger(__name__)

class GoogleCalendarService:
    def __init__(self):
        # Google Calendar API設定
        self.calendar_id = os.environ.get('GOOGLE_CALENDAR_ID', 'primary')

        # 営業時間設定（平日9:00-18:00）
        self.business_hours = {
            'start_hour': 9,
            'end_hour': 18,
            'weekdays': [0, 1, 2, 3, 4]  # 月-金
        }

    def generate_time_slots(self, date_str, duration_minutes=30):
        """
        指定日の利用可能な時間枠を生成
        """
        try:
            from datetime import datetime, timedelta

            target_date = datetime.strptime(date_str, '%Y-%m-%d')

            # 営業日チェック
            if target_date.weekday() not in self.business_hours['weekdays']:
                return []

            # 過去日チェック
            if target_date.date() <= datetime.now().date():
                return []

            # 時間枠生成
            slots = []
            start_time = target_date.replace(
                hour=self.business_hours['start_hour'],
                minute=0,
                second=0,
                microsecond=0
            )

            while start_time.hour < self.business_hours['end_hour']:
                end_time = start_time + timedelta(minutes=duration_minutes)

                # 営業時間内チェック
                if end_time.hour <= self.business_hours['end_hour']:
                    slots.append({
                        'start_time': start_time.isoformat(),
                        'end_time': end_time.isoformat(),
                        'display_time': start_time.strftime('%H:%M'),
                        'available': True  # 実際にはGoogle Calendar APIで予約済みチェック
                    })

                start_time += timedelta(minutes=duration_minutes)

            return slots

        except Exception as e:
            logger.error(f"時間枠生成エラー: {e}")
            return []

    def create_consultation_event(self, consultation_id, user_name, user_email,
                                start_datetime, duration_minutes=30):
        """
        専門家相談のGoogle Calendarイベントを作成
        """
        try:
            from datetime import datetime, timedelta

            # 現在はシンプルな実装（実際のGoogle Calendar API統合は後で実装）
            end_datetime = start_datetime + timedelta(minutes=duration_minutes)

            # Meet URLを生成（実際にはGoogle Calendar APIで自動生成）
            meet_url = f"https://meet.google.com/lookup/{consultation_id[:10]}"

            event_data = {
                'consultation_id': consultation_id,
                'title': f'助成金専門家相談 - {user_name}様',
                'start_time': start_datetime.isoformat(),
                'end_time': end_datetime.isoformat(),
                'user_name': user_name,
                'user_email': user_email,
                'meet_url': meet_url,
                'description': f'''
助成金専門家相談（30分）

【相談者情報】
名前: {user_name}
メール: {user_email}
相談ID: {consultation_id}

【Google Meet参加URL】
{meet_url}

【注意事項】
- 開始時刻の5分前からMeetに参加可能です
- 相談時間は30分間です
- 録画は行いませんが、必要に応じてメモを取らせていただきます
                '''.strip(),
                'created_at': datetime.now().isoformat()
            }

            # Firestoreに保存
            db = firebase_service.get_db()
            event_ref = db.collection('calendar_events').document(consultation_id)
            event_ref.set(event_data)

            logger.info(f"相談イベント作成: {consultation_id}")
            return event_data

        except Exception as e:
            logger.error(f"相談イベント作成エラー: {e}")
            return None

    def get_available_dates(self, days_ahead=14):
        """
        利用可能な日付リストを取得
        """
        try:
            from datetime import datetime, timedelta

            available_dates = []
            current_date = datetime.now().date() + timedelta(days=1)  # 明日から

            for i in range(days_ahead):
                check_date = current_date + timedelta(days=i)

                # 営業日のみ
                if check_date.weekday() in self.business_hours['weekdays']:
                    available_dates.append({
                        'date': check_date.strftime('%Y-%m-%d'),
                        'display_date': check_date.strftime('%m月%d日 (%a)'),
                        'weekday': check_date.weekday()
                    })

            return available_dates

        except Exception as e:
            logger.error(f"利用可能日取得エラー: {e}")
            return []

    def book_consultation_slot(self, consultation_id, user_name, user_email,
                             date_str, time_str):
        """
        相談枠を予約
        """
        try:
            # 日時パース
            datetime_str = f"{date_str} {time_str}"
            start_datetime = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')

            # イベント作成
            event_data = self.create_consultation_event(
                consultation_id=consultation_id,
                user_name=user_name,
                user_email=user_email,
                start_datetime=start_datetime
            )

            if event_data:
                return {
                    'success': True,
                    'event_data': event_data,
                    'meet_url': event_data['meet_url'],
                    'start_time': event_data['start_time']
                }
            else:
                return {'success': False, 'error': 'イベント作成に失敗しました'}

        except Exception as e:
            logger.error(f"相談枠予約エラー: {e}")
            return {'success': False, 'error': str(e)}

    def get_consultation_event(self, consultation_id):
        """
        相談イベント情報を取得
        """
        try:
            db = firebase_service.get_db()
            event_ref = db.collection('calendar_events').document(consultation_id)
            event_doc = event_ref.get()

            if event_doc.exists:
                return event_doc.to_dict()
            return None

        except Exception as e:
            logger.error(f"相談イベント取得エラー: {e}")
            return None

    def cancel_consultation_event(self, consultation_id):
        """
        相談イベントをキャンセル
        """
        try:
            db = firebase_service.get_db()
            event_ref = db.collection('calendar_events').document(consultation_id)

            # キャンセル状態に更新
            event_ref.update({
                'status': 'cancelled',
                'cancelled_at': datetime.now().isoformat()
            })

            logger.info(f"相談イベントキャンセル: {consultation_id}")
            return True

        except Exception as e:
            logger.error(f"相談イベントキャンセルエラー: {e}")
            return False

    def send_consultation_reminder(self, consultation_id):
        """
        相談リマインダーメール送信
        """
        try:
            event_data = self.get_consultation_event(consultation_id)
            if not event_data:
                return False

            # 実際のメール送信はここで実装
            # 現在はログ出力のみ
            logger.info(f"リマインダー送信: {consultation_id} to {event_data['user_email']}")
            return True

        except Exception as e:
            logger.error(f"リマインダー送信エラー: {e}")
            return False

# グローバルインスタンス
google_calendar_service = GoogleCalendarService()