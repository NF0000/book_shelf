import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import fitz  # PyMuPDF
import os
import threading
import io as tk_io

class FullscreenReader:
    def __init__(self, root, pdf_path=None, reading_direction='right_to_left', start_page=0):
        self.root = root
        self.root.title("PDF Reader")
        self.root.configure(bg='#1a1a1a')
        
        # Start maximized instead of fullscreen
        self.root.state('zoomed') if os.name == 'nt' else self.root.attributes('-zoomed', True)
        
        self.pdf_document = None
        self.current_page = start_page  # Start from specified page (bookmark)
        self.total_pages = 0
        self.page_images = {}
        self.display_scale = 1.0
        self.is_loading = False
        self.initial_pdf_path = pdf_path
        self.reading_direction = reading_direction
        self.is_fullscreen = False
        # Handle bookshelf file path for both .exe and Python script execution
        if getattr(sys, 'frozen', False):
            # Running as .exe - data folder should be next to executable
            base_path = os.path.dirname(sys.executable)
        else:
            # Running as Python script
            base_path = os.path.dirname(os.path.abspath(__file__))
        
        self.bookshelf_file = os.path.join(base_path, "data", "bookshelf.json")  # For saving bookmarks
        self.last_bookmark_save = 0  # Track when we last saved bookmark
        
        self.setup_ui()
        self.bind_keys()
        
        # Auto-save bookmark on close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Auto-open file dialog on startup or load provided PDF
        if pdf_path and os.path.exists(pdf_path):
            self.root.after(100, lambda: self.load_pdf_async(pdf_path))
        else:
            self.root.after(100, self.open_pdf)
    
    def setup_ui(self):
        # Create main canvas frame that fills entire screen
        self.canvas_frame = tk.Frame(self.root, bg='#1a1a1a')
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left page canvas (no borders or padding)
        self.left_canvas = tk.Canvas(
            self.canvas_frame, 
            bg='white', 
            highlightthickness=0,
            bd=0
        )
        self.left_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Right page canvas (no borders or padding)
        self.right_canvas = tk.Canvas(
            self.canvas_frame, 
            bg='white',
            highlightthickness=0,
            bd=0
        )
        self.right_canvas.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Status bar (minimal, only shows when needed)
        self.status_var = tk.StringVar()
        self.status_var.set("Press 'O' to open PDF, 'F' to toggle fullscreen, 'Q' to quit")
        
        self.status_label = tk.Label(
            self.root,
            textvariable=self.status_var,
            font=("Arial", 10),
            bg='#1a1a1a',
            fg='white',
            pady=2
        )
        # Don't pack status label initially - show only when needed
        
        # Loading overlay
        self.loading_frame = tk.Frame(self.root, bg='#1a1a1a')
        self.loading_label = tk.Label(
            self.loading_frame,
            text="Loading PDF...",
            font=("Arial", 24),
            bg='#1a1a1a',
            fg='white'
        )
        
        # Bind click events for navigation
        self.left_canvas.bind("<Button-1>", lambda e: self.prev_page())
        self.right_canvas.bind("<Button-1>", lambda e: self.next_page())
        
        # Hide status after 3 seconds
        self.root.after(3000, self.hide_status)
    
    def show_status(self, message=None, duration=3000):
        if message:
            self.status_var.set(message)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)
        if duration > 0:
            self.root.after(duration, self.hide_status)
    
    def hide_status(self):
        self.status_label.pack_forget()
    
    def bind_keys(self):
        # Navigation keys
        self.root.bind('<Left>', lambda e: self.prev_page())
        self.root.bind('<Right>', lambda e: self.next_page())
        self.root.bind('<Prior>', lambda e: self.prev_page())  # Page Up
        self.root.bind('<Next>', lambda e: self.next_page())   # Page Down
        self.root.bind('<Up>', lambda e: self.prev_page())
        self.root.bind('<Down>', lambda e: self.next_page())
        self.root.bind('<space>', lambda e: self.next_page())
        self.root.bind('<BackSpace>', lambda e: self.prev_page())
        
        # Zoom keys
        self.root.bind('<plus>', lambda e: self.zoom_in())
        self.root.bind('<equal>', lambda e: self.zoom_in())  # + without shift
        self.root.bind('<minus>', lambda e: self.zoom_out())
        self.root.bind('<0>', lambda e: self.fit_to_window())
        
        # File operations
        self.root.bind('<o>', lambda e: self.open_pdf())
        self.root.bind('<O>', lambda e: self.open_pdf())
        
        # Fullscreen toggle  
        self.root.bind('<f>', lambda e: self.toggle_fullscreen())
        self.root.bind('<F>', lambda e: self.toggle_fullscreen())
        self.root.bind('<F11>', lambda e: self.toggle_fullscreen())
        self.root.bind('<Escape>', lambda e: self.exit_fullscreen())
        
        # Quit
        self.root.bind('<q>', lambda e: self.quit_app())
        self.root.bind('<Q>', lambda e: self.quit_app())
        self.root.bind('<Control-q>', lambda e: self.quit_app())
        
        # Help
        self.root.bind('<h>', lambda e: self.show_help())
        self.root.bind('<H>', lambda e: self.show_help())
        self.root.bind('<question>', lambda e: self.show_help())
        
        # Manual bookmark save
        self.root.bind('<b>', lambda e: self.save_bookmark_manual())
        self.root.bind('<B>', lambda e: self.save_bookmark_manual())
        
        self.root.focus_set()
    
    def show_help(self):
        help_text = """Keyboard Shortcuts:
        
Navigation:
  ←/→  or  ↑/↓     Navigate pages
  Space            Next page
  Backspace        Previous page
  Page Up/Down     Navigate pages

Zoom:
  +/=              Zoom in
  -                Zoom out
  0                Fit to window

File:
  O                Open PDF
  
View:
  F / F11 / Esc    Toggle fullscreen
  H / ?            Show this help
  
Bookmark:
  B                Save bookmark manually
  
Quit:
  Q                Quit application

Click left/right pages to navigate
Bookmarks are saved automatically when changing pages"""
        
        self.show_status(help_text, 8000)
    
    def toggle_fullscreen(self):
        if self.is_fullscreen:
            self.exit_fullscreen()
        else:
            self.enter_fullscreen()
    
    def enter_fullscreen(self):
        self.root.attributes('-fullscreen', True)
        self.is_fullscreen = True
        self.show_status("Entered fullscreen mode - Press Esc to exit", 3000)
    
    def exit_fullscreen(self):
        self.root.attributes('-fullscreen', False)
        self.root.state('zoomed') if os.name == 'nt' else self.root.attributes('-zoomed', True)
        self.is_fullscreen = False
        self.show_status("Exited fullscreen mode", 2000)
    
    def quit_app(self):
        self.root.quit()
    
    def open_pdf(self):
        if self.is_loading:
            return
            
        file_path = filedialog.askopenfilename(
            title="Select PDF file",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        
        if file_path:
            self.load_pdf_async(file_path)
    
    def load_pdf_async(self, file_path):
        if self.is_loading:
            return
        
        self.is_loading = True
        self.show_loading()
        
        def load_worker():
            try:
                # Open PDF document
                self.pdf_document = fitz.open(file_path)
                self.total_pages = len(self.pdf_document)
                self.page_images = {}
                
                # Pre-render only the first page for faster startup
                # Additional pages will be rendered on demand
                if self.total_pages > 0:
                    self.render_page(self.current_page)
                    # Pre-render next page if it exists for smooth navigation
                    if self.current_page + 1 < self.total_pages:
                        self.render_page(self.current_page + 1)
                
                # Set current page to start_page if within valid range
                if 0 <= self.current_page < self.total_pages:
                    pass  # Keep the start_page from init
                else:
                    self.current_page = 0  # Reset to first page if invalid
                
                filename = os.path.basename(file_path)
                self.root.after(0, self.on_pdf_loaded, filename)
                
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to load PDF: {str(e)}"))
                self.root.after(0, self.hide_loading)
        
        threading.Thread(target=load_worker, daemon=True).start()
    
    def render_page(self, page_num):
        """Render a PDF page to PIL Image"""
        if page_num in self.page_images or page_num >= self.total_pages or page_num < 0:
            return
        
        try:
            page = self.pdf_document[page_num]
            # Use adaptive resolution based on page size for better performance
            mat = fitz.Matrix(1.5, 1.5)  # Reduced from 2.0 for faster rendering
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("ppm")
            
            # Convert to PIL Image
            pil_image = Image.open(tk_io.BytesIO(img_data))
            self.page_images[page_num] = pil_image
            
        except Exception as e:
            print(f"Error rendering page {page_num}: {e}")
    
    def show_loading(self):
        self.loading_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        self.loading_label.pack()
    
    def hide_loading(self):
        self.loading_frame.place_forget()
        self.loading_label.pack_forget()
        self.is_loading = False
    
    def on_pdf_loaded(self, filename):
        self.hide_loading()
        self.update_display()
        
        # Show bookmark status if started from bookmark
        if self.current_page > 0:
            self.show_status(f"📖 Loaded: {filename} ({self.total_pages} pages) - Resumed from bookmark (page {self.current_page + 1}) - Press H for help", 5000)
        else:
            self.show_status(f"Loaded: {filename} ({self.total_pages} pages) - Press H for help", 4000)
    
    def update_display(self):
        if not self.pdf_document:
            return
        
        self.left_canvas.delete("all")
        self.right_canvas.delete("all")
        
        # Get canvas dimensions
        self.root.update_idletasks()
        canvas_width = self.left_canvas.winfo_width()
        canvas_height = self.left_canvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            self.root.after(100, self.update_display)
            return
        
        # Determine page order based on reading direction
        if self.reading_direction == 'left_to_right':
            left_page_idx = self.current_page
            right_page_idx = self.current_page + 1
        else:  # right_to_left (Japanese style)
            left_page_idx = self.current_page + 1
            right_page_idx = self.current_page
        
        # Display left page
        if left_page_idx < self.total_pages:
            self.display_page_on_canvas(self.left_canvas, left_page_idx, canvas_width, canvas_height)
        
        # Display right page
        if right_page_idx < self.total_pages:
            self.display_page_on_canvas(self.right_canvas, right_page_idx, canvas_width, canvas_height)
    
    def display_page_on_canvas(self, canvas, page_idx, canvas_width, canvas_height):
        # Render page if not already rendered
        if page_idx not in self.page_images:
            self.render_page(page_idx)
        
        if page_idx not in self.page_images:
            # Display error message if rendering failed
            canvas.create_text(
                canvas_width // 2, canvas_height // 2,
                text=f"Error loading page {page_idx + 1}",
                font=("Arial", 16),
                fill="red"
            )
            return
        
        page_image = self.page_images[page_idx].copy()
        
        # Calculate scaling to fit canvas perfectly
        img_width, img_height = page_image.size
        scale_x = (canvas_width * self.display_scale) / img_width
        scale_y = (canvas_height * self.display_scale) / img_height
        scale = min(scale_x, scale_y)
        
        new_width = int(img_width * scale)
        new_height = int(img_height * scale)
        
        # Resize image
        page_image = page_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Convert to PhotoImage
        photo = ImageTk.PhotoImage(page_image)
        
        # Store reference to prevent garbage collection
        canvas.image = photo
        
        # Center the image on canvas
        x = (canvas_width - new_width) // 2
        y = (canvas_height - new_height) // 2
        
        canvas.create_image(x, y, anchor=tk.NW, image=photo)
    
    def prev_page(self):
        if not self.pdf_document or self.current_page <= 0:
            return
        
        self.current_page = max(0, self.current_page - 2)
        
        # Pre-render nearby pages
        self.preload_nearby_pages()
        
        self.update_display()
        self.show_page_status()
        
        # Auto-save bookmark (throttled)
        import time
        current_time = time.time()
        if current_time - self.last_bookmark_save > 2:  # Save at most every 2 seconds
            self.save_bookmark()
            self.last_bookmark_save = current_time
    
    def next_page(self):
        if not self.pdf_document:
            return
        
        if self.current_page + 2 < self.total_pages:
            self.current_page += 2
            
            # Pre-render nearby pages
            self.preload_nearby_pages()
            
            self.update_display()
            self.show_page_status()
            
            # Auto-save bookmark (throttled)
            import time
            current_time = time.time()
            if current_time - self.last_bookmark_save > 2:  # Save at most every 2 seconds
                self.save_bookmark()
                self.last_bookmark_save = current_time
    
    def show_page_status(self):
        if not self.pdf_document:
            return
        
        if self.reading_direction == 'left_to_right':
            left_page = self.current_page + 1
            right_page = min(self.current_page + 2, self.total_pages)
        else:  # right_to_left
            left_page = min(self.current_page + 2, self.total_pages)
            right_page = self.current_page + 1
        
        if self.current_page + 1 >= self.total_pages:
            status = f"Page {right_page} of {self.total_pages}"
        else:
            if self.current_page + 2 <= self.total_pages:
                if self.reading_direction == 'left_to_right':
                    status = f"Pages {left_page}-{right_page} of {self.total_pages}"
                else:
                    status = f"Pages {right_page}-{left_page} of {self.total_pages}"
            else:
                status = f"Page {right_page} of {self.total_pages}"
        
        direction_text = "→" if self.reading_direction == 'left_to_right' else "←"
        self.show_status(f"{status} {direction_text}", 2000)
    
    def preload_nearby_pages(self):
        """Pre-render nearby pages for smooth navigation"""
        # Reduce preload range for better performance
        start_page = max(0, self.current_page - 1)
        end_page = min(self.total_pages, self.current_page + 3)
        
        # Use background thread for preloading to avoid UI blocking
        def preload_worker():
            for i in range(start_page, end_page):
                if i not in self.page_images:
                    self.render_page(i)
        
        threading.Thread(target=preload_worker, daemon=True).start()
    
    def zoom_in(self):
        self.display_scale = min(self.display_scale * 1.2, 3.0)
        self.update_display()
        self.show_status(f"Zoom: {int(self.display_scale * 100)}%", 1500)
    
    def zoom_out(self):
        self.display_scale = max(self.display_scale / 1.2, 0.3)
        self.update_display()
        self.show_status(f"Zoom: {int(self.display_scale * 100)}%", 1500)
    
    def fit_to_window(self):
        self.display_scale = 1.0
        self.update_display()
        self.show_status("Fit to window", 1500)
    
    def save_bookmark(self):
        """Save current page as bookmark"""
        if not self.pdf_document or not self.initial_pdf_path:
            return
        
        try:
            import json
            from datetime import datetime
            
            # Load existing bookshelf data
            books = []
            if os.path.exists(self.bookshelf_file):
                with open(self.bookshelf_file, 'r', encoding='utf-8') as f:
                    books = json.load(f)
            else:
                return
            
            # Find and update the current book (normalize paths for comparison)
            book_found = False
            normalized_current_path = os.path.normpath(self.initial_pdf_path)
            for book in books:
                normalized_book_path = os.path.normpath(book['path'])
                if normalized_book_path == normalized_current_path:
                    book['last_page'] = self.current_page
                    book['last_opened'] = datetime.now().isoformat()
                    book_found = True
                    break
            
            if not book_found:
                return
            
            # Save updated data
            os.makedirs(os.path.dirname(self.bookshelf_file), exist_ok=True)
            with open(self.bookshelf_file, 'w', encoding='utf-8') as f:
                json.dump(books, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"Error saving bookmark: {e}")
    
    def save_bookmark_manual(self):
        """Manually save bookmark with user feedback"""
        self.save_bookmark()
        self.show_status(f"📖 Bookmark saved at page {self.current_page + 1}", 2000)
    
    def on_closing(self):
        """Handle window closing - save bookmark"""
        self.save_bookmark()
        self.root.quit()

def main():
    import sys
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else None
    reading_direction = sys.argv[2] if len(sys.argv) > 2 else 'right_to_left'
    start_page = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    
    root = tk.Tk()
    app = FullscreenReader(root, pdf_path, reading_direction, start_page)
    root.mainloop()

if __name__ == "__main__":
    main()