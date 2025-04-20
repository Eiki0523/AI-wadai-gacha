from flask import Flask, render_template, jsonify, request
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

# プロンプトを生成するヘルパー関数 (specific=False または keywordなし の場合のみ担当)
def create_prompt(keyword=None, specific=False): # specific引数はgenerate_themeからの呼び出し整合性のために残す
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

    以下の条件を厳守してください:
    - 楽しくて盛り上がる話題
    - 現実的でリアルなお題含む
    - 恋愛や仕事、学校に関する話題含む
    - 想像が膨らみやすい話題含む
    - ユーモアがあるお題含む
    - 具体的で想像しやすいお題とヒント
    - 今までに生成した以下のテーマとは被らないように: {existing_themes}
    """

    # specific=True の場合のプロンプト生成は generate_theme 内の step1_prompt/step2_prompt で直接行うため、
    # この関数では specific=False または keyword なしの場合のみを扱う。
    if keyword:
        # キーワードあり、かつ specific=False の場合
        instruction = f"「{keyword}」というキーワードに必ず関連した、明るく楽しい雑談テーマを1つ考えてください。"
        prompt = instruction + base_prompt
    else:
        # キーワードなしの場合 (specific=False)
        instruction = "明るく楽しい雑談テーマを1つ考えてください。"
        prompt = instruction + base_prompt

    # 既存テーマをプロンプトに追加
    existing_themes_str = ", ".join(generated_themes) if generated_themes else "なし"
    full_prompt = prompt.replace("{existing_themes}", existing_themes_str)
    return full_prompt

# API呼び出しを行うヘルパー関数
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
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, timeout=30) # タイムアウト設定
        response.raise_for_status()
        result = response.json()
        content = result['choices'][0]['message']['content']
        return content, None # 成功時はコンテンツとNone(エラーなし)を返す
    except requests.exceptions.Timeout:
        print("APIリクエストがタイムアウトしました。")
        return None, "タイムアウトエラー"
    except requests.exceptions.RequestException as e:
        print(f"APIリクエストエラー: {e}")
        # 401エラーの場合は特別なメッセージを出すなど、詳細なハンドリングも可能
        if response.status_code == 401:
             return None, "APIキー認証エラー"
        return None, f"APIリクエストエラー ({response.status_code})"
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        print(f"API応答の解析エラー: {e}")
        return None, "API応答解析エラー"
    except Exception as e:
        print(f"予期せぬAPI関連エラー: {e}")
        return None, "予期せぬAPIエラー"

# テーマ生成関数（2ステップ対応版）
def generate_theme(keyword=None, specific=False):
    MAX_RETRIES = 3

    if specific and keyword:
        # --- Step 1: 具体名を取得 ---
        specific_item = None
        for attempt in range(MAX_RETRIES):
            print(f"Step 1: 具体名取得試行 {attempt + 1}/{MAX_RETRIES}")
            step1_prompt = f"""
キーワード「{keyword}」内に含まれる具体的な対象（固有名詞や種類名）を**1つだけ**単語で挙げてください。
例：
- キーワードが「アニメ」なら、「鬼滅の刃」や「呪術廻戦」など具体的な作品名を1つ。
- キーワードが「ドラゴンボール」なら、「孫悟空」や「フリーザ」など具体的なキャラクター名を1つ。
出力は、選んだ具体名**だけ**をテキストで返してください。例：「飛行機」
既存のテーマリストとは被らないようにしてください: {", ".join(generated_themes) if generated_themes else "なし"}
"""
            content, error = call_openrouter_api(step1_prompt, max_tokens=50) # 具体名なので短いトークンで十分

            if error:
                print(f"Step 1 エラー: {error}")
                if error == "APIキー認証エラー": break # 認証エラーならリトライしない
                continue # 他のエラーならリトライ

            if content:
                # 簡単なバリデーション（空でないか、長すぎないかなど）
                potential_item = content.strip().replace("\"", "").replace("「", "").replace("」", "") # 不要な文字を除去
                if 0 < len(potential_item) < 50: # 短すぎず長すぎない
                    specific_item = potential_item
                    print(f"Step 1 成功: 具体名「{specific_item}」を取得")
                    break # 成功したらループを抜ける
                else:
                    print(f"Step 1 取得内容が不適切: {content}")
            else:
                 print("Step 1 応答が空でした。")
            # 成功しなかった場合はリトライ

        if not specific_item:
            print("Step 1: 最大試行回数でも具体名を取得できませんでした。")
            return {"theme": "ハズレ", "hint": "うまく具体化できなかったみたい…もう一度試すかキーワードを変えてみて！"}

        # --- Step 2: 具体名から話題を生成 ---
        for attempt in range(MAX_RETRIES):
            print(f"Step 2: 話題生成試行 {attempt + 1}/{MAX_RETRIES} (具体名: {specific_item})")
            step2_prompt = f"""
