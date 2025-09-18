# Stripe請求書機能（カード決済限定版） - 実装案

## 機能概要
**目的**: 専門家相談後の追加作業に対するプロフェッショナルな請求書発行
**決済方法**: カード決済のみ（銀行振込無効）
**対象**: 管理者が面談後に任意金額で請求書作成

## システム要件

### 基本仕様
- **請求書タイプ**: Stripe Invoice（メール送信型）
- **決済方法**: カード決済限定
- **支払期限**: 7日間
- **通貨**: 日本円（JPY）
- **権限**: 管理者のみ作成可能

### 使用ケース
1. 専門家相談（30分）後の追加コンサルティング
2. 書類作成代行サービス
3. 申請サポート業務
4. その他カスタム作業

## 詳細実装

### 1. 核心機能：カード決済限定請求書作成

```python
import stripe
import uuid
from datetime import datetime, timedelta
from firebase_admin import firestore

def create_card_only_invoice(customer_id, amount, description, custom_data=None):
    """
    カード決済限定のプロ仕様請求書作成

    Args:
        customer_id (str): Stripe顧客ID
        amount (int): 請求金額（円）
        description (str): 請求内容説明
        custom_data (dict): カスタム情報（面談日時、合意事項等）

    Returns:
        dict: 作成された請求書情報
    """
    try:
        # 1. 請求書作成
        invoice = stripe.Invoice.create(
            customer=customer_id,
            collection_method='send_invoice',  # メール送信型
            days_until_due=7,  # 支払期限7日
            currency='jpy',
            description="助成金レスキュー - 追加作業費用",

            # フッター情報
            footer="ご不明な点がございましたらお気軽にお問い合わせください。\nEmail: support@jyoseikin.jp",

            # 👈 ここが重要：カード決済のみ設定
            payment_settings={
                'payment_method_types': ['card'],  # 銀行振込無効、カードのみ
                'payment_method_options': {
                    'card': {
                        'request_three_d_secure': 'automatic'  # 3Dセキュア自動
                    }
                }
            },

            # カスタムメタデータ
            metadata={
                'type': 'consultation_additional_work',
                'created_by': 'admin',
                'meeting_date': custom_data.get('meeting_date', '') if custom_data else '',
                'work_type': custom_data.get('work_type', '') if custom_data else ''
            }
        )

        # 2. 任意金額の明細追加
        stripe.InvoiceItem.create(
            customer=customer_id,
            invoice=invoice.id,
            amount=amount,
            currency='jpy',
            description=description,
            metadata={
                'item_type': 'additional_consultation',
                'amount_jpy': amount
            }
        )

        # 3. 請求書確定・送信
        finalized_invoice = stripe.Invoice.finalize_invoice(invoice.id)
        sent_invoice = stripe.Invoice.send_invoice(finalized_invoice.id)

        # 4. Firestoreに記録保存
        invoice_record = {
            'invoice_id': sent_invoice.id,
            'customer_id': customer_id,
            'amount': amount,
            'currency': 'jpy',
            'description': description,
            'status': sent_invoice.status,
            'payment_method_types': ['card'],
            'due_date': sent_invoice.due_date,
            'invoice_url': sent_invoice.hosted_invoice_url,
            'invoice_pdf': sent_invoice.invoice_pdf,
            'custom_data': custom_data or {},
            'created_at': firestore.SERVER_TIMESTAMP,
            'created_by': 'admin'
        }

        # Firestoreに保存
        db = firestore.client()
        invoice_ref = db.collection('custom_invoices').document(sent_invoice.id)
        invoice_ref.set(invoice_record)

        return {
            'success': True,
            'invoice_id': sent_invoice.id,
            'invoice_url': sent_invoice.hosted_invoice_url,
            'invoice_pdf': sent_invoice.invoice_pdf,
            'amount': amount,
            'due_date': sent_invoice.due_date,
            'status': sent_invoice.status
        }

    except stripe.error.StripeError as e:
        logger.error(f"Stripe請求書作成エラー: {e}")
        return {
            'success': False,
            'error': f"Stripe エラー: {str(e)}"
        }
    except Exception as e:
        logger.error(f"請求書作成エラー: {e}")
        return {
            'success': False,
            'error': f"システム エラー: {str(e)}"
        }
```

### 2. 管理者専用API エンドポイント

