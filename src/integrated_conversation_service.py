"""
統合会話履歴管理サービス (ChatGPT/Claude風)
メッセージを会話スレッドごとに統合保存
"""
import logging
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from firebase_admin import firestore

logger = logging.getLogger(__name__)

class IntegratedConversationService:
    def __init__(self, db):
        self.db = db
        self.collection_name = 'conversations'
        self.max_messages_per_conversation = 50  # メッセージ上限
    
    def create_conversation(self, user_id: str, agent_id: str, agent_name: str, initial_message: str = None) -> Dict[str, Any]:
        """新しい統合会話を作成"""
        try:
            conversation_id = str(uuid.uuid4())
            now = datetime.utcnow()
            
            conversation_data = {
                'id': conversation_id,
                'user_id': user_id,
                'agent_id': agent_id,
                'agent_name': agent_name,
                'title': f"{agent_name}との会話",  # デフォルトタイトル
                'messages': [],
                'created_at': now,
                'updated_at': now,
                'is_active': True
            }
            
            # 初期メッセージがある場合は追加
            if initial_message:
                conversation_data['messages'].append({
                    'content': initial_message,
                    'sender': 'user',
                    'timestamp': now
                })
                # 最初のメッセージからタイトル生成
                conversation_data['title'] = self._generate_title(initial_message, agent_name)
            
            # Firestoreに保存
            doc_ref = self.db.collection(self.collection_name).document(conversation_id)
            doc_ref.set(conversation_data)
            
            logger.info(f"Created integrated conversation: {conversation_id} for user: {user_id}")
            return conversation_data
            
        except Exception as e:
            logger.error(f"Error creating integrated conversation: {str(e)}")
            raise
    
    def add_message(self, conversation_id: str, user_id: str, content: str, sender: str) -> bool:
        """会話にメッセージを追加"""
        try:
            doc_ref = self.db.collection(self.collection_name).document(conversation_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                logger.error(f"Conversation {conversation_id} not found")
                return False
            
            conversation_data = doc.to_dict()
            
            # ユーザー権限チェック
            if conversation_data['user_id'] != user_id:
                logger.error(f"Unauthorized access to conversation {conversation_id}")
                return False
            
            # メッセージ上限チェック
            if len(conversation_data['messages']) >= self.max_messages_per_conversation:
                # 古いメッセージを削除（最初の2件を削除して容量を確保）
                conversation_data['messages'] = conversation_data['messages'][2:]
                logger.info(f"Trimmed old messages for conversation {conversation_id}")
            
            # 新しいメッセージを追加
            now = datetime.utcnow()
            new_message = {
                'content': content,
                'sender': sender,
                'timestamp': now
            }
            
            conversation_data['messages'].append(new_message)
            conversation_data['updated_at'] = now
            
            # タイトルが未設定またはデフォルトの場合、最初のユーザーメッセージから生成
            if (conversation_data['title'] == f"{conversation_data['agent_name']}との会話" and 
                sender == 'user' and 
                len([msg for msg in conversation_data['messages'] if msg['sender'] == 'user']) == 1):
                conversation_data['title'] = self._generate_title(content, conversation_data['agent_name'])
            
            # Firestoreを更新
            doc_ref.update({
                'messages': conversation_data['messages'],
                'updated_at': now,
                'title': conversation_data['title']
            })
            
            logger.info(f"Added message to conversation {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding message to conversation: {str(e)}")
            return False
    
    def get_conversation(self, conversation_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """会話を取得（ユーザー認証付き）"""
        try:
            doc_ref = self.db.collection(self.collection_name).document(conversation_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return None
            
            conversation_data = doc.to_dict()
            
            # ユーザー権限チェック
            if conversation_data['user_id'] != user_id:
                logger.error(f"Unauthorized access to conversation {conversation_id}")
                return None
            
            return conversation_data
            
        except Exception as e:
            logger.error(f"Error getting conversation: {str(e)}")
            return None
    
    def get_conversations(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """ユーザーの会話一覧を取得（更新日時順）"""
        try:
            # シンプルなクエリに変更してテスト
            conversations_ref = (self.db.collection(self.collection_name)
                               .where('user_id', '==', user_id)
                               .limit(limit))
            
            docs = conversations_ref.stream()
            conversations = []
            
            for doc in docs:
                conversation_data = doc.to_dict()
                
                # プレビュー生成（最後のメッセージから）
                preview = "まだメッセージがありません"
                if conversation_data['messages']:
                    last_message = conversation_data['messages'][-1]
                    preview = last_message['content'][:50] + ('...' if len(last_message['content']) > 50 else '')
                
                conversation_data['preview'] = preview
                conversations.append(conversation_data)
            
            logger.info(f"Retrieved {len(conversations)} conversations for user: {user_id}")
            return conversations
            
        except Exception as e:
            logger.error(f"Error getting conversations for user {user_id}: {str(e)}")
            return []
    
    def update_conversation_title(self, conversation_id: str, user_id: str, title: str) -> bool:
        """会話タイトルを更新"""
        try:
            doc_ref = self.db.collection(self.collection_name).document(conversation_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return False
            
            conversation_data = doc.to_dict()
            if conversation_data['user_id'] != user_id:
                return False
            
            doc_ref.update({
                'title': title,
                'updated_at': datetime.utcnow()
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating conversation title: {str(e)}")
            return False
    
    def delete_conversation(self, conversation_id: str, user_id: str) -> bool:
        """会話を削除（論理削除）"""
        try:
            doc_ref = self.db.collection(self.collection_name).document(conversation_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return False
            
            conversation_data = doc.to_dict()
            if conversation_data['user_id'] != user_id:
                return False
            
            doc_ref.update({
                'is_active': False,
                'updated_at': datetime.utcnow()
            })
            
            logger.info(f"Deleted conversation: {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting conversation: {str(e)}")
            return False
    
    def _generate_title(self, first_message: str, agent_name: str) -> str:
        """最初のメッセージから会話タイトルを生成"""
        # メッセージが短い場合はそのまま使用
        if len(first_message) <= 20:
            return first_message
        
        # 長い場合は最初の20文字 + "..."
        title = first_message[:20] + "..."
        
        # 質問系のキーワードがあれば適切なタイトルに
        keywords = {
            "申請": "申請について",
            "手続き": "手続きについて", 
            "要件": "要件について",
            "支給": "支給について",
            "条件": "条件について",
            "書類": "書類について",
            "スケジュール": "スケジュールについて"
        }
        
        for keyword, title_suffix in keywords.items():
            if keyword in first_message:
                return title_suffix
        
        return title
    
    def get_conversation_messages(self, conversation_id: str, user_id: str) -> List[Dict[str, Any]]:
        """会話のメッセージ履歴を取得"""
        try:
            conversation = self.get_conversation(conversation_id, user_id)
            if not conversation:
                return []
            
            return conversation.get('messages', [])
            
        except Exception as e:
            logger.error(f"Error getting conversation messages: {str(e)}")
            return []