import customtkinter as ctk
from tkinter import filedialog, messagebox
from pathlib import Path
from threading import Thread, Event
import json

from enhanced_downloader import GoogleDriveDownloader

# Set global modern theme settings
ctk.set_appearance_mode("System")  # Follows Windows/macOS dark/light mode
ctk.set_default_color_theme("blue")  # Clean, modern blue accent

def extract_folder_id(folder_input: str) -> str:
    """
    Extract folder ID from either a full Google Drive link or just the ID.
    
    Handles:
    - https://drive.google.com/drive/folders/1A2b3C4d5E6f7G8h9I0j...
    - 1A2b3C4d5E6f7G8h9I0j...
    
    Returns the folder ID or raises ValueError if invalid.
    """
    folder_input = folder_input.strip()
    
    # If it's a link, extract the ID
    if "drive.google.com" in folder_input:
        try:
            # Extract ID from URL: look for /folders/ followed by the ID
            if "/folders/" in folder_input:
                folder_id = folder_input.split("/folders/")[1].split("?")[0].split("&")[0]
                return folder_id.strip()
            else:
                raise ValueError("Could not find 'folders/' in the link")
        except (IndexError, AttributeError):
            raise ValueError("Invalid Google Drive folder link format")
    else:
        # Assume it's just the folder ID
        if len(folder_input) > 10:  # Folder IDs are typically long alphanumeric strings
            return folder_input
        else:
            raise ValueError("Invalid folder ID format")

class DownloadAutomationUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Google Drive Download Automation")
        
        # Modern UX: Responsive window sizing with better proportions
        self.root.geometry("900x1050")
        self.root.minsize(700, 800)
        
        # State management
        self.downloader = None
        self.is_downloading = False
        
        # True cancellation token for threading
        self.cancel_event = Event()

        self.create_widgets()
        self.load_last_values()

    def create_widgets(self):
        """Create modern, polished UI widgets using CustomTkinter."""
        
        # Main scrollable container
        self.main_container = ctk.CTkScrollableFrame(
            self.root, 
            fg_color="transparent",
            scrollbar_button_color=("gray70", "gray30")
        )
        self.main_container.pack(fill="both", expand=True, padx=20, pady=20)

        # --- HEADER SECTION ---
        self.header_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.header_frame.pack(fill="x", pady=(0, 30))
        
        self.title = ctk.CTkLabel(
            self.header_frame, 
            text="📁 Google Drive Download", 
            font=ctk.CTkFont(size=28, weight="bold")
        )
        self.title.pack(anchor="w", pady=(0, 5))
        
        self.subtitle = ctk.CTkLabel(
            self.header_frame, 
            text="Download entire folders while preserving your folder structure", 
            text_color=("gray50", "gray50"),
            font=ctk.CTkFont(size=12)
        )
        self.subtitle.pack(anchor="w", fill="x")

        # --- SOURCE SECTION ---
        self.source_frame = ctk.CTkFrame(self.main_container, fg_color=("gray95", "gray10"), corner_radius=10)
        self.source_frame.pack(fill="x", pady=(0, 15), padx=0)
        
        self.source_inner = ctk.CTkFrame(self.source_frame, fg_color="transparent")
        self.source_inner.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(
            self.source_inner, 
            text="📤 Source", 
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(
            self.source_inner, 
            text="Folder Link or ID", 
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=("gray50", "gray50")
        ).pack(anchor="w", pady=(0, 4))
        
        self.source_folder_var = ctk.StringVar()
        self.source_entry = ctk.CTkEntry(
            self.source_inner, 
            textvariable=self.source_folder_var,
            placeholder_text="https://drive.google.com/drive/folders/... or folder ID",
            height=36
        )
        self.source_entry.pack(fill="x", pady=(0, 0))

        # --- DESTINATION SECTION ---
        self.dest_frame = ctk.CTkFrame(self.main_container, fg_color=("gray95", "gray10"), corner_radius=10)
        self.dest_frame.pack(fill="x", pady=(0, 15), padx=0)
        
        self.dest_inner = ctk.CTkFrame(self.dest_frame, fg_color="transparent")
        self.dest_inner.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(
            self.dest_inner, 
            text="💾 Destination", 
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(
            self.dest_inner, 
            text="Save Location", 
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=("gray50", "gray50")
        ).pack(anchor="w", pady=(0, 4))
        
        dest_row = ctk.CTkFrame(self.dest_inner, fg_color="transparent")
        dest_row.pack(fill="x")
        
        self.dest_folder_var = ctk.StringVar()
        self.dest_entry = ctk.CTkEntry(
            dest_row, 
            textvariable=self.dest_folder_var, 
            height=36
        )
        self.dest_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.browse_dest_btn = ctk.CTkButton(
            dest_row, 
            text="Browse", 
            width=85, 
            height=36,
            command=self.browse_destination_folder
        )
        self.browse_dest_btn.pack(side="right")

        # --- CREDENTIALS SECTION ---
        self.creds_frame = ctk.CTkFrame(self.main_container, fg_color=("gray95", "gray10"), corner_radius=10)
        self.creds_frame.pack(fill="x", pady=(0, 15), padx=0)
        
        self.creds_inner = ctk.CTkFrame(self.creds_frame, fg_color="transparent")
        self.creds_inner.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(
            self.creds_inner, 
            text="🔐 Authentication", 
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", pady=(0, 10))

        # Token file row
        token_label_frame = ctk.CTkFrame(self.creds_inner, fg_color="transparent")
        token_label_frame.pack(anchor="w", fill="x", pady=(0, 4))
        
        ctk.CTkLabel(
            token_label_frame, 
            text="Token File", 
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=("gray50", "gray50")
        ).pack(side="left", padx=(0, 8))
        
        ctk.CTkLabel(
            token_label_frame, 
            text="(Stores your authentication)", 
            font=ctk.CTkFont(size=9),
            text_color=("gray60", "gray40")
        ).pack(side="left")
        
        token_row = ctk.CTkFrame(self.creds_inner, fg_color="transparent")
        token_row.pack(fill="x", pady=(0, 12))
        
        self.token_file_var = ctk.StringVar()
        self.token_entry = ctk.CTkEntry(
            token_row, 
            textvariable=self.token_file_var, 
            height=36
        )
        self.token_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        
        self.browse_token_btn = ctk.CTkButton(
            token_row, 
            text="Browse", 
            width=75, 
            height=36,
            command=self.browse_token_file
        )
        self.browse_token_btn.pack(side="left", padx=(0, 8))
        
        self.change_account_btn = ctk.CTkButton(
            token_row, 
            text="🔄 Switch Account", 
            width=130, 
            height=36,
            fg_color=("gray70", "gray30"),
            text_color=("black", "white"),
            hover_color=("gray60", "gray40"),
            command=self.change_account
        )
        self.change_account_btn.pack(side="left")
        
        # Help text below buttons
        ctk.CTkLabel(
            self.creds_inner, 
            text="💡 Tip: Use 'Switch Account' to authenticate with a different Google account", 
            font=ctk.CTkFont(size=9),
            text_color=("gray50", "gray50")
        ).pack(anchor="w", pady=(0, 12))

        # Secret file row
        ctk.CTkLabel(
            self.creds_inner, 
            text="Client Secret", 
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=("gray50", "gray50")
        ).pack(anchor="w", pady=(0, 4))
        
        secret_row = ctk.CTkFrame(self.creds_inner, fg_color="transparent")
        secret_row.pack(fill="x")
        
        self.secret_file_var = ctk.StringVar()
        self.secret_entry = ctk.CTkEntry(
            secret_row, 
            textvariable=self.secret_file_var, 
            height=36
        )
        self.secret_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        
        self.browse_secret_btn = ctk.CTkButton(
            secret_row, 
            text="Browse", 
            width=85, 
            height=36,
            command=self.browse_secret_file
        )
        self.browse_secret_btn.pack(side="right")

        # --- FILTERS SECTION ---
        self.filters_frame = ctk.CTkFrame(self.main_container, fg_color=("gray95", "gray10"), corner_radius=10)
        self.filters_frame.pack(fill="x", pady=(0, 15))
        
        self.filters_inner = ctk.CTkFrame(self.filters_frame, fg_color="transparent")
        self.filters_inner.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(
            self.filters_inner, 
            text="🎯 File Filters (Optional)", 
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", pady=(0, 10))
        
        filter_row = ctk.CTkFrame(self.filters_inner, fg_color="transparent")
        filter_row.pack(fill="x")

        self.skip_photos_var = ctk.BooleanVar(value=False)
        self.photo_switch = ctk.CTkSwitch(
            filter_row, 
            text="Skip Photos", 
            variable=self.skip_photos_var,
            font=ctk.CTkFont(size=11)
        )
        self.photo_switch.pack(side="left", padx=(0, 20))

        self.skip_videos_var = ctk.BooleanVar(value=False)
        self.video_switch = ctk.CTkSwitch(
            filter_row, 
            text="Skip Videos", 
            variable=self.skip_videos_var,
            font=ctk.CTkFont(size=11)
        )
        self.video_switch.pack(side="left", padx=(0, 20))

        self.skip_audio_var = ctk.BooleanVar(value=False)
        self.audio_switch = ctk.CTkSwitch(
            filter_row, 
            text="Skip Audio", 
            variable=self.skip_audio_var,
            font=ctk.CTkFont(size=11)
        )
        self.audio_switch.pack(side="left")

        # --- CONSOLE OUTPUT SECTION ---
        self.logs_frame = ctk.CTkFrame(self.main_container, fg_color=("gray95", "gray10"), corner_radius=10)
        self.logs_frame.pack(fill="both", expand=True, pady=(0, 15))
        
        self.logs_inner = ctk.CTkFrame(self.logs_frame, fg_color="transparent")
        self.logs_inner.pack(fill="both", expand=True, padx=16, pady=16)

        logs_header = ctk.CTkFrame(self.logs_inner, fg_color="transparent")
        logs_header.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(
            logs_header, 
            text="📋 Console Output", 
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(side="left")
        
        self.clear_log_btn = ctk.CTkButton(
            logs_header, 
            text="Clear", 
            width=60, 
            height=28,
            font=ctk.CTkFont(size=10),
            fg_color=("gray70", "gray30"),
            text_color=("black", "white"),
            hover_color=("gray60", "gray40"),
            command=self.clear_log
        )
        self.clear_log_btn.pack(side="right")

        self.log_text = ctk.CTkTextbox(
            self.logs_inner, 
            font=ctk.CTkFont(family="Consolas", size=10),
            scrollbar_button_color=("gray70", "gray30"),
            height=150
        )
        self.log_text.pack(fill="both", expand=True)

        # --- ACTION FOOTER ---
        self.footer_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.footer_frame.pack(fill="x", side="bottom", padx=20, pady=15)

        button_container = ctk.CTkFrame(self.footer_frame, fg_color="transparent")
        button_container.pack(fill="x", expand=True)

        self.download_btn = ctk.CTkButton(
            button_container, 
            text="▶ Start Download", 
            font=ctk.CTkFont(size=14, weight="bold"),
            height=44,
            command=self.start_download
        )
        self.download_btn.pack(side="left", fill="x", expand=True, padx=(0, 12))

        self.cancel_btn = ctk.CTkButton(
            button_container, 
            text="⏹ Cancel", 
            font=ctk.CTkFont(size=14, weight="bold"),
            height=44,
            fg_color="#ef4444", 
            hover_color="#dc2626",
            state="disabled",
            width=120,
            command=self.cancel_download
        )
        self.cancel_btn.pack(side="right")

    def browse_destination_folder(self):
        folder = filedialog.askdirectory(title="Select Destination Folder")
        if folder:
            self.dest_folder_var.set(folder)
            self.save_last_values()

    def browse_token_file(self):
        file = filedialog.askopenfilename(title="Select Token File", filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if file:
            self.token_file_var.set(file)
            self.save_last_values()

    def browse_secret_file(self):
        file = filedialog.askopenfilename(title="Select Client Secret File", filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if file:
            self.secret_file_var.set(file)
            self.save_last_values()

    def change_account(self):
        """Switch to a different Google account."""
        token_path = self.token_file_var.get().strip()
        
        if not token_path:
            messagebox.showerror("Error", "Please specify a token file path first.")
            return
        
        # Confirm the action
        result = messagebox.askyesno(
            "Change Account",
            "This will remove your current authentication token.\n\n"
            "You'll need to log in with a different Google account on the next download.\n\n"
            "Continue?"
        )
        
        if not result:
            return
        
        try:
            # Remove the token file
            token_file_path = Path(token_path)
            if token_file_path.exists():
                token_file_path.unlink()
            
            # Clear the logs and show instructions
            self.clear_log()
            self.log_message("=" * 70)
            self.log_message("ACCOUNT CHANGED - FOLLOW THESE STEPS:")
            self.log_message("=" * 70)
            self.log_message("")
            self.log_message("1. Click 'Start Download' with any folder ID")
            self.log_message("")
            self.log_message("2. A browser window will open asking you to:")
            self.log_message("   - Sign in with your Google account")
            self.log_message("   - Grant permission to access Google Drive")
            self.log_message("")
            self.log_message("3. After authentication, the download will begin")
            self.log_message("")
            self.log_message("4. Your new account's token will be saved for future downloads")
            self.log_message("")
            self.log_message("=" * 70)
            self.log_message("")
            
            messagebox.showinfo(
                "Success",
                "Token removed successfully!\n\n"
                "Instructions have been displayed in the console.\n\n"
                "Click 'Start Download' to authenticate with a different account."
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to remove token file: {str(e)}")

    def log_message(self, message: str):
        # CTkTextbox requires enabling/disabling states to make it read-only visually but editable via code
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")

    def clear_log(self):
        self.log_text.delete("1.0", "end")

    def save_last_values(self):
        config_data = {
            "source_folder_id": self.source_folder_var.get(),
            "destination_folder": self.dest_folder_var.get(),
            "token_file": self.token_file_var.get(),
            "secret_file": self.secret_file_var.get(),
            "skip_photos": self.skip_photos_var.get(),
            "skip_videos": self.skip_videos_var.get(),
            "skip_audio": self.skip_audio_var.get(),
        }
        try:
            with open(Path(".") / "ui_config.json", "w") as f:
                json.dump(config_data, f, indent=2)
        except Exception:
            pass

    def load_last_values(self):
        config_path = Path(".") / "ui_config.json"
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    config_data = json.load(f)
                    self.source_folder_var.set(config_data.get("source_folder_id", ""))
                    self.dest_folder_var.set(config_data.get("destination_folder", ""))
                    self.token_file_var.set(config_data.get("token_file", ""))
                    self.secret_file_var.set(config_data.get("secret_file", ""))
                    self.skip_photos_var.set(config_data.get("skip_photos", False))
                    self.skip_videos_var.set(config_data.get("skip_videos", False))
                    self.skip_audio_var.set(config_data.get("skip_audio", False))
            except Exception:
                pass

    def validate_inputs(self) -> bool:
        if not self.source_folder_var.get().strip() or not self.dest_folder_var.get().strip():
            messagebox.showerror("Error", "Source Folder and Destination are required.")
            return False
        if not self.token_file_var.get().strip() or not self.secret_file_var.get().strip():
            messagebox.showerror("Error", "Credentials (Token and Secret files) are required.")
            return False
        return True
    
    def get_folder_id(self) -> str:
        """Extract and validate folder ID from user input."""
        try:
            folder_id = extract_folder_id(self.source_folder_var.get())
            return folder_id
        except ValueError as e:
            messagebox.showerror("Invalid Folder Link", f"{str(e)}\n\nPlease paste a valid Google Drive folder link or folder ID.")
            return None

    def start_download(self):
        if self.is_downloading:
            return

        if not self.validate_inputs():
            return
        
        # Extract folder ID from link/input
        folder_id = self.get_folder_id()
        if not folder_id:
            return

        self.is_downloading = True
        self.cancel_event.clear()  # Reset the cancel token
        
        self.download_btn.configure(state="disabled", text="Downloading...")
        self.cancel_btn.configure(state="normal")
        self.clear_log()

        file_filters = {
            "photos": self.skip_photos_var.get(),
            "videos": self.skip_videos_var.get(),
            "audio": self.skip_audio_var.get(),
        }

        self.save_last_values()

        # Run in thread, passing the cancel_event
        download_thread = Thread(
            target=self.run_download,
            args=(
                folder_id,
                self.dest_folder_var.get(),
                self.secret_file_var.get(),
                self.token_file_var.get(),
                file_filters,
                self.cancel_event  # Crucial: passing the event to the thread
            ),
            daemon=True,
        )
        download_thread.start()

    def run_download(self, folder_id, dest_dir, secret_file, token_file, file_filters, cancel_event):
        try:
            self.log_message("Starting download process...")
            self.log_message(f"Destination: {dest_dir}\n")

            self.downloader = GoogleDriveDownloader(
                credentials_file=secret_file,
                token_file=token_file,
                log_callback=self.log_message,
                cancel_event=cancel_event  # Passing the event down to your downloader logic
            )

            # Execution logic
            self.downloader.download_folder(
                folder_id=folder_id,
                download_dir=dest_dir,
                file_filters=file_filters,
            )

            # Only show success if no exception was raised
            if cancel_event.is_set():
                self.log_message("\n[INFO] Download was cancelled by the user.")
            else:
                self.log_message("\n[SUCCESS] Download completed!")

        except Exception as e:
            # Error already logged by downloader, just ensure no success message is shown
            pass
            
        finally:
            # Reset UI via thread-safe call (CustomTkinter allows basic configure from threads)
            self.is_downloading = False
            self.download_btn.configure(state="normal", text="Start Download")
            self.cancel_btn.configure(state="disabled")

    def cancel_download(self):
        """Trigger the actual thread cancellation."""
        if self.is_downloading:
            self.log_message("\n[INFO] Cancelling... Waiting for current file to finish...")
            self.cancel_btn.configure(state="disabled", text="Stopping...")
            self.cancel_event.set()  # This alerts the downloader thread to stop

def main():
    root = ctk.CTk()
    DownloadAutomationUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()