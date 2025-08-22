# exporter.py
import os
import json
import shutil
import datetime

# --- 常數設定 ---
# 假設此腳本與 manager.py 在同一個目錄下
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PAGES_DIR = os.path.join(SCRIPT_DIR, "pages")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "out")
MAIN_INDEX_FILE = os.path.join(PAGES_DIR, 'index.json')

def get_target_date():
    """
    提示使用者輸入一個日期，並驗證其格式是否為 YYYY-MM-DD。
    如果格式不正確，將要求使用者重新輸入。
    """
    while True:
        date_str = input("請輸入要匯出的日期 (格式 YYYY-MM-DD): ")
        try:
            # 嘗試將輸入的字串解析為日期物件，以驗證格式
            datetime.datetime.strptime(date_str, '%Y-%m-%d')
            return date_str
        except ValueError:
            print("無效的日期格式，請確保您的輸入格式為 YYYY-MM-DD。")

def main():
    """
    主執行函數：
    1. 獲取使用者指定的日期。
    2. 檢查必要的檔案和資料夾是否存在。
    3. 建立輸出資料夾。
    4. 讀取主索引檔以獲取所有車輛列表。
    5. 遍歷每輛車，檢查其圖片索引中是否有符合日期的照片。
    6. 如果找到符合的照片，將其複製到 'out' 資料夾。
    7. 將找到的車輛資訊整理起來，準備寫入檔案。
    8. 生成 'out.txt' 檔案，其中包含所有找到的車輛資訊。
    9. 顯示最終處理結果。
    """
    # 步驟 1: 獲取使用者輸入的目標日期
    target_date = get_target_date()
    print(f"\n正在搜尋拍攝日期為 '{target_date}' 的所有照片...")

    # 步驟 2: 檢查 'pages' 資料夾和主索引檔是否存在
    if not os.path.exists(MAIN_INDEX_FILE):
        print(f"錯誤：找不到主索引檔 '{MAIN_INDEX_FILE}'。")
        print("請確認此腳本是否與 manager.py 在同一個資料夾，且 'pages' 資料夾已存在。")
        return

    # 步驟 3: 建立輸出資料夾 'out'，如果它不存在的話
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"已建立輸出資料夾: '{os.path.abspath(OUTPUT_DIR)}'")

    # 步驟 4: 讀取主索引檔
    try:
        with open(MAIN_INDEX_FILE, 'r', encoding='utf-8') as f:
            main_index_data = json.load(f)
    except json.JSONDecodeError:
        print(f"錯誤：主索引檔 '{MAIN_INDEX_FILE}' 格式損毀，無法解析。")
        return

    # 步驟 5 & 6: 處理所有車輛，尋找並複製照片
    found_photos_count = 0
    # 使用一個字典來儲存所有找到照片的車輛資訊，可避免重複記錄
    vehicles_with_photos = {}

    # 遍歷主索引中的每一輛車
    for plate, vehicle_info in main_index_data.items():
        vehicle_dir = os.path.join(PAGES_DIR, plate)
        vehicle_index_path = os.path.join(vehicle_dir, 'index.json')

        if not os.path.exists(vehicle_index_path):
            continue  # 如果車輛的索引檔不存在，則跳過

        try:
            with open(vehicle_index_path, 'r', encoding='utf-8') as f:
                vehicle_index_data = json.load(f)
        except json.JSONDecodeError:
            print(f"警告：'{plate}' 的索引檔格式錯誤，已跳過。")
            continue

        # 遍歷該車輛的所有圖片記錄
        for image_name, image_info in vehicle_index_data.items():
            if image_info.get("date") == target_date:
                # 日期相符，執行複製操作
                source_path = os.path.join(vehicle_dir, image_name)
                dest_path = os.path.join(OUTPUT_DIR, image_name)

                if os.path.exists(source_path):
                    try:
                        shutil.copy2(source_path, dest_path)
                        print(f"  > 已複製: {image_name}")
                        found_photos_count += 1
                        
                        # 如果這輛車是第一次被找到，就記錄它的資訊
                        if plate not in vehicles_with_photos:
                            vehicles_with_photos[plate] = vehicle_info
                    except Exception as e:
                        print(f"錯誤：複製檔案 '{image_name}' 時失敗: {e}")
                else:
                    print(f"警告：索引中存在 '{image_name}' 的記錄，但找不到實體檔案。")

    # 步驟 7 & 8: 產生報告檔案並顯示總結
    if found_photos_count > 0:
        output_info_file = os.path.join(OUTPUT_DIR, "out.txt")

        try:
            with open(output_info_file, 'w', encoding='utf-8') as f:
                # 為了讓輸出順序固定，對車牌號進行排序
                sorted_plates = sorted(vehicles_with_photos.keys())
                
                # --- 主要變更點 ---
                # 將日期中的 '-' 替換為 '/'
                output_date_format = target_date.replace('-', '/')
                
                for i, plate in enumerate(sorted_plates):
                    info = vehicles_with_photos[plate]
                    
                    # 組合文字區塊
                    year = info.get("year", "年份不詳")
                    manufacturer = info.get("manufacturer", "廠牌不詳")
                    model = info.get("model", "型號不詳")
                    company = info.get("company", "客運不詳")
                    
                    f.write(f"{plate}\n")
                    f.write(f"{year} {manufacturer} {model}\n")
                    # 使用新的日期格式寫入檔案
                    f.write(f"{output_date_format}\n\n")
                    f.write(f"#{company}\n")

                    # 在每個車輛資訊塊之間插入兩行空行（最後一個除外）
                    if i < len(sorted_plates) - 1:
                        f.write("\n\n")

            print("-" * 40)
            print("處理完成！")
            print(f"總共複製了 {found_photos_count} 張照片至 '{os.path.abspath(OUTPUT_DIR)}' 資料夾。")
            print(f"車輛資訊已寫入 '{os.path.abspath(output_info_file)}'。")

        except Exception as e:
            print(f"錯誤：寫入資訊檔案 '{output_info_file}' 時失敗: {e}")

    else:
        print("-" * 40)
        print(f"完成搜尋，但在 '{target_date}' 這天找不到任何照片。")

if __name__ == "__main__":
    main()