「{specific_item}」というキーワードに必ず関連した、楽しい雑談テーマを1つ考えてください。

形式は以下のJSON形式で**必ず**返してください。
```json
{{
    "theme": "具体的な話題",
    "hint": "会話のきっかけ"
}}
```
例：
```json
{{
    "theme": "飛行機に乗るときのワクワク感",
    "hint": "窓側の席が好き？通路側？離陸の瞬間のGがかかる感じ、たまらないよね！"
}}
```
```json
{{
    "theme": "我愛羅と戦うならどんな戦略を立てるか",
    "hint": "あの大量の砂を捌いて完全勝利を収めるにはどうすれば良いか考えてみよう"
}}
```
生成済みのテーマとは被らないようにしてください: {", ".join(generated_themes) if generated_themes else "なし"}
"""
            content, error = call_openrouter_api(step2_prompt) # 通常のトークン数

            if error:
                print(f"Step 2 エラー: {error}")
                if error == "APIキー認証エラー": break
                continue

            if content:
                try:
                    # マークダウン形式の除去を試みる
                    cleaned_content_str = content.strip().removeprefix("```json").removesuffix("```").strip()
                    theme_data = json.loads(cleaned_content_str)
                    theme = theme_data.get("theme")
                    hint = theme_data.get("hint")

                    if theme and hint and theme not in generated_themes:
                        generated_themes.add(theme)
                        print(f"Step 2 成功: テーマ「{theme}」")
                        return {"theme": theme, "hint": hint}
                    elif theme in generated_themes:
                        print(f"Step 2 テーマ重複: {theme}")
                    else:
                        print(f"Step 2 JSON形式不正: {content}")

                except json.JSONDecodeError:
                    print(f"Step 2 JSONパースエラー: {content}")
            else:
                print("Step 2 応答が空でした。")
            # 成功しなかった場合はリトライ

        print(f"Step 2: 最大試行回数でも話題を生成できませんでした (具体名: {specific_item})。")
        return {"theme": "ハズレ", "hint": f"「{specific_item}」からうまく話題を作れなかった…ごめんね！"}

    else:
        # --- specific=False または keywordなし の場合 (従来通り) ---
        for attempt in range(MAX_RETRIES):
            print(f"通常生成試行 {attempt + 1}/{MAX_RETRIES}")
            # create_prompt はキーワードのみ、またはキーワードなしのプロンプトを生成
            full_prompt = create_prompt(keyword, specific=False) # specific=False を明示
            # JSON形式を期待するプロンプトなので、system メッセージも調整
            system_message = "あなたは楽しい会話のテーマをJSON形式で考えるアシスタントです。"
            # API呼び出し (call_openrouter_api を使うように変更)
            content, error = call_openrouter_api(full_prompt) # model, temp, max_tokens はデフォルト値を使用

            if error:
                print(f"通常生成エラー: {error}")
                if error == "APIキー認証エラー": break
                continue # 他のエラーならリトライ

            if content:
                try:
                    cleaned_content_str = content.strip().removeprefix("```json").removesuffix("```").strip()
                    theme_data = json.loads(cleaned_content_str)
                    theme = theme_data.get("theme")
                    hint = theme_data.get("hint")

                    if theme and hint and theme not in generated_themes:
                        generated_themes.add(theme)
                        print(f"通常生成成功: テーマ「{theme}」")
                        return {"theme": theme, "hint": hint}
                    elif theme in generated_themes:
                        print(f"通常生成 テーマ重複: {theme}")
                    else:
                        print(f"通常生成 JSON形式不正: {content}")
                except json.JSONDecodeError:
                    print(f"通常生成 JSONパースエラー: {content}")
            else:
                print("通常生成 応答が空でした。")
            # 成功しなかった場合はリトライ

        print("通常生成: 最大試行回数でもユニークなテーマを取得できませんでした。")
        return {"theme": "ハズレ", "hint": "空のカプセルが出てきちゃった！もう一度回そう"}


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
