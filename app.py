from flask import Flask, render_template, jsonify, request
import requests
import json
import os

app = Flask(__name__)

# ----------------------- OpenRouter API 設定 -----------------------
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    print("警告: 環境変数 'OPENROUTER_API_KEY' が設定されていません。API 呼び出しは失敗します。")

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# ----------------------- グローバル状態 -----------------------
generated_themes: set[str] = set()          # 生成済みテーマ
last_specific_item: str | None = None       # 直近の具体名
consecutive_specific_duplicates: int = 0    # 同じ具体名が連続した回数

# ----------------------- ヘルパー -----------------------
def create_prompt(keyword: str | None = None) -> str:
    base_prompt = """
    形式は以下のJSON形式で返してください。
    {
        "theme": "具体的な話題",
        "hint":  "会話のきっかけ"
    }

    以下の条件を厳守してください:
    - 楽しく盛り上がる現実的なお題
    - 恋愛・仕事・学校など身近な話題も含む
    - ユーモアがあり想像しやすい
    - 既に生成したテーマと重複しない: {existing_themes}
    """

    instruction = (
        f"「{keyword}」というキーワードに必ず関連した、明るく楽しい雑談テーマを1つ考えてください。"
        if keyword else
        "明るく楽しい雑談テーマを1つ考えてください。"
    )

    existing = ", ".join(generated_themes) if generated_themes else "なし"
    return (instruction + base_prompt).replace("{existing_themes}", existing)

def call_openrouter_api(prompt: str,
                        model: str = "openai/gpt-4.1-nano",
                        temperature: float = 0.7,
                        max_tokens: int = 150):
    if not OPENROUTER_API_KEY:
        return None, "APIキー未設定エラー"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type":  "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "あなたは指示に従ってテキストを生成するアシスタントです。"},
            {"role": "user",   "content": prompt}
        ],
        "temperature": temperature,
        "max_tokens":  max_tokens
    }

    try:
        r = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, timeout=30)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"], None
    except requests.exceptions.Timeout:
        return None, "タイムアウトエラー"
    except requests.exceptions.RequestException as e:
        if r.status_code == 401:
            return None, "APIキー認証エラー"
        return None, f"APIリクエストエラー ({r.status_code})"
    except (KeyError, IndexError, json.JSONDecodeError):
        return None, "API応答解析エラー"
    except Exception:
        return None, "予期せぬAPIエラー"

# ----------------------- メイン生成ロジック -----------------------
def generate_theme(keyword: str | None = None, specific: bool = False):
    global last_specific_item, consecutive_specific_duplicates

    STEP1_MAX_RETRIES = 6
    STEP2_MAX_RETRIES = 3

    # ---------- specific = True : 2ステップ ----------
    if specific and keyword:
        specific_item = None

        # --- Step 1: 具体名取得 ---
        for attempt in range(STEP1_MAX_RETRIES):
            print(f"Step 1: 具体名取得試行 {attempt + 1}/{STEP1_MAX_RETRIES}")

            avoid_instruction = ""
            if consecutive_specific_duplicates >= 3 and last_specific_item:
                avoid_instruction = (
                    f"\n**重要:** 前回の試行で生成された「{last_specific_item}」は**絶対に避けてください**。"
                )
                print(f"    -> 「{last_specific_item}」を避けるように指示を追加")

            step1_prompt = f"""
キーワード「{keyword}」に関連する固有名詞または特定キャラクター/作品名を**1つだけ**挙げてください。{avoid_instruction}
出力はその具体名のみ (例: 織田信長)
"""

            content, err = call_openrouter_api(step1_prompt, max_tokens=50)
            if err:
                print("Step 1 エラー:", err)
                if err == "APIキー認証エラー":
                    break
                continue

            potential_item = (content or "").strip().strip("「」\"")
            if not potential_item or len(potential_item) >= 50:
                print("Step 1 不適切応答:", content)
                continue

            print(f"    -> 取得候補: 「{potential_item}」")

            # 重複チェック
            if potential_item == last_specific_item:
                consecutive_specific_duplicates += 1
                print(f"    -> 連続重複 {consecutive_specific_duplicates} 回目")
                continue

            # 新しい具体名確定
            specific_item = potential_item
            last_specific_item = potential_item
            consecutive_specific_duplicates = 1
            print(f"Step 1 成功: 具体名「{specific_item}」を取得")
            break

        if not specific_item:
            print("Step 1 失敗: 具体名取得不能")
            return {"theme": "ハズレ",
                    "hint": "うまく具体化できなかったみたい…もう一度試すかキーワードを変えてみて！"}

        # --- Step 2: 話題生成 ---
        for attempt in range(STEP2_MAX_RETRIES):
            print(f"Step 2: 話題生成試行 {attempt + 1}/{STEP2_MAX_RETRIES}")
            step2_prompt = f"""
「{specific_item}」({keyword})に必ず関連した、楽しい雑談テーマを1つ考えてください。
次の JSON 形式で返してください:
{{
  "theme": "具体的な話題",
  "hint":  "会話のきっかけ"
}}
生成済みテーマと重複禁止: {', '.join(generated_themes) if generated_themes else 'なし'}
"""
            content, err = call_openrouter_api(step2_prompt)
            if err:
                print("Step 2 エラー:", err)
                continue

            try:
                cleaned = content.strip().removeprefix("```json").removesuffix("```").strip()
                data = json.loads(cleaned)
                theme, hint = data.get("theme"), data.get("hint")
            except Exception:
                print("Step 2 JSON パースエラー:", content)
                continue

            if theme and hint and theme not in generated_themes:
                generated_themes.add(theme)
                print(f"Step 2 成功: テーマ「{theme}」")
                return {"theme": theme, "hint": hint}

        # すべて失敗
        return {"theme": "ハズレ",
                "hint": f"「{specific_item}」からうまく話題を作れなかった…ごめんね！"}

    # ---------- specific = False : 1ステップ ----------
    NORMAL_MAX_RETRIES = 3
    for attempt in range(NORMAL_MAX_RETRIES):
        print(f"通常生成試行 {attempt + 1}/{NORMAL_MAX_RETRIES}")
        prompt = create_prompt(keyword)
        content, err = call_openrouter_api(prompt)
        if err:
            print("通常生成エラー:", err)
            continue

        try:
            cleaned = content.strip().removeprefix("```json").removesuffix("```").strip()
            data = json.loads(cleaned)
            theme, hint = data.get("theme"), data.get("hint")
        except Exception:
            print("通常生成 JSON パースエラー:", content)
            continue

        if theme and hint and theme not in generated_themes:
            generated_themes.add(theme)
            print(f"通常生成成功: テーマ「{theme}」")
            return {"theme": theme, "hint": hint}

    return {"theme": "ハズレ", "hint": "空のカプセルが出てきちゃった！もう一度回そう"}

# ----------------------- Flask Routes -----------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/spin")
def spin():
    keyword = request.args.get("keyword")
    is_specific = request.args.get("specific") == "true"
    return jsonify(generate_theme(keyword, specific=is_specific))
