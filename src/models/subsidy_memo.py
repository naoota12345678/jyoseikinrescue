"""
助成金メモ・スケジュール管理のデータモデル
"""
from datetime import datetime
from typing import List, Optional, Dict
from dataclasses import dataclass, field, asdict

@dataclass
class Document:
    """必要書類"""
    name: str
    completed: bool = False
    
    def to_dict(self):
        return asdict(self)

@dataclass
class ApplicationPhase:
    """申請フェーズ（計画申請/支給申請）"""
    required: bool
    deadline: Optional[str] = None
    documents: List[Document] = field(default_factory=list)
    memo: str = ""
    
    def to_dict(self):
        return {
            'required': self.required,
            'deadline': self.deadline,
            'documents': [doc.to_dict() for doc in self.documents],
            'memo': self.memo
        }

@dataclass
class ChatHistory:
    """チャット履歴"""
    date: datetime
    content: str
    
    def to_dict(self):
        return {
            'date': self.date.isoformat(),
            'content': self.content
        }

@dataclass
class SubsidyMemo:
    """助成金メモのメインモデル"""
    id: str
    user_id: str
    name: str  # 助成金名
    target_person: str  # 対象者
    plan_application: ApplicationPhase  # 計画申請
    payment_application: ApplicationPhase  # 支給申請
    chat_history: List[ChatHistory] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    source: str = "manual"  # "manual", "ai_diagnosis", "free_diagnosis"
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'target_person': self.target_person,
            'plan_application': self.plan_application.to_dict(),
            'payment_application': self.payment_application.to_dict(),
            'chat_history': [ch.to_dict() for ch in self.chat_history],
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'source': self.source
        }
    
    @classmethod
    def from_dict(cls, data: Dict):
        """Firestoreから取得したデータをモデルに変換"""
        plan_docs = [Document(**doc) for doc in data.get('plan_application', {}).get('documents', [])]
        payment_docs = [Document(**doc) for doc in data.get('payment_application', {}).get('documents', [])]
        
        plan_app = ApplicationPhase(
            required=data.get('plan_application', {}).get('required', False),
            deadline=data.get('plan_application', {}).get('deadline'),
            documents=plan_docs,
            memo=data.get('plan_application', {}).get('memo', '')
        )
        
        payment_app = ApplicationPhase(
            required=data.get('payment_application', {}).get('required', True),
            deadline=data.get('payment_application', {}).get('deadline'),
            documents=payment_docs,
            memo=data.get('payment_application', {}).get('memo', '')
        )
        
        chat_history = []
        for ch in data.get('chat_history', []):
            chat_history.append(ChatHistory(
                date=datetime.fromisoformat(ch['date']),
                content=ch['content']
            ))
        
        return cls(
            id=data['id'],
            user_id=data['user_id'],
            name=data['name'],
            target_person=data['target_person'],
            plan_application=plan_app,
            payment_application=payment_app,
            chat_history=chat_history,
            created_at=datetime.fromisoformat(data.get('created_at', datetime.now().isoformat())),
            updated_at=datetime.fromisoformat(data.get('updated_at', datetime.now().isoformat())),
            source=data.get('source', 'manual')
        )
    
    def calculate_progress(self) -> float:
        """進捗率を計算（0-100%）"""
        total_docs = 0
        completed_docs = 0
        
        if self.plan_application.required:
            for doc in self.plan_application.documents:
                total_docs += 1
                if doc.completed:
                    completed_docs += 1
        
        for doc in self.payment_application.documents:
            total_docs += 1
            if doc.completed:
                completed_docs += 1
        
        if total_docs == 0:
            return 0.0
        
        return (completed_docs / total_docs) * 100

@dataclass
class TempDiagnosis:
    """無料診断の一時保存用モデル"""
    session_id: str
    result: Dict
    timestamp: datetime
    expires_at: datetime
    
    def to_dict(self):
        return {
            'session_id': self.session_id,
            'result': self.result,
            'timestamp': self.timestamp.isoformat(),
            'expires_at': self.expires_at.isoformat()
        }