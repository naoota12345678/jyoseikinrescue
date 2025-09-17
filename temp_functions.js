        // 専門家相談用のJavaScript関数
        let selectedCategory = null;
        let selectedPlan = null;

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

        function selectPlan(plan) {
            selectedPlan = plan;

            // すべてのプランのスタイルをリセット
            document.querySelectorAll('.consultation-plan').forEach(el => {
                if (!el.style.background.includes('#f0f9ff')) {
                    el.style.border = '2px solid #e5e7eb';
                    el.style.background = 'white';
                }
            });

            // 選択されたプランをハイライト
            const selectedElement = event.target.closest('.consultation-plan');
            selectedElement.style.border = '2px solid #059669';
            if (!selectedElement.style.background.includes('#f0f9ff')) {
                selectedElement.style.background = '#ecfdf5';
            }

            updateBookingButton();
        }

        function updateBookingButton() {
            const bookBtn = document.getElementById('bookConsultationBtn');
            if (selectedCategory && selectedPlan) {
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
            if (!selectedCategory || !selectedPlan) {
                alert('相談内容とプランを選択してください');
                return;
            }

            // 予約画面に遷移
            showBookingCalendar();
        }

        function showBookingCalendar() {
            const content = document.getElementById('expertConsultationContent');
            if (content) {
                // プラン情報を取得
                const planDetails = {
                    'basic': { name: '基本相談 (30分)', price: '¥8,800', duration: '30分' },
                    'standard': { name: '詳細相談 (60分)', price: '¥15,400', duration: '60分' },
                    'premium': { name: '包括相談 (90分)', price: '¥22,000', duration: '90分' }
                };

                const categoryNames = {
                    'business_improvement': '業務改善助成金',
                    'career_up': 'キャリアアップ助成金',
                    'human_development': '人材開発支援助成金',
                    'comprehensive': '総合相談'
                };

                content.innerHTML = `
                    <div style="margin-bottom: 2rem;">
                        <button onclick="showExpertConsultation()" style="background: #6b7280; color: white; border: none; padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; font-size: 0.9rem; margin-bottom: 1rem;">
                            ← 相談内容選択に戻る
                        </button>

                        <div style="background: #f9fafb; border: 1px solid #d1d5db; border-radius: 8px; padding: 1rem; margin-bottom: 2rem;">
                            <h4 style="color: #374151; margin: 0 0 0.5rem 0;">選択内容</h4>
                            <p style="margin: 0; color: #6b7280;"><strong>相談内容:</strong> ${categoryNames[selectedCategory]}</p>
                            <p style="margin: 0; color: #6b7280;"><strong>プラン:</strong> ${planDetails[selectedPlan].name} - ${planDetails[selectedPlan].price}</p>
                        </div>

                        <div style="text-align: center;">
                            <h3 style="color: #374151; margin-bottom: 1rem;">🗓️ 日時選択・決済</h3>
                            <div style="background: #fef3c7; border: 1px solid #f59e0b; border-radius: 8px; padding: 2rem; margin: 2rem 0;">
                                <p style="font-size: 1.1rem; margin: 0; color: #92400e;">
                                    <strong>Calendly予約システム連携</strong><br>
                                    <span style="font-size: 0.9rem;">決済完了後、予約カレンダーが表示されます</span>
                                </p>
                            </div>

                            <button onclick="proceedToPayment()" style="background: #059669; color: white; border: none; padding: 1rem 2rem; border-radius: 8px; font-size: 1.1rem; font-weight: 600; cursor: pointer; margin-top: 1rem;">
                                💳 決済に進む (${planDetails[selectedPlan].price})
                            </button>
                        </div>
                    </div>
                `;
            }
        }

        function proceedToPayment() {
            if (!selectedCategory || !selectedPlan) {
                alert('相談内容とプランを選択してください');
                return;
            }

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

            // Stripe決済API呼び出し
            fetch('/api/payment/consultation', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${user?.accessToken || ''}`
                },
                body: JSON.stringify({
                    plan_type: selectedPlan,
                    consultation_category: selectedCategory
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
                showBookingCalendar();
            });
        }