```python
# app.py - 管理者専用請求書作成API
@app.route('/admin/create-custom-invoice', methods=['POST'])
@require_auth
@require_admin  # 管理者権限チェック
def create_custom_invoice():
    """管理者専用：カスタム請求書作成"""
    try:
        data = request.json

        # バリデーション
        required_fields = ['customer_email', 'amount', 'description']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({
                    'success': False,
                    'error': f'必須フィールドが不足: {field}'
                }), 400

        # 金額バリデーション
        amount = int(data['amount'])
        if amount < 100:  # 最低金額100円
            return jsonify({
                'success': False,
                'error': '最低金額は100円です'
            }), 400

        if amount > 1000000:  # 最高金額100万円
            return jsonify({
                'success': False,
                'error': '最高金額は1,000,000円です'
            }), 400

        # 顧客検索・作成
        customer_email = data['customer_email']
        existing_customers = stripe.Customer.list(email=customer_email, limit=1)

        if existing_customers.data:
            customer_id = existing_customers.data[0].id
        else:
            # 新規顧客作成
            customer = stripe.Customer.create(
                email=customer_email,
                name=data.get('customer_name', ''),
                metadata={'created_for': 'custom_invoice'}
            )
            customer_id = customer.id

        # カスタムデータ準備
        custom_data = {
            'meeting_date': data.get('meeting_date', ''),
            'agreement_details': data.get('agreement_details', ''),
            'work_description': data.get('work_description', ''),
            'work_type': data.get('work_type', 'additional_consultation'),
            'created_by_admin': get_current_user()['email']
        }

        # 詳細説明文作成
        detailed_description = f"""
助成金レスキュー - 追加作業費用

【面談日時】{custom_data['meeting_date']}
【合意事項】{custom_data['agreement_details']}
【作業内容】{custom_data['work_description']}

お忙しい中、ありがとうございました。
追加作業の費用をご請求させていただきます。
        """

        # 請求書作成
        result = create_card_only_invoice(
            customer_id=customer_id,
            amount=amount,
            description=detailed_description,
            custom_data=custom_data
        )

        if result['success']:
            return jsonify({
                'success': True,
                'message': '請求書を作成し、お客様にメール送信しました',
                'invoice_id': result['invoice_id'],
                'invoice_url': result['invoice_url'],
                'amount': f"¥{amount:,}",
                'due_date': result['due_date']
            })
        else:
            return jsonify(result), 500

    except ValueError as e:
        return jsonify({
            'success': False,
            'error': f'入力値エラー: {str(e)}'
        }), 400
    except Exception as e:
        logger.error(f"カスタム請求書作成エラー: {e}")
        return jsonify({
            'success': False,
            'error': 'システムエラーが発生しました'
        }), 500


@app.route('/admin/invoices', methods=['GET'])
@require_auth
@require_admin
def admin_invoices_list():
    """管理者専用：請求書一覧表示"""
    try:
        # Firestoreから請求書データ取得
        db = firestore.client()
        invoices_ref = db.collection('custom_invoices')
        invoices = invoices_ref.order_by('created_at', direction=firestore.Query.DESCENDING).limit(50).get()

        invoice_list = []
        for invoice in invoices:
            data = invoice.to_dict()

            # Stripeから最新ステータス取得
            try:
                stripe_invoice = stripe.Invoice.retrieve(data['invoice_id'])
                data['current_status'] = stripe_invoice.status
                data['paid_at'] = stripe_invoice.status_transitions.paid_at
            except:
                data['current_status'] = data.get('status', 'unknown')
                data['paid_at'] = None

            invoice_list.append(data)

        return render_template('admin_invoices.html', invoices=invoice_list)

    except Exception as e:
        logger.error(f"請求書一覧取得エラー: {e}")
        return render_template('error.html', message="データ取得に失敗しました")


@app.route('/admin/invoice/<invoice_id>')
@require_auth
@require_admin
def admin_invoice_detail(invoice_id):
    """管理者専用：請求書詳細表示"""
    try:
        # Stripeから詳細情報取得
        stripe_invoice = stripe.Invoice.retrieve(invoice_id)

        # Firestoreから追加情報取得
        db = firestore.client()
        invoice_ref = db.collection('custom_invoices').document(invoice_id)
        invoice_doc = invoice_ref.get()

        custom_data = {}
        if invoice_doc.exists:
            custom_data = invoice_doc.to_dict().get('custom_data', {})

        return render_template('admin_invoice_detail.html',
                             invoice=stripe_invoice,
                             custom_data=custom_data)

    except stripe.error.InvalidRequestError:
        return render_template('error.html', message="請求書が見つかりません")
    except Exception as e:
        logger.error(f"請求書詳細取得エラー: {e}")
        return render_template('error.html', message="データ取得に失敗しました")
```

