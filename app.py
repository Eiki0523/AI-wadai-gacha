from flask import Flask, render_template, jsonify, request
import requests
import json
import os
from collections import deque

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
# 直近の具体名を記録するdeque (最大5件)
recent_specific_items = deque(maxlen=5)

# プロンプトを生成するヘルパー関数 (specific=False または keywordなし の場合のみ担当)
def create_prompt(keyword=None, specific=False): # specific引数はgenerate_themeからの呼び出し整合性のために残す
    base_prompt = """
    形式は以下のJSON形式で**必ず**返してください。
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
def call_openrouter_api(prompt, model="openai/gpt-4.1-nano", temperature=0.9, max_tokens=150):
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
            {"role": "system", "content": "あなたは指示に従って多様なテキストを生成するアシスタントです。"},
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
    MAX_RETRIES = 3 # Step2 と 通常生成 の最大リトライ回数
    MAX_STEP1_RETRIES = 7 # Step1 (具体名取得) の最大リトライ回数

    if specific and keyword:
        # --- Step 1: 具体名を取得 ---
        specific_item = None
        for attempt in range(MAX_STEP1_RETRIES): # Step1専用のリトライ回数を使用
            print(f"Step 1: 具体名取得試行 {attempt + 1}/{MAX_STEP1_RETRIES}")
            step1_prompt = f"""
キーワード「{keyword}」に属する**固有名詞またはキャラクター**を被りがないように**1つだけ**挙げてください。
例：
- キーワードが「戦国武将」なら、「織田信長」や「武田信玄」など具体的な武将名を1つ。
- キーワードが「アニメ」なら、「鬼滅の刃」や「呪術廻戦」など具体的な作品名を1つ。
- キーワードが「ドラゴンボール」なら、「孫悟空」や「フリーザ」など具体的なキャラクター名を1つ。
- キーワードが「動物」なら、「アライグマ」や「キリン」など具体的な動物の名を1つ。
出力は、選んだ具体名の単語**だけ**をテキストで返してください。例：「織田信長」
"""
            content, error = call_openrouter_api(step1_prompt, max_tokens=50) # 具体名なので短いトークンで十分

            if error:
                print(f"Step 1 エラー: {error}")
                if error == "APIキー認証エラー": break # 認証エラーならリトライしない
                continue # 他のエラーならリトライ

            # content が返ってきたらバリデーションと重複チェック
            potential_item = content.strip().replace("\"", "").replace("「", "").replace("」", "") # 不要な文字を除去
            if 0 < len(potential_item) < 50:
                if potential_item in recent_specific_items:
                    print(f"Step 1 重複検出: 具体名「{potential_item}」は最近使用されました。再試行します。")
                    continue # 重複している場合は再試行
                else:
                    specific_item = potential_item
                    recent_specific_items.append(specific_item) # 新しい具体名をdequeに追加 (古いものは自動で削除される)
                    print(f"Step 1 成功: 具体名「{specific_item}」を取得 (最近の具体名: {list(recent_specific_items)})")
                    break # 有効で重複しない具体名が見つかったのでループを抜ける
            else:
                print(f"Step 1 取得内容が不適切: {content}")

        if not specific_item:
            print("Step 1: 最大試行回数でも具体名を取得できませんでした。")
            return {"theme": "ハズレ", "hint": "具体名が取得できませんでした。"}

        # --- Step 2: 具体名から話題を生成 ---
        for attempt in range(MAX_RETRIES):
            print(f"Step 2: 話題生成試行 {attempt + 1}/{MAX_RETRIES} (具体名: {specific_item})")
            instruction = f"「{specific_item}」というキーワードに必ず関連した、明るく楽しい雑談テーマを1つ考えてください({keyword}に関する)。"
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
    """
            step2_prompt = instruction + base_prompt
            content, error = call_openrouter_api(step2_prompt) 
            if error:
                print(f"Step 2 エラー: {error}")
                if error == "APIキー認証エラー":
                    break
                continue

            if content:
                try:
                    cleaned = content.strip().removeprefix("```json").removesuffix("```").strip()
                    data  = json.loads(cleaned)
                    theme = data.get("theme")
                    hint  = data.get("hint")

                    # 重複チェック (Step2)
                    if theme in generated_themes:
                        print(f"重複検出 (Step2): {theme} → 再生成")
                        continue

                    generated_themes.add(theme)
                    print(f"Step2 成功: {theme}")
                    return {"theme": theme, "hint": hint}
                except json.JSONDecodeError:
                    print("Step2 JSONパースエラー")
            else:
                print("Step 2 応答が空でした。")

        print(f"Step 2: 最大試行回数でも話題生成に失敗 (具体名: {specific_item})。")
        return {"theme": "ハズレ", "hint": "話題生成に失敗しました。"}

    else:
        # --- specific=False または keywordなし の場合 (通常生成) ---
        for attempt in range(MAX_RETRIES):
            print(f"通常生成試行 {attempt + 1}/{MAX_RETRIES}")
            full_prompt = create_prompt(keyword, specific=False)
            content, error = call_openrouter_api(full_prompt)

            if error:
                print(f"通常生成エラー: {error}")
                if error == "APIキー認証エラー":
                    break
                continue

            if content:
                try:
                    cleaned = content.strip().removeprefix("```json").removesuffix("```").strip()
                    data  = json.loads(cleaned)
                    theme = data.get("theme")
                    hint  = data.get("hint")

                    # 重複チェック (通常生成)
                    if theme in generated_themes:
                        print(f"重複検出 (通常生成): {theme} → 再生成")
                        continue

                    generated_themes.add(theme)
                    print(f"通常生成 成功: {theme}")
                    return {"theme": theme, "hint": hint}
                except json.JSONDecodeError:
                    print("通常生成 JSONパースエラー")
            else:
                print("通常生成 応答が空でした。")

        print("通常生成: 最大試行回数でもユニークなテーマを取得できませんでした。")
        return {"theme": "ハズレ", "hint": "空のカプセルが出てきちゃった！もう一度回そう"}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/spin')
def spin():
    keyword     = request.args.get("keyword")
    is_specific = request.args.get("specific") == "true"
    theme       = generate_theme(keyword, specific=is_specific)
    return jsonify(theme)
