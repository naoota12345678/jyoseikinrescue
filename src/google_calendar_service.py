"""
Google Calendar & Meet統合サービス
専門家相談の予約管理
"""

import os
import logging
from datetime import datetime, timedelta
from firebase_config import firebase_service

# Google Calendar API
try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    import json
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False

# スケジュール管理サービス
try:
    from consultation_schedule_service import consultation_schedule_service
    SCHEDULE_SERVICE_AVAILABLE = True
except ImportError:
    SCHEDULE_SERVICE_AVAILABLE = False

logger = logging.getLogger(__name__)

class GoogleCalendarService:
    def __init__(self):
        # Google Calendar API設定
        self.calendar_id = os.environ.get('GOOGLE_CALENDAR_ID', 'primary')
        self.google_service = None

        # Google Calendar API初期化
        if GOOGLE_API_AVAILABLE:
            try:
                self._initialize_google_api()
            except Exception as e:
                logger.warning(f"Google Calendar API初期化失敗: {e}")

        # スケジュール管理サービス連携
        self.schedule_service = consultation_schedule_service if SCHEDULE_SERVICE_AVAILABLE else None

    def _initialize_google_api(self):
        """Google Calendar API初期化"""
        try:
            # サービスアカウントキーの設定
            service_account_info = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')

            if service_account_info:
                # JSON文字列から辞書に変換
                if isinstance(service_account_info, str):
                    service_account_info = json.loads(service_account_info)

                # 認証情報作成
                credentials = Credentials.from_service_account_info(
                    service_account_info,
                    scopes=['https://www.googleapis.com/auth/calendar']
                )

                # Google Calendar APIサービス構築
                self.google_service = build('calendar', 'v3', credentials=credentials)
                logger.info("Google Calendar API初期化成功")

            else:
                logger.warning("GOOGLE_SERVICE_ACCOUNT_JSON環境変数が設定されていません")

        except Exception as e:
            logger.error(f"Google Calendar API初期化エラー: {e}")
            self.google_service = None

    def is_google_api_enabled(self):
        """Google Calendar API が利用可能かチェック"""
        return self.google_service is not None

    def generate_time_slots(self, date_str, duration_minutes=30):
        """
        指定日の利用可能な時間枠を生成（スケジュール管理サービス連携）
        """
        try:
            from datetime import datetime, timedelta

            target_date = datetime.strptime(date_str, '%Y-%m-%d')

            # 過去日チェック
            if target_date.date() <= datetime.now().date():
                return []

            # スケジュール管理サービスでの日付チェック
            if self.schedule_service:
                date_available, message = self.schedule_service.is_date_available(date_str)
                if not date_available:
                    logger.info(f"日付利用不可: {date_str} - {message}")
                    return []

                # 営業時間を取得
                business_hours = self.schedule_service.get_business_hours()
                weekday_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
                weekday_name = weekday_names[target_date.weekday()]
                day_hours = business_hours.get(weekday_name, {})

                if not day_hours.get('enabled', False):
                    return []

                start_hour_str = day_hours.get('start', '09:00')
                end_hour_str = day_hours.get('end', '18:00')

            else:
                # フォールバック: デフォルト営業時間
                weekdays = [0, 1, 2, 3, 4]  # 月-金
                if target_date.weekday() not in weekdays:
                    return []
                start_hour_str = '09:00'
                end_hour_str = '18:00'

            # 時間枠生成
            slots = []
            start_hour, start_minute = map(int, start_hour_str.split(':'))
            end_hour, end_minute = map(int, end_hour_str.split(':'))

            start_time = target_date.replace(
                hour=start_hour,
                minute=start_minute,
                second=0,
                microsecond=0
            )

            end_time_limit = target_date.replace(
                hour=end_hour,
                minute=end_minute,
                second=0,
                microsecond=0
            )

            while start_time < end_time_limit:
                slot_end_time = start_time + timedelta(minutes=duration_minutes)

                # 営業時間内チェック
                if slot_end_time <= end_time_limit:
                    start_time_str = start_time.strftime('%H:%M')
                    end_time_str = slot_end_time.strftime('%H:%M')

                    # スケジュール管理サービスでの時間枠チェック
                    available = True
                    if self.schedule_service:
                        available, message = self.schedule_service.is_time_slot_available(
                            date_str, start_time_str, end_time_str
                        )

                    slots.append({
                        'start_time': start_time.isoformat(),
                        'end_time': slot_end_time.isoformat(),
                        'display_time': start_time_str,
                        'available': available
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

            end_datetime = start_datetime + timedelta(minutes=duration_minutes)

            # Google Calendar APIが利用可能な場合は実際にイベントを作成
            if self.is_google_api_enabled():
                try:
                    event_data = self._create_real_calendar_event(
                        consultation_id, user_name, user_email,
                        start_datetime, end_datetime
                    )
                    if event_data:
                        return event_data
                except Exception as e:
                    logger.error(f"Google Calendar API実行エラー: {e}")

            # フォールバック: シンプルな実装
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
                'created_at': datetime.now().isoformat(),
                'api_created': False  # フォールバック作成フラグ
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

    def _create_real_calendar_event(self, consultation_id, user_name, user_email,
                                  start_datetime, end_datetime):
        """
        Google Calendar APIを使用して実際のイベントを作成
        """
        try:
            event = {
                'summary': f'助成金専門家相談 - {user_name}様',
                'description': f'''
助成金専門家相談（30分）

【相談者情報】
名前: {user_name}
メール: {user_email}
相談ID: {consultation_id}

【注意事項】
- 開始時刻の5分前からMeetに参加可能です
- 相談時間は30分間です
- 録画は行いませんが、必要に応じてメモを取らせていただきます
                '''.strip(),
                'start': {
                    'dateTime': start_datetime.isoformat(),
                    'timeZone': 'Asia/Tokyo',
                },
                'end': {
                    'dateTime': end_datetime.isoformat(),
                    'timeZone': 'Asia/Tokyo',
                },
                'attendees': [
                    {'email': user_email},
                    # {'email': 'expert@jyoseikin.jp'},  # 専門家のメール
                ],
                'conferenceData': {
                    'createRequest': {
                        'requestId': f'meet-{consultation_id}',
                        'conferenceSolutionKey': {
                            'type': 'hangoutsMeet'
                        }
                    }
                },
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 24 * 60},  # 前日
                        {'method': 'email', 'minutes': 60},  # 1時間前
                        {'method': 'popup', 'minutes': 15},  # 15分前
                    ],
                },
            }

            # イベントを作成（conferenceDataRequestId付きで）
            created_event = self.google_service.events().insert(
                calendarId=self.calendar_id,
                body=event,
                conferenceDataVersion=1
            ).execute()

            # Meet URLを取得
            meet_url = None
            if 'conferenceData' in created_event:
                meet_url = created_event['conferenceData'].get('entryPoints', [{}])[0].get('uri')

            event_data = {
                'consultation_id': consultation_id,
                'title': created_event['summary'],
                'start_time': start_datetime.isoformat(),
                'end_time': end_datetime.isoformat(),
                'user_name': user_name,
                'user_email': user_email,
                'meet_url': meet_url or f"https://meet.google.com/lookup/{consultation_id[:10]}",
                'google_event_id': created_event['id'],
                'google_event_link': created_event.get('htmlLink'),
                'description': event['description'],
                'created_at': datetime.now().isoformat(),
                'api_created': True  # API作成フラグ
            }

            # Firestoreに保存
            db = firebase_service.get_db()
            event_ref = db.collection('calendar_events').document(consultation_id)
            event_ref.set(event_data)

            logger.info(f"Google Calendar API経由でイベント作成: {consultation_id}, Meet URL: {meet_url}")
            return event_data

        except Exception as e:
            logger.error(f"Google Calendar API実行エラー: {e}")
            raise

    def get_available_dates(self, days_ahead=14):
        """
        利用可能な日付リストを取得（スケジュール管理サービス連携）
        """
        try:
            from datetime import datetime, timedelta

            available_dates = []
            current_date = datetime.now().date() + timedelta(days=1)  # 明日から

            # 営業時間設定を取得
            if self.schedule_service:
                business_hours = self.schedule_service.get_business_hours()
            else:
                business_hours = None

            for i in range(days_ahead):
                check_date = current_date + timedelta(days=i)
                date_str = check_date.strftime('%Y-%m-%d')

                # スケジュール管理サービスでの可用性チェック
                if self.schedule_service:
                    is_available, message = self.schedule_service.is_date_available(date_str)
                    if not is_available:
                        continue
                else:
                    # フォールバック: デフォルト営業日チェック（平日のみ）
                    if check_date.weekday() not in [0, 1, 2, 3, 4]:
                        continue

                # 曜日名を日本語で取得
                weekday_names_jp = ['月', '火', '水', '木', '金', '土', '日']
                weekday_jp = weekday_names_jp[check_date.weekday()]

                available_dates.append({
                    'date': date_str,
                    'display_date': check_date.strftime(f'%m月%d日 ({weekday_jp})'),
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