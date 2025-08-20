from flask import Flask, render_template, request, jsonify, session
import os
from dotenv import load_dotenv
from claude_service import ClaudeService
import logging

load_dotenv()

app = Flask(__name__, template_folder='../templates', static_folder='../static')
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

claude_service = ClaudeService()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        company_info = data.get('company_info', {})
        question = data.get('question', '')
        
        if not question:
            return jsonify({'error': '質問を入力してください'}), 400
        
        # セッションに会社情報を保存
        session['company_info'] = company_info
        
        # Claude APIに質問を送信
        response = claude_service.get_grant_consultation(company_info, question)
        
        return jsonify({
            'response': response,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        return jsonify({'error': 'サーバーエラーが発生しました'}), 500

@app.route('/api/grant-check', methods=['POST'])
def grant_check():
    try:
        data = request.json
        company_info = data.get('company_info', {})
        
        if not company_info:
            return jsonify({'error': '会社情報を入力してください'}), 400
        
        # 利用可能な助成金をチェック
        available_grants = claude_service.check_available_grants(company_info)
        
        return jsonify({
            'grants': available_grants,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Error in grant check endpoint: {str(e)}")
        return jsonify({'error': 'サーバーエラーが発生しました'}), 500

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)