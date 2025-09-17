#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""業務改善助成金エージェントのファイル読み込みテスト"""

import os
import sys
import glob

# srcディレクトリをパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from claude_service import ClaudeService

def test_file_loading():
    """ファイル読み込みテスト"""
    print("=" * 60)
    print("業務改善助成金エージェント ファイル読み込みテスト")
    print("=" * 60)

    # ClaudeServiceインスタンス作成
    service = ClaudeService()

    # 汎用エージェントプロンプト生成をテスト
    print("\n1. 汎用システムでのプロンプト生成テスト:")
    print("-" * 40)

    try:
        prompt = service._get_agent_prompt('業務改善助成金', 'file/業務改善助成金')

        # プロンプトに含まれるファイル名をチェック
        expected_files = [
            'gyoumukaizen07.txt',
            'gyoumukaizenmanyual.txt',
            '業務改善助成金Ｑ＆Ａ.txt',
            '業務改善助成金交付要領.txt',
            '最低賃金額以上かどうかを確認する方法.txt'
        ]

        files_found = []
        for file_name in expected_files:
            if file_name in prompt:
                files_found.append(file_name)
                print(f"[OK] {file_name} - 読み込み成功")
            else:
                print(f"[NG] {file_name} - 読み込み失敗")

        print(f"\n読み込み成功: {len(files_found)}/{len(expected_files)} ファイル")
        print(f"プロンプト全体の文字数: {len(prompt)} 文字")

    except Exception as e:
        print(f"[ERROR] エラー発生: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)

    # ファイルの存在確認
    print("\n2. ファイルの物理的存在確認:")
    print("-" * 40)

    base_dir = os.path.dirname(__file__)
    folder_path = os.path.join(base_dir, 'file', '業務改善助成金')

    print(f"フォルダパス: {folder_path}")
    print(f"フォルダ存在: {'[OK]' if os.path.exists(folder_path) else '[NG]'}")

    if os.path.exists(folder_path):
        txt_files = glob.glob(os.path.join(folder_path, '*.txt'))
        print(f"\n見つかったファイル数: {len(txt_files)}")
        for file_path in txt_files:
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            print(f"  - {file_name} ({file_size:,} バイト)")

if __name__ == "__main__":
    test_file_loading()