from flask import Flask, render_template, jsonify
import random
import requests
import json

app = Flask(__name__)

# OpenRouter API設定
OPENROUTER_API_KEY = "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"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# 明るく楽しい雑談テーマを生成する関数
# 生成済みテーマを記録するセット
generated_themes = set()

def generate_theme():
    prompt = """
    明るく楽しい雑談テーマを1つ考えてください。
    形式は以下のJSON形式で返してください。
    {
        "theme": "具体的な話題",
        "hint": "会話のきっかけ"
    }
    例:
    {
        "theme": "夏の思い出",
        "hint": "子供の頃の夏休みの思い出や、最近の夏の楽しみ方を話してみよう"
    }
    
    以下の条件を厳守してください:
    - 楽しくて思わず考えたくなる話題
    - 空想や想像が膨らみやすい話題含む
    - 恋愛や仕事、学校に関する話題含む
    - 思わず笑うようなユーモアがあるお題含む
    - 具体的で想像しやすいヒント
    - 暗い話題は出さないこと
    - 今までに生成した以下のテーマとは被らないように: {existing_themes}
    """
    
    # 既存テーマをプロンプトに追加
    existing_themes_str = ", ".join(generated_themes) if generated_themes else "なし"
    full_prompt = prompt.replace("{existing_themes}", existing_themes_str)
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "openai/gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": "あなたは楽しい会話のテーマを考えるアシスタントです"},
            {"role": "user", "content": full_prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 150
    }
    
    try:
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        
        # JSON形式で返す
        theme_data = json.loads(result['choices'][0]['message']['content'])
        theme = theme_data.get("theme", "楽しい話題")
        hint = theme_data.get("hint", "気軽に話してみましょう")
        
        # テーマが重複していないか確認
        if theme in generated_themes:
            raise ValueError("生成されたテーマが既に存在します")
            
        generated_themes.add(theme)
        return {
            "theme": theme,
            "hint": hint
        }
    except Exception as e:
        print(f"Error generating theme: {e}")
        return {
            "theme": "楽しい話題", 
            "hint": "今日の気分について話してみましょう"
        }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/spin')
def spin():
    theme = generate_theme()
    return jsonify(theme)

if __name__ == '__main__':
    app.run(debug=True)
