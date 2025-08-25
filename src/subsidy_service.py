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
            logger.info(f"SERVICE: Creating memo for user_id: '{user_id}'")
            logger.info(f"SERVICE: user_id type: {type(user_id)}")
            logger.info(f"SERVICE: user_id length: {len(user_id) if user_id else 0}")
            
            # 入力検証
            if not user_id or not isinstance(user_id, str) or len(user_id.strip()) == 0:
                logger.error(f"SERVICE: Invalid user_id for memo creation: '{user_id}'")
                raise ValueError("Invalid user_id")
                
            user_id = user_id.strip()  # 余分な空白を除去
            
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
            memo_dict = memo.to_dict()
            
            logger.info(f"Saving memo to path: users/{user_id}/subsidies/{memo_id}")
            logger.info(f"Memo data keys: {list(memo_dict.keys())}")
            
            doc_ref.set(memo_dict)
            
            # 保存確認
            saved_doc = doc_ref.get()
            if saved_doc.exists:
                logger.info(f"✓ Successfully saved subsidy memo: {memo_id} for user: {user_id}")
            else:
                logger.error(f"✗ Failed to save subsidy memo: {memo_id} for user: {user_id}")
            
            return memo
            
        except Exception as e:
            logger.error(f"Error creating subsidy memo: {str(e)}")
            raise
    
    def get_user_subsidies(self, user_id: str) -> List[SubsidyMemo]:
        """ユーザーの全助成金メモを取得"""
        try:
            subsidies = []
            logger.info(f"SERVICE: Fetching subsidies for user_id: '{user_id}'")
            logger.info(f"SERVICE: user_id type: {type(user_id)}")
            logger.info(f"SERVICE: user_id length: {len(user_id) if user_id else 0}")
            
            # 入力検証
            if not user_id or not isinstance(user_id, str) or len(user_id.strip()) == 0:
                logger.error(f"SERVICE: Invalid user_id: '{user_id}'")
                return []
            
            user_id = user_id.strip()  # 余分な空白を除去
            
            # デバッグ: コレクションパスを確認
            collection_path = f'users/{user_id}/subsidies'
            logger.info(f"SERVICE: Collection path: {collection_path}")
            
            # コレクション参照を取得
            collection_ref = self.db.collection('users').document(user_id).collection('subsidies')
            docs = collection_ref.stream()
            
            doc_count = 0
            for doc in docs:
                doc_count += 1
                logger.info(f"Found document: {doc.id}")
                data = doc.to_dict()
                logger.info(f"Document data keys: {list(data.keys()) if data else 'None'}")
                data['id'] = doc.id
                try:
                    subsidies.append(SubsidyMemo.from_dict(data))
                except Exception as parse_error:
                    logger.error(f"Error parsing document {doc.id}: {str(parse_error)}")
                    continue
            
            logger.info(f"Total documents found: {doc_count}, Successfully parsed: {len(subsidies)}")
            
            # 更新日時でソート（新しい順）
            subsidies.sort(key=lambda x: x.updated_at, reverse=True)
            
            return subsidies
            
        except Exception as e:
            logger.error(f"Error fetching subsidies: {str(e)}")
            logger.error(f"Exception type: {type(e).__name__}")
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
            
            # 最初の助成金のデータを使用（複数ある場合は最初のもの）
            subsidies = temp_result.get('subsidies', [])
            if not subsidies:
                return None
            
            first_subsidy = subsidies[0]
            
            # メモデータを構築
            memo_data = {
                'name': first_subsidy.get('subsidy_name', ''),
                'target_person': first_subsidy.get('target', ''),
                'plan_application': {
                    'required': first_subsidy.get('plan_required', False),
                    'deadline': first_subsidy.get('plan_deadline'),
                    'documents': [{'name': doc, 'completed': False} 
                                for doc in first_subsidy.get('plan_documents', [])],
                    'memo': first_subsidy.get('plan_memo', '')
                },
                'payment_application': {
                    'required': True,
                    'deadline': first_subsidy.get('payment_deadline'),
                    'documents': [{'name': doc, 'completed': False} 
                                for doc in first_subsidy.get('payment_documents', [])],
                    'memo': first_subsidy.get('payment_memo', '')
                },
                'source': 'free_diagnosis'
            }
            
            # メモを作成
            memo = self.create_subsidy_memo(user_id, memo_data)
            
            # 診断時のメモをチャット履歴として追加
            initial_memo = first_subsidy.get('initial_memo', '')
            if initial_memo:
                self.add_chat_history(user_id, memo.id, initial_memo)
            
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