from flask import Flask, render_template, jsonify, request
import requests
import json
import os  # osモジュールを追加

app = Flask(__name__)

# OpenRouter API設定
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    print("警告: 環境変数 'OPENROUTER_API_KEY' が設定されていません。API呼び出しは失敗します。")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

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
    if keyword:
        instruction = f"「{keyword}」というキーワードに必ず関連した、明るく楽しい雑談テーマを1つ考えてください。"
    else:
        instruction = "明るく楽しい雑談テーマを1つ考えてください。"

    existing_themes = ", ".join(generated_themes) if generated_themes else "なし"
    return instruction + base_prompt.replace("{existing_themes}", existing_themes)


# OpenRouter API呼び出し
def call_openrouter_api(prompt, model="openai/gpt-4.1-nano", temperature=0.7, max_tokens=150):
    if not OPENROUTER_API_KEY:
        print("エラー: APIキーが設定されていません。")
        return None, "APIキー未設定エラー"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "あなたは指示に従ってテキストを生成するアシスタントです。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    try:
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        content = response.json()['choices'][0]['message']['content']
        return content, None
    except requests.exceptions.Timeout:
        return None, "タイムアウトエラー"
    except requests.exceptions.RequestException as e:
        if response.status_code == 401:
            return None, "APIキー認証エラー"
        return None, f"APIリクエストエラー ({response.status_code})"
    except (KeyError, IndexError, json.JSONDecodeError):
        return None, "API応答解析エラー"
    except Exception as e:
        return None, f"予期せぬAPIエラー: {e}"


# テーマ生成関数（2ステップ対応版）
def generate_theme(keyword=None, specific=False):
    STEP1_MAX_RETRIES = 5
    STEP2_MAX_RETRIES = 3

    if specific and keyword:
        # --- Step 1: 具体名取得 ---
        specific_item = None
        last_generated_item = None
        consecutive_duplicates = 0

        for attempt in range(STEP1_MAX_RETRIES):
            print(f"Step 1: 具体名取得試行 {attempt + 1}/{STEP1_MAX_RETRIES}")

            avoid_instruction = ""
            if consecutive_duplicates >= 3 and last_generated_item:
                avoid_instruction = f"\n**重要:** 前回の試行で生成された「{last_generated_item}」は**絶対に避けてください**。"

            step1_prompt = f"""
キーワード「{keyword}」に関連する**完全な固有名詞または特定のキャラクター/作品名**を**1つだけ**挙げてください。{avoid_instruction}
例：
- キーワードが「戦国武将」なら、「織田信長」や「武田信玄」
- キーワードが「アニメ」なら、「鬼滅の刃」や「呪術廻戦」
- キーワードが「ドラゴンボール」なら、「孫悟空」や「フリーザ」
出力は名前だけ。既存テーマ重複禁止: {", ".join(generated_themes) if generated_themes else "なし"}
"""
            content, error = call_openrouter_api(step1_prompt, max_tokens=50)

            if error:
                consecutive_duplicates = 0
                if error == "APIキー認証エラー":
                    break
                continue

            if content:
                potential_item = content.strip().replace("\"", "").replace("「", "").replace("」", "")
                if 0 < len(potential_item) < 50:
                    if potential_item == last_generated_item:
                        consecutive_duplicates += 1
                        print(f"    -> 連続重複 {consecutive_duplicates} 回目")
                    else:
                        specific_item = potential_item
                        last_generated_item = potential_item
                        consecutive_duplicates = 1
                        print(f"Step 1 成功: 具体名「{specific_item}」を取得")
                        break
                else:
                    consecutive_duplicates = 0
            else:
                consecutive_duplicates = 0

        if not specific_item:
            return {"theme": "ハズレ", "hint": "うまく具体化できなかったみたい…もう一度試すかキーワードを変えてみて！"}

        # --- Step 2: 話題生成 ---
        for attempt in range(STEP2_MAX_RETRIES):
            print(f"Step 2: 話題生成試行 {attempt + 1}/{STEP2_MAX_RETRIES} (具体名: {specific_item})")
            step2_prompt = f"""
「{specific_item}」というキーワード({keyword}に含まれる)に必ず関連した、楽しい雑談テーマを1つ考えてください。

形式は以下のJSON形式で**必ず**返してください。
```json
{{
    "theme": "具体的な話題",
    "hint": "会話のきっかけ"
}}
```
生成済みテーマ重複禁止: {", ".join(generated_themes) if generated_themes else "なし"}
"""
            content, error = call_openrouter_api(step2_prompt)

            if error:
                if error == "APIキー認証エラー":
                    break
                continue

            if content:
                try:
                    cleaned = content.strip().removeprefix("```json").removesuffix("```").strip()
                    data = json.loads(cleaned)
                    theme, hint = data.get("theme"), data.get("hint")
                    if theme and hint and theme not in generated_themes:
                        generated_themes.add(theme)
                        print(f"Step 2 成功: テーマ「{theme}」")
                        return {"theme": theme, "hint": hint}
                    elif theme in generated_themes:
                        print(f"Step 2 テーマ重複: {theme}")
                except json.JSONDecodeError:
                    print(f"Step 2 JSON解析エラー: {content}")

        return {"theme": "ハズレ", "hint": f"「{specific_item}」からうまく話題を作れなかった…ごめんね！"}

    # --- specific=False または keyword なし ---
    NORMAL_MAX_RETRIES = 3
    for attempt in range(NORMAL_MAX_RETRIES):
        print(f"通常生成試行 {attempt + 1}/{NORMAL_MAX_RETRIES}")
        full_prompt = create_prompt(keyword, specific=False)
        content, error = call_openrouter_api(full_prompt)

        if error:
            if error == "APIキー認証エラー":
                break
            continue

        if content:
            try:
                cleaned = content.strip().removeprefix("```json").removesuffix("```").strip()
                data = json.loads(cleaned)
                theme, hint = data.get("theme"), data.get("hint")
                if theme and hint and theme not in generated_themes:
                    generated_themes.add(theme)
                    print(f"通常生成成功: テーマ「{theme}」")
                    return {"theme": theme, "hint": hint}
                elif theme in generated_themes:
                    print(f"通常生成 テーマ重複: {theme}")
            except json.JSONDecodeError:
                print(f"通常生成 JSON解析エラー: {content}")

    return {"theme": "ハズレ", "hint": "空のカプセルが出てきちゃった！もう一度回そう"}


# Flask ルート
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/spin")
def spin():
    keyword = request.args.get("keyword")
    is_specific = request.args.get("specific") == "true"
    theme = generate_theme(keyword, specific=is_specific)
    return jsonify(theme)


if __name__ == "__main__":
    app.run(debug=True)
