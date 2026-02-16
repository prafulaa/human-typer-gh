import customtkinter as ctk
import threading
import time
import human_typer  # Import the logic from the CLI script
import keyboard

# Theme Definitions (Light, Dark)
# Light = Natural Flow (Cream/Sage)
# Dark = Forest Mode (Deep Green/Neon)

COLOR_BG = ("#F2F4EC", "#0F1E15")       # Cream / Deep Forest
COLOR_CARD = ("#FFFFFF", "#1A2A20")     # White / Jungle Green
COLOR_PRIMARY = ("#5D7052", "#98E02E")  # Olive / Neon Lime
COLOR_SECONDARY = ("#C4A484", "#5D4037")# Tan / Dark Wood
COLOR_TEXT = ("#2D3328", "#E0E0E0")     # Dark Olive / Light Gray
COLOR_MUTED = ("#8A9485", "#6E8B76")    # Muted Green / Forest Gray
COLOR_ERROR = ("#D9534F", "#FF5252")    # Soft Red / Neon Red
COLOR_TRACK = ("#E0E0E0", "#2C3E30")    # Light Gray / Darker Jungle

class HumanTyperApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Human Typer - Natural Flow v2.0")
        self.geometry("450x780") 
        self.resizable(False, True)
        
        # Icon
        try:
            self.iconbitmap("human_typer_icon.ico")
        except:
            pass 

        # Default Theme
        ctk.set_appearance_mode("Light") 
        self.configure(fg_color=COLOR_BG)
        
        # Fonts
        self.font_header = ctk.CTkFont(family="Roboto", size=22, weight="bold")
        self.font_sub = ctk.CTkFont(family="Roboto", size=13)
        self.font_label = ctk.CTkFont(family="Roboto", size=14, weight="bold")
        self.font_body = ctk.CTkFont(family="Roboto", size=12)
        self.font_code = ctk.CTkFont(family="Consolas", size=12)

        # GRID SETUP
        self.grid_columnconfigure(0, weight=1)

        # --- HEADER ---
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, padx=20, pady=(25, 15), sticky="ew")
        
        # Icon 
        self.icon_label = ctk.CTkLabel(self.header_frame, text="🌿", font=ctk.CTkFont(size=32), text_color=COLOR_PRIMARY)
        self.icon_label.pack(side="left", padx=(0, 10))
        
        # Title Stack
        self.title_stack = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.title_stack.pack(side="left")
        
        self.title_label = ctk.CTkLabel(self.title_stack, text="Human Typer", font=self.font_header, text_color=COLOR_TEXT)
        self.title_label.pack(anchor="w")
        self.subtitle_label = ctk.CTkLabel(self.title_stack, text="Natural Flow v2.0", font=self.font_sub, text_color=COLOR_MUTED)
        self.subtitle_label.pack(anchor="w")

        # Buttons Stack (Settings + Theme)
        self.btn_stack = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.btn_stack.pack(side="right")

        # Theme Toggle
        self.theme_mode = "Light"
        self.theme_btn = ctk.CTkButton(self.btn_stack, text="🌙", width=40, height=40, font=ctk.CTkFont(size=20),
                                          fg_color=COLOR_CARD, text_color=COLOR_TEXT, hover_color=COLOR_TRACK, corner_radius=20, command=self.toggle_theme)
        self.theme_btn.pack(side="right", padx=(5, 0))

        # Settings Button
        self.settings_btn = ctk.CTkButton(self.btn_stack, text="⚙️", width=40, height=40, font=ctk.CTkFont(size=20),
                                          fg_color=COLOR_CARD, text_color=COLOR_TEXT, hover_color=COLOR_TRACK, corner_radius=20, command=self.toggle_settings)
        self.settings_btn.pack(side="right")

        # --- STATUS CARDS ROW ---
        self.cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.cards_frame.grid(row=1, column=0, padx=20, pady=5, sticky="ew")
        self.cards_frame.grid_columnconfigure(0, weight=1)
        self.cards_frame.grid_columnconfigure(1, weight=1)

        # Status Card
        self.card_status = ctk.CTkFrame(self.cards_frame, fg_color=COLOR_CARD, corner_radius=20)
        self.card_status.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        
        self.lbl_status_title = ctk.CTkLabel(self.card_status, text="STATUS", font=self.font_body, text_color=COLOR_MUTED)
        self.lbl_status_title.pack(anchor="w", padx=15, pady=(15, 0))
        self.lbl_status_val = ctk.CTkLabel(self.card_status, text="Ready", font=self.font_label, text_color=COLOR_TEXT)
        self.lbl_status_val.pack(anchor="w", padx=15, pady=(0, 5))
        self.bar_status = ctk.CTkProgressBar(self.card_status, height=4, progress_color=COLOR_PRIMARY)
        self.bar_status.set(0)
        self.bar_status.pack(fill="x", padx=15, pady=(5, 15))

        # Target Card
        self.card_target = ctk.CTkFrame(self.cards_frame, fg_color=COLOR_CARD, corner_radius=20)
        self.card_target.grid(row=0, column=1, padx=(10, 0), sticky="ew")

        self.lbl_target_title = ctk.CTkLabel(self.card_target, text="TARGET", font=self.font_body, text_color=COLOR_MUTED)
        self.lbl_target_title.pack(anchor="w", padx=15, pady=(15, 0))
        self.lbl_target_val = ctk.CTkLabel(self.card_target, text="Window", font=self.font_label, text_color=COLOR_TEXT)
        self.lbl_target_val.pack(anchor="w", padx=15, pady=(0, 5))
        self.bar_target = ctk.CTkProgressBar(self.card_target, height=4, progress_color=COLOR_SECONDARY)
        self.bar_target.set(1)
        self.bar_target.pack(fill="x", padx=15, pady=(5, 15))

        # --- PREVIEW AREA ---
        self.lbl_preview = ctk.CTkLabel(self, text="<>  Input Text", font=self.font_body, text_color=COLOR_MUTED)
        self.lbl_preview.grid(row=2, column=0, padx=30, pady=(20, 5), sticky="w")

        self.text_area = ctk.CTkTextbox(self, width=400, height=150, corner_radius=20, 
                                        fg_color=COLOR_CARD, text_color=COLOR_TEXT, font=self.font_code, border_width=0)
        self.text_area.grid(row=3, column=0, padx=20, pady=0, sticky="nsew")
        self.text_area.insert("0.0", "Paste your text here...")

        # --- CONTROLS CARD ---
        self.controls_card = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=25)
        self.controls_card.grid(row=4, column=0, padx=20, pady=25, sticky="ew")
        
        # Speed Slider
        self.lbl_speed_icon = ctk.CTkLabel(self.controls_card, text="⚡ Flow Speed", font=self.font_label, text_color=COLOR_TEXT)
        self.lbl_speed_icon.grid(row=0, column=0, padx=20, pady=(20, 5), sticky="w")
        
        self.lbl_speed_val = ctk.CTkLabel(self.controls_card, text="70 WPM", font=ctk.CTkFont(family="Roboto", size=12), text_color=COLOR_MUTED, fg_color=COLOR_TRACK, corner_radius=6)
        self.lbl_speed_val.grid(row=0, column=1, padx=20, pady=(20, 5), sticky="e")

        self.slider_speed = ctk.CTkSlider(self.controls_card, from_=30, to=150, number_of_steps=24, 
                                          button_color=COLOR_SECONDARY, button_hover_color=COLOR_PRIMARY, 
                                          progress_color=COLOR_PRIMARY, fg_color=COLOR_TRACK)
        self.slider_speed.set(70)
        self.slider_speed.grid(row=1, column=0, columnspan=2, padx=20, pady=(0, 15), sticky="ew")
        self.slider_speed.configure(command=self.update_speed_label)

        # Variation Slider (Error Rate)
        self.lbl_var_icon = ctk.CTkLabel(self.controls_card, text="🌲 Natural Variation", font=self.font_label, text_color=COLOR_TEXT)
        self.lbl_var_icon.grid(row=2, column=0, padx=20, pady=(5, 5), sticky="w")

        self.lbl_var_val = ctk.CTkLabel(self.controls_card, text="6.0 %", font=ctk.CTkFont(family="Roboto", size=12), text_color=COLOR_MUTED, fg_color=COLOR_TRACK, corner_radius=6)
        self.lbl_var_val.grid(row=2, column=1, padx=20, pady=(5, 5), sticky="e")

        self.slider_var = ctk.CTkSlider(self.controls_card, from_=0, to=0.20, number_of_steps=20,
                                        button_color=COLOR_SECONDARY, button_hover_color=COLOR_PRIMARY,
                                        progress_color=COLOR_SECONDARY, fg_color=COLOR_TRACK)
        self.slider_var.set(0.06)
        self.slider_var.grid(row=3, column=0, columnspan=2, padx=20, pady=(0, 20), sticky="ew")
        self.slider_var.configure(command=self.update_var_label)

        # --- HIDDEN SETTINGS MODAL (Advanced) ---
        self.settings_visible = False
        self.settings_frame = ctk.CTkFrame(self, fg_color=COLOR_TRACK, corner_radius=15, height=0) # Hidden initially
        
        self.chk_indent = ctk.CTkCheckBox(self.settings_frame, text="Anti-Double Indent", font=self.font_body, 
                                          fg_color=COLOR_PRIMARY, text_color=COLOR_TEXT, hover_color=COLOR_PRIMARY)
        self.chk_indent.pack(side="left", padx=20, pady=10)
        
        self.ent_hotkey = ctk.CTkEntry(self.settings_frame, width=80, font=self.font_code, fg_color=COLOR_CARD, text_color=COLOR_TEXT)
        self.ent_hotkey.insert(0, "ctrl+q")
        self.ent_hotkey.pack(side="right", padx=20, pady=10)
        
        self.lbl_hotkey = ctk.CTkLabel(self.settings_frame, text="Stop Hotkey:", font=self.font_body, text_color=COLOR_TEXT)
        self.lbl_hotkey.pack(side="right", padx=5)

        # --- START BUTTON ---
        self.btn_start = ctk.CTkButton(self, text="▶  START SESSION", height=55, corner_radius=27, 
                                       font=ctk.CTkFont(family="Roboto", size=16, weight="bold"),
                                       fg_color=COLOR_PRIMARY, hover_color="#4B5A42", text_color="#FFFFFF",
                                       command=self.start_typing_thread)
        self.btn_start.grid(row=6, column=0, padx=30, pady=10, sticky="ew")

        # Footer
        self.lbl_footer = ctk.CTkLabel(self, text="🌷 Natural Typing Environment", font=ctk.CTkFont(size=10), text_color=COLOR_MUTED)
        self.lbl_footer.grid(row=7, column=0, pady=(10, 20))

        # Logic
        self.typing_thread = None
        self.stop_event = threading.Event()

    def toggle_theme(self):
        if self.theme_mode == "Light":
            ctk.set_appearance_mode("Dark")
            self.theme_mode = "Dark"
            self.theme_btn.configure(text="☀️")
            self.subtitle_label.configure(text="Forest Mode v2.0")
            self.icon_label.configure(text="🌲")
            self.lbl_footer.configure(text="🌲 Deep Forest Environment")
        else:
            ctk.set_appearance_mode("Light")
            self.theme_mode = "Light"
            self.theme_btn.configure(text="🌙")
            self.subtitle_label.configure(text="Natural Flow v2.0")
            self.icon_label.configure(text="🌿")
            self.lbl_footer.configure(text="🌷 Natural Typing Environment")

    def toggle_settings(self):
        if not self.settings_visible:
            self.settings_frame.grid(row=5, column=0, padx=30, pady=(0, 10), sticky="ew")
            self.settings_visible = True
        else:
            self.settings_frame.grid_forget()
            self.settings_visible = False

    def update_speed_label(self, value):
        self.lbl_speed_val.configure(text=f"{int(value)} WPM")

    def update_var_label(self, value):
        self.lbl_var_val.configure(text=f"{value*100:.1f} %")

    def start_typing_thread(self):
        if self.typing_thread and self.typing_thread.is_alive():
            return
        
        text = self.text_area.get("0.0", "end")
        if "Paste your text here..." in text and len(text) < 40:
             if text.strip() == "Paste your text here...":
                 self.lbl_status_val.configure(text="No Text!", text_color=COLOR_ERROR)
                 return
        
        if not text.strip():
             self.lbl_status_val.configure(text="No Text!", text_color=COLOR_ERROR)
             return

        text = text.rstrip()
        wpm = int(self.slider_speed.get())
        errors = self.slider_var.get()
        delay = 5 
        suppress_indent = self.chk_indent.get()
        hotkey_str = self.ent_hotkey.get().strip()

        # Update UI state
        self.stop_event.clear()
        self.btn_start.configure(state="disabled", text="RUNNING...", fg_color=COLOR_SECONDARY)
        self.text_area.configure(state="disabled")
        self.lbl_status_val.configure(text="Initializing...", text_color=COLOR_PRIMARY)
        self.bar_status.configure(progress_color=COLOR_SECONDARY) 
        
        # Hotkey registration
        try:
            keyboard.add_hotkey(hotkey_str, self.stop_typing)
        except:
            self.lbl_status_val.configure(text="Hotkey Error", text_color=COLOR_ERROR)

        self.typing_thread = threading.Thread(target=self.run_typing, args=(text, wpm, errors, delay, suppress_indent, hotkey_str))
        self.typing_thread.start()

    def stop_typing(self):
        if self.typing_thread and self.typing_thread.is_alive():
            self.lbl_status_val.configure(text="Stopping...", text_color=COLOR_ERROR)
            self.stop_event.set()

    def run_typing(self, text, wpm, errors, delay, suppress_indent, hotkey_str):
        # Countdown
        for i in range(delay, 0, -1):
            if self.stop_event.is_set(): break
            self.lbl_status_val.configure(text=f"Click Window: {i}s", text_color=COLOR_SECONDARY)
            self.bar_status.set(1.0 - (i/delay))
            time.sleep(1)
        
        if not self.stop_event.is_set():
            self.lbl_status_val.configure(text="Injecting...", text_color=COLOR_PRIMARY)
            self.bar_status.configure(progress_color=COLOR_PRIMARY)
            self.bar_status.set(0) 
            
            # Since we don't track progress % in human_typer, we just run it
            human_typer.type_text(text, wpm=wpm, error_rate=errors, start_delay=0, stop_event=self.stop_event, suppress_indent=suppress_indent)
        
        # Cleanup
        try: keyboard.remove_hotkey(hotkey_str)
        except: pass

        # Reset UI
        is_stopped = self.stop_event.is_set()
        self.lbl_status_val.configure(text="Aborted" if is_stopped else "Completed", text_color=COLOR_ERROR if is_stopped else COLOR_PRIMARY)
        self.btn_start.configure(state="normal", text="▶  START SESSION", fg_color=COLOR_PRIMARY)
        self.text_area.configure(state="normal")
        self.bar_status.set(0)
        self.bar_status.configure(progress_color=COLOR_PRIMARY)

if __name__ == "__main__":
    app = HumanTyperApp()
    app.mainloop()
