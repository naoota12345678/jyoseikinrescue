#!/usr/bin/env python3
"""
Debug script to test memo save/retrieve functionality
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from firebase_config import firebase_service
from subsidy_service import SubsidyService
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_memo_operations():
    """Test saving and retrieving a memo"""
    # Initialize services
    service = SubsidyService(firebase_service.get_db())
    
    # Test user ID - this should match what's being used in the app
    test_user_id = "test_debug_user"
    
    # Test memo data
    memo_data = {
        'name': 'テスト助成金',
        'target_person': 'テスト対象者',
        'plan_application': {
            'required': True,
            'deadline': '2025-12-31',
            'documents': [{'name': 'テスト書類', 'completed': False}],
            'memo': 'テストメモ'
        },
        'payment_application': {
            'required': True,
            'deadline': '2026-06-30',
            'documents': [{'name': '実績報告書', 'completed': False}],
            'memo': ''
        },
        'source': 'debug_test'
    }
    
    try:
        # Test save
        logger.info("=== SAVING MEMO ===")
        saved_memo = service.create_subsidy_memo(test_user_id, memo_data)
        logger.info(f"Saved memo ID: {saved_memo.id}")
        
        # Test retrieve
        logger.info("=== RETRIEVING MEMOS ===")
        retrieved_memos = service.get_user_subsidies(test_user_id)
        logger.info(f"Retrieved {len(retrieved_memos)} memos")
        
        if retrieved_memos:
            for memo in retrieved_memos:
                logger.info(f"  - {memo.name} (ID: {memo.id})")
        else:
            logger.warning("No memos found!")
            
        # Test specific retrieval
        logger.info("=== RETRIEVING SPECIFIC MEMO ===")
        specific_memo = service.get_subsidy_by_id(test_user_id, saved_memo.id)
        if specific_memo:
            logger.info(f"Successfully retrieved specific memo: {specific_memo.name}")
        else:
            logger.error("Failed to retrieve specific memo!")
            
        return True
        
    except Exception as e:
        logger.error(f"Error during test: {str(e)}")
        return False

if __name__ == "__main__":
    test_memo_operations()