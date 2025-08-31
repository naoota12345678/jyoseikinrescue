"""
AIエージェント会話履歴管理サービス
"""
import logging
import uuid
from datetime import datetime
from typing import List, Optional
from firebase_admin import firestore
from models.agent_conversation import AgentConversation, Message

logger = logging.getLogger(__name__)

class ConversationService:
    def __init__(self, db):
        self.db = db
        self.collection_name = 'agent_conversations'
    
    def create_conversation(self, user_id: str, agent_id: str, agent_name: str, initial_message: str = None) -> AgentConversation:
        """新しい会話を作成"""
        try:
            conversation_id = str(uuid.uuid4())
            
            conversation = AgentConversation(
                id=conversation_id,
                user_id=user_id,
                agent_id=agent_id,
                agent_name=agent_name,
                title=f"{agent_name}との会話"
            )
            
            # 初期メッセージがある場合は追加
            if initial_message:
                conversation.add_message('user', initial_message)
                # タイトルを生成
                conversation.title = conversation.generate_title()
            
            # Firestoreに保存
            doc_ref = self.db.collection(self.collection_name).document(conversation_id)
            doc_ref.set(conversation.to_dict())
            
            logger.info(f"Created conversation: {conversation_id} for user: {user_id}")
            return conversation
            
        except Exception as e:
            logger.error(f"Error creating conversation: {str(e)}")
            raise
    
    def get_conversation(self, conversation_id: str, user_id: str) -> Optional[AgentConversation]:
        """会話を取得（ユーザー認証付き）"""
        try:
            doc_ref = self.db.collection(self.collection_name).document(conversation_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return None
            
            data = doc.to_dict()
            
            # ユーザー認証
            if data.get('user_id') != user_id:
                logger.warning(f"Unauthorized access to conversation {conversation_id} by user {user_id}")
                return None
            
            return AgentConversation.from_dict(data)
            
        except Exception as e:
            logger.error(f"Error getting conversation {conversation_id}: {str(e)}")
            return None
    
    def get_user_conversations(self, user_id: str, limit: int = 50) -> List[AgentConversation]:
        """ユーザーの全会話を取得（最新順）"""
        try:
            query = self.db.collection(self.collection_name)\
                          .where('user_id', '==', user_id)\
                          .where('is_active', '==', True)\
                          .order_by('updated_at', direction=firestore.Query.DESCENDING)\
                          .limit(limit)
            
            docs = query.stream()
            conversations = []
            
            for doc in docs:
                data = doc.to_dict()
                conversation = AgentConversation.from_dict(data)
                conversations.append(conversation)
            
            logger.info(f"Retrieved {len(conversations)} conversations for user: {user_id}")
            return conversations
            
        except Exception as e:
            logger.error(f"Error getting conversations for user {user_id}: {str(e)}")
            return []
    
    def add_message_to_conversation(self, conversation_id: str, user_id: str, sender: str, content: str) -> bool:
        """会話にメッセージを追加"""
        try:
            # 会話を取得
            conversation = self.get_conversation(conversation_id, user_id)
            if not conversation:
                logger.error(f"Conversation {conversation_id} not found or access denied")
                return False
            
            # メッセージを追加
            conversation.add_message(sender, content)
            
            # タイトルを更新（最初のユーザーメッセージの場合）
            if sender == 'user' and len([m for m in conversation.messages if m.sender == 'user']) == 1:
                conversation.title = conversation.generate_title()
            
            # Firestoreに保存
            doc_ref = self.db.collection(self.collection_name).document(conversation_id)
            doc_ref.set(conversation.to_dict())
            
            logger.info(f"Added message to conversation {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding message to conversation {conversation_id}: {str(e)}")
            return False
    
    def update_conversation_title(self, conversation_id: str, user_id: str, title: str) -> bool:
        """会話タイトルを更新"""
        try:
            conversation = self.get_conversation(conversation_id, user_id)
            if not conversation:
                return False
            
            conversation.title = title
            conversation.updated_at = datetime.now()
            
            doc_ref = self.db.collection(self.collection_name).document(conversation_id)
            doc_ref.set(conversation.to_dict())
            
            logger.info(f"Updated title for conversation {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating conversation title {conversation_id}: {str(e)}")
            return False
    
    def delete_conversation(self, conversation_id: str, user_id: str) -> bool:
        """会話を削除（論理削除）"""
        try:
            conversation = self.get_conversation(conversation_id, user_id)
            if not conversation:
                return False
            
            conversation.is_active = False
            conversation.updated_at = datetime.now()
            
            doc_ref = self.db.collection(self.collection_name).document(conversation_id)
            doc_ref.set(conversation.to_dict())
            
            logger.info(f"Deleted conversation {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting conversation {conversation_id}: {str(e)}")
            return False
    
    def get_conversation_summary(self, conversation_id: str, user_id: str) -> Optional[dict]:
        """会話のサマリーを取得（リスト表示用）"""
        try:
            conversation = self.get_conversation(conversation_id, user_id)
            if not conversation:
                return None
            
            # 最後のメッセージを取得
            last_message = conversation.messages[-1] if conversation.messages else None
            preview = last_message.content[:50] + "..." if last_message and len(last_message.content) > 50 else (last_message.content if last_message else "")
            
            return {
                'id': conversation.id,
                'title': conversation.title,
                'agent_name': conversation.agent_name,
                'preview': preview,
                'message_count': len(conversation.messages),
                'updated_at': conversation.updated_at.isoformat(),
                'created_at': conversation.created_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting conversation summary {conversation_id}: {str(e)}")
            return None