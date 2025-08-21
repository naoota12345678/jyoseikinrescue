# コスト計算とトークン管理

class TokenCostCalculator:
    def __init__(self):
        # Claude-3.5-Sonnet料金 (USD per 1M tokens)
        self.input_price = 3.00
        self.output_price = 15.00
        
        # 現在のシステムプロンプトサイズ
        self.full_system_prompt_tokens = 23800
        self.summary_system_prompt_tokens = 2000  # 要約版
        
    def calculate_cost(self, input_tokens, output_tokens):
        """コスト計算（USD）"""
        input_cost = (input_tokens / 1_000_000) * self.input_price
        output_cost = (output_tokens / 1_000_000) * self.output_price
        return input_cost + output_cost
    
    def estimate_current_cost(self, user_question_tokens=100, ai_response_tokens=1000):
        """現在の1回あたりコスト"""
        total_input = self.full_system_prompt_tokens + user_question_tokens
        return self.calculate_cost(total_input, ai_response_tokens)
    
    def estimate_with_history(self, history_tokens=500, user_question_tokens=100, ai_response_tokens=1000):
        """履歴機能ありのコスト"""
        total_input = self.summary_system_prompt_tokens + history_tokens + user_question_tokens
        return self.calculate_cost(total_input, ai_response_tokens)
    
    def cost_savings(self):
        """履歴機能による削減効果"""
        current = self.estimate_current_cost()
        with_history = self.estimate_with_history()
        savings = current - with_history
        savings_percent = (savings / current) * 100
        
        return {
            'current_cost': current,
            'with_history_cost': with_history,
            'savings_usd': savings,
            'savings_percent': savings_percent,
            'savings_jpy': savings * 150  # 1USD=150JPY換算
        }

# 計算実行
calc = TokenCostCalculator()
savings = calc.cost_savings()

print("=== コスト分析結果 ===")
print(f"現在（履歴なし）: ${savings['current_cost']:.4f} ({savings['current_cost']*150:.1f}円)")
print(f"履歴機能あり: ${savings['with_history_cost']:.4f} ({savings['with_history_cost']*150:.1f}円)")
print(f"削減額: ${savings['savings_usd']:.4f} ({savings['savings_jpy']:.1f}円)")
print(f"削減率: {savings['savings_percent']:.1f}%")

print("\n=== 月間コスト試算 ===")
for queries in [100, 500, 1000]:
    current_monthly = savings['current_cost'] * queries
    history_monthly = savings['with_history_cost'] * queries
    monthly_savings = (current_monthly - history_monthly) * 150
    
    print(f"{queries}質問/月:")
    print(f"  現在: {current_monthly*150:.0f}円")
    print(f"  履歴機能: {history_monthly*150:.0f}円")
    print(f"  月間削減: {monthly_savings:.0f}円")
    print()