from flask import Flask, render_template, jsonify, request
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

def generate_theme(keyword=None):
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
        
        "theme": "映画館で頼む食べ物",
        "hint": "楽しい映画には外せない,美味しいグルメについて語ろう"
        
        "theme": "学生時代の失敗談",
        "hint": "思い出したくない黒歴史,今だから笑える失敗を思い出そう"
        
        "theme": "異世界に行ったら何をしたい？",
        "hint": "もし異世界に行ったら魔法使いとして旅に出る？街で商売して大儲け？"
    }
    
    以下の条件を厳守してください:
    - 楽しくて盛り上がる話題
    - 現実的でリアルなお題含む
    - 恋愛や仕事、学校に関する話題含む
    - 想像が膨らみやすい話題含む
    - ユーモアがあるお題含む
    - 具体的で想像しやすいお題とヒント
    - 今までに生成した以下のテーマとは被らないように: {existing_themes}
    """
    
    if keyword:
        prompt += f"\n    - 必ず以下のキーワードに関連した話題にすること: {keyword}"
    
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
        hint = theme_data.get("hint", "おもろい話")
        
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
            "theme": "ハズレ", 
            "hint": "空のカプセルが出てきちゃった！もう一度回そう"
        }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/spin')
def spin():
    keyword = request.args.get('keyword')
    theme = generate_theme(keyword)
    return jsonify(theme)

if __name__ == '__main__':
    app.run(debug=True)