### 3. 管理者UI - 請求書作成画面

```html
<!-- templates/admin_create_invoice.html -->
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>カスタム請求書作成 - 管理者</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='styles.css') }}">
</head>
<body>
    <div class="admin-container">
        <h1>💳 カスタム請求書作成</h1>

        <div class="invoice-form-container">
            <form id="createInvoiceForm">
                <!-- 顧客情報 -->
                <div class="form-section">
                    <h2>👤 顧客情報</h2>

                    <div class="form-group">
                        <label for="customerEmail">メールアドレス *</label>
                        <input type="email" id="customerEmail" required>
                        <small>請求書送信先メールアドレス</small>
                    </div>

                    <div class="form-group">
                        <label for="customerName">お名前</label>
                        <input type="text" id="customerName">
                        <small>空白の場合は既存情報を使用</small>
                    </div>
                </div>

                <!-- 請求内容 -->
                <div class="form-section">
                    <h2>💰 請求内容</h2>

                    <div class="form-group">
                        <label for="amount">金額 *</label>
                        <div class="amount-input">
                            ¥ <input type="number" id="amount" min="100" max="1000000" required>
                        </div>
                        <small>100円〜1,000,000円</small>
                    </div>

                    <div class="form-group">
                        <label for="workType">作業種別</label>
                        <select id="workType">
                            <option value="additional_consultation">追加コンサルティング</option>
                            <option value="document_creation">書類作成代行</option>
                            <option value="application_support">申請サポート</option>
                            <option value="custom_work">その他カスタム作業</option>
                        </select>
                    </div>

                    <div class="form-group">
                        <label for="description">作業内容 *</label>
                        <textarea id="description" rows="4" required placeholder="具体的な作業内容を記載してください"></textarea>
                    </div>
                </div>

                <!-- 面談情報 -->
                <div class="form-section">
                    <h2>📅 面談情報</h2>

                    <div class="form-group">
                        <label for="meetingDate">面談日時</label>
                        <input type="datetime-local" id="meetingDate">
                    </div>

                    <div class="form-group">
                        <label for="agreementDetails">合意事項</label>
                        <textarea id="agreementDetails" rows="3" placeholder="面談で合意した内容を記載"></textarea>
                    </div>
                </div>

                <!-- プレビュー -->
                <div class="form-section">
                    <h2>👀 請求書プレビュー</h2>
                    <div id="invoicePreview" class="invoice-preview">
                        <p>上記の情報を入力すると、ここにプレビューが表示されます。</p>
                    </div>
                </div>

                <!-- 送信ボタン -->
                <div class="form-actions">
                    <button type="button" id="previewBtn" class="btn btn-secondary">
                        👀 プレビュー更新
                    </button>
                    <button type="submit" class="btn btn-primary">
                        📧 請求書作成・送信
                    </button>
                </div>
            </form>
        </div>

        <!-- 結果表示 -->
        <div id="resultMessage" class="result-message" style="display: none;"></div>
    </div>

    <script>
        // フォーム要素取得
        const form = document.getElementById('createInvoiceForm');
        const previewDiv = document.getElementById('invoicePreview');
        const resultDiv = document.getElementById('resultMessage');

        // プレビュー更新
        document.getElementById('previewBtn').addEventListener('click', updatePreview);

        // 入力値変更時の自動プレビュー
        ['customerEmail', 'customerName', 'amount', 'workType', 'description', 'meetingDate', 'agreementDetails'].forEach(id => {
            document.getElementById(id).addEventListener('input', updatePreview);
        });

        function updatePreview() {
            const data = getFormData();

            if (!data.customerEmail || !data.amount || !data.description) {
                previewDiv.innerHTML = '<p class="preview-incomplete">必須項目を入力してください。</p>';
                return;
            }

            const meetingDate = data.meetingDate ? new Date(data.meetingDate).toLocaleString('ja-JP') : '未設定';

            previewDiv.innerHTML = `
                <div class="preview-invoice">
                    <h3>📋 請求書プレビュー</h3>
                    <table class="preview-table">
                        <tr><th>宛先</th><td>${data.customerEmail}</td></tr>
                        <tr><th>金額</th><td>¥${parseInt(data.amount).toLocaleString()}</td></tr>
                        <tr><th>支払期限</th><td>7日後</td></tr>
                        <tr><th>決済方法</th><td>カード決済のみ</td></tr>
                    </table>

                    <div class="preview-description">
                        <h4>作業内容</h4>
                        <pre>${data.description}</pre>

                        <h4>面談情報</h4>
                        <p><strong>面談日時:</strong> ${meetingDate}</p>
                        <p><strong>合意事項:</strong> ${data.agreementDetails || '未記載'}</p>
                    </div>
                </div>
            `;
        }

        function getFormData() {
            return {
                customerEmail: document.getElementById('customerEmail').value,
                customerName: document.getElementById('customerName').value,
                amount: document.getElementById('amount').value,
                workType: document.getElementById('workType').value,
                description: document.getElementById('description').value,
                meetingDate: document.getElementById('meetingDate').value,
                agreementDetails: document.getElementById('agreementDetails').value
            };
        }

        // フォーム送信
        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const submitBtn = form.querySelector('button[type="submit"]');
            submitBtn.disabled = true;
            submitBtn.textContent = '📧 作成中...';

            try {
                const response = await fetch('/admin/create-custom-invoice', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(getFormData())
                });

                const result = await response.json();

                if (result.success) {
                    resultDiv.className = 'result-message success';
                    resultDiv.innerHTML = `
                        <h3>✅ 請求書作成完了</h3>
                        <p>${result.message}</p>
                        <div class="invoice-details">
                            <p><strong>請求書ID:</strong> ${result.invoice_id}</p>
                            <p><strong>金額:</strong> ${result.amount}</p>
                            <p><strong>支払期限:</strong> ${result.due_date}</p>
                            <a href="${result.invoice_url}" target="_blank" class="btn btn-link">
                                📄 請求書を確認
                            </a>
                        </div>
                    `;
                    form.reset();
                    updatePreview();
                } else {
                    resultDiv.className = 'result-message error';
                    resultDiv.innerHTML = `
                        <h3>❌ エラー</h3>
                        <p>${result.error}</p>
                    `;
                }

                resultDiv.style.display = 'block';
                resultDiv.scrollIntoView({ behavior: 'smooth' });

            } catch (error) {
                resultDiv.className = 'result-message error';
                resultDiv.innerHTML = `
                    <h3>❌ 通信エラー</h3>
                    <p>請求書の作成に失敗しました: ${error.message}</p>
                `;
                resultDiv.style.display = 'block';
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = '📧 請求書作成・送信';
            }
        });

        // 初期プレビュー
        updatePreview();
    </script>

    <style>
        .admin-container {
            max-width: 800px;
            margin: 0 auto;
            padding: 2rem;
        }

        .invoice-form-container {
            background: white;
            border-radius: 10px;
            padding: 2rem;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }

        .form-section {
            margin-bottom: 2rem;
            padding-bottom: 1.5rem;
            border-bottom: 1px solid #eee;
        }

        .form-section:last-child {
            border-bottom: none;
        }

        .form-section h2 {
            color: #333;
            margin-bottom: 1rem;
        }

        .form-group {
            margin-bottom: 1rem;
        }

        .form-group label {
            display: block;
            font-weight: bold;
            margin-bottom: 0.5rem;
            color: #555;
        }

        .form-group input,
        .form-group select,
        .form-group textarea {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
        }

        .form-group small {
            color: #666;
            font-size: 12px;
        }

        .amount-input {
            display: flex;
            align-items: center;
            gap: 5px;
            font-size: 18px;
            font-weight: bold;
        }

        .amount-input input {
            flex: 1;
        }

        .invoice-preview {
            background: #f9f9f9;
            border: 1px solid #ddd;
            border-radius: 6px;
            padding: 1rem;
            min-height: 200px;
        }

        .preview-invoice {
            background: white;
            padding: 1rem;
            border-radius: 4px;
        }

        .preview-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 1rem;
        }

        .preview-table th,
        .preview-table td {
            padding: 8px;
            border: 1px solid #ddd;
            text-align: left;
        }

        .preview-table th {
            background: #f5f5f5;
            font-weight: bold;
            width: 30%;
        }

        .preview-description pre {
            background: #f8f8f8;
            padding: 10px;
            border-radius: 4px;
            white-space: pre-wrap;
            font-family: inherit;
        }

        .preview-incomplete {
            color: #999;
            font-style: italic;
        }

        .form-actions {
            display: flex;
            gap: 1rem;
            justify-content: flex-end;
            margin-top: 2rem;
        }

        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            font-weight: bold;
            cursor: pointer;
            text-decoration: none;
            display: inline-block;
            transition: all 0.3s ease;
        }

        .btn-primary {
            background: #007bff;
            color: white;
        }

        .btn-primary:hover {
            background: #0056b3;
        }

        .btn-secondary {
            background: #6c757d;
            color: white;
        }

        .btn-secondary:hover {
            background: #545b62;
        }

        .btn-link {
            background: #17a2b8;
            color: white;
        }

        .btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }

        .result-message {
            margin-top: 2rem;
            padding: 1.5rem;
            border-radius: 6px;
        }

        .result-message.success {
            background: #d4edda;
            border: 1px solid #c3e6cb;
            color: #155724;
        }

        .result-message.error {
            background: #f8d7da;
            border: 1px solid #f5c6cb;
            color: #721c24;
        }

        .invoice-details {
            margin-top: 1rem;
            padding: 1rem;
            background: rgba(255,255,255,0.5);
            border-radius: 4px;
        }

        @media (max-width: 768px) {
            .admin-container {
                padding: 1rem;
            }

            .form-actions {
                flex-direction: column;
            }

            .btn {
                width: 100%;
            }
        }
    </style>
</body>
</html>
```

