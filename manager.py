import os
import json
import re
import sys  # 用於判斷作業系統
import subprocess  # 用於在 macOS/Linux 開啟檔案
from tkinter import Tk, Frame, Listbox, Label, Entry, Button, Scrollbar, messagebox, StringVar, PanedWindow
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
SUPPORTED_FORMATS = ('.jpg', '.jpeg', '.png', '.bmp', '.gif')


class IndexManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("圖庫索引管理器")

        # --- 資料變數 (無變動) ---
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.pages_dir = os.path.join(self.script_dir, "pages")
        self.main_index_data = {}
        self.vehicle_index_data = {}
        self.current_plate = None
        self.current_image = None

        # --- GUI 元件 ---
        main_pane = PanedWindow(root, orient='horizontal', sashrelief='raised', bg="gray90")
        main_pane.pack(fill='both', expand=True, padx=10, pady=10)

        left_pane = Frame(main_pane, bd=2, relief='sunken')
        main_pane.add(left_pane, width=350)

        right_pane = Frame(main_pane, bd=2, relief='sunken')
        main_pane.add(right_pane)

        # --- 左側：車牌管理 (無變動) ---
        Label(left_pane, text="車輛檔案 (資料夾)", font=("Arial", 12, "bold")).pack(pady=5)
        search_frame = Frame(left_pane, padx=5)
        search_frame.pack(fill='x', pady=5)
        Label(search_frame, text="搜尋車牌:").pack(side='left')
        self.search_var = StringVar()
        search_entry = Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side='left', fill='x', expand=True, padx=5)
        search_entry.bind("<KeyRelease>", self.filter_plates)
        plate_list_frame = Frame(left_pane)
        plate_list_frame.pack(fill='both', expand=True, padx=5, pady=5)
        plate_scrollbar = Scrollbar(plate_list_frame)
        plate_scrollbar.pack(side='right', fill='y')
        self.plates_listbox = Listbox(plate_list_frame, yscrollcommand=plate_scrollbar.set, exportselection=False)
        self.plates_listbox.pack(side='left', fill='both', expand=True)
        plate_scrollbar.config(command=self.plates_listbox.yview)
        self.plates_listbox.bind('<<ListboxSelect>>', self.on_plate_select)
        plate_info_frame = Frame(left_pane)
        plate_info_frame.pack(fill='x', padx=5, pady=10)
        self.company_var, self.year_var, self.manufacturer_var, self.model_var = StringVar(), StringVar(), StringVar(), StringVar()
        labels = ["客運公司:", "車輛年份:", "車輛公司:", "車輛型號:"]
        variables = [self.company_var, self.year_var, self.manufacturer_var, self.model_var]
        for i, (label_text, var) in enumerate(zip(labels, variables)):
            Label(plate_info_frame, text=label_text).grid(row=i, column=0, sticky='w', pady=2)
            entry = Entry(plate_info_frame, textvariable=var)
            entry.grid(row=i, column=1, sticky='ew', pady=2, padx=5)
            entry.bind("<FocusOut>", self.auto_save_main_index_from_ui)
        plate_info_frame.grid_columnconfigure(1, weight=1)

        # --- 右側：圖片管理 ---
        Label(right_pane, text="圖片 (檔案)", font=("Arial", 12, "bold")).pack(pady=5)

        image_list_frame = Frame(right_pane)
        image_list_frame.pack(fill='both', expand=True, padx=5, pady=5)
        image_scrollbar = Scrollbar(image_list_frame)
        image_scrollbar.pack(side='right', fill='y')
        self.images_listbox = Listbox(image_list_frame, yscrollcommand=image_scrollbar.set, exportselection=False)
        self.images_listbox.pack(side='left', fill='both', expand=True)
        image_scrollbar.config(command=self.images_listbox.yview)
        self.images_listbox.bind('<<ListboxSelect>>', self.on_image_select)

        image_info_frame = Frame(right_pane)
        image_info_frame.pack(fill='x', padx=5, pady=10)
        self.image_date_var, self.image_desc_var = StringVar(), StringVar()
        Label(image_info_frame, text="拍攝日期:").grid(row=0, column=0, sticky='w')
        image_date_entry = Entry(image_info_frame, textvariable=self.image_date_var)
        image_date_entry.grid(row=0, column=1, sticky='ew', pady=2)
        Label(image_info_frame, text="圖片說明:").grid(row=1, column=0, sticky='w')
        image_desc_entry = Entry(image_info_frame, textvariable=self.image_desc_var)
        image_desc_entry.grid(row=1, column=1, sticky='ew', pady=2)
        image_info_frame.grid_columnconfigure(1, weight=1)
        image_date_entry.bind("<FocusOut>", self.auto_save_vehicle_index_from_ui)
        image_desc_entry.bind("<FocusOut>", self.auto_save_vehicle_index_from_ui)

        # --- 核心變更：新增「開啟圖片」按鈕 ---
        self.open_image_button = Button(right_pane, text="在外部開啟圖片", command=self.open_image_externally,
                                        state='disabled')
        self.open_image_button.pack(pady=5)

        bottom_frame = Frame(root, padx=5, pady=2)
        bottom_frame.pack(side='bottom', fill='x')
        Button(bottom_frame, text="資料夾健康檢查", command=self.perform_health_check).pack(side='left')
        self.status_label = Label(bottom_frame, text="正在初始化...", bd=1, relief='sunken', anchor='w')
        self.status_label.pack(side='right', fill='x', expand=True)

        self.root.after(100, self.initialize_and_scan_all)

    def on_plate_select(self, event):
        selection_indices = self.plates_listbox.curselection()
        if not selection_indices: return
        self.current_plate = self.plates_listbox.get(selection_indices[0])
        plate_data = self.main_index_data.get(self.current_plate, {})
        self.company_var.set(plate_data.get("company", ""))
        self.year_var.set(plate_data.get("year", ""))
        self.manufacturer_var.set(plate_data.get("manufacturer", ""))
        self.model_var.set(plate_data.get("model", ""))
        self.load_and_display_images()

    def on_image_select(self, event):
        selection_indices = self.images_listbox.curselection()
        if not selection_indices: return
        self.current_image = self.images_listbox.get(selection_indices[0])
        image_data = self.vehicle_index_data.get(self.current_image, {})
        self.image_date_var.set(image_data.get("date", ""))
        self.image_desc_var.set(image_data.get("description", ""))
        self.open_image_button.config(state='normal')  # 啟用按鈕
        self.update_status_progress()

    def open_image_externally(self):
        """使用作業系統預設的應用程式開啟圖片"""
        if not self.current_plate or not self.current_image:
            messagebox.showinfo("提示", "沒有選擇任何圖片。")
            return

        image_path = os.path.join(self.pages_dir, self.current_plate, self.current_image)
        if not os.path.exists(image_path):
            messagebox.showerror("錯誤", f"找不到圖片檔案：\n{image_path}")
            return

        try:
            if sys.platform == "win32":
                os.startfile(image_path)
            elif sys.platform == "darwin":  # macOS
                subprocess.run(["open", image_path], check=True)
            else:  # Linux and other Unix-like
                subprocess.run(["xdg-open", image_path], check=True)
        except Exception as e:
            messagebox.showerror("開啟失敗", f"無法使用預設應用程式開啟圖片。\n錯誤訊息: {e}")

    def clear_right_panels(self):
        self.company_var.set("")
        self.year_var.set("")
        self.manufacturer_var.set("")
        self.model_var.set("")
        self.images_listbox.delete(0, 'end')
        self.current_image = None
        self.clear_image_fields()

    def clear_image_fields(self):
        self.image_date_var.set("")
        self.image_desc_var.set("")
        self.open_image_button.config(state='disabled')  # 清除時禁用按鈕

    # --- 以下是其他未變動的函式 ---
    def initialize_and_scan_all(self):
        self._sync_main_index()
        self.status_label.config(text="正在掃描並生成所有索引...")
        self.root.update_idletasks()
        for plate in self.main_index_data.keys():
            self._sync_vehicle_index(plate)
        self.status_label.config(text="所有索引已同步完成。")
        self.populate_plates_listbox()

    def _sync_vehicle_index(self, plate_folder):
        vehicle_dir = os.path.join(self.pages_dir, plate_folder)
        vehicle_index_path = os.path.join(vehicle_dir, 'index.json')
        is_dirty, vehicle_data = False, {}
        try:
            with open(vehicle_index_path, 'r', encoding='utf-8') as f:
                vehicle_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            is_dirty = True
        initial_keys = set(vehicle_data.keys())
        found_images = {f for f in os.listdir(vehicle_dir) if f.lower().endswith(SUPPORTED_FORMATS)}
        for img_filename in found_images:
            entry = vehicle_data.get(img_filename)
            if not entry:
                match = re.match(r".*?_(\d{4}-\d{2}-\d{2})", img_filename)
                date_guess = match.group(1) if match else "YYYY-MM-DD"
                entry = {"date": date_guess, "description": ""}
                vehicle_data[img_filename] = entry
                is_dirty = True
            if "width" not in entry or "height" not in entry:
                try:
                    with Image.open(os.path.join(vehicle_dir, img_filename)) as img:
                        width, height = img.size
                        entry["width"], entry["height"] = width, height
                        is_dirty = True
                except Exception as e:
                    print(f"警告：無法讀取圖片 '{img_filename}' 的解析度。錯誤: {e}")
                    entry["width"], entry["height"] = 0, 0
        images_to_remove = [img for img in vehicle_data if img not in found_images]
        for img in images_to_remove: del vehicle_data[img]
        if initial_keys != set(vehicle_data.keys()): is_dirty = True
        if is_dirty: self._write_vehicle_index(plate_folder, vehicle_data)

    def filter_plates(self, event=None):
        search_term = self.search_var.get().upper().strip()
        self.plates_listbox.delete(0, 'end')
        all_plates = sorted(self.main_index_data.keys())
        filtered_plates = [plate for plate in all_plates if search_term in plate.upper()]
        for plate in filtered_plates: self.plates_listbox.insert('end', plate)
        self.clear_right_panels()

    def _sync_main_index(self):
        if not os.path.isdir(self.pages_dir): os.makedirs(self.pages_dir, exist_ok=True)
        main_index_path = os.path.join(self.pages_dir, 'index.json')
        is_dirty = False
        try:
            with open(main_index_path, 'r', encoding='utf-8') as f:
                self.main_index_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.main_index_data = {}
            is_dirty = True
        initial_keys = set(self.main_index_data.keys())
        found_plates = {d for d in os.listdir(self.pages_dir) if os.path.isdir(os.path.join(self.pages_dir, d))}
        for plate in found_plates:
            if plate not in self.main_index_data:
                self.main_index_data[plate] = {"company": "", "year": "", "manufacturer": "", "model": ""}
        plates_to_remove = [plate for plate in self.main_index_data if plate not in found_plates]
        for plate in plates_to_remove: del self.main_index_data[plate]
        if initial_keys != set(self.main_index_data.keys()): is_dirty = True
        if is_dirty: self._write_main_index()

    def auto_save_main_index_from_ui(self, event=None):
        if not self.current_plate: return
        current_data = self.main_index_data[self.current_plate]
        new_data = {
            "company": self.company_var.get(), "year": self.year_var.get(),
            "manufacturer": self.manufacturer_var.get(), "model": self.model_var.get()
        }
        if current_data != new_data:
            self.main_index_data[self.current_plate] = new_data
            if self._write_main_index():
                self.show_timed_status("主索引已自動儲存。")

    def perform_health_check(self):
        if not os.path.isdir(self.pages_dir): return
        empty_folders = []
        for item_name in os.listdir(self.pages_dir):
            item_path = os.path.join(self.pages_dir, item_name)
            if os.path.isdir(item_path):
                has_images = any(f.lower().endswith(SUPPORTED_FORMATS) for f in os.listdir(item_path))
                if not has_images: empty_folders.append(item_name)
        if empty_folders:
            message = "警告：以下車牌資料夾是空的：\n\n" + "\n".join(empty_folders)
            message += "\n\n建議您將圖片放入這些資料夾，或將它們刪除。"
            messagebox.showwarning("健康檢查結果", message)
        else:
            messagebox.showinfo("健康檢查結果", "太棒了！所有車牌資料夾都包含圖片。")

    def populate_plates_listbox(self):
        self.filter_plates()
        self.update_status_progress()

    def load_and_display_images(self):
        if not self.current_plate: return
        vehicle_index_path = os.path.join(self.pages_dir, self.current_plate, 'index.json')
        try:
            with open(vehicle_index_path, 'r', encoding='utf-8') as f:
                self.vehicle_index_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.vehicle_index_data = {}
        self.images_listbox.delete(0, 'end')
        for img in sorted(self.vehicle_index_data.keys()): self.images_listbox.insert('end', img)
        self.clear_image_fields()
        self.update_status_progress()

    def _write_main_index(self):
        main_index_path = os.path.join(self.pages_dir, 'index.json')
        try:
            with open(main_index_path, 'w', encoding='utf-8') as f:
                json.dump(self.main_index_data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            messagebox.showerror("寫入失敗", f"無法寫入主索引檔案：\n{e}")
            return False

    def _write_vehicle_index(self, plate_folder, data):
        vehicle_index_path = os.path.join(self.pages_dir, plate_folder, 'index.json')
        try:
            with open(vehicle_index_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            messagebox.showerror("寫入失敗", f"無法寫入 '{plate_folder}' 的索引檔案：\n{e}")
            return False

    def auto_save_vehicle_index_from_ui(self, event=None):
        if not self.current_plate or not self.current_image: return
        current_data = self.vehicle_index_data[self.current_image]
        new_date, new_desc = self.image_date_var.get(), self.image_desc_var.get()
        if current_data["date"] != new_date or current_data["description"] != new_desc:
            current_data["date"], current_data["description"] = new_date, new_desc
            if self._write_vehicle_index(self.current_plate, self.vehicle_index_data): self.show_timed_status(
                f"'{self.current_plate}' 的索引已自動儲存。")

    def show_timed_status(self, message):
        self.status_label.config(text=message)
        self.root.after(3000, self.update_status_progress)

    def update_status_progress(self):
        if self.current_plate and self.current_image:
            status_text = f"正在編輯 車輛: {self.current_plate}, 圖片: {self.current_image}"
        elif self.current_plate:
            status_text = f"正在編輯 車輛: {self.current_plate}"
        else:
            status_text = f"顯示 {self.plates_listbox.size()} / {len(self.main_index_data)} 個項目"
        self.status_label.config(text=status_text)


if __name__ == "__main__":
    root = Tk()
    root.geometry("1024x768")
    app = IndexManagerApp(root)
    root.mainloop()