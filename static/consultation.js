// 専門家相談用JavaScript（単一プラン版）
let selectedCategory = null;

function selectCategory(category) {
    selectedCategory = category;

    // すべてのカテゴリのスタイルをリセット
    document.querySelectorAll('.consultation-category').forEach(el => {
        el.style.border = '2px solid #e5e7eb';
        el.style.background = 'white';
    });

    // 選択されたカテゴリをハイライト
    event.target.closest('.consultation-category').style.border = '2px solid #3b82f6';
    event.target.closest('.consultation-category').style.background = '#f0f9ff';

    updateBookingButton();
}

function validateConsultationForm() {
    // 必須項目のチェック
    const companyInfo = document.getElementById('companyInfo')?.value?.trim();
    const currentIssues = document.getElementById('currentIssues')?.value?.trim();

    if (selectedCategory && companyInfo && currentIssues) {
        return true;
    }
    return false;
}

function updateBookingButton() {
    const bookBtn = document.getElementById('bookConsultationBtn');
    if (validateConsultationForm()) {
        bookBtn.style.opacity = '1';
        bookBtn.disabled = false;
        bookBtn.style.background = '#3b82f6';
    } else {
        bookBtn.style.opacity = '0.5';
        bookBtn.disabled = true;
        bookBtn.style.background = '#9ca3af';
    }
}

function proceedToBooking() {
    if (!validateConsultationForm()) {
        alert('相談カテゴリを選択し、必須項目（会社情報、現在の課題）をご記入ください');
        return;
    }

    // 相談内容を収集
    const consultationDetails = {
        category: selectedCategory,
        companyInfo: document.getElementById('companyInfo').value,
        currentIssues: document.getElementById('currentIssues').value,
        targetSubsidies: document.getElementById('targetSubsidies').value,
        pastApplications: document.getElementById('pastApplications').value,
        additionalQuestions: document.getElementById('additionalQuestions').value
    };

    // 決済画面に遷移
    proceedToPayment(consultationDetails);
}

function proceedToPayment(consultationDetails) {
    // ローディング表示
    const content = document.getElementById('expertConsultationContent');
    content.innerHTML = `
        <div style="text-align: center; padding: 2rem;">
            <div style="display: inline-block; animation: spin 1s linear infinite; width: 32px; height: 32px; border: 3px solid #f3f3f3; border-top: 3px solid #3b82f6; border-radius: 50%;"></div>
            <p style="margin-top: 1rem; color: #6b7280;">決済処理を開始しています...</p>
        </div>
        <style>
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        </style>
    `;

    // Stripe決済API呼び出し - 常に30分14,300円プラン（税込）
    fetch('/api/payment/consultation', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${user?.accessToken || ''}`
        },
        body: JSON.stringify({
            plan_type: 'basic',  // 30分プラン固定
            consultation_category: consultationDetails.category,
            consultation_details: consultationDetails  // 相談詳細を送信
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Stripe Checkoutページにリダイレクト
            window.location.href = data.payment_url;
        } else {
            throw new Error(data.error || '決済セッションの作成に失敗しました');
        }
    })
    .catch(error => {
        console.error('Payment error:', error);
        alert('決済処理でエラーが発生しました: ' + error.message);
        // エラー時は元の画面に戻る
        showExpertConsultation();
    });
}

// 入力フィールドのイベントリスナーを追加
document.addEventListener('DOMContentLoaded', function() {
    const inputs = ['companyInfo', 'currentIssues', 'targetSubsidies', 'pastApplications', 'additionalQuestions'];
    inputs.forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.addEventListener('input', updateBookingButton);
        }
    });
});