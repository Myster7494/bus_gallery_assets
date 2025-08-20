import os
import re
import sys
from tkinter import Tk, Label, Button, Entry, Canvas, Frame, filedialog, StringVar, messagebox
from PIL import Image, ImageTk
from datetime import date, datetime
import piexif

# --- 修復大圖警告 ---
Image.MAX_IMAGE_PIXELS = None
SUPPORTED_FORMATS = ('.jpg', '.jpeg', '.png', '.bmp', '.gif')


def get_script_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))


def sanitize_foldername(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)


class ImageTaggerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("圖片處理與歸檔工具")

        # --- 資料變數 ---
        self.script_dir = get_script_dir()
        self.image_folder = ""
        self.image_paths = []
        self.current_index = 0
        # --- 修改：計數器現在同時基於車牌和日期 ---
        self.plate_date_counters = {}
        self.last_used_date = None
        self.original_img = None
        self.displayed_img_info = {}

        # --- 框選功能變數 ---
        self.selection_rect = None
        self.selection_start_x = 0
        self.selection_start_y = 0

        # --- GUI 元件 ---
        top_frame = Frame(root, padx=10, pady=10)
        top_frame.pack(fill='x')

        Button(top_frame, text="選擇圖片資料夾", command=self.select_folder).pack(side='left')
        self.folder_label = Label(top_frame, text="尚未選擇資料夾", fg="blue")
        self.folder_label.pack(side='left', padx=10)

        # --- 主內容區 (左右分割) ---
        content_frame = Frame(root)
        content_frame.pack(fill='both', expand=True, padx=10)

        # 左側: 圖片顯示區
        canvas_frame = Frame(content_frame)
        canvas_frame.pack(side='left', fill='both', expand=True)
        self.canvas = Canvas(canvas_frame, width=800, height=600, bg="gray")
        self.canvas.pack(fill='both', expand=True)

        # 右側: 放大預覽區
        zoom_frame = Frame(content_frame, padx=10)
        zoom_frame.pack(side='right', fill='y')
        Label(zoom_frame, text="放大預覽\n(請在左側圖片上拖曳選取)").pack(pady=5)
        self.zoom_canvas = Canvas(zoom_frame, width=300, height=300, bg="darkgray")
        self.zoom_canvas.pack()

        mid_frame = Frame(root, padx=10, pady=10)
        mid_frame.pack(fill='x')

        Label(mid_frame, text="車牌號碼：").grid(row=0, column=0, sticky='w', pady=5)
        self.plate_var = StringVar()
        self.plate_entry = Entry(mid_frame, textvariable=self.plate_var, width=30)
        self.plate_entry.grid(row=0, column=1, sticky='w', padx=5)

        Label(mid_frame, text="拍攝日期 (YYYY-MM-DD)：").grid(row=1, column=0, sticky='w', pady=5)
        self.date_var = StringVar()
        self.date_entry = Entry(mid_frame, textvariable=self.date_var, width=30)
        self.date_entry.grid(row=1, column=1, sticky='w', padx=5)

        self.date_entry.bind("<Return>", self.save_and_next)
        self.plate_entry.bind("<Return>", self.save_and_next)

        bottom_frame = Frame(root, padx=10, pady=10)
        bottom_frame.pack(fill='x')

        self.save_button = Button(bottom_frame, text="儲存並下一張", command=self.save_and_next, state='disabled')
        self.save_button.pack(side='left')

        # --- 移除：移除重新命名原始檔案的勾選框 ---
        # self.rename_var = BooleanVar(value=False)
        # Checkbutton(bottom_frame, text="同時重新命名原始檔案", variable=self.rename_var).pack(side='left', padx=10)

        self.status_label = Label(bottom_frame, text="請選擇圖片資料夾以開始")
        self.status_label.pack(side='right')

        # --- 綁定框選事件 ---
        self.canvas.bind("<ButtonPress-1>", self._on_mouse_press)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_release)

    def _on_mouse_press(self, event):
        """滑鼠左鍵按下，開始選取"""
        self.selection_start_x = event.x
        self.selection_start_y = event.y
        if self.selection_rect:
            self.canvas.delete(self.selection_rect)
        self.selection_rect = self.canvas.create_rectangle(
            self.selection_start_x, self.selection_start_y,
            self.selection_start_x, self.selection_start_y,
            outline='red', dash=(2, 2))

    def _on_mouse_drag(self, event):
        """拖曳滑鼠，更新選框"""
        if not self.selection_rect:
            return
        self.canvas.coords(self.selection_rect, self.selection_start_x,
                           self.selection_start_y, event.x, event.y)

    def _on_mouse_release(self, event):
        """放開滑鼠，處理放大"""
        if not self.original_img or not self.selection_rect:
            return
        x1, y1, x2, y2 = self.canvas.coords(self.selection_rect)
        box_left, box_top = min(x1, x2), min(y1, y2)
        box_right, box_bottom = max(x1, x2), max(y1, y2)

        img_x_start = self.displayed_img_info['x_offset']
        img_y_start = self.displayed_img_info['y_offset']
        img_width = self.displayed_img_info['width']
        img_height = self.displayed_img_info['height']

        x_scale = self.original_img.width / img_width
        y_scale = self.original_img.height / img_height

        orig_left = (box_left - img_x_start) * x_scale
        orig_top = (box_top - img_y_start) * y_scale
        orig_right = (box_right - img_x_start) * x_scale
        orig_bottom = (box_bottom - img_y_start) * y_scale

        orig_left = max(0, orig_left)
        orig_top = max(0, orig_top)
        orig_right = min(self.original_img.width, orig_right)
        orig_bottom = min(self.original_img.height, orig_bottom)

        if orig_left >= orig_right or orig_top >= orig_bottom:
            return

        cropped_img = self.original_img.crop((orig_left, orig_top, orig_right, orig_bottom))
        zoom_canvas_width = self.zoom_canvas.winfo_width()
        zoom_canvas_height = self.zoom_canvas.winfo_height()
        cropped_img.thumbnail((zoom_canvas_width, zoom_canvas_height), Image.Resampling.LANCZOS)

        self.zoom_photo = ImageTk.PhotoImage(cropped_img)
        self.zoom_canvas.delete("all")
        self.zoom_canvas.create_image(
            zoom_canvas_width / 2, zoom_canvas_height / 2,
            anchor='center', image=self.zoom_photo)

    def select_folder(self):
        folder = filedialog.askdirectory()
        if not folder: return
        self.image_folder = folder
        self.folder_label.config(text=f"目前資料夾: {self.image_folder}")
        # --- 修改：清空新的計數器 ---
        self.plate_date_counters.clear()
        self.last_used_date = None
        self.image_paths = sorted([os.path.join(self.image_folder, f) for f in os.listdir(self.image_folder) if
                                   f.lower().endswith(SUPPORTED_FORMATS)])
        if not self.image_paths:
            messagebox.showinfo("提示", "此資料夾中沒有找到任何支援的圖片檔案！")
            return
        self.current_index = 0
        self.load_image()

    def load_image(self):
        if self.current_index >= len(self.image_paths):
            self.display_completion_message()
            return

        self.save_button.config(state='normal')
        self.plate_entry.config(state='normal')
        self.date_entry.config(state='normal')
        filepath = self.image_paths[self.current_index]
        self.canvas.delete("all")
        self.zoom_canvas.delete("all")
        self.selection_rect = None

        try:
            self.original_img = Image.open(filepath)
            img_for_display = self.original_img.copy()
            self.root.update_idletasks()
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            img_for_display.thumbnail((canvas_width, canvas_height), Image.Resampling.LANCZOS)
            self.displayed_img_info = {
                'width': img_for_display.width,
                'height': img_for_display.height,
                'x_offset': (canvas_width - img_for_display.width) / 2,
                'y_offset': (canvas_height - img_for_display.height) / 2
            }
            self.photo = ImageTk.PhotoImage(img_for_display)
            self.canvas.create_image(canvas_width / 2, canvas_height / 2, anchor='center', image=self.photo)
        except Exception as e:
            self.original_img = None
            self.canvas.create_text(400, 300, text=f"無法載入圖片:\n{os.path.basename(filepath)}\n{e}",
                                    font=("Arial", 16), fill="red")

        self.status_label.config(text=f"進度：{self.current_index + 1} / {len(self.image_paths)}")
        self.plate_var.set("")
        if self.last_used_date:
            self.date_var.set(self.last_used_date)
        else:
            self.date_var.set(date.today().strftime("%Y-%m-%d"))
        self.plate_entry.focus_set()

    def save_and_next(self, event=None):
        plate = self.plate_var.get().strip().upper()
        shot_date = self.date_var.get().strip()

        if not plate or not shot_date:
            messagebox.showwarning("輸入錯誤", "車牌號碼和拍攝日期不能為空！")
            return
        try:
            datetime.strptime(shot_date, "%Y-%m-%d")
        except ValueError:
            messagebox.showwarning("格式錯誤", "拍攝日期格式不正確，請使用 YYYY-MM-DD 格式。")
            return
        self.last_used_date = shot_date

        original_filepath = self.image_paths[self.current_index]
        
        # --- 移除：移除所有與重新命名原始檔案相關的邏輯 ---
        
        try:
            pages_dir = os.path.join(self.script_dir, "pages")
            safe_plate_name = sanitize_foldername(plate)
            plate_dir = os.path.join(pages_dir, safe_plate_name)
            os.makedirs(plate_dir, exist_ok=True)

            # --- 修改：使用 (車牌, 日期) 作為鍵來取得計數 ---
            counter_key = (safe_plate_name, shot_date)
            count = self.plate_date_counters.get(counter_key, 0) + 1
            
            _ , file_ext = os.path.splitext(os.path.basename(original_filepath))
            new_copy_filename = f"{plate}_{shot_date}_{count:02d}{file_ext}"
            dest_path = os.path.join(plate_dir, new_copy_filename)

            # 每次都重新開啟原始圖片以進行儲存
            img_to_save = Image.open(original_filepath)

            # 準備並寫入EXIF日期資訊
            exif_date_str = shot_date.replace('-', ':') + " 00:00:00"
            exif_date_bytes = exif_date_str.encode('utf-8')
            exif_dict = {"Exif": {piexif.ExifIFD.DateTimeOriginal: exif_date_bytes,
                                  piexif.ExifIFD.DateTimeDigitized: exif_date_bytes}}
            exif_bytes = piexif.dump(exif_dict)

            if dest_path.lower().endswith(('.jpg', '.jpeg')):
                img_to_save.save(dest_path, "jpeg", exif=exif_bytes)
            else:
                img_to_save.save(dest_path)

            img_to_save.close()
            
            # --- 修改：更新新的計數器 ---
            self.plate_date_counters[counter_key] = count
            
        except Exception as e:
            messagebox.showerror("複製或處理檔案失敗", f"發生錯誤：\n{e}")
            # 如果出錯，不要跳到下一張，讓使用者可以重試
            return

        self.current_index += 1
        self.load_image()

    def display_completion_message(self):
        if self.original_img:
            self.original_img.close()
            self.original_img = None
        self.canvas.delete("all")
        self.zoom_canvas.delete("all")
        self.canvas.create_text(400, 300, text="所有圖片皆已處理完畢！", font=("Arial", 24), justify='center')
        self.save_button.config(state='disabled')
        self.plate_entry.config(state='disabled')
        self.date_entry.config(state='disabled')
        self.status_label.config(text=f"完成！共處理 {len(self.image_paths)} 張圖片")

    def on_closing(self):
        if self.original_img:
            self.original_img.close()
        self.root.destroy()


if __name__ == "__main__":
    root = Tk()
    app = ImageTaggerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()