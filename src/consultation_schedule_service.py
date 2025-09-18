"""
専門家相談スケジュール管理サービス
営業時間、休日、予約不可時間の管理
"""

import time
import logging
from datetime import datetime, timedelta, date
from firebase_config import firebase_service

logger = logging.getLogger(__name__)

class ConsultationScheduleService:
    def __init__(self):
        self.db = firebase_service.get_db()
        self.default_business_hours = {
            'monday': {'enabled': True, 'start': '09:00', 'end': '18:00'},
            'tuesday': {'enabled': True, 'start': '09:00', 'end': '18:00'},
            'wednesday': {'enabled': True, 'start': '09:00', 'end': '18:00'},
            'thursday': {'enabled': True, 'start': '09:00', 'end': '18:00'},
            'friday': {'enabled': True, 'start': '09:00', 'end': '18:00'},
            'saturday': {'enabled': False, 'start': '09:00', 'end': '18:00'},
            'sunday': {'enabled': False, 'start': '09:00', 'end': '18:00'}
        }

    def get_business_hours(self):
        """営業時間設定を取得"""
        try:
            doc_ref = self.db.collection('consultation_settings').document('business_hours')
            doc = doc_ref.get()

            if doc.exists:
                return doc.to_dict()
            else:
                # デフォルト設定を保存
                self.save_business_hours(self.default_business_hours)
                return self.default_business_hours

        except Exception as e:
            logger.error(f"営業時間取得エラー: {e}")
            return self.default_business_hours

    def save_business_hours(self, business_hours):
        """営業時間設定を保存"""
        try:
            doc_ref = self.db.collection('consultation_settings').document('business_hours')
            doc_ref.set(business_hours)
            logger.info("営業時間設定を保存しました")
            return True

        except Exception as e:
            logger.error(f"営業時間保存エラー: {e}")
            return False

    def get_blocked_dates(self):
        """予約不可日（休日）を取得"""
        try:
            blocked_dates_ref = self.db.collection('consultation_settings').document('blocked_dates')
            doc = blocked_dates_ref.get()

            if doc.exists:
                data = doc.to_dict()
                return data.get('dates', [])
            return []

        except Exception as e:
            logger.error(f"休日取得エラー: {e}")
            return []

    def add_blocked_date(self, date_str, reason=""):
        """予約不可日を追加"""
        try:
            blocked_dates = self.get_blocked_dates()

            # 重複チェック
            for blocked_date in blocked_dates:
                if blocked_date['date'] == date_str:
                    return False, "既に登録済みの日付です"

            blocked_dates.append({
                'date': date_str,
                'reason': reason,
                'created_at': time.time()
            })

            doc_ref = self.db.collection('consultation_settings').document('blocked_dates')
            doc_ref.set({'dates': blocked_dates})

            logger.info(f"休日追加: {date_str}")
            return True, "休日を追加しました"

        except Exception as e:
            logger.error(f"休日追加エラー: {e}")
            return False, "休日の追加に失敗しました"

    def remove_blocked_date(self, date_str):
        """予約不可日を削除"""
        try:
            blocked_dates = self.get_blocked_dates()

            # 該当日付を削除
            blocked_dates = [bd for bd in blocked_dates if bd['date'] != date_str]

            doc_ref = self.db.collection('consultation_settings').document('blocked_dates')
            doc_ref.set({'dates': blocked_dates})

            logger.info(f"休日削除: {date_str}")
            return True, "休日を削除しました"

        except Exception as e:
            logger.error(f"休日削除エラー: {e}")
            return False, "休日の削除に失敗しました"

    def get_blocked_time_slots(self, date_str):
        """特定日の予約不可時間枠を取得"""
        try:
            time_slots_ref = self.db.collection('consultation_settings').document('blocked_time_slots')
            doc = time_slots_ref.get()

            if doc.exists:
                data = doc.to_dict()
                date_slots = data.get('dates', {})
                return date_slots.get(date_str, [])
            return []

        except Exception as e:
            logger.error(f"予約不可時間枠取得エラー: {e}")
            return []

    def add_blocked_time_slot(self, date_str, start_time, end_time, reason=""):
        """特定日時の予約不可時間枠を追加"""
        try:
            doc_ref = self.db.collection('consultation_settings').document('blocked_time_slots')
            doc = doc_ref.get()

            if doc.exists:
                data = doc.to_dict()
            else:
                data = {'dates': {}}

            if date_str not in data['dates']:
                data['dates'][date_str] = []

            data['dates'][date_str].append({
                'start_time': start_time,
                'end_time': end_time,
                'reason': reason,
                'created_at': time.time()
            })

            doc_ref.set(data)
            logger.info(f"予約不可時間追加: {date_str} {start_time}-{end_time}")
            return True, "予約不可時間を追加しました"

        except Exception as e:
            logger.error(f"予約不可時間追加エラー: {e}")
            return False, "予約不可時間の追加に失敗しました"

    def remove_blocked_time_slot(self, date_str, start_time, end_time):
        """特定日時の予約不可時間枠を削除"""
        try:
            doc_ref = self.db.collection('consultation_settings').document('blocked_time_slots')
            doc = doc_ref.get()

            if not doc.exists:
                return False, "該当する予約不可時間が見つかりません"

            data = doc.to_dict()

            if date_str not in data['dates']:
                return False, "該当する日付が見つかりません"

            # 該当時間枠を削除
            data['dates'][date_str] = [
                slot for slot in data['dates'][date_str]
                if not (slot['start_time'] == start_time and slot['end_time'] == end_time)
            ]

            # 空の配列の場合は日付ごと削除
            if not data['dates'][date_str]:
                del data['dates'][date_str]

            doc_ref.set(data)
            logger.info(f"予約不可時間削除: {date_str} {start_time}-{end_time}")
            return True, "予約不可時間を削除しました"

        except Exception as e:
            logger.error(f"予約不可時間削除エラー: {e}")
            return False, "予約不可時間の削除に失敗しました"

    def is_date_available(self, date_str):
        """指定日が予約可能かチェック"""
        try:
            # 曜日チェック
            target_date = datetime.strptime(date_str, '%Y-%m-%d')
            weekday_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            weekday_name = weekday_names[target_date.weekday()]

            business_hours = self.get_business_hours()
            if not business_hours.get(weekday_name, {}).get('enabled', False):
                return False, "営業日ではありません"

            # 休日チェック
            blocked_dates = self.get_blocked_dates()
            for blocked_date in blocked_dates:
                if blocked_date['date'] == date_str:
                    reason = blocked_date.get('reason', '休日')
                    return False, f"予約不可日です: {reason}"

            return True, "予約可能です"

        except Exception as e:
            logger.error(f"日付可用性チェックエラー: {e}")
            return False, "システムエラーが発生しました"

    def is_time_slot_available(self, date_str, start_time, end_time):
        """指定時間枠が予約可能かチェック"""
        try:
            # 日付チェック
            date_available, message = self.is_date_available(date_str)
            if not date_available:
                return False, message

            # 営業時間チェック
            target_date = datetime.strptime(date_str, '%Y-%m-%d')
            weekday_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            weekday_name = weekday_names[target_date.weekday()]

            business_hours = self.get_business_hours()
            day_hours = business_hours.get(weekday_name, {})

            if start_time < day_hours.get('start', '09:00') or end_time > day_hours.get('end', '18:00'):
                return False, "営業時間外です"

            # 予約不可時間枠チェック
            blocked_slots = self.get_blocked_time_slots(date_str)

            start_datetime = datetime.strptime(f"{date_str} {start_time}", '%Y-%m-%d %H:%M')
            end_datetime = datetime.strptime(f"{date_str} {end_time}", '%Y-%m-%d %H:%M')

            for blocked_slot in blocked_slots:
                blocked_start = datetime.strptime(f"{date_str} {blocked_slot['start_time']}", '%Y-%m-%d %H:%M')
                blocked_end = datetime.strptime(f"{date_str} {blocked_slot['end_time']}", '%Y-%m-%d %H:%M')

                # 時間重複チェック
                if (start_datetime < blocked_end and end_datetime > blocked_start):
                    reason = blocked_slot.get('reason', '予約不可')
                    return False, f"予約不可時間です: {reason}"

            return True, "予約可能です"

        except Exception as e:
            logger.error(f"時間枠可用性チェックエラー: {e}")
            return False, "システムエラーが発生しました"

    def get_schedule_summary(self, days_ahead=30):
        """スケジュール概要を取得（管理者ダッシュボード用）"""
        try:
            business_hours = self.get_business_hours()
            blocked_dates = self.get_blocked_dates()

            # 今後N日間の情報を生成
            today = date.today()
            summary = {
                'business_hours': business_hours,
                'total_blocked_dates': len(blocked_dates),
                'upcoming_blocked_dates': [],
                'settings_updated_at': time.time()
            }

            # 今後の休日をフィルタ
            for blocked_date in blocked_dates:
                blocked_date_obj = datetime.strptime(blocked_date['date'], '%Y-%m-%d').date()
                if blocked_date_obj >= today and blocked_date_obj <= today + timedelta(days=days_ahead):
                    summary['upcoming_blocked_dates'].append(blocked_date)

            return summary

        except Exception as e:
            logger.error(f"スケジュール概要取得エラー: {e}")
            return None

# グローバルインスタンス
consultation_schedule_service = ConsultationScheduleService()