import os
import re
import sys
from tkinter import Tk, Label, Button, Entry, Canvas, Frame, filedialog, StringVar, BooleanVar, Checkbutton, messagebox
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
        self.plate_counters = {}
        self.last_used_date = None

        # --- GUI 元件 ---
        top_frame = Frame(root, padx=10, pady=10)
        top_frame.pack(fill='x')

        Button(top_frame, text="選擇圖片資料夾", command=self.select_folder).pack(side='left')
        self.folder_label = Label(top_frame, text="尚未選擇資料夾", fg="blue")
        self.folder_label.pack(side='left', padx=10)

        self.canvas = Canvas(root, width=800, height=600, bg="gray")
        self.canvas.pack()

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

        # 綁定 Enter 鍵
        self.date_entry.bind("<Return>", self.save_and_next)
        self.plate_entry.bind("<Return>", self.save_and_next)

        bottom_frame = Frame(root, padx=10, pady=10)
        bottom_frame.pack(fill='x')

        self.save_button = Button(bottom_frame, text="儲存並下一張", command=self.save_and_next, state='disabled')
        self.save_button.pack(side='left')

        self.rename_var = BooleanVar(value=False)
        Checkbutton(bottom_frame, text="同時重新命名原始檔案", variable=self.rename_var).pack(side='left', padx=10)

        self.status_label = Label(bottom_frame, text="請選擇圖片資料夾以開始")
        self.status_label.pack(side='right')

    def select_folder(self):
        folder = filedialog.askdirectory()
        if not folder: return
        self.image_folder = folder
        self.folder_label.config(text=f"目前資料夾: {self.image_folder}")
        self.plate_counters.clear()
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

        try:
            img = Image.open(filepath)
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            img.thumbnail((canvas_width, canvas_height), Image.Resampling.LANCZOS)
            self.photo = ImageTk.PhotoImage(img)
            self.canvas.create_image(canvas_width / 2, canvas_height / 2, anchor='center', image=self.photo)
        except Exception as e:
            self.canvas.delete("all")
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
        original_filename = os.path.basename(original_filepath)

        if self.rename_var.get():
            file_ext = os.path.splitext(original_filename)[1]
            new_filename = f"{shot_date}_{plate}{file_ext}"
            new_path = os.path.join(self.image_folder, new_filename)
            if os.path.exists(new_path) and original_filepath != new_path:
                messagebox.showerror("錯誤", f"檔案 '{new_filename}' 已存在，無法重新命名！")
                return
            try:
                os.rename(original_filepath, new_path)
                self.image_paths[self.current_index] = new_path
                original_filepath = new_path
            except Exception as e:
                messagebox.showerror("重新命名失敗", f"無法重新命名檔案：\n{e}")
                return

        try:
            pages_dir = os.path.join(self.script_dir, "pages")
            safe_plate_name = sanitize_foldername(plate)
            plate_dir = os.path.join(pages_dir, safe_plate_name)
            os.makedirs(plate_dir, exist_ok=True)

            count = self.plate_counters.get(safe_plate_name, 0) + 1
            file_ext = os.path.splitext(original_filename)[1]

            # --- 核心變更：在檔名前方加上車牌號碼 ---
            new_copy_filename = f"{plate}_{shot_date}_{count:02d}{file_ext}"

            dest_path = os.path.join(plate_dir, new_copy_filename)

            img = Image.open(original_filepath)
            exif_date_str = shot_date.replace('-', ':') + " 00:00:00"
            exif_date_bytes = exif_date_str.encode('utf-8')
            exif_dict = {"Exif": {piexif.ExifIFD.DateTimeOriginal: exif_date_bytes,
                                  piexif.ExifIFD.DateTimeDigitized: exif_date_bytes}}
            exif_bytes = piexif.dump(exif_dict)
            if dest_path.lower().endswith(('.jpg', '.jpeg')):
                img.save(dest_path, "jpeg", exif=exif_bytes)
            else:
                img.save(dest_path)
            self.plate_counters[safe_plate_name] = count
        except Exception as e:
            messagebox.showerror("複製或處理檔案失敗", f"發生錯誤：\n{e}")

        self.current_index += 1
        self.load_image()

    def display_completion_message(self):
        self.canvas.delete("all")
        self.canvas.create_text(400, 300, text="所有圖片皆已處理完畢！", font=("Arial", 24), justify='center')
        self.save_button.config(state='disabled')
        self.plate_entry.config(state='disabled')
        self.date_entry.config(state='disabled')
        self.status_label.config(text=f"完成！共處理 {len(self.image_paths)} 張圖片")

    def on_closing(self):
        self.root.destroy()


if __name__ == "__main__":
    root = Tk()
    app = ImageTaggerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()