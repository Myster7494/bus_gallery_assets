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

        # --- 左側：車牌管理 ---
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
        labels = ["客運:", "年份:", "廠牌:", "型號:"]
        variables = [self.company_var, self.year_var, self.manufacturer_var, self.model_var]
        for i, (label_text, var) in enumerate(zip(labels, variables)):
            Label(plate_info_frame, text=label_text).grid(row=i, column=0, sticky='w', pady=2)
            entry = Entry(plate_info_frame, textvariable=var)
            entry.grid(row=i, column=1, sticky='ew', pady=2, padx=5)
            entry.bind("<FocusOut>", self.auto_save_main_index_from_ui)
            entry.bind("<Return>", self.auto_save_main_index_from_ui)
        plate_info_frame.grid_columnconfigure(1, weight=1)

        plate_actions_frame = Frame(left_pane)
        plate_actions_frame.pack(fill='x', padx=5, pady=5)
        copy_button = Button(plate_actions_frame, text="複製資訊", command=self.copy_plate_info)
        copy_button.pack(side='left', expand=True, fill='x', padx=2)
        paste_button = Button(plate_actions_frame, text="貼上資訊", command=self.paste_plate_info)
        paste_button.pack(side='left', expand=True, fill='x', padx=2)

        # --- 右側：圖片管理 ---
        Label(right_pane, text="圖片 (檔案)", font=("Arial", 12, "bold")).pack(pady=5)

        image_management_frame = Frame(right_pane)
        image_management_frame.pack(fill='both', expand=True, padx=5, pady=5)

        image_list_frame = Frame(image_management_frame)
        image_list_frame.pack(side='left', fill='both', expand=True)
        image_scrollbar = Scrollbar(image_list_frame)
        image_scrollbar.pack(side='right', fill='y')
        self.images_listbox = Listbox(image_list_frame, yscrollcommand=image_scrollbar.set, exportselection=False)
        self.images_listbox.pack(side='left', fill='both', expand=True)
        image_scrollbar.config(command=self.images_listbox.yview)
        self.images_listbox.bind('<<ListboxSelect>>', self.on_image_select)

        # --- 修改：整合所有圖片操作按鈕 ---
        image_buttons_frame = Frame(image_management_frame)
        image_buttons_frame.pack(side='left', fill='y', padx=(5, 0))

        self.move_up_button = Button(image_buttons_frame, text="上移 ↑", command=self.move_image_up, state='disabled')
        self.move_up_button.pack(fill='x', pady=2)
        self.move_down_button = Button(image_buttons_frame, text="下移 ↓", command=self.move_image_down, state='disabled')
        self.move_down_button.pack(fill='x', pady=2)

        self.open_image_button = Button(image_buttons_frame, text="在外部開啟圖片", command=self.open_image_externally, state='disabled')
        self.open_image_button.pack(fill='x', pady=(10, 2)) # 使用 pady 增加垂直間距
        self.show_in_folder_button = Button(image_buttons_frame, text="在檔案總管中開啟", command=self.show_in_explorer, state='disabled')
        self.show_in_folder_button.pack(fill='x', pady=2)

        self.delete_image_button = Button(image_buttons_frame, text="刪除圖片", command=self.delete_image, state='disabled', fg="red")
        self.delete_image_button.pack(fill='x', pady=(10, 2))

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
        image_date_entry.bind("<Return>", self.auto_save_vehicle_index_from_ui)
        image_desc_entry.bind("<FocusOut>", self.auto_save_vehicle_index_from_ui)
        image_desc_entry.bind("<Return>", self.auto_save_vehicle_index_from_ui)

        # 將所有圖片操作按鈕分組，方便統一管理狀態
        self.image_action_buttons = [
            self.open_image_button, self.move_up_button, self.move_down_button,
            self.show_in_folder_button, self.delete_image_button
        ]

        bottom_frame = Frame(root, padx=5, pady=2)
        bottom_frame.pack(side='bottom', fill='x')
        Button(bottom_frame, text="資料夾健康檢查", command=self.perform_health_check).pack(side='left')
        self.status_label = Label(bottom_frame, text="正在初始化...", bd=1, relief='sunken', anchor='w')
        self.status_label.pack(side='right', fill='x', expand=True)

        self.root.after(100, self.initialize_and_scan_all)

    def copy_plate_info(self):
        """將目前選擇的車輛資訊以 JSON 格式複製到剪貼簿"""
        if not self.current_plate:
            messagebox.showinfo("提示", "請先選擇一個車牌。")
            return
        data_to_copy = {
            "company": self.company_var.get(), "year": self.year_var.get(),
            "manufacturer": self.manufacturer_var.get(), "model": self.model_var.get()
        }
        try:
            json_string = json.dumps(data_to_copy, ensure_ascii=False)
            self.root.clipboard_clear()
            self.root.clipboard_append(json_string)
            self.show_timed_status(f"已複製 '{self.current_plate}' 的資訊。")
        except Exception as e:
            messagebox.showerror("複製失敗", f"無法將資訊複製到剪貼簿。\n錯誤: {e}")

    def paste_plate_info(self):
        """從剪貼簿讀取 JSON 資訊並貼上到目前的車輛欄位"""
        if not self.current_plate:
            messagebox.showinfo("提示", "請先選擇一個要貼上資訊的車牌。")
            return
        try:
            clipboard_content = self.root.clipboard_get()
            if not clipboard_content:
                messagebox.showinfo("提示", "剪貼簿是空的。")
                return
            data_to_paste = json.loads(clipboard_content)
            required_keys = ["company", "year", "manufacturer", "model"]
            if not all(key in data_to_paste for key in required_keys):
                messagebox.showerror("貼上失敗", "剪貼簿中的資料格式不正確，缺少必要的欄位。")
                return
            self.company_var.set(data_to_paste.get("company", ""))
            self.year_var.set(data_to_paste.get("year", ""))
            self.manufacturer_var.set(data_to_paste.get("manufacturer", ""))
            self.model_var.set(data_to_paste.get("model", ""))
            self.auto_save_main_index_from_ui()
            self.show_timed_status(f"已將資訊貼上至 '{self.current_plate}'。")
        except json.JSONDecodeError:
            messagebox.showerror("貼上失敗", "剪貼簿中的內容不是有效的 JSON 格式。")
        except Exception as e:
            messagebox.showerror("貼上失敗", f"處理剪貼簿內容時發生錯誤。\n錯誤: {e}")

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
        for button in self.image_action_buttons:
            button.config(state='normal')
        self.update_status_progress()

    def open_image_externally(self):
        """使用作業系統預設的應用程式開啟圖片"""
        if not self.current_plate or not self.current_image:
            return
        image_path = os.path.join(self.pages_dir, self.current_plate, self.current_image)
        if not os.path.exists(image_path):
            messagebox.showerror("錯誤", f"找不到圖片檔案：\n{image_path}")
            return
        try:
            if sys.platform == "win32":
                os.startfile(image_path)
            elif sys.platform == "darwin":
                subprocess.run(["open", image_path], check=True)
            else:
                subprocess.run(["xdg-open", image_path], check=True)
        except Exception as e:
            messagebox.showerror("開啟失敗", f"無法使用預設應用程式開啟圖片。\n錯誤訊息: {e}")

    def show_in_explorer(self):
        """在檔案總管中顯示所選圖片"""
        if not self.current_plate or not self.current_image:
            return
        image_path = os.path.join(self.pages_dir, self.current_plate, self.current_image)
        if not os.path.exists(image_path):
            messagebox.showerror("錯誤", f"找不到圖片檔案：\n{image_path}")
            return
        try:
            if sys.platform == "win32":
                # --- 修改：使用 abspath 確保路徑格式正確，修復 explorer.exe 錯誤 ---
                final_path = os.path.abspath(image_path)
                subprocess.run(['explorer', '/select,', final_path], check=True)
            elif sys.platform == "darwin":
                subprocess.run(["open", "-R", image_path], check=True)
            else:
                subprocess.run(["xdg-open", os.path.dirname(image_path)], check=True)
        except Exception as e:
            messagebox.showerror("開啟失敗", f"無法在檔案總管中顯示圖片。\n錯誤訊息: {e}")

    def delete_image(self):
        """刪除所選的圖片檔案及其索引項目"""
        if not self.current_plate or not self.current_image: return
        confirm = messagebox.askyesno(
            "確認刪除", f"您確定要永久刪除以下檔案嗎？\n\n{self.current_image}\n\n此操作無法復原！"
        )
        if not confirm: return
        image_path = os.path.join(self.pages_dir, self.current_plate, self.current_image)
        try:
            if os.path.exists(image_path): os.remove(image_path)
            if self.current_image in self.vehicle_index_data: del self.vehicle_index_data[self.current_image]
            self._write_vehicle_index(self.current_plate, self.vehicle_index_data)
            self.show_timed_status(f"已刪除圖片 '{self.current_image}'。")
            self.load_and_display_images()
        except Exception as e:
            messagebox.showerror("刪除失敗", f"刪除圖片時發生錯誤。\n錯誤: {e}")

    def _move_image(self, direction):
        """輔助函式，用於將所選圖片上移或下移"""
        selection_indices = self.images_listbox.curselection()
        if not selection_indices: return
        index = selection_indices[0]
        if direction == "up" and index == 0: return
        if direction == "down" and index == self.images_listbox.size() - 1: return
        items = list(self.vehicle_index_data.keys())
        new_index = index - 1 if direction == "up" else index + 1
        items[index], items[new_index] = items[new_index], items[index]
        new_data = {key: self.vehicle_index_data[key] for key in items}
        self.vehicle_index_data = new_data
        if self._write_vehicle_index(self.current_plate, self.vehicle_index_data):
            current_image_filename = self.images_listbox.get(index)
            self.load_and_display_images()
            self.images_listbox.selection_set(new_index)
            self.images_listbox.activate(new_index)
            self.images_listbox.see(new_index)
            self.on_image_select(None)
            self.show_timed_status(f"已移動 '{current_image_filename}'。")

    def move_image_up(self):
        self._move_image("up")

    def move_image_down(self):
        self._move_image("down")

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
        for button in self.image_action_buttons:
            button.config(state='disabled')

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
        for img in self.vehicle_index_data.keys():
            self.images_listbox.insert('end', img)
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