### 4. 管理者ダッシュボードへの統合

```python
# dashboard.htmlに管理者セクション追加
@app.route('/dashboard')
@require_auth
def dashboard():
    current_user = get_current_user()

    # 既存のダッシュボード機能...

    # 管理者の場合、請求書管理機能を追加
    is_admin = check_admin_permission(current_user)

    return render_template('dashboard.html',
                         user=current_user,
                         is_admin=is_admin,
                         # 既存の変数...
                         )
```

```html
<!-- dashboard.htmlに管理者専用セクション追加 -->
{% if is_admin %}
<div id="adminInvoiceSection" class="admin-section">
    <h3>🔧 管理者機能</h3>

    <div class="admin-tools">
        <a href="/admin/create-invoice" class="admin-tool-btn">
            💳 カスタム請求書作成
        </a>

        <a href="/admin/invoices" class="admin-tool-btn">
            📋 請求書一覧・管理
        </a>

        <a href="/admin/appointments" class="admin-tool-btn">
            📅 予約管理
        </a>
    </div>
</div>

<style>
.admin-section {
    background: linear-gradient(135deg, #6c5ce7, #a29bfe);
    color: white;
    padding: 1.5rem;
    border-radius: 10px;
    margin-top: 2rem;
}

.admin-tools {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
    margin-top: 1rem;
}

.admin-tool-btn {
    background: rgba(255,255,255,0.2);
    color: white;
    padding: 1rem;
    text-decoration: none;
    border-radius: 8px;
    text-align: center;
    font-weight: bold;
    transition: all 0.3s ease;
}

.admin-tool-btn:hover {
    background: rgba(255,255,255,0.3);
    transform: translateY(-2px);
}
</style>
{% endif %}
```

