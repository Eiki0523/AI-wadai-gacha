from flask import Flask, render_template, jsonify, request
import random
import requests
import json
import os # osモジュールを追加

app = Flask(__name__)

# OpenRouter API設定
# 環境変数からAPIキーを読み込む
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
# APIキーが設定されていない場合のチェック
if not OPENROUTER_API_KEY:
    print("警告: 環境変数 'OPENROUTER_API_KEY' が設定されていません。API呼び出しは失敗します。")
    # 必要に応じて、ここでプログラムを終了させるなどの処理を追加できます
    # raise ValueError("APIキーが設定されていません")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# 明るく楽しい雑談テーマを生成する関数
# 生成済みテーマを記録するセット
generated_themes = set()

# プロンプトを生成するヘルパー関数
def create_prompt(keyword=None, specific=False):
    base_prompt = """
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
    例:
    {
        "theme": "夏の思い出",
        "hint": "子供の頃の夏休みの思い出や、最近の夏の楽しみ方を話してみよう"
    }
    {
        "theme": "映画館で頼む食べ物",
        "hint": "楽しい映画には外せない,美味しいグルメについて語ろう"
    }
    {
        "theme": "学生時代の失敗談",
        "hint": "思い出したくない黒歴史,今だから笑える失敗を思い出そう"
    }
    {
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

    if specific and keyword:
        # 「より具体的に」がチェックされている場合
        instruction = f"「{keyword}」のcharacterを必ず具体的に1種類挙げ,それをテーマにした雑談の話題を考えて。"
        prompt = instruction + base_prompt
    elif keyword:
        # キーワードのみ指定されている場合
        instruction = f"「{keyword}」というキーワードに必ず関連した、明るく楽しい雑談テーマを1つ考えてください。"
        prompt = instruction + base_prompt
    else:
        # キーワードなしの場合
        instruction = "明るく楽しい雑談テーマを1つ考えてください。"
        prompt = instruction + base_prompt

    # 既存テーマをプロンプトに追加
    existing_themes_str = ", ".join(generated_themes) if generated_themes else "なし"
    full_prompt = prompt.replace("{existing_themes}", existing_themes_str)
    return full_prompt

def generate_theme(keyword=None, specific=False): # specific パラメータを追加
    # プロンプト生成をヘルパー関数に任せる
    full_prompt = create_prompt(keyword, specific)
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "openai/gpt-4.1-nano",
        "messages": [
            {"role": "system", "content": "あなたは楽しい会話のテーマを考えるアシスタントです"},
            {"role": "user", "content": full_prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 150
    }

    MAX_RETRIES = 3 # 最大再試行回数

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload)
            response.raise_for_status() # HTTPエラーチェック
            result = response.json()

            # JSON形式で返す
            content_str = result['choices'][0]['message']['content']
            # マークダウンのコードブロック形式を取り除く (復活！)
            cleaned_content_str = content_str.strip().removeprefix("```json").removesuffix("```").strip()
            theme_data = json.loads(cleaned_content_str) # JSONパース
            theme = theme_data.get("theme", "楽しい話題")
            hint = theme_data.get("hint", "おもろい話")

            # テーマが重複していないか確認
            if theme not in generated_themes:
                generated_themes.add(theme)
                # print(f"新しいテーマを追加: {theme}") # デバッグ用
                return { # 成功！テーマを返す
                    "theme": theme,
                    "hint": hint
                }
            else:
                # 重複した場合
                print(f"テーマ「{theme}」が重複しました。再抽選します。(試行 {attempt + 1}/{MAX_RETRIES})")
                # 次のループで再試行

        except requests.exceptions.RequestException as e:
            print(f"APIリクエストエラー (試行 {attempt + 1}/{MAX_RETRIES}): {e}")
            # リクエスト自体に失敗した場合はループを抜けてハズレを返す
            break
        except json.JSONDecodeError as e:
             print(f"JSONパースエラー (試行 {attempt + 1}/{MAX_RETRIES}): {e}")
             # パースできなかった内容を表示 (cleaned_content_str の前なので元の content_str を表示)
             print(f"応答内容: {content_str}")
             # JSONパースに失敗した場合もループを抜けてハズレを返す
             break
        except Exception as e:
            # その他の予期せぬエラー
            print(f"予期せぬエラー (試行 {attempt + 1}/{MAX_RETRIES}): {e}")
            break # ループを抜けてハズレを返す

    # ループが完了してもユニークなテーマが見つからなかった場合、または途中でエラーが発生した場合
    print(f"{MAX_RETRIES}回の試行でユニークなテーマを取得できませんでした。")
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
    # specific パラメータを取得 (文字列 'true' かどうかで判定)
    is_specific = request.args.get('specific') == 'true'
    theme = generate_theme(keyword, specific=is_specific) # specific を渡す
    return jsonify(theme)
