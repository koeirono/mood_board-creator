from dotenv import load_dotenv
load_dotenv()
import os
import io
import bcrypt
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from PIL import Image, ImageTk, ImageEnhance, ImageFilter
from pymongo import MongoClient
from datetime import datetime
from bson import ObjectId

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "moodboard_db")

UPLOAD_ROOT = "uploads"

os.makedirs(UPLOAD_ROOT, exist_ok=True)

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
users_col = db["users"]
images_col = db["images"]
boards_col = db["boards"]

def hash_password(plain_text_password: str) -> bytes:
    return bcrypt.hashpw(plain_text_password.encode("utf-8"), bcrypt.gensalt())

def check_password(plain_text_password: str, hashed: bytes) -> bool:
    return bcrypt.checkpw(plain_text_password.encode("utf-8"), hashed)

def save_image_file(pil_img: Image.Image, username: str, orig_filename: str) -> str:
    safe_folder = os.path.join(UPLOAD_ROOT, username)
    os.makedirs(safe_folder, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")
    base, ext = os.path.splitext(os.path.basename(orig_filename))
    out_name = f"{timestamp}_{base}.png"
    out_path = os.path.join(safe_folder, out_name)
    pil_img.save(out_path, format="PNG")
    return out_path

def make_thumbnail(pil_img: Image.Image, size=(180, 130)):
    img = pil_img.copy()
    img.thumbnail(size)
    return img

class MoodBoardApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MoodBoard Maker")
        self.geometry("1100x720")
        self.minsize(1000, 650)
        self.configure(bg="#f3f4f6")
        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except Exception:
            pass
        self.style.configure("TFrame", background="#f3f4f6")
        self.style.configure("Card.TFrame", background="#ffffff")
        self.style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"), background="#f3f4f6")
        self.current_user = None
        self.current_image_path = None
        self.current_original_image = None
        self.current_work_image = None
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        self.pages = {}
        for Page in (LandingPage, LoginPage, DashboardPage, EditorPage, GalleryPage, MoodBoardPage, ProfilePage):
            page = Page(parent=container, controller=self)
            self.pages[Page.__name__] = page
            page.grid(row=0, column=0, sticky="nsew")
        self.show_page("LandingPage")

    def show_page(self, name):
        page = self.pages.get(name)
        if page:
            page.tkraise()
            if hasattr(page, "on_show"):
                page.on_show()

    def login(self, username: str):
        self.current_user = username
        self.show_page("DashboardPage")

    def logout(self):
        self.current_user = None
        self.current_image_path = None
        self.current_original_image = None
        self.current_work_image = None
        self.show_page("LandingPage")

class Card(ttk.Frame):
    def __init__(self, parent, padding=12, **kwargs):
        super().__init__(parent, style="Card.TFrame", padding=padding, **kwargs)

class LandingPage(ttk.Frame):
    def __init__(self, parent, controller: MoodBoardApp):
        super().__init__(parent)
        self.controller = controller
        wrap = ttk.Frame(self)
        wrap.place(relx=0.5, rely=0.48, anchor="center")
        title = ttk.Label(wrap, text="MoodBoard Maker", font=("Segoe UI", 24, "bold"))
        title.pack(pady=(0, 8))
        subtitle = ttk.Label(wrap, text="Create and save beautiful mood boards", font=("Segoe UI", 12))
        subtitle.pack(pady=(0, 16))
        btns = ttk.Frame(wrap)
        btns.pack(fill="x", pady=8)
        ttk.Button(btns, text="Get Started", command=lambda: controller.show_page("LoginPage")).pack(side="left", padx=6, ipadx=6)
        ttk.Button(btns, text="About", command=self.show_about).pack(side="left", padx=6, ipadx=6)
        ttk.Button(btns, text="Exit", command=self.controller.destroy).pack(side="left", padx=6, ipadx=6)
        footer = ttk.Label(self, text="Tip: Create a free account to save boards to the cloud", font=("Segoe UI", 9))
        footer.place(relx=0.5, rely=0.92, anchor="center")

    def show_about(self):
        messagebox.showinfo("About", "MoodBoard Maker\nUpload, arrange, and save image boards tied to your account.")

class LoginPage(ttk.Frame):
    def __init__(self, parent, controller: MoodBoardApp):
        super().__init__(parent)
        self.controller = controller
        wrap = ttk.Frame(self)
        wrap.place(relx=0.5, rely=0.5, anchor="center")
        card = Card(wrap, padding=20)
        card.pack()
        ttk.Label(card, text="MoodBoard Maker", style="Title.TLabel").pack(pady=(0, 8))
        ttk.Label(card, text="Sign in or create an account").pack(pady=(0, 10))
        self.username = tk.StringVar()
        self.password = tk.StringVar()
        ttk.Label(card, text="Username").pack(anchor="w")
        self.e_user = ttk.Entry(card, textvariable=self.username, width=32)
        self.e_user.pack(pady=4)
        ttk.Label(card, text="Password").pack(anchor="w")
        self.e_pass = ttk.Entry(card, textvariable=self.password, show="*", width=32)
        self.e_pass.pack(pady=4)
        btns = ttk.Frame(card)
        btns.pack(fill="x", pady=(10, 0))
        ttk.Button(btns, text="Login", command=self.attempt_login).pack(side="left", expand=True, fill="x", padx=(0,6))
        ttk.Button(btns, text="Register", command=self.attempt_register).pack(side="left", expand=True, fill="x")

    def attempt_register(self):
        u = self.username.get().strip()
        p = self.password.get()
        if not u or not p:
            messagebox.showwarning("Missing", "Provide username and password")
            return
        if users_col.find_one({"username": u}):
            messagebox.showerror("Exists", "Username already exists")
            return
        hashed = hash_password(p)
        users_col.insert_one({"username": u, "password": hashed, "created_at": datetime.utcnow()})
        messagebox.showinfo("Registered", "Account created — please login.")
        self.password.set("")

    def attempt_login(self):
        u = self.username.get().strip()
        p = self.password.get()
        if not u or not p:
            messagebox.showwarning("Missing", "Provide username and password")
            return
        doc = users_col.find_one({"username": u})
        if not doc:
            messagebox.showerror("Not found", "No such user")
            return
        if check_password(p, doc["password"]):
            self.username.set("")
            self.password.set("")
            self.controller.login(u)
        else:
            messagebox.showerror("Unauthorized", "Incorrect password")

class DashboardPage(ttk.Frame):
    def __init__(self, parent, controller: MoodBoardApp):
        super().__init__(parent)
        self.controller = controller
        header = ttk.Frame(self)
        header.pack(fill="x", padx=12, pady=8)
        self.title_lbl = ttk.Label(header, text="Dashboard", style="Title.TLabel")
        self.title_lbl.pack(side="left")
        btns = ttk.Frame(header)
        btns.pack(side="right")
        ttk.Button(btns, text="Editor", command=lambda: controller.show_page("EditorPage")).pack(side="left", padx=6)
        ttk.Button(btns, text="Gallery", command=lambda: controller.show_page("GalleryPage")).pack(side="left", padx=6)
        ttk.Button(btns, text="Boards", command=lambda: controller.show_page("MoodBoardPage")).pack(side="left", padx=6)
        ttk.Button(btns, text="Profile", command=lambda: controller.show_page("ProfilePage")).pack(side="left", padx=6)
        ttk.Button(btns, text="Logout", command=self.do_logout).pack(side="left", padx=6)
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        card = Card(body, padding=16)
        card.pack(fill="x")
        self.welcome = ttk.Label(card, text="", font=("Segoe UI", 12))
        self.welcome.pack()
        tips_card = Card(body, padding=12)
        tips_card.pack(fill="both", expand=True, pady=12)
        ttk.Label(tips_card, text="Quick tips", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(tips_card, text="• Use Editor to upload and tweak images.\n• Create boards, add images, drag to arrange.\n• Save each board", wraplength=760).pack(anchor="w", pady=8)

    def on_show(self):
        u = self.controller.current_user or ""
        self.welcome.config(text=f"Welcome, {u} — create a new mood board or open your gallery!")

    def do_logout(self):
        if messagebox.askyesno("Logout", "Are you sure you want to logout?"):
            self.controller.logout()

class EditorPage(ttk.Frame):
    def __init__(self, parent, controller: MoodBoardApp):
        super().__init__(parent)
        self.controller = controller
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=12, pady=8)
        ttk.Button(toolbar, text="Back", command=lambda: controller.show_page("DashboardPage")).pack(side="left", padx=6)
        ttk.Button(toolbar, text="Upload Image", command=self.upload_image).pack(side="left", padx=6)
        ttk.Button(toolbar, text="Reset", command=self.reset_edits).pack(side="left", padx=6)
        ttk.Button(toolbar, text="Save Edited", command=self.save_edited).pack(side="right", padx=6)
        content = ttk.Frame(self)
        content.pack(fill="both", expand=True, padx=12, pady=8)
        preview_card = Card(content, padding=10)
        preview_card.pack(side="left", fill="both", expand=True, padx=(0,8))
        self.preview_label = ttk.Label(preview_card, text="No image loaded\nUse Upload Image", anchor="center", font=("Segoe UI", 14))
        self.preview_label.pack(fill="both", expand=True)
        controls = Card(content, padding=10)
        controls.pack(side="right", fill="y")
        self.var_grayscale = tk.BooleanVar(value=False)
        ttk.Checkbutton(controls, text="Grayscale", variable=self.var_grayscale, command=self.apply_filters).pack(anchor="w", pady=6)
        ttk.Label(controls, text="Blur:").pack(anchor="w")
        self.blur_var = tk.DoubleVar(value=0.0)
        ttk.Scale(controls, from_=0.0, to=10.0, orient="horizontal", variable=self.blur_var, command=lambda *_: self.apply_filters()).pack(fill="x", pady=4)
        ttk.Label(controls, text="Brightness:").pack(anchor="w", pady=(8,0))
        self.brightness_var = tk.DoubleVar(value=1.0)
        ttk.Scale(controls, from_=0.2, to=2.0, orient="horizontal", variable=self.brightness_var, command=lambda *_: self.apply_filters()).pack(fill="x", pady=4)
        ttk.Label(controls, text="Contrast:").pack(anchor="w", pady=(8,0))
        self.contrast_var = tk.DoubleVar(value=1.0)
        ttk.Scale(controls, from_=0.2, to=2.0, orient="horizontal", variable=self.contrast_var, command=lambda *_: self.apply_filters()).pack(fill="x", pady=4)
        self._preview_tkimg = None

    def on_show(self):
        self.refresh_preview()

    def upload_image(self):
        filetypes = [("Image files", "*.jpg *.jpeg *.png *.bmp *.gif"), ("All files", "*.*")]
        path = filedialog.askopenfilename(title="Select an image", filetypes=filetypes)
        if not path:
            return
        try:
            img = Image.open(path).convert("RGBA")
        except Exception as e:
            messagebox.showerror("Error", f"Can't open image: {e}")
            return
        self.controller.current_image_path = path
        self.controller.current_original_image = img.copy()
        self.controller.current_work_image = img.copy()
        self.var_grayscale.set(False)
        self.blur_var.set(0.0)
        self.brightness_var.set(1.0)
        self.contrast_var.set(1.0)
        self.refresh_preview()

    def apply_filters(self):
        base = self.controller.current_original_image
        if base is None:
            return
        img = base.copy()
        if self.var_grayscale.get():
            img = img.convert("L").convert("RGBA")
        blur_val = float(self.blur_var.get())
        if blur_val > 0.01:
            img = img.filter(ImageFilter.GaussianBlur(radius=blur_val))
        bright = float(self.brightness_var.get())
        if abs(bright - 1.0) > 1e-3:
            img = ImageEnhance.Brightness(img).enhance(bright)
        contrast = float(self.contrast_var.get())
        if abs(contrast - 1.0) > 1e-3:
            img = ImageEnhance.Contrast(img).enhance(contrast)
        self.controller.current_work_image = img
        self.refresh_preview()

    def reset_edits(self):
        if self.controller.current_original_image is None:
            return
        self.var_grayscale.set(False)
        self.blur_var.set(0.0)
        self.brightness_var.set(1.0)
        self.contrast_var.set(1.0)
        self.controller.current_work_image = self.controller.current_original_image.copy()
        self.refresh_preview()

    def refresh_preview(self):
        img = self.controller.current_work_image
        if img is None:
            self.preview_label.config(text="No image loaded\nUse Upload Image", image="")
            return
        w = max(380, int(self.winfo_width() * 0.45))
        h = max(300, int(self.winfo_height() * 0.6))
        tmp = img.copy()
        tmp.thumbnail((w, h))
        self._preview_tkimg = ImageTk.PhotoImage(tmp)
        self.preview_label.config(image=self._preview_tkimg, text="")

    def save_edited(self):
        if self.controller.current_work_image is None:
            messagebox.showwarning("No Image", "Load an image first")
            return
        username = self.controller.current_user
        if not username:
            messagebox.showerror("Not logged in", "You must be logged in to save images")
            return
        orig_name = os.path.basename(self.controller.current_image_path) if self.controller.current_image_path else "untitled"
        out_path = save_image_file(self.controller.current_work_image.convert("RGBA"), username, orig_name)
        metadata = {
            "username": username,
            "orig_filename": orig_name,
            "saved_path": out_path,
            "filters": {
                "grayscale": bool(self.var_grayscale.get()),
                "blur": float(self.blur_var.get()),
                "brightness": float(self.brightness_var.get()),
                "contrast": float(self.contrast_var.get())
            },
            "saved_at": datetime.utcnow()
        }
        images_col.insert_one(metadata)
        messagebox.showinfo("Saved", f"Edited image saved to:\n{out_path}")

class GalleryPage(ttk.Frame):
    def __init__(self, parent, controller: MoodBoardApp):
        super().__init__(parent)
        self.controller = controller
        header = ttk.Frame(self)
        header.pack(fill="x", padx=12, pady=6)
        ttk.Button(header, text="Back", command=lambda: controller.show_page("DashboardPage")).pack(side="left")
        ttk.Label(header, text="My Gallery", style="Title.TLabel").pack(side="left", padx=12)
        self.canvas = tk.Canvas(self, bg="#f3f4f6", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=12, pady=8)
        self._tk_thumbs = []

    def on_show(self):
        self.reload()

    def reload(self):
        self.canvas.delete("all")
        self._tk_thumbs.clear()
        username = self.controller.current_user
        if not username:
            return
        docs = list(images_col.find({"username": username}).sort("saved_at", -1))
        x, y = 16, 12
        pad = 18
        thumb_w, thumb_h = 180, 130
        for doc in docs:
            path = doc.get("saved_path")
            if not path or not os.path.exists(path):
                continue
            try:
                img = Image.open(path)
                img.thumbnail((thumb_w, thumb_h))
                tkimg = ImageTk.PhotoImage(img)
                self._tk_thumbs.append(tkimg)
                rect = self.canvas.create_rectangle(x-6, y-6, x+thumb_w+6, y+thumb_h+36, fill="#ffffff", outline="#e5e7eb")
                img_id = self.canvas.create_image(x, y, anchor="nw", image=tkimg)
                self.canvas.create_text(x+4, y+thumb_h+10, anchor="nw", text=os.path.basename(path), font=("Segoe UI", 9))
                self.canvas.tag_bind(img_id, "<Button-1>", lambda ev, p=path: self.preview_image(p))
                x += thumb_w + pad
                if x + thumb_w > self.winfo_width() - 60:
                    x = 16
                    y += thumb_h + 70
            except Exception:
                continue

    def preview_image(self, path):
        if not os.path.exists(path):
            messagebox.showerror("Missing", "File not found")
            self.reload()
            return
        win = tk.Toplevel(self)
        win.title("Preview")
        win.geometry("640x520")
        try:
            img = Image.open(path)
            img.thumbnail((600, 420))
            tkimg = ImageTk.PhotoImage(img)
            lbl = ttk.Label(win, image=tkimg)
            lbl.image = tkimg
            lbl.pack(padx=10, pady=10)
        except Exception as e:
            messagebox.showerror("Error", f"Can't open image: {e}")
            win.destroy()
            return
        btnf = ttk.Frame(win)
        btnf.pack(pady=8)
        ttk.Button(btnf, text="Close", command=win.destroy).pack(side="left", padx=6)
        def do_delete():
            if not messagebox.askyesno("Confirm", "Delete this image?"):
                return
            images_col.delete_one({"saved_path": path})
            try:
                os.remove(path)
            except Exception:
                pass
            win.destroy()
            self.reload()
        ttk.Button(btnf, text="Delete", command=do_delete).pack(side="left", padx=6)

class MoodBoardPage(ttk.Frame):
    def __init__(self, parent, controller: MoodBoardApp):
        super().__init__(parent)
        self.controller = controller
        header = ttk.Frame(self)
        header.pack(fill="x", padx=12, pady=8)
        ttk.Button(header, text="Back", command=lambda: controller.show_page("DashboardPage")).pack(side="left", padx=6)
        ttk.Label(header, text="Mood Boards", style="Title.TLabel").pack(side="left", padx=12)
        btns = ttk.Frame(header)
        btns.pack(side="right")
        ttk.Button(btns, text="New Board", command=self.new_board).pack(side="left", padx=4)
        ttk.Button(btns, text="Add Image", command=self.add_image_to_board).pack(side="left", padx=4)
        ttk.Button(btns, text="Load Board", command=self.load_board_dialog).pack(side="left", padx=4)
        ttk.Button(btns, text="Save Board", command=self.save_board).pack(side="left", padx=4)
        ttk.Button(btns, text="Clear Canvas", command=self.clear_canvas).pack(side="left", padx=4)
        left = ttk.Frame(self)
        left.pack(side="left", fill="y", padx=(12,6), pady=8)
        ttk.Label(left, text="Your Boards", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0,6))
        self.boards_list = tk.Listbox(left, width=28, height=18)
        self.boards_list.pack(fill="y")
        self.boards_list.bind("<<ListboxSelect>>", self.on_board_select)
        ttk.Button(left, text="Delete Board", command=self.delete_selected_board).pack(pady=(8,0))
        self.canvas_frame = ttk.Frame(self)
        self.canvas_frame.pack(side="left", fill="both", expand=True, padx=(6,12), pady=8)
        self.canvas = tk.Canvas(self.canvas_frame, bg="#ffffff", highlightthickness=1, highlightbackground="#d1d5db")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.update()
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.board_items = []
        self._tk_images = []
        self.selected_item = None
        self.drag_offset = (0, 0)
        self.current_board = None
        self.refresh_board_list()

    def on_show(self):
        self.refresh_board_list()

    def refresh_board_list(self):
        self.boards_list.delete(0, tk.END)
        username = self.controller.current_user
        if not username:
            return
        docs = list(boards_col.find({"username": username}).sort("saved_at", -1))
        for d in docs:
            display = f"{d.get('board_name')}  —  {d.get('saved_at').strftime('%Y-%m-%d %H:%M') if d.get('saved_at') else ''}"
            self.boards_list.insert(tk.END, display)
        self._board_docs = docs

    def new_board(self):
        username = self.controller.current_user
        if not username:
            messagebox.showerror("Error", "Please login")
            return
        name = simpledialog.askstring("New Board", "Enter board name:")
        if not name:
            return
        doc = {
            "username": username,
            "board_name": name,
            "layout": [],
            "saved_at": datetime.utcnow()
        }
        res = boards_col.insert_one(doc)
        messagebox.showinfo("Created", f"Board '{name}' created.")
        self.refresh_board_list()

    def delete_selected_board(self):
        sel = self.boards_list.curselection()
        if not sel:
            messagebox.showwarning("Select", "Pick a board to delete.")
            return
        idx = sel[0]
        doc = self._board_docs[idx]
        if not messagebox.askyesno("Confirm", f"Delete board '{doc.get('board_name')}'?"):
            return
        boards_col.delete_one({"_id": doc["_id"]})
        messagebox.showinfo("Deleted", "Board removed.")
        self.refresh_board_list()
        if self.current_board == doc.get("board_name"):
            self.clear_canvas()

    def on_board_select(self, event):
        sel = self.boards_list.curselection()
        if not sel:
            return
        idx = sel[0]
        doc = self._board_docs[idx]
        self.load_board(doc.get("_id"))

    def add_image_to_board(self):
        if not self.current_board:
            if not messagebox.askyesno("No Board", "No board selected. Do you want to create a new board now?"):
                return
            self.new_board()
            self.refresh_board_list()
            if hasattr(self, "_board_docs") and self._board_docs:
                self.current_board = self._board_docs[0].get("board_name")
        choice = messagebox.askquestion("Image source", "Load from your saved uploads? (No = choose a file from disk)")
        if choice == "yes":
            username = self.controller.current_user
            docs = list(images_col.find({"username": username}).sort("saved_at", -1))
            if not docs:
                messagebox.showinfo("No images", "No saved images found. Upload in Editor first or choose a file.")
                return
            sel = SelectionDialog(self, docs, title="Select an uploaded image")
            self.wait_window(sel)
            pick = sel.selected_doc
            if not pick:
                return
            path = pick.get("saved_path")
        else:
            path = filedialog.askopenfilename(title="Select an image", filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.gif")])
            if not path:
                return
        try:
            pil = Image.open(path).convert("RGBA")
        except Exception as e:
            messagebox.showerror("Error", f"Can't open image: {e}")
            return
        pil.thumbnail((300, 300))
        tkimg = ImageTk.PhotoImage(pil)
        self._tk_images.append(tkimg)
        x, y = 40 + len(self.board_items)*10, 40 + len(self.board_items)*10
        item = self.canvas.create_image(x, y, anchor="nw", image=tkimg)
        meta = {"id": item, "path": path, "x": x, "y": y, "w": pil.width, "h": pil.height, "tk": tkimg}
        self.board_items.append(meta)
        if not self.current_board:
            self.current_board = simpledialog.askstring("Board", "Enter board name to save to:")
        self.canvas.tag_raise(item)

    def on_canvas_click(self, event):
        items = self.canvas.find_overlapping(event.x, event.y, event.x, event.y)
        if not items:
            self.selected_item = None
            return
        top = items[-1]
        for meta in self.board_items:
            if meta["id"] == top:
                self.selected_item = meta
                coords = self.canvas.coords(meta["id"])
                self.drag_offset = (event.x - coords[0], event.y - coords[1])
                self.canvas.tag_raise(meta["id"])
                break

    def on_canvas_drag(self, event):
        if not self.selected_item:
            return
        dx = event.x - self.drag_offset[0]
        dy = event.y - self.drag_offset[1]
        self.canvas.coords(self.selected_item["id"], dx, dy)
        self.selected_item["x"] = dx
        self.selected_item["y"] = dy

    def on_canvas_release(self, event):
        self.selected_item = None

    def save_board(self):
        if not self.current_board:
            messagebox.showwarning("No Board", "Select or create a board first.")
            return
        username = self.controller.current_user
        if not username:
            messagebox.showerror("Error", "Login first")
            return
        layout = []
        for meta in self.board_items:
            coords = self.canvas.coords(meta["id"])
            x, y = (coords[0], coords[1]) if coords else (meta.get("x", 0), meta.get("y", 0))
            layout.append({
                "path": meta["path"],
                "x": float(x),
                "y": float(y),
                "w": int(meta.get("w", 100)),
                "h": int(meta.get("h", 100))
            })
        boards_col.update_one(
            {"username": username, "board_name": self.current_board},
            {"$set": {"username": username, "board_name": self.current_board, "layout": layout, "saved_at": datetime.utcnow()}},
            upsert=True
        )
        messagebox.showinfo("Saved", f"Board '{self.current_board}' saved.")
        self.refresh_board_list()

    def load_board_dialog(self):
        username = self.controller.current_user
        if not username:
            messagebox.showerror("Error", "Login first")
            return
        docs = list(boards_col.find({"username": username}).sort("saved_at", -1))
        if not docs:
            messagebox.showinfo("No boards", "You have not created any boards yet.")
            return
        sel = BoardSelectionDialog(self, docs, title="Select a board to load")
        self.wait_window(sel)
        picked = sel.selected_doc
        if not picked:
            return
        self.load_board(picked.get("_id"))

    def load_board(self, board_id):
        doc = boards_col.find_one({"_id": ObjectId(board_id)})
        if not doc:
            messagebox.showerror("Error", "Board not found")
            return
        self.current_board = doc.get("board_name")
        self.clear_canvas()
        layout = doc.get("layout", [])
        for item in layout:
            path = item.get("path")
            if not path or not os.path.exists(path):
                continue
            try:
                pil = Image.open(path).convert("RGBA")
                pil.thumbnail((item.get("w", 200), item.get("h", 200)))
                tkimg = ImageTk.PhotoImage(pil)
                self._tk_images.append(tkimg)
                id_ = self.canvas.create_image(item.get("x", 10), item.get("y", 10), anchor="nw", image=tkimg)
                meta = {"id": id_, "path": path, "x": item.get("x", 0), "y": item.get("y", 0), "w": pil.width, "h": pil.height, "tk": tkimg}
                self.board_items.append(meta)
            except Exception:
                continue
        self.canvas.update()
        messagebox.showinfo("Loaded", f"Board '{self.current_board}' loaded.")

    def clear_canvas(self):
        self.canvas.delete("all")
        self.board_items.clear()
        self._tk_images.clear()
        self.selected_item = None

class ProfilePage(ttk.Frame):
    def __init__(self, parent, controller: MoodBoardApp):
        super().__init__(parent)
        self.controller = controller
        header = ttk.Frame(self)
        header.pack(fill="x", padx=12, pady=8)
        ttk.Button(header, text="Back", command=lambda: controller.show_page("DashboardPage")).pack(side="left")
        ttk.Label(header, text="Profile", style="Title.TLabel").pack(side="left", padx=12)
        self.card = Card(self, padding=14)
        self.card.pack(padx=12, pady=12, fill="x")
        ttk.Label(self.card, text="User details", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.info_label = ttk.Label(self.card, text="", font=("Segoe UI", 10))
        self.info_label.pack(anchor="w", pady=(6,0))

    def on_show(self):
        u = self.controller.current_user or "<not logged>"
        doc = users_col.find_one({"username": u})
        created = doc.get("created_at") if doc else None
        created_str = created.strftime("%Y-%m-%d %H:%M:%S") if created else "—"
        self.info_label.config(text=f"Username: {u}\nMember since: {created_str}")

class SelectionDialog(tk.Toplevel):
    def __init__(self, parent, docs, title="Select"):
        super().__init__(parent)
        self.title(title)
        self.selected_doc = None
        self.geometry("540x400")
        self.transient(parent)
        self.grab_set()
        left = ttk.Frame(self)
        left.pack(side="left", fill="y", padx=8, pady=8)
        self.listbox = tk.Listbox(left, width=40, height=20)
        self.listbox.pack()
        for d in docs:
            label = f"{d.get('orig_filename', os.path.basename(d.get('saved_path','')))} — {d.get('saved_at').strftime('%Y-%m-%d %H:%M') if d.get('saved_at') else ''}"
            self.listbox.insert(tk.END, label)
        right = ttk.Frame(self)
        right.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        self.preview_lbl = ttk.Label(right, text="Preview", anchor="center")
        self.preview_lbl.pack(fill="both", expand=True)
        btnf = ttk.Frame(right)
        btnf.pack(pady=6)
        ttk.Button(btnf, text="Select", command=self.do_select).pack(side="left", padx=6)
        ttk.Button(btnf, text="Cancel", command=self.destroy).pack(side="left", padx=6)
        self.docs = docs
        self._preview_img = None
        self.listbox.bind("<<ListboxSelect>>", self.on_select)

    def on_select(self, event):
        idx = self.listbox.curselection()
        if not idx:
            return
        doc = self.docs[idx[0]]
        path = doc.get("saved_path")
        if not path or not os.path.exists(path):
            self.preview_lbl.config(text="File not found")
            return
        try:
            img = Image.open(path)
            img.thumbnail((360, 300))
            self._preview_img = ImageTk.PhotoImage(img)
            self.preview_lbl.config(image=self._preview_img, text="")
        except Exception as e:
            self.preview_lbl.config(text=f"Can't open: {e}")

    def do_select(self):
        idx = self.listbox.curselection()
        if not idx:
            messagebox.showwarning("Select", "Pick an image")
            return
        self.selected_doc = self.docs[idx[0]]
        self.destroy()

class BoardSelectionDialog(tk.Toplevel):
    def __init__(self, parent, docs, title="Select board"):
        super().__init__(parent)
        self.title(title)
        self.selected_doc = None
        self.geometry("480x360")
        self.transient(parent)
        self.grab_set()
        lbl = ttk.Label(self, text="Select a board to load", font=("Segoe UI", 11, "bold"))
        lbl.pack(pady=8)
        self.listbox = tk.Listbox(self, width=60, height=12)
        self.listbox.pack(padx=8, pady=8)
        for d in docs:
            name = d.get("board_name")
            ts = d.get("saved_at")
            ts_str = ts.strftime("%Y-%m-%d %H:%M") if ts else ""
            self.listbox.insert(tk.END, f"{name}  —  {ts_str}")
        btnf = ttk.Frame(self)
        btnf.pack(pady=6)
        ttk.Button(btnf, text="Load", command=self.do_load).pack(side="left", padx=6)
        ttk.Button(btnf, text="Cancel", command=self.destroy).pack(side="left", padx=6)
        self.docs = docs

    def do_load(self):
        idx = self.listbox.curselection()
        if not idx:
            messagebox.showwarning("Select", "Pick a board")
            return
        self.selected_doc = self.docs[idx[0]]
        self.destroy()

def main():
    app = MoodBoardApp()
    app.mainloop()

if __name__ == "__main__":
    main()