## Webhook処理

### 請求書ステータス更新

```python
@app.route('/webhook/stripe-invoice', methods=['POST'])
def stripe_invoice_webhook():
    """Stripe請求書Webhook処理"""
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.environ.get('STRIPE_INVOICE_WEBHOOK_SECRET')
        )
    except ValueError:
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError:
        return jsonify({'error': 'Invalid signature'}), 400

    # 請求書関連イベント処理
    if event['type'] == 'invoice.payment_succeeded':
        invoice = event['data']['object']
        handle_invoice_paid(invoice)

    elif event['type'] == 'invoice.payment_failed':
        invoice = event['data']['object']
        handle_invoice_payment_failed(invoice)

    elif event['type'] == 'invoice.finalized':
        invoice = event['data']['object']
        handle_invoice_finalized(invoice)

    return jsonify({'status': 'success'})


def handle_invoice_paid(invoice):
    """請求書支払い完了処理"""
    try:
        # Firestoreの請求書ステータス更新
        db = firestore.client()
        invoice_ref = db.collection('custom_invoices').document(invoice['id'])

        invoice_ref.update({
            'status': 'paid',
            'paid_at': firestore.SERVER_TIMESTAMP,
            'amount_paid': invoice['amount_paid']
        })

        # 支払い完了メール送信
        send_payment_confirmation_email(
            invoice['customer_email'],
            invoice['id'],
            invoice['amount_paid']
        )

        logger.info(f"請求書支払い完了: {invoice['id']}")

    except Exception as e:
        logger.error(f"請求書支払い処理エラー: {e}")


def handle_invoice_payment_failed(invoice):
    """請求書支払い失敗処理"""
    try:
        # Firestoreの請求書ステータス更新
        db = firestore.client()
        invoice_ref = db.collection('custom_invoices').document(invoice['id'])

        invoice_ref.update({
            'status': 'payment_failed',
            'last_payment_attempt': firestore.SERVER_TIMESTAMP
        })

        # 支払い失敗通知メール送信
        send_payment_failed_notification(
            invoice['customer_email'],
            invoice['id']
        )

        logger.warning(f"請求書支払い失敗: {invoice['id']}")

    except Exception as e:
        logger.error(f"請求書支払い失敗処理エラー: {e}")
```

