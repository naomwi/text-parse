import customtkinter as ctk
import threading
import asyncio
import logging
import sys
from pathlib import Path
from types import SimpleNamespace
from main import main_loop
from config import OUTPUT_DIR, MAX_CHAPTERS

# Set theme and color options
ctk.set_appearance_mode("System")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

class TextHandler(logging.Handler):
    """This class allows you to log to a Tkinter Text or Scrollbar widget"""
    def __init__(self, text_widget):
        logging.Handler.__init__(self)
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        def append():
            self.text_widget.configure(state="normal")
            self.text_widget.insert(ctk.END, msg + '\n')
            self.text_widget.configure(state="disabled")
            self.text_widget.see(ctk.END)
        # Use after to add log text from a separate thread back to the main GUI thread
        self.text_widget.after(0, append)

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Novelpia Extractor & Translator")
        self.geometry("800x600")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Create main frame
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.main_frame.grid_columnconfigure(1, weight=1)

        # Title Label
        self.title_label = ctk.CTkLabel(self.main_frame, text="Novelpia & Pixiv Extractor", font=ctk.CTkFont(size=20, weight="bold"))
        self.title_label.grid(row=0, column=0, columnspan=2, padx=20, pady=(20, 10))

        # Platform Dropdown
        self.platform_label = ctk.CTkLabel(self.main_frame, text="Platform:")
        self.platform_label.grid(row=1, column=0, padx=20, pady=10, sticky="w")
        self.platform_var = ctk.StringVar(value="Novelpia (novelpia.com)")
        self.platform_dropdown = ctk.CTkComboBox(self.main_frame, variable=self.platform_var, values=["Novelpia (novelpia.com)", "Pixiv (pixiv.net)"], command=self.update_placeholder)
        self.platform_dropdown.grid(row=1, column=1, padx=20, pady=10, sticky="ew")

        # Start URL
        self.url_label = ctk.CTkLabel(self.main_frame, text="Start Chapter URL:")
        self.url_label.grid(row=2, column=0, padx=20, pady=10, sticky="w")
        self.url_entry = ctk.CTkEntry(self.main_frame, placeholder_text="https://novelpia.com/novel/...")
        self.url_entry.grid(row=2, column=1, padx=20, pady=10, sticky="ew")

        # Max Chapters
        self.ch_label = ctk.CTkLabel(self.main_frame, text="Max Chapters:")
        self.ch_label.grid(row=3, column=0, padx=20, pady=10, sticky="w")
        self.ch_entry = ctk.CTkEntry(self.main_frame)
        self.ch_entry.insert(0, str(MAX_CHAPTERS))
        self.ch_entry.grid(row=3, column=1, padx=20, pady=10, sticky="ew")

        # Output Dir
        self.out_label = ctk.CTkLabel(self.main_frame, text="Output Directory:")
        self.out_label.grid(row=4, column=0, padx=20, pady=10, sticky="w")
        
        # Create a frame to hold the entry and the button
        self.out_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.out_frame.grid(row=4, column=1, padx=20, pady=10, sticky="ew")
        self.out_frame.grid_columnconfigure(0, weight=1)
        
        self.out_entry = ctk.CTkEntry(self.out_frame)
        self.out_entry.insert(0, str(OUTPUT_DIR))
        self.out_entry.grid(row=0, column=0, sticky="ew")
        
        self.out_btn = ctk.CTkButton(self.out_frame, text="Browse...", width=80, command=self.browse_directory)
        self.out_btn.grid(row=0, column=1, padx=(10, 0))

        # Translate Toggle
        self.translate_var = ctk.BooleanVar(value=False)
        self.translate_switch = ctk.CTkSwitch(self.main_frame, text="Enable Vietnamese Translation (Gemini 2.5 Pro)", variable=self.translate_var)
        self.translate_switch.grid(row=5, column=0, columnspan=2, padx=20, pady=20, sticky="w")

        # Run Button
        self.run_button = ctk.CTkButton(self.main_frame, text="Start Extraction", command=self.show_login_warning, height=40)
        self.run_button.grid(row=6, column=0, columnspan=2, padx=20, pady=10, sticky="ew")

        # Log Text Box
        self.log_box = ctk.CTkTextbox(self.main_frame, state="disabled")
        self.log_box.grid(row=7, column=0, columnspan=2, padx=20, pady=20, sticky="nsew")
        self.main_frame.grid_rowconfigure(7, weight=1)

        self.setup_logging()

    def update_placeholder(self, choice):
        if "Pixiv" in choice:
            self.url_entry.configure(placeholder_text="https://www.pixiv.net/novel/...")
            self.title_label.configure(text="Pixiv Novel Extractor")
        else:
            self.url_entry.configure(placeholder_text="https://novelpia.com/novel/...")
            self.title_label.configure(text="Novelpia Chapter Extractor")

    def show_login_warning(self):
        """Show a warning dialog to remind the user about logging in."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Before You Begin...")
        dialog.geometry("450x250")
        dialog.attributes("-topmost", True)
        
        # Center dialog
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 450) // 2
        y = self.winfo_y() + (self.winfo_height() - 250) // 2
        dialog.geometry(f"+{x}+{y}")
        
        platform = self.platform_var.get()
        msg = f"When the extraction begins, a Google Chrome window will open.\n\n"
        msg += f"You MUST be logged into {platform} in that window for the scraper to read R-18, PLUS, or restricted content.\n\n"
        msg += "If you are not logged in, please open the browser, log in manually right now, and then click Continue!"
        
        label = ctk.CTkLabel(dialog, text=msg, wraplength=400, justify="center")
        label.pack(padx=20, pady=30)
        
        def on_continue():
            dialog.destroy()
            self.start_thread()
            
        def on_cancel():
            dialog.destroy()
            
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=10)
        
        cancel_btn = ctk.CTkButton(btn_frame, text="Cancel", fg_color="gray", hover_color="darkgray", command=on_cancel)
        cancel_btn.pack(side="left", padx=10)
        
        continue_btn = ctk.CTkButton(btn_frame, text="I'm Ready! ->", command=on_continue)
        continue_btn.pack(side="left", padx=10)

    def setup_logging(self):
        text_handler = TextHandler(self.log_box)
        text_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
        
        # Add handler to main logger
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        # Prevent adding multiple handlers if setup_logging runs again
        if not any(isinstance(h, TextHandler) for h in logger.handlers):
            logger.addHandler(text_handler)

    def start_thread(self):
        self.run_button.configure(state="disabled", text="Running...")
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", ctk.END)
        self.log_box.configure(state="disabled")

        # Get values
        url = self.url_entry.get().strip()
        
        try:
            chapters = int(self.ch_entry.get().strip())
        except ValueError:
            logging.error("Max Chapters must be an integer.")
            self.run_button.configure(state="normal", text="Start Extraction")
            return

        out_dir = Path(self.out_entry.get().strip())
        translate = self.translate_var.get()

        args = SimpleNamespace(
            mode="persistent",
            port=9222,
            start_url=url if url else None,
            max_chapters=chapters,
            output_dir=out_dir,
            translate=translate,
            gui=True
        )

        threading.Thread(target=self.run_asyncio_loop, args=(args,), daemon=True).start()

    def run_asyncio_loop(self, args):
        try:
            asyncio.run(main_loop(args))
        except Exception as e:
            logging.error(f"Execution Error: {e}")
        finally:
            self.after(0, lambda: self.run_button.configure(state="normal", text="Start Extraction"))

    def browse_directory(self):
        directory = ctk.filedialog.askdirectory()
        if directory:
            self.out_entry.delete(0, ctk.END)
            self.out_entry.insert(0, directory)

if __name__ == "__main__":
    app = App()
    app.mainloop()
