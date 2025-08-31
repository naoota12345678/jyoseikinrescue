"""
AIエージェント会話履歴のデータモデル
"""
from datetime import datetime
from typing import List, Optional, Dict
from dataclasses import dataclass, field, asdict

@dataclass
class Message:
    """会話メッセージ"""
    sender: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime
    order: int
    
    def to_dict(self):
        return {
            'sender': self.sender,
            'content': self.content,
            'timestamp': self.timestamp.isoformat(),
            'order': self.order
        }
    
    @classmethod
    def from_dict(cls, data: Dict):
        return cls(
            sender=data['sender'],
            content=data['content'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            order=data['order']
        )

@dataclass
class AgentConversation:
    """AIエージェント会話履歴"""
    id: str
    user_id: str
    agent_id: str  # 'gyoumukaizen', 'career-up_seishain' 等
    agent_name: str  # 表示用名前
    title: str
    messages: List[Message] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'agent_id': self.agent_id,
            'agent_name': self.agent_name,
            'title': self.title,
            'messages': [msg.to_dict() for msg in self.messages],
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'is_active': self.is_active
        }
    
    @classmethod
    def from_dict(cls, data: Dict):
        """Firestoreから取得したデータをモデルに変換"""
        messages = []
        for msg_data in data.get('messages', []):
            messages.append(Message.from_dict(msg_data))
        
        return cls(
            id=data['id'],
            user_id=data['user_id'],
            agent_id=data['agent_id'],
            agent_name=data['agent_name'],
            title=data['title'],
            messages=messages,
            created_at=datetime.fromisoformat(data.get('created_at', datetime.now().isoformat())),
            updated_at=datetime.fromisoformat(data.get('updated_at', datetime.now().isoformat())),
            is_active=data.get('is_active', True)
        )
    
    def add_message(self, sender: str, content: str) -> Message:
        """新しいメッセージを追加"""
        new_order = len(self.messages)
        message = Message(
            sender=sender,
            content=content,
            timestamp=datetime.now(),
            order=new_order
        )
        self.messages.append(message)
        self.updated_at = datetime.now()
        return message
    
    def get_last_messages(self, count: int = 10) -> List[Message]:
        """最後のN件のメッセージを取得"""
        return self.messages[-count:] if self.messages else []
    
    def generate_title(self) -> str:
        """最初のユーザーメッセージから会話タイトルを生成"""
        for message in self.messages:
            if message.sender == 'user':
                # 最初の30文字をタイトルとして使用
                title = message.content[:30]
                if len(message.content) > 30:
                    title += "..."
                return title
        return f"{self.agent_name}との会話"