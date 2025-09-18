# 円山動物病院方式 - 専門家相談予約システム実装案

## 実装概要
**採用方式**: 円山動物病院方式（決済 → Firestore保存 → Calendly予約 → Webhook連携）
**既存システムへの影響**: ゼロ（新機能のみ追加）
**対象**: 会員のみ

## システムフロー

### 完全なフロー図
```
1. 専門家相談ページ（既存）
   ↓
2. 「支払い・ご予約に進む」ボタン（既存）
   ↓
3. Stripe決済処理（既存API使用）
   ↓
4. 決済成功ページ（拡張）
   ├─ 決済完了メッセージ表示
   ├─ 予約情報をFirestoreに保存 ← 新機能
   └─ Calendly埋め込み表示 ← 新機能
   ↓
5. 顧客がCalendlyで日時選択
   ↓
6. Calendly Webhook受信 ← 新機能
   ├─ Firestoreの予約情報更新
   ├─ 予約確定メール送信
   └─ Zoom URL自動送信（将来実装）
   ↓
7. 管理者ダッシュボードで予約確認 ← 新機能
```

## 詳細実装

### 1. Firestoreデータ構造設計

```javascript
// 新規コレクション：appointments
appointments/{appointment_id} = {
    // 基本情報
    appointment_id: "uuid",
    user_id: "user123",
    user_email: "user@example.com",

    // 決済情報
    stripe_session_id: "cs_xxxx",
    stripe_customer_id: "cus_xxxx",
    amount: 14300,
    currency: "jpy",

    // 予約状況
    booking_status: "payment_completed" | "calendly_scheduled" | "completed" | "cancelled",

    // Calendly情報（Webhook後に更新）
    calendly_event_id: null,
    calendly_invitee_id: null,
    scheduled_time: null,
    calendly_meeting_url: null,

    // 面談情報
    zoom_url: null,
    meeting_notes: null,

    // タイムスタンプ
    created_at: timestamp,
    updated_at: timestamp,
    scheduled_at: null
}
```

### 2. 決済成功ページの拡張

```python
# app.py - 既存エンドポイントの拡張
@app.route('/consultation/payment-success')
def consultation_payment_success():
    session_id = request.args.get('session_id')

    if not session_id:
        return redirect('/dashboard')

    # 既存：決済情報確認
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status != 'paid':
            return render_template('payment_error.html')
    except Exception as e:
        logger.error(f"決済確認エラー: {e}")
        return render_template('payment_error.html')

    # 👇 新機能：予約情報をFirestoreに保存
    try:
        current_user = get_current_user()
        appointment_data = {
            'appointment_id': str(uuid.uuid4()),
            'user_id': current_user['user_id'],
            'user_email': current_user['email'],
            'stripe_session_id': session_id,
            'stripe_customer_id': session.customer,
            'amount': 14300,
            'currency': 'jpy',
            'booking_status': 'payment_completed',
            'calendly_event_id': None,
            'calendly_invitee_id': None,
            'scheduled_time': None,
            'calendly_meeting_url': None,
            'zoom_url': None,
            'meeting_notes': None,
            'created_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP,
            'scheduled_at': None
        }

        # Firestoreに保存
        appointment_ref = db.collection('appointments').document(appointment_data['appointment_id'])
        appointment_ref.set(appointment_data)

        logger.info(f"予約データ保存完了: {appointment_data['appointment_id']}")

    except Exception as e:
        # エラーでも既存機能は継続
        logger.error(f"予約データ保存エラー: {e}")
        appointment_data = {'appointment_id': 'error'}

    # 既存のテンプレート表示（拡張版）
    return render_template('consultation_payment_success.html',
                         session_id=session_id,
                         appointment_id=appointment_data['appointment_id'],
                         show_calendly=True,
                         calendly_url="https://calendly.com/your-account/30min")
```

### 3. 拡張されたテンプレート

