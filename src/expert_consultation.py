"""
専門家相談システム
30分14,300円の専門家相談サービス
円山動物病院方式での実装
"""

import time
import logging
from firebase_config import firebase_service
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class ExpertConsultationService:
    def __init__(self):
        self.consultation_fee = 14300  # 30分 14,300円
        self.consultation_duration = 30  # 分

    def create_consultation_request(self, user_id, user_email, user_name, notes=""):
        """専門家相談のリクエストを作成"""
        try:
            db = firebase_service.get_db()

            consultation_data = {
                'user_id': user_id,
                'user_email': user_email,
                'user_name': user_name,
                'notes': notes,
                'fee': self.consultation_fee,
                'duration': self.consultation_duration,
                'status': 'pending_payment',  # pending_payment, paid, scheduled, completed, cancelled
                'created_at': time.time(),
                'payment_completed_at': None,
                'scheduled_at': None,
                'calendly_event_uri': None,
                'calendly_booking_url': None,
                'consultation_completed_at': None
            }

            # Firestoreに相談リクエストを保存
            consultation_ref = db.collection('expert_consultations').add(consultation_data)
            consultation_id = consultation_ref[1].id

            logger.info(f"専門家相談リクエスト作成: {consultation_id} for user {user_id}")
            return consultation_id

        except Exception as e:
            logger.error(f"専門家相談リクエスト作成エラー: {e}")
            return None

    def get_consultation(self, consultation_id):
        """相談情報を取得"""
        try:
            db = firebase_service.get_db()
            consultation_ref = db.collection('expert_consultations').document(consultation_id)
            consultation_doc = consultation_ref.get()

            if consultation_doc.exists:
                consultation_data = consultation_doc.to_dict()
                consultation_data['id'] = consultation_id
                return consultation_data
            return None

        except Exception as e:
            logger.error(f"相談情報取得エラー: {e}")
            return None

    def update_consultation_payment(self, consultation_id, stripe_payment_intent_id):
        """決済完了時の相談情報更新"""
        try:
            db = firebase_service.get_db()
            consultation_ref = db.collection('expert_consultations').document(consultation_id)

            update_data = {
                'status': 'paid',
                'stripe_payment_intent_id': stripe_payment_intent_id,
                'payment_completed_at': time.time()
            }

            consultation_ref.update(update_data)
            logger.info(f"相談決済完了更新: {consultation_id}")
            return True

        except Exception as e:
            logger.error(f"相談決済更新エラー: {e}")
            return False

    def update_consultation_schedule(self, consultation_id, calendly_event_uri, scheduled_datetime):
        """Calendly予約完了時の相談情報更新"""
        try:
            db = firebase_service.get_db()
            consultation_ref = db.collection('expert_consultations').document(consultation_id)

            update_data = {
                'status': 'scheduled',
                'calendly_event_uri': calendly_event_uri,
                'scheduled_at': scheduled_datetime.timestamp() if scheduled_datetime else None,
                'scheduled_datetime_iso': scheduled_datetime.isoformat() if scheduled_datetime else None
            }

            consultation_ref.update(update_data)
            logger.info(f"相談予約完了更新: {consultation_id}")
            return True

        except Exception as e:
            logger.error(f"相談予約更新エラー: {e}")
            return False

    def complete_consultation(self, consultation_id, completion_notes=""):
        """相談完了時の更新"""
        try:
            db = firebase_service.get_db()
            consultation_ref = db.collection('expert_consultations').document(consultation_id)

            update_data = {
                'status': 'completed',
                'consultation_completed_at': time.time(),
                'completion_notes': completion_notes
            }

            consultation_ref.update(update_data)
            logger.info(f"相談完了更新: {consultation_id}")
            return True

        except Exception as e:
            logger.error(f"相談完了更新エラー: {e}")
            return False

    def get_user_consultations(self, user_id, limit=10):
        """ユーザーの相談履歴を取得"""
        try:
            db = firebase_service.get_db()
            consultations_ref = db.collection('expert_consultations') \
                .where('user_id', '==', user_id) \
                .order_by('created_at', direction='DESCENDING') \
                .limit(limit)

            consultations = []
            for doc in consultations_ref.stream():
                consultation_data = doc.to_dict()
                consultation_data['id'] = doc.id
                consultations.append(consultation_data)

            return consultations

        except Exception as e:
            logger.error(f"ユーザー相談履歴取得エラー: {e}")
            return []

    def get_all_consultations(self, status_filter=None, limit=50):
        """管理者用：全相談一覧を取得"""
        try:
            db = firebase_service.get_db()

            if status_filter:
                consultations_ref = db.collection('expert_consultations') \
                    .where('status', '==', status_filter) \
                    .order_by('created_at', direction='DESCENDING') \
                    .limit(limit)
            else:
                consultations_ref = db.collection('expert_consultations') \
                    .order_by('created_at', direction='DESCENDING') \
                    .limit(limit)

            consultations = []
            for doc in consultations_ref.stream():
                consultation_data = doc.to_dict()
                consultation_data['id'] = doc.id
                consultations.append(consultation_data)

            return consultations

        except Exception as e:
            logger.error(f"全相談一覧取得エラー: {e}")
            return []

    def can_user_book_consultation(self, user_id):
        """ユーザーが相談予約可能かチェック（認証済みユーザーは利用可能）"""
        try:
            logger.info(f"チェック開始 - user_id: {user_id}")
            db = firebase_service.get_db()
            logger.info(f"DB取得完了 - プロジェクト: {db.project}")

            # user_idフィールドで検索
            users_ref = db.collection('users').where('user_id', '==', user_id)
            user_docs = users_ref.get()
            logger.info(f"クエリ実行完了 - 件数: {len(user_docs)}")

            if not user_docs:
                logger.error(f"ユーザーが見つかりません: user_id={user_id}")
                return False, "ユーザー情報が見つかりません"

            user_doc = user_docs[0]  # 最初のドキュメント
            logger.info(f"ユーザー情報取得完了 - doc_id: {user_doc.id}")

            if False:  # この条件は不要になった
                logger.error(f"ユーザードキュメントが存在しません: users/{user_id}")
                return False, "ユーザー情報が見つかりません"

            logger.info(f"ユーザー情報確認完了 - user_id: {user_id}")
            # 認証済みユーザーは全員相談予約可能（trialユーザー含む）
            return True, "相談予約が可能です"

        except Exception as e:
            logger.error(f"相談予約可能性チェックエラー: {e}")
            return False, "システムエラーが発生しました"

    def create_temp_reservation(self, user_id, datetime_str, timezone="Asia/Tokyo"):
        """仮予約を作成（15分間キープ）"""
        try:
            import uuid
            from datetime import datetime, timezone as tz, timedelta

            db = firebase_service.get_db()

            # 仮予約IDを生成
            temp_reservation_id = f"temp_{str(uuid.uuid4())[:8]}"

            # 15分後の期限を計算
            now = datetime.now(tz.utc)
            expires_at = now + timedelta(minutes=15)

            # 仮予約データ
            temp_reservation_data = {
                'temp_reservation_id': temp_reservation_id,
                'user_id': user_id,
                'datetime': datetime_str,
                'timezone': timezone,
                'created_at': now.timestamp(),
                'expires_at': expires_at.timestamp(),
                'status': 'pending',
                'consultation_id': None,  # 決済時に設定
                'stripe_session_id': None  # 決済時に設定
            }

            # Firestoreに保存
            db.collection('temp_reservations').document(temp_reservation_id).set(temp_reservation_data)

            logger.info(f"仮予約作成: {temp_reservation_id} for user {user_id} at {datetime_str}")

            return {
                'success': True,
                'temp_reservation_id': temp_reservation_id,
                'expires_at': expires_at.isoformat(),
                'expires_timestamp': expires_at.timestamp()
            }

        except Exception as e:
            logger.error(f"仮予約作成エラー: {e}")
            return {'success': False, 'error': str(e)}

    def get_temp_reservation(self, temp_reservation_id):
        """仮予約情報を取得"""
        try:
            db = firebase_service.get_db()
            temp_reservation_ref = db.collection('temp_reservations').document(temp_reservation_id)
            temp_reservation_doc = temp_reservation_ref.get()

            if temp_reservation_doc.exists:
                return temp_reservation_doc.to_dict()
            return None

        except Exception as e:
            logger.error(f"仮予約取得エラー: {e}")
            return None

    def is_temp_reservation_valid(self, temp_reservation_id):
        """仮予約が有効か確認（期限切れチェック）"""
        try:
            temp_reservation = self.get_temp_reservation(temp_reservation_id)
            if not temp_reservation:
                return False

            import time
            current_time = time.time()
            expires_at = temp_reservation.get('expires_at', 0)

            return current_time < expires_at and temp_reservation.get('status') == 'pending'

        except Exception as e:
            logger.error(f"仮予約有効性チェックエラー: {e}")
            return False

    def convert_temp_to_consultation(self, temp_reservation_id, consultation_id):
        """仮予約を正式な相談に変換"""
        try:
            db = firebase_service.get_db()

            # 仮予約情報を取得
            temp_reservation = self.get_temp_reservation(temp_reservation_id)
            if not temp_reservation:
                logger.error(f"仮予約が見つかりません: {temp_reservation_id}")
                return False

            # expert_consultationsに仮予約情報を紐付け
            consultation_ref = db.collection('expert_consultations').document(consultation_id)
            consultation_ref.update({
                'temp_reservation_id': temp_reservation_id,
                'scheduled_datetime_iso': temp_reservation['datetime'],
                'scheduled_at': time.time()
            })

            # 仮予約のステータスを更新
            temp_reservation_ref = db.collection('temp_reservations').document(temp_reservation_id)
            temp_reservation_ref.update({
                'consultation_id': consultation_id,
                'status': 'converted'
            })

            logger.info(f"仮予約を相談に変換: {temp_reservation_id} -> {consultation_id}")
            return True

        except Exception as e:
            logger.error(f"仮予約変換エラー: {e}")
            return False

    def cleanup_expired_temp_reservations(self):
        """期限切れ仮予約を削除"""
        try:
            import time
            db = firebase_service.get_db()
            current_time = time.time()

            # 期限切れの仮予約を検索
            expired_reservations = db.collection('temp_reservations') \
                .where('expires_at', '<', current_time) \
                .where('status', '==', 'pending') \
                .get()

            deleted_count = 0
            for doc in expired_reservations:
                doc.reference.delete()
                deleted_count += 1

            if deleted_count > 0:
                logger.info(f"期限切れ仮予約を削除: {deleted_count}件")

            return deleted_count

        except Exception as e:
            logger.error(f"期限切れ仮予約削除エラー: {e}")
            return 0

# グローバルインスタンス
expert_consultation_service = ExpertConsultationService()