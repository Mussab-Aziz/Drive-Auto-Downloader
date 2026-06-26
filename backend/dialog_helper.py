import sys
import tkinter as tk
from tkinter import filedialog

def main():
    if len(sys.argv) < 2:
        return
    
    action = sys.argv[1]
    title = sys.argv[2] if len(sys.argv) > 2 else "Select"
    initial_dir = sys.argv[3] if len(sys.argv) > 3 else ""
    
    # Provide a fallback if initial_dir is empty
    if not initial_dir:
        initial_dir = "/"

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    
    if action == "folder":
        path = filedialog.askdirectory(title=title, initialdir=initial_dir)
    else:
        path = filedialog.askopenfilename(
            title=title,
            initialdir=initial_dir,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
    root.destroy()
    print(path if path else "")

if __name__ == "__main__":
    main()