```html
<!-- templates/consultation_payment_success.html -->
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>決済完了 - 助成金レスキュー</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='styles.css') }}">
</head>
<body>
    <div class="container">
        <!-- 既存：決済完了メッセージ -->
        <div class="success-header">
            <h1>✅ 決済が完了しました</h1>
            <div class="success-details">
                <p><strong>専門家相談（30分）</strong></p>
                <p>金額: ¥14,300（税込）</p>
                <p>決済ID: {{ session_id }}</p>
                {% if appointment_id != 'error' %}
                <p>予約ID: {{ appointment_id }}</p>
                {% endif %}
            </div>
        </div>

        <!-- 👇 新機能：Calendly予約セクション -->
        {% if show_calendly %}
        <div class="calendly-booking-section">
            <h2>📅 面談日時をご選択ください</h2>
            <div class="booking-instructions">
                <p>次に、面談の日時をご予約ください。ご都合の良い時間をお選びいただけます。</p>
                <ul>
                    <li>⏰ 面談時間：30分</li>
                    <li>💻 面談方法：Zoom（リンクは後日お送りします）</li>
                    <li>👨‍💼 相談員：社会保険労務士</li>
                </ul>
            </div>

            <!-- Calendly埋め込み -->
            <div class="calendly-container">
                <div class="calendly-inline-widget"
                     data-url="{{ calendly_url }}"
                     style="min-width:320px;height:700px;">
                </div>
            </div>

            <!-- Calendlyスクリプト -->
            <script type="text/javascript" src="https://assets.calendly.com/assets/external/widget.js" async></script>
        </div>
        {% endif %}

        <!-- 既存：ダッシュボードへのリンク -->
        <div class="navigation-section">
            <a href="/dashboard" class="btn btn-primary">
                🏠 ダッシュボードに戻る
            </a>
        </div>

        <!-- お問い合わせ情報 -->
        <div class="support-section">
            <h3>📞 お困りの場合</h3>
            <p>予約でお困りの場合は、お気軽にお問い合わせください。</p>
            <p>Email: support@jyoseikin.jp</p>
        </div>
    </div>

    <style>
        .success-header {
            text-align: center;
            margin-bottom: 2rem;
            padding: 2rem;
            background: linear-gradient(135deg, #4CAF50, #45a049);
            color: white;
            border-radius: 10px;
        }

        .success-details {
            background: rgba(255,255,255,0.1);
            padding: 1rem;
            border-radius: 8px;
            margin-top: 1rem;
        }

        .calendly-booking-section {
            margin: 2rem 0;
            padding: 2rem;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            background: #fafafa;
        }

        .booking-instructions {
            margin-bottom: 2rem;
        }

        .booking-instructions ul {
            list-style: none;
            padding: 0;
        }

        .booking-instructions li {
            padding: 0.5rem 0;
            border-bottom: 1px solid #eee;
        }

        .calendly-container {
            background: white;
            border-radius: 8px;
            padding: 1rem;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }

        .navigation-section {
            text-align: center;
            margin: 2rem 0;
        }

        .support-section {
            background: #f0f8ff;
            padding: 1.5rem;
            border-radius: 8px;
            border-left: 4px solid #2196F3;
        }

        .btn {
            display: inline-block;
            padding: 12px 24px;
            text-decoration: none;
            border-radius: 6px;
            font-weight: bold;
            transition: all 0.3s ease;
        }

        .btn-primary {
            background: #2196F3;
            color: white;
        }

        .btn-primary:hover {
            background: #1976D2;
            transform: translateY(-2px);
        }

        @media (max-width: 768px) {
            .calendly-inline-widget {
                height: 600px !important;
            }

            .container {
                padding: 1rem;
            }
        }
    </style>
</body>
</html>
```

### 4. Calendly Webhook処理

```python
# app.py - 新規エンドポイント
@app.route('/webhook/calendly', methods=['POST'])
def calendly_webhook():
    """Calendly Webhook処理"""
    try:
        # Webhookデータ取得
        webhook_data = request.json
        event_type = webhook_data.get('event')

        if event_type == 'invitee.created':
            # 予約確定処理
            payload = webhook_data.get('payload', {})
            invitee_email = payload.get('email')
            event_start_time = payload.get('start_time')
            event_end_time = payload.get('end_time')
            calendly_event_id = payload.get('event', {}).get('uuid')
            calendly_invitee_id = payload.get('uuid')
            meeting_url = payload.get('event', {}).get('location', {}).get('join_url')

            # Firestoreの該当予約を検索・更新
            appointments_ref = db.collection('appointments')
            query = appointments_ref.where('user_email', '==', invitee_email).where('booking_status', '==', 'payment_completed')

            appointments = query.get()

            if appointments:
                # 最新の予約を更新
                latest_appointment = max(appointments, key=lambda x: x.get('created_at'))
                appointment_ref = appointments_ref.document(latest_appointment.id)

                update_data = {
                    'booking_status': 'calendly_scheduled',
                    'calendly_event_id': calendly_event_id,
                    'calendly_invitee_id': calendly_invitee_id,
                    'scheduled_time': event_start_time,
                    'calendly_meeting_url': meeting_url,
                    'updated_at': firestore.SERVER_TIMESTAMP,
                    'scheduled_at': firestore.SERVER_TIMESTAMP
                }

                appointment_ref.update(update_data)

                # 予約確定メール送信
                send_booking_confirmation_email(invitee_email, event_start_time, latest_appointment.id)

                logger.info(f"予約確定: {latest_appointment.id} - {invitee_email}")

        elif event_type == 'invitee.canceled':
            # キャンセル処理
            payload = webhook_data.get('payload', {})
            calendly_invitee_id = payload.get('uuid')

            # 該当予約を検索してキャンセル状態に更新
            appointments_ref = db.collection('appointments')
            query = appointments_ref.where('calendly_invitee_id', '==', calendly_invitee_id)

            appointments = query.get()
            if appointments:
                for appointment in appointments:
                    appointment_ref = appointments_ref.document(appointment.id)
                    appointment_ref.update({
                        'booking_status': 'cancelled',
                        'updated_at': firestore.SERVER_TIMESTAMP
                    })

                logger.info(f"予約キャンセル: {appointment.id}")

        return jsonify({'status': 'success'}), 200

    except Exception as e:
        logger.error(f"Calendly Webhook エラー: {e}")
        return jsonify({'error': 'Internal server error'}), 500


def send_booking_confirmation_email(email, scheduled_time, appointment_id):
    """予約確定メール送信"""
    try:
        # メール内容作成
        subject = "【助成金レスキュー】専門家相談のご予約確定"

        # 日時をJSTに変換
        from datetime import datetime
        import pytz

        utc_time = datetime.fromisoformat(scheduled_time.replace('Z', '+00:00'))
        jst_time = utc_time.astimezone(pytz.timezone('Asia/Tokyo'))
        formatted_time = jst_time.strftime('%Y年%m月%d日 %H:%M')

        body = f"""
ご予約いただき、ありがとうございます。

【予約詳細】
・面談日時: {formatted_time}
・面談時間: 30分
・面談方法: Zoom（リンクは面談前日にお送りします）
・相談員: 社会保険労務士
・予約ID: {appointment_id}

【ご注意】
・面談開始時刻の5分前にはZoomにご参加ください
・資料等がある場合は事前にご準備ください

ご不明な点がございましたら、お気軽にお問い合わせください。

助成金レスキュー
Email: support@jyoseikin.jp
"""

        # メール送信（実装は既存のメール送信機能を使用）
        send_email(email, subject, body)

    except Exception as e:
        logger.error(f"予約確定メール送信エラー: {e}")
```

