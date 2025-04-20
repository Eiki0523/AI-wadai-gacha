import random
import time
from themes import conversation_themes

def spin_gacha():
    print("雑談ガチャを回します...")
    time.sleep(1)
    print("ドキドキ...")
    time.sleep(1.5)
    print("ガチャン！")
    time.sleep(0.5)
    
    selected = random.choice(conversation_themes)
    print("\n＝＝＝ 結果 ＝＝＝")
    print(f"今日の雑談テーマ: {selected['theme']}")
    print(f"話題のヒント: {selected['hint']}")
    print("＝＝＝＝＝＝＝＝＝\n")

if __name__ == "__main__":
    print("ようこそ雑談ガチャへ！")
    while True:
        input("Enterキーを押してガチャを回す (終了するにはCtrl+C) > ")
        spin_gacha()
