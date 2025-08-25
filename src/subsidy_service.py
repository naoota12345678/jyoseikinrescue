"""
助成金メモ・スケジュール管理のサービスクラス
"""
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import logging
from firebase_admin import firestore
from models.subsidy_memo import SubsidyMemo, ApplicationPhase, Document, ChatHistory, TempDiagnosis

logger = logging.getLogger(__name__)

class SubsidyService:
    def __init__(self, db):
        self.db = db
    
    # === 助成金メモ関連 ===
    
    def create_subsidy_memo(self, user_id: str, memo_data: Dict) -> SubsidyMemo:
        """新規助成金メモを作成"""
        try:
            memo_id = str(uuid.uuid4())
            
            # デフォルト値を設定
            plan_app_data = memo_data.get('plan_application', {})
            payment_app_data = memo_data.get('payment_application', {})
            
            plan_app = ApplicationPhase(
                required=plan_app_data.get('required', False),
                deadline=plan_app_data.get('deadline'),
                documents=[Document(**doc) for doc in plan_app_data.get('documents', [])],
                memo=plan_app_data.get('memo', '')
            )
            
            payment_app = ApplicationPhase(
                required=payment_app_data.get('required', True),
                deadline=payment_app_data.get('deadline'),
                documents=[Document(**doc) for doc in payment_app_data.get('documents', [])],
                memo=payment_app_data.get('memo', '')
            )
            
            memo = SubsidyMemo(
                id=memo_id,
                user_id=user_id,
                name=memo_data['name'],
                target_person=memo_data.get('target_person', ''),
                plan_application=plan_app,
                payment_application=payment_app,
                chat_history=[],
                source=memo_data.get('source', 'manual')
            )
            
            # Firestoreに保存
            doc_ref = self.db.collection('users').document(user_id).collection('subsidies').document(memo_id)
            doc_ref.set(memo.to_dict())
            
            logger.info(f"Created subsidy memo: {memo_id} for user: {user_id}")
            return memo
            
        except Exception as e:
            logger.error(f"Error creating subsidy memo: {str(e)}")
            raise
    
    def get_user_subsidies(self, user_id: str) -> List[SubsidyMemo]:
        """ユーザーの全助成金メモを取得"""
        try:
            subsidies = []
            docs = self.db.collection('users').document(user_id).collection('subsidies').stream()
            
            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id
                subsidies.append(SubsidyMemo.from_dict(data))
            
            # 更新日時でソート（新しい順）
            subsidies.sort(key=lambda x: x.updated_at, reverse=True)
            
            return subsidies
            
        except Exception as e:
            logger.error(f"Error fetching subsidies: {str(e)}")
            return []
    
    def get_subsidy_by_id(self, user_id: str, subsidy_id: str) -> Optional[SubsidyMemo]:
        """特定の助成金メモを取得"""
        try:
            doc = self.db.collection('users').document(user_id).collection('subsidies').document(subsidy_id).get()
            
            if doc.exists:
                data = doc.to_dict()
                data['id'] = doc.id
                return SubsidyMemo.from_dict(data)
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching subsidy: {str(e)}")
            return None
    
    def update_subsidy_memo(self, user_id: str, subsidy_id: str, updates: Dict) -> bool:
        """助成金メモを更新"""
        try:
            doc_ref = self.db.collection('users').document(user_id).collection('subsidies').document(subsidy_id)
            
            # 更新日時を追加
            updates['updated_at'] = datetime.now().isoformat()
            
            doc_ref.update(updates)
            logger.info(f"Updated subsidy memo: {subsidy_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating subsidy: {str(e)}")
            return False
    
    def update_document_status(self, user_id: str, subsidy_id: str, phase: str, doc_index: int, completed: bool) -> bool:
        """書類の完了状態を更新"""
        try:
            # 現在のデータを取得
            memo = self.get_subsidy_by_id(user_id, subsidy_id)
            if not memo:
                return False
            
            # 該当する書類の状態を更新
            if phase == 'plan':
                if doc_index < len(memo.plan_application.documents):
                    memo.plan_application.documents[doc_index].completed = completed
            elif phase == 'payment':
                if doc_index < len(memo.payment_application.documents):
                    memo.payment_application.documents[doc_index].completed = completed
            else:
                return False
            
            # Firestoreに保存
            doc_ref = self.db.collection('users').document(user_id).collection('subsidies').document(subsidy_id)
            doc_ref.update({
                f'{phase}_application.documents': [doc.to_dict() for doc in 
                    (memo.plan_application.documents if phase == 'plan' else memo.payment_application.documents)],
                'updated_at': datetime.now().isoformat()
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating document status: {str(e)}")
            return False
    
    def add_chat_history(self, user_id: str, subsidy_id: str, content: str) -> bool:
        """チャット履歴を追加"""
        try:
            chat_entry = ChatHistory(
                date=datetime.now(),
                content=content
            )
            
            doc_ref = self.db.collection('users').document(user_id).collection('subsidies').document(subsidy_id)
            doc_ref.update({
                'chat_history': firestore.ArrayUnion([chat_entry.to_dict()]),
                'updated_at': datetime.now().isoformat()
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Error adding chat history: {str(e)}")
            return False
    
    def delete_subsidy_memo(self, user_id: str, subsidy_id: str) -> bool:
        """助成金メモを削除"""
        try:
            self.db.collection('users').document(user_id).collection('subsidies').document(subsidy_id).delete()
            logger.info(f"Deleted subsidy memo: {subsidy_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting subsidy: {str(e)}")
            return False
    
    # === 一時診断結果関連 ===
    
    def save_temp_diagnosis(self, result: Dict) -> str:
        """無料診断結果を一時保存"""
        try:
            session_id = str(uuid.uuid4())
            
            temp_diagnosis = TempDiagnosis(
                session_id=session_id,
                result=result,
                timestamp=datetime.now(),
                expires_at=datetime.now() + timedelta(hours=24)
            )
            
            # Firestoreに保存（24時間後に自動削除するように設定）
            doc_ref = self.db.collection('temp_diagnosis').document(session_id)
            doc_ref.set(temp_diagnosis.to_dict())
            
            logger.info(f"Saved temp diagnosis: {session_id}")
            return session_id
            
        except Exception as e:
            logger.error(f"Error saving temp diagnosis: {str(e)}")
            raise
    
    def get_temp_diagnosis(self, session_id: str) -> Optional[Dict]:
        """一時保存された診断結果を取得"""
        try:
            doc = self.db.collection('temp_diagnosis').document(session_id).get()
            
            if doc.exists:
                data = doc.to_dict()
                # 有効期限チェック
                expires_at = datetime.fromisoformat(data['expires_at'])
                if expires_at > datetime.now():
                    return data['result']
                else:
                    # 期限切れの場合は削除
                    doc.reference.delete()
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching temp diagnosis: {str(e)}")
            return None
    
    def convert_temp_to_memo(self, session_id: str, user_id: str) -> Optional[SubsidyMemo]:
        """一時診断結果を正式なメモに変換"""
        try:
            # 一時診断結果を取得
            temp_result = self.get_temp_diagnosis(session_id)
            if not temp_result:
                return None
            
            # メモデータを構築
            memo_data = {
                'name': temp_result.get('subsidy_name', ''),
                'target_person': temp_result.get('target', ''),
                'plan_application': {
                    'required': temp_result.get('plan_required', False),
                    'deadline': temp_result.get('plan_deadline'),
                    'documents': [{'name': doc, 'completed': False} 
                                for doc in temp_result.get('plan_documents', [])],
                    'memo': temp_result.get('plan_memo', '')
                },
                'payment_application': {
                    'required': True,
                    'deadline': temp_result.get('payment_deadline'),
                    'documents': [{'name': doc, 'completed': False} 
                                for doc in temp_result.get('payment_documents', [])],
                    'memo': temp_result.get('payment_memo', '')
                },
                'source': 'free_diagnosis'
            }
            
            # メモを作成
            memo = self.create_subsidy_memo(user_id, memo_data)
            
            # 一時診断結果を削除
            self.db.collection('temp_diagnosis').document(session_id).delete()
            
            return memo
            
        except Exception as e:
            logger.error(f"Error converting temp to memo: {str(e)}")
            return None
    
    # === 検索・フィルタ関連 ===
    
    def search_subsidies(self, user_id: str, keyword: str) -> List[SubsidyMemo]:
        """キーワードで助成金メモを検索"""
        try:
            all_subsidies = self.get_user_subsidies(user_id)
            
            # キーワードが空の場合は全件返す
            if not keyword:
                return all_subsidies
            
            keyword_lower = keyword.lower()
            filtered = []
            
            for subsidy in all_subsidies:
                # 助成金名、対象者、メモで検索
                if (keyword_lower in subsidy.name.lower() or
                    keyword_lower in subsidy.target_person.lower() or
                    keyword_lower in subsidy.plan_application.memo.lower() or
                    keyword_lower in subsidy.payment_application.memo.lower()):
                    filtered.append(subsidy)
            
            return filtered
            
        except Exception as e:
            logger.error(f"Error searching subsidies: {str(e)}")
            return []
    
    def get_upcoming_deadlines(self, user_id: str, days: int = 30) -> List[Dict]:
        """期限が近い助成金を取得"""
        try:
            subsidies = self.get_user_subsidies(user_id)
            upcoming = []
            cutoff_date = datetime.now() + timedelta(days=days)
            
            for subsidy in subsidies:
                # 計画申請の期限チェック
                if subsidy.plan_application.required and subsidy.plan_application.deadline:
                    deadline_date = datetime.fromisoformat(subsidy.plan_application.deadline)
                    if datetime.now() <= deadline_date <= cutoff_date:
                        upcoming.append({
                            'subsidy_id': subsidy.id,
                            'subsidy_name': subsidy.name,
                            'phase': '計画申請',
                            'deadline': subsidy.plan_application.deadline,
                            'days_remaining': (deadline_date - datetime.now()).days
                        })
                
                # 支給申請の期限チェック
                if subsidy.payment_application.deadline:
                    deadline_date = datetime.fromisoformat(subsidy.payment_application.deadline)
                    if datetime.now() <= deadline_date <= cutoff_date:
                        upcoming.append({
                            'subsidy_id': subsidy.id,
                            'subsidy_name': subsidy.name,
                            'phase': '支給申請',
                            'deadline': subsidy.payment_application.deadline,
                            'days_remaining': (deadline_date - datetime.now()).days
                        })
            
            # 期限が近い順にソート
            upcoming.sort(key=lambda x: x['days_remaining'])
            
            return upcoming
            
        except Exception as e:
            logger.error(f"Error getting upcoming deadlines: {str(e)}")
            return []