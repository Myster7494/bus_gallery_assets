import os
import json
import re
import sys  # 用於判斷作業系統
import subprocess  # 用於在 macOS/Linux 開啟檔案
import shutil # 用於安全地刪除資料夾
# 匯入 simpledialog 來建立簡單的輸入對話框
from tkinter import Tk, Frame, Listbox, Label, Entry, Button, Scrollbar, messagebox, StringVar, PanedWindow, simpledialog
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
        
        # --- 新增：重命名車牌按鈕 ---
        self.rename_plate_button = Button(plate_actions_frame, text="重命名車牌", command=self.rename_or_merge_plate, state='disabled')
        self.rename_plate_button.pack(side='left', expand=True, fill='x', padx=2)
        
        copy_button = Button(plate_actions_frame, text="複製資訊", command=self.copy_plate_info)
        copy_button.pack(side='left', expand=True, fill='x', padx=2)
        paste_button = Button(plate_actions_frame, text="貼上資訊", command=self.paste_plate_info)
        paste_button.pack(side='left', expand=True, fill='x', padx=2)
        self.rebuild_index_button = Button(plate_actions_frame, text="重建索引", command=self.rebuild_selected_vehicle_index, state='disabled')
        self.rebuild_index_button.pack(side='left', expand=True, fill='x', padx=2)

        # 將車牌操作按鈕分組
        self.plate_action_buttons = [copy_button, paste_button, self.rebuild_index_button, self.rename_plate_button]

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

        image_buttons_frame = Frame(image_management_frame)
        image_buttons_frame.pack(side='left', fill='y', padx=(5, 0))

        self.move_up_button = Button(image_buttons_frame, text="上移 ↑", command=self.move_image_up, state='disabled')
        self.move_up_button.pack(fill='x', pady=2)
        self.move_down_button = Button(image_buttons_frame, text="下移 ↓", command=self.move_image_down, state='disabled')
        self.move_down_button.pack(fill='x', pady=2)

        # --- 新增：重命名圖片按鈕 ---
        self.rename_image_button = Button(image_buttons_frame, text="重命名圖片", command=self.rename_image, state='disabled')
        self.rename_image_button.pack(fill='x', pady=(10, 2))

        self.open_image_button = Button(image_buttons_frame, text="在外部開啟圖片", command=self.open_image_externally, state='disabled')
        self.open_image_button.pack(fill='x', pady=2)
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
        
        self.image_action_buttons = [
            self.open_image_button, self.move_up_button, self.move_down_button,
            self.show_in_folder_button, self.delete_image_button, self.rename_image_button
        ]

        bottom_frame = Frame(root, padx=5, pady=2)
        bottom_frame.pack(side='bottom', fill='x')
        Button(bottom_frame, text="資料夾健康檢查", command=self.perform_health_check).pack(side='left')
        self.status_label = Label(bottom_frame, text="正在初始化...", bd=1, relief='sunken', anchor='w')
        self.status_label.pack(side='right', fill='x', expand=True)

        self.root.after(100, self.initialize_and_scan_all)

    def rename_or_merge_plate(self):
        """重命名選定的車牌，或在名稱衝突時將其與現有車牌合併。"""
        if not self.current_plate:
            messagebox.showinfo("提示", "請先選擇一個要重命名的車牌。")
            return

        old_name = self.current_plate
        new_name = simpledialog.askstring(
            "重命名或合併車牌",
            f"請為 '{old_name}' 輸入新的車牌號碼:",
            initialvalue=old_name
        )

        if not new_name:
            return  # 使用者取消

        new_name = new_name.strip().upper()
        if not new_name or new_name == old_name:
            return  # 沒有變更或輸入為空

        old_path = os.path.join(self.pages_dir, old_name)
        new_path = os.path.join(self.pages_dir, new_name)

        try:
            # 情況 1: 簡單重命名 (新名稱不存在)
            if not os.path.isdir(new_path):
                # 1. 重命名實體資料夾
                os.rename(old_path, new_path)
                
                # 2. 在記憶體中更新主索引資料
                self.main_index_data[new_name] = self.main_index_data.pop(old_name)
                
                # 3. 將更新後的主索引寫入檔案
                self._write_main_index()

                self.show_timed_status(f"已成功將 '{old_name}' 重命名為 '{new_name}'。")

            # 情況 2: 合併 (新名稱已存在)
            else:
                confirm = messagebox.askyesno(
                    "確認合併",
                    f"車牌 '{new_name}' 已存在。\n\n"
                    f"您確定要將 '{old_name}' 的所有圖片合併到 '{new_name}' 嗎？\n\n"
                    f"這將會移動所有圖片，並根據拍攝日期自動重新編號。\n"
                    f"'{old_name}' 資料夾將會被刪除。此操作無法復原！"
                )
                if not confirm:
                    return

                # 執行合併操作
                self._perform_merge(old_name, new_name)
                
                # 更新主索引：移除舊項目
                del self.main_index_data[old_name]
                self._write_main_index()

                self.show_timed_status(f"已成功將 '{old_name}' 合併入 '{new_name}'。")

            # 對於兩種情況都更新 UI
            self._post_rename_ui_update(new_name)

        except Exception as e:
            messagebox.showerror("操作失敗", f"處理車牌時發生錯誤：\n{e}")
            # 如果出錯，重新同步所有內容以反映檔案系統的實際狀態
            self.initialize_and_scan_all()

    def _perform_merge(self, old_name, new_name):
        """執行將一個車牌的圖片合併到另一個車牌並重新編號的後端邏輯。"""
        old_path = os.path.join(self.pages_dir, old_name)
        new_path = os.path.join(self.pages_dir, new_name)

        # 1. 將所有圖片檔案從舊資料夾移動到新資料夾
        for filename in os.listdir(old_path):
            if filename.lower().endswith(SUPPORTED_FORMATS):
                shutil.move(os.path.join(old_path, filename), os.path.join(new_path, filename))

        # 2. 刪除舊資料夾
        shutil.rmtree(old_path)

        # 3. 重新編號目標資料夾中的所有圖片
        all_images = [f for f in os.listdir(new_path) if f.lower().endswith(SUPPORTED_FORMATS)]
        
        # 為了避免在重新命名時發生衝突 (例如 A->B, B->C)，我們先將所有檔案重命名為暫存名稱
        temp_suffix = "_TEMP_RENAME_"
        for filename in all_images:
            try:
                os.rename(os.path.join(new_path, filename), os.path.join(new_path, filename + temp_suffix))
            except FileExistsError: # 如果暫存檔已存在，則使用更獨特的名稱
                os.rename(os.path.join(new_path, filename), os.path.join(new_path, filename + temp_suffix + os.urandom(4).hex()))


        temp_images = [f for f in os.listdir(new_path) if temp_suffix in f]
        date_groups = {}
        
        # 根據原始檔名中的日期對暫存檔案進行分組
        for temp_filename in temp_images:
            original_name = temp_filename.split(temp_suffix)[0]
            match = re.match(r".*?_(\d{4}-\d{2}-\d{2})", original_name)
            date_key = match.group(1) if match else "unknown_date"
            if date_key not in date_groups:
                date_groups[date_key] = []
            date_groups[date_key].append(temp_filename)

        # 在每個日期組內對檔案進行排序並重命名
        for date, files in date_groups.items():
            # 對於無法解析日期的檔案，為安全起見僅還原其原始名稱
            if date == "unknown_date":
                print(f"警告：在 '{new_name}' 中發現無法解析日期的檔案，將跳過重新編號：{[f.split(temp_suffix)[0] for f in files]}")
                for temp_filename in files:
                    original_name = temp_filename.split(temp_suffix)[0]
                    os.rename(os.path.join(new_path, temp_filename), os.path.join(new_path, original_name))
                continue
            
            # 排序以確保重新編號順序的一致性
            for i, temp_filename in enumerate(sorted(files), 1):
                original_name = temp_filename.split(temp_suffix)[0]
                _, ext = os.path.splitext(original_name)
                # 建立新的標準化檔名
                new_filename = f"{new_name}_{date}_{i:02d}{ext.lower()}"
                os.rename(os.path.join(new_path, temp_filename), os.path.join(new_path, new_filename))

        # 4. 強制為合併後的資料夾重建索引
        self._sync_vehicle_index(new_name)

    def _post_rename_ui_update(self, select_plate_name):
        """在重命名或合併操作後刷新 UI。"""
        self.current_plate = None
        self.clear_right_panels()
        
        # 刷新列表框
        self.search_var.set("")
        self.filter_plates()

        # 嘗試找到並選中新的/合併後的項目
        try:
            all_items = self.plates_listbox.get(0, 'end')
            if select_plate_name in all_items:
                new_index = all_items.index(select_plate_name)
                self.plates_listbox.selection_set(new_index)
                self.plates_listbox.see(new_index)
                self.on_plate_select(None) # 手動觸發選擇事件
        except ValueError:
            # 項目未找到，不執行任何操作
            pass

    def rebuild_selected_vehicle_index(self):
        """為當前選擇的車牌重建索引"""
        if not self.current_plate:
            messagebox.showinfo("提示", "請先選擇一個車牌。")
            return
        
        confirm = messagebox.askyesno(
            "確認重建索引",
            f"您確定要為 '{self.current_plate}' 重建圖片索引嗎？\n\n"
            "這將會：\n"
            "- 移除無效的圖片記錄\n"
            "- 新增資料夾中未記錄的圖片"
        )
        if not confirm:
            return
        
        try:
            self.status_label.config(text=f"正在為 {self.current_plate} 重建索引...")
            self.root.update_idletasks()
            
            self._sync_vehicle_index(self.current_plate)
            self.load_and_display_images() # 重新載入以顯示變更
            
            self.show_timed_status(f"'{self.current_plate}' 的索引已成功重建。")
        except Exception as e:
            messagebox.showerror("重建失敗", f"重建索引時發生錯誤：\n{e}")
            self.update_status_progress()

    def rename_image(self):
        """重命名所選的圖片檔案及其索引項目"""
        if not self.current_plate or not self.current_image:
            return

        old_name = self.current_image
        # 彈出對話框讓使用者輸入新檔名
        new_name = simpledialog.askstring(
            "重命名圖片",
            "請輸入新的檔案名稱:",
            initialvalue=old_name
        )

        # 驗證使用者輸入
        if not new_name or new_name == old_name:
            return # 使用者取消或未變更

        # 自動補上副檔名
        old_base, old_ext = os.path.splitext(old_name)
        new_base, new_ext = os.path.splitext(new_name)
        if not new_ext:
            new_name += old_ext
        
        # 檢查新檔名是否已存在
        new_path = os.path.join(self.pages_dir, self.current_plate, new_name)
        if os.path.exists(new_path):
            messagebox.showerror("重命名失敗", f"檔案 '{new_name}' 已存在於此資料夾中。")
            return

        try:
            old_path = os.path.join(self.pages_dir, self.current_plate, old_name)
            
            # 1. 重命名實體檔案
            os.rename(old_path, new_path)
            
            # 2. 更新索引字典 (保持順序)
            items = list(self.vehicle_index_data.items())
            new_vehicle_data = {}
            for key, value in items:
                if key == old_name:
                    new_vehicle_data[new_name] = value
                else:
                    new_vehicle_data[key] = value
            self.vehicle_index_data = new_vehicle_data

            # 3. 寫回索引檔
            self._write_vehicle_index(self.current_plate, self.vehicle_index_data)

            # 4. 更新UI
            self.load_and_display_images()
            
            # 找到新項目的索引並選取它
            try:
                new_list_index = list(self.vehicle_index_data.keys()).index(new_name)
                self.images_listbox.selection_set(new_list_index)
                self.on_image_select(None)
            except ValueError:
                pass # 如果找不到就不選取

            self.show_timed_status(f"已成功將 '{old_name}' 重命名為 '{new_name}'。")

        except Exception as e:
            messagebox.showerror("重命名失敗", f"重命名時發生錯誤：\n{e}")


    def copy_plate_info(self):
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
        
        # 啟用車牌操作按鈕
        for button in self.plate_action_buttons:
            button.config(state='normal')
            
        self.load_and_display_images()

    def on_image_select(self, event):
        selection_indices = self.images_listbox.curselection()
        if not selection_indices:
            for button in self.image_action_buttons:
                button.config(state='disabled')
            return
            
        self.current_image = self.images_listbox.get(selection_indices[0])
        image_data = self.vehicle_index_data.get(self.current_image, {})
        self.image_date_var.set(image_data.get("date", ""))
        self.image_desc_var.set(image_data.get("description", ""))
        
        for button in self.image_action_buttons:
            button.config(state='normal')
        
        index = selection_indices[0]
        if index == 0:
            self.move_up_button.config(state='disabled')
        if index == self.images_listbox.size() - 1:
            self.move_down_button.config(state='disabled')
            
        self.update_status_progress()

    def open_image_externally(self):
        if not self.current_plate or not self.current_image: return
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
        if not self.current_plate or not self.current_image: return
        image_path = os.path.join(self.pages_dir, self.current_plate, self.current_image)
        if not os.path.exists(image_path):
            messagebox.showerror("錯誤", f"找不到圖片檔案：\n{image_path}")
            return
        try:
            if sys.platform == "win32":
                final_path = os.path.abspath(image_path)
                subprocess.run(['explorer', '/select,', final_path])
            elif sys.platform == "darwin":
                subprocess.run(["open", "-R", image_path], check=True)
            else:
                subprocess.run(["xdg-open", os.path.dirname(image_path)], check=True)
        except Exception as e:
            messagebox.showerror("開啟失敗", f"無法在檔案總管中顯示圖片。\n錯誤訊息: {e}")

    def delete_image(self):
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

    def move_image_up(self): self._move_image("up")
    def move_image_down(self): self._move_image("down")

    def clear_right_panels(self):
        self.company_var.set("")
        self.year_var.set("")
        self.manufacturer_var.set("")
        self.model_var.set("")
        self.images_listbox.delete(0, 'end')
        self.current_image = None
        self.clear_image_fields()
        
        # 禁用車牌操作按鈕
        for button in self.plate_action_buttons:
            button.config(state='disabled')

    def clear_image_fields(self):
        self.image_date_var.set("")
        self.image_desc_var.set("")
        for button in self.image_action_buttons:
            button.config(state='disabled')

    def initialize_and_scan_all(self):
        self._sync_main_index()
        self.status_label.config(text="正在掃描並生成所有索引...")
        self.root.update_idletasks()
        for plate in sorted(self.main_index_data.keys()):
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
        
        found_images_set = {f for f in os.listdir(vehicle_dir) if f.lower().endswith(SUPPORTED_FORMATS)}
        
        images_to_remove = [img for img in vehicle_data if img not in found_images_set]
        if images_to_remove:
            for img in images_to_remove:
                del vehicle_data[img]
            is_dirty = True

        for img_filename in sorted(list(found_images_set)):
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
        
        if is_dirty:
            self._write_vehicle_index(plate_folder, vehicle_data)

    def filter_plates(self, event=None):
        search_term = self.search_var.get().upper().strip()
        self.plates_listbox.delete(0, 'end')
        all_plates = sorted(self.main_index_data.keys())
        filtered_plates = [plate for plate in all_plates if search_term in plate.upper()]
        for plate in filtered_plates: self.plates_listbox.insert('end', plate)
        if not search_term:
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
        
        found_plates = {d for d in os.listdir(self.pages_dir) if os.path.isdir(os.path.join(self.pages_dir, d))}
        
        for plate in found_plates:
            if plate not in self.main_index_data:
                self.main_index_data[plate] = {"company": "", "year": "", "manufacturer": "", "model": ""}
                is_dirty = True

        plates_to_remove = [plate for plate in self.main_index_data if plate not in found_plates]
        if plates_to_remove:
            for plate in plates_to_remove:
                del self.main_index_data[plate]
            is_dirty = True
        
        if is_dirty:
            self._write_main_index()

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
        if not os.path.isdir(self.pages_dir):
            messagebox.showinfo("健康檢查結果", "找不到 'pages' 資料夾。")
            return

        # 檢查 1：空的車牌資料夾
        empty_folders = []
        all_folders = [d for d in os.listdir(self.pages_dir) if os.path.isdir(os.path.join(self.pages_dir, d))]
        for folder_name in all_folders:
            folder_path = os.path.join(self.pages_dir, folder_name)
            has_images = any(f.lower().endswith(SUPPORTED_FORMATS) for f in os.listdir(folder_path))
            if not has_images:
                empty_folders.append(folder_name)

        # 檢查 2：缺少資訊的車輛項目
        folders_with_missing_info = []
        for plate, info in self.main_index_data.items():
            # 檢查是否有任何一個欄位是空的或只包含空白字元
            if not info.get("company", "").strip() or \
               not info.get("year", "").strip() or \
               not info.get("manufacturer", "").strip() or \
               not info.get("model", "").strip():
                folders_with_missing_info.append(plate)

        # 組合報告訊息
        message_parts = []
        if folders_with_missing_info:
            message_parts.append(
                "警告：以下車輛缺少部分或全部資訊（客運、年份、廠牌、型號）：\n\n" + 
                "\n".join(sorted(folders_with_missing_info))
            )
        
        if empty_folders:
            message_parts.append(
                "警告：以下車牌資料夾是空的（沒有圖片）：\n\n" + 
                "\n".join(sorted(empty_folders))
            )

        # 顯示最終結果
        if message_parts:
            final_message = "\n\n".join(message_parts)
            final_message += "\n\n建議您修正以上問題。"
            messagebox.showwarning("健康檢查結果", final_message)
        else:
            messagebox.showinfo("健康檢查結果", "太棒了！所有車牌資料夾都包含圖片，且所有車輛資訊都已完整填寫。")


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
        sorted_main_index_data = {key: self.main_index_data[key] for key in sorted(self.main_index_data.keys())}
        try:
            with open(main_index_path, 'w', encoding='utf-8') as f:
                json.dump(sorted_main_index_data, f, indent=4, ensure_ascii=False)
            self.main_index_data = sorted_main_index_data
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