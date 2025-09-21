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
            db = firebase_service.get_db()
            user_ref = db.collection('users').document(user_id)
            user_doc = user_ref.get()

            if not user_doc.exists:
                return False, "ユーザー情報が見つかりません"

            # 認証済みユーザーは全員相談予約可能（trialユーザー含む）
            return True, "相談予約が可能です"

        except Exception as e:
            logger.error(f"相談予約可能性チェックエラー: {e}")
            return False, "システムエラーが発生しました"

# グローバルインスタンス
expert_consultation_service = ExpertConsultationService()