### 5. 管理者用予約管理画面

```python
# app.py - 管理者用エンドポイント
@app.route('/admin/appointments')
@require_admin  # 管理者権限チェック
def admin_appointments():
    """管理者用予約管理画面"""
    try:
        # 予約データ取得
        appointments_ref = db.collection('appointments')
        appointments = appointments_ref.order_by('created_at', direction=firestore.Query.DESCENDING).limit(100).get()

        appointment_list = []
        for appointment in appointments:
            data = appointment.to_dict()
            data['id'] = appointment.id
            appointment_list.append(data)

        return render_template('admin_appointments.html', appointments=appointment_list)

    except Exception as e:
        logger.error(f"管理者予約画面エラー: {e}")
        return render_template('error.html', message="データ取得に失敗しました")


@app.route('/admin/appointment/<appointment_id>')
@require_admin
def admin_appointment_detail(appointment_id):
    """個別予約詳細画面"""
    try:
        appointment_ref = db.collection('appointments').document(appointment_id)
        appointment = appointment_ref.get()

        if not appointment.exists:
            return render_template('error.html', message="予約が見つかりません")

        data = appointment.to_dict()
        data['id'] = appointment.id

        return render_template('admin_appointment_detail.html', appointment=data)

    except Exception as e:
        logger.error(f"予約詳細取得エラー: {e}")
        return render_template('error.html', message="データ取得に失敗しました")
```

## 実装フェーズ

### Phase 1: 基本予約機能 ✅
1. ✅ 決済成功ページ拡張
2. ✅ Firestore予約データ保存
3. ✅ Calendly埋め込み表示
4. ⏳ 管理者予約確認画面

### Phase 2: Webhook連携 ⏳
1. ⏳ Calendly Webhook受信
2. ⏳ 予約確定処理
3. ⏳ 確定メール送信
4. ⏳ キャンセル処理

### Phase 3: 高度な機能 🔄
1. 🔄 Zoom URL自動送信
2. 🔄 面談メモ機能
3. 🔄 予約変更機能
4. 🔄 統計・レポート機能

## セキュリティ・エラーハンドリング

### 1. Webhook認証
```python
# Calendly Webhook署名検証
@app.route('/webhook/calendly', methods=['POST'])
def calendly_webhook():
    # 署名検証
    signature = request.headers.get('Calendly-Webhook-Signature')
    if not verify_calendly_signature(request.data, signature):
        return jsonify({'error': 'Unauthorized'}), 401

    # 処理続行...
```

### 2. データバリデーション
```python
def validate_appointment_data(data):
    """予約データバリデーション"""
    required_fields = ['user_id', 'user_email', 'stripe_session_id', 'amount']

    for field in required_fields:
        if field not in data or not data[field]:
            raise ValueError(f"必須フィールドが不足: {field}")

    if data['amount'] != 14300:
        raise ValueError(f"金額が不正: {data['amount']}")

    return True
```

### 3. エラー処理
```python
def safe_firestore_operation(operation_func, *args, **kwargs):
    """Firestore操作の安全な実行"""
    max_retries = 3

    for attempt in range(max_retries):
        try:
            return operation_func(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Firestore操作失敗 (試行 {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)  # 指数バックオフ
```

## 結論

この円山動物病院方式により、以下が実現されます：

✅ **既存システムの完全保護**
- 既存APIへの変更なし
- 新機能追加のみ

✅ **プロフェッショナルな予約管理**
- 決済→予約の一貫したフロー
- Calendly連携による自動化
- 管理者による予約管理

✅ **将来への拡張性**
- Zoom連携機能
- 追加請求システム連携
- 高度な予約管理機能

この実装により、助成金レスキューの専門家相談システムが大幅に改善され、円山動物病院レベルのプロフェッショナルなサービスが提供可能になります。