## セキュリティ対策

### 1. 管理者権限チェック
```python
def require_admin(f):
    """管理者権限デコレータ"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_user = get_current_user()
        if not check_admin_permission(current_user):
            return jsonify({'error': 'Forbidden: 管理者権限が必要です'}), 403
        return f(*args, **kwargs)
    return decorated_function

def check_admin_permission(user):
    """管理者権限確認"""
    admin_emails = [
        'admin@jyoseikin.jp',
        'support@jyoseikin.jp'
        # 必要に応じて追加
    ]
    return user.get('email') in admin_emails
```

### 2. 入力値検証
```python
def validate_invoice_data(data):
    """請求書データバリデーション"""

    # メールアドレス検証
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, data.get('customer_email', '')):
        raise ValueError('有効なメールアドレスを入力してください')

    # 金額検証
    amount = data.get('amount')
    if not isinstance(amount, int) or amount < 100 or amount > 1000000:
        raise ValueError('金額は100円〜1,000,000円の範囲で入力してください')

    # 説明文検証
    description = data.get('description', '').strip()
    if len(description) < 10:
        raise ValueError('作業内容は10文字以上で入力してください')

    # 危険な文字列チェック
    dangerous_patterns = ['<script', 'javascript:', 'onload=']
    for pattern in dangerous_patterns:
        if pattern.lower() in description.lower():
            raise ValueError('不正な文字列が含まれています')

    return True
```

## 運用フロー

### 1. 通常の使用手順
```
1. 専門家相談実施（既存フロー）
   ↓
2. 追加作業が必要と判断
   ↓
3. 管理者が請求書作成画面にアクセス
   ↓
4. 顧客情報・作業内容・金額を入力
   ↓
5. プレビュー確認後、送信
   ↓
6. 顧客にメール送信（Stripe経由）
   ↓
7. 顧客がカード決済で支払い
   ↓
8. Webhook経由で支払い確認
   ↓
9. 完了通知メール送信
```

### 2. 管理者監視
- 請求書一覧での支払いステータス確認
- 未払い請求書の督促管理
- 支払い統計・レポート

### 3. 顧客体験
- プロフェッショナルな請求書デザイン
- カード決済のみの明確な決済フロー
- 安全な3Dセキュア認証
- 支払い完了の即座な確認

## 結論

この実装により以下が実現されます：

✅ **安全な追加請求システム**
- カード決済限定で確実な回収
- 管理者のみの作成権限
- プロフェッショナルな請求書

✅ **既存システムとの完全分離**
- 新機能のみ追加
- 既存決済フローに影響なし

✅ **運用効率の向上**
- 面談後の追加作業を適切に収益化
- 自動化された決済・確認フロー
- 管理者による一元管理

この実装により、助成金レスキューは専門家相談の付加価値を適切に収益化し、より持続可能なビジネスモデルを構築できます。