import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import fitz  # PyMuPDF
import os
import sys
import threading
import io as tk_io

class FullscreenReader:
    def __init__(self, root, pdf_path=None, reading_direction='left_to_right', start_page=0):
        self.root = root
        self.root.title("PDF Reader")
        self.root.configure(bg='#1a1a1a')
        
        # Start maximized instead of fullscreen
        self.root.state('zoomed') if os.name == 'nt' else self.root.attributes('-zoomed', True)
        
        self.pdf_document = None
        # Store the PDF start page and convert to virtual page later
        self.start_pdf_page = start_page
        self.current_page = 0  # Will be set correctly after PDF loads
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
        
        # お気に入りページ機能
        self.favorite_pages = []  # Current book's favorite pages
        self.show_favorites = False  # Favorite panel visibility
        
        # Setup UI immediately for instant visual feedback
        self.setup_ui()
        self.bind_keys()
        
        # Auto-save bookmark on close and other events
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Set up periodic auto-save (every 30 seconds)
        self.root.after(30000, self.periodic_bookmark_save)
        
        # Auto-save on focus loss (when user switches to another app)
        self.root.bind("<FocusOut>", self.on_focus_lost)
        
        # Auto-save on window minimize
        self.root.bind("<Unmap>", self.on_window_minimize)
        
        # Show loading state immediately if PDF provided
        if pdf_path and os.path.exists(pdf_path):
            self.show_initial_loading(os.path.basename(pdf_path))
            # Load PDF after UI is fully rendered
            self.root.after(10, lambda: self.load_pdf_async(pdf_path))
        else:
            # Show ready state for file selection
            self.show_ready_state()
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
        
        # Favorite pages (シンプルなキーバインド)
        self.root.bind('<f>', lambda e: self.add_favorite_page())
        self.root.bind('<F>', lambda e: self.add_favorite_page())
        self.root.bind('<Control-f>', lambda e: self.toggle_favorites_panel())
        self.root.bind('<g>', lambda e: self.show_goto_favorite())
        self.root.bind('<G>', lambda e: self.show_goto_favorite())
        
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
  
Favorites:
  F                Add current page to favorites
  Ctrl+F           Show/hide favorites panel
  G                Go to favorite page
  
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
        
        # Update loading message to show PDF processing
        self.loading_label.configure(text=f"📄 Loading PDF document...")
        self.root.update()
        
        def load_worker():
            try:
                # Stage 1: Open PDF document
                self.root.after(0, lambda: self.loading_label.configure(text="📂 Opening PDF file..."))
                self.pdf_document = fitz.open(file_path)
                self.total_pages = len(self.pdf_document)
                self.page_images = {}
                
                # Stage 2: Prepare for rendering
                self.root.after(0, lambda: self.loading_label.configure(text=f"📋 Processing {self.total_pages} pages..."))
                
                # Set current page from bookmark (convert PDF page to virtual page)
                if 0 <= self.start_pdf_page < self.total_pages:
                    self.current_page = self.get_virtual_page_from_pdf(self.start_pdf_page)
                    print(f"DEBUG: Loading bookmark - PDF page {self.start_pdf_page} -> virtual page {self.current_page}")
                else:
                    self.current_page = 0  # Reset to cover page if invalid
                
                # Stage 3: Render initial pages
                self.root.after(0, lambda: self.loading_label.configure(text="🎨 Rendering pages..."))
                
                # Pre-render only the current page for immediate display  
                if self.total_pages > 0:
                    self.render_page(self.current_page)
                
                filename = os.path.basename(file_path)
                self.root.after(0, self.on_pdf_loaded, filename)
                
                # Pre-render additional pages in background after UI is ready
                self.root.after(100, self.preload_initial_pages)
                
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to load PDF: {str(e)}"))
                self.root.after(0, self.hide_loading)
        
        threading.Thread(target=load_worker, daemon=True).start()
    
    def preload_initial_pages(self):
        """Preload nearby pages after initial display is ready"""
        def preload_worker():
            try:
                # Preload next page for smooth navigation
                if self.current_page + 1 < self.total_pages:
                    self.render_page(self.current_page + 1)
                
                # Preload a few more pages in background
                for i in range(max(0, self.current_page - 1), min(self.total_pages, self.current_page + 4)):
                    if i not in self.page_images:
                        self.render_page(i)
            except Exception as e:
                print(f"Error preloading pages: {e}")
        
        threading.Thread(target=preload_worker, daemon=True).start()
    
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
    
    def show_initial_loading(self, filename):
        """Show immediate loading state when PDF is being opened"""
        self.loading_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        self.loading_label.configure(text=f"📖 Opening {filename}...")
        self.loading_label.pack()
        # Don't set is_loading = True here, let load_pdf_async handle it
        
        # Update root to ensure loading message is shown
        self.root.update()
    
    def show_ready_state(self):
        """Show ready state when no PDF is loaded"""
        self.loading_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        self.loading_label.configure(text="📚 Ready to open PDF\nPress 'O' to select file")
        self.loading_label.pack()
    
    def show_loading(self):
        if not self.is_loading:
            self.loading_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
            self.loading_label.configure(text="📄 Loading PDF pages...")
            self.loading_label.pack()
            self.is_loading = True
    
    def hide_loading(self):
        self.loading_frame.place_forget()
        self.loading_label.pack_forget()
        self.is_loading = False
    
    def on_pdf_loaded(self, filename):
        self.hide_loading()
        
        # Load favorite pages for this book
        self.load_favorite_pages()
        
        self.update_display()
        
        # Show bookmark status if started from bookmark
        fav_count = len(self.favorite_pages)
        fav_text = f" | ⭐ {fav_count} favorites" if fav_count > 0 else ""
        
        if self.current_page > 0:
            self.show_status(f"📖 Loaded: {filename} ({self.total_pages} pages) - Resumed from bookmark (page {self.current_page + 1}){fav_text} - Press H for help", 5000)
        else:
            self.show_status(f"Loaded: {filename} ({self.total_pages} pages){fav_text} - Press H for help", 4000)
    
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
        
        # Determine page order based on reading direction with virtual blank page
        # We insert a virtual blank page at the beginning so cover (page 1) appears alone
        # and content pages (2-3, 4-5, etc.) appear as proper spreads
        
        if self.reading_direction == 'left_to_right':
            # For left-to-right: 
            # virtual_page=0 -> blank + page 1 (cover alone on right)
            # virtual_page=2 -> page 2 + page 3 (content spread)
            if self.current_page == 0:
                # Show cover alone on the right side
                left_page_idx = -1  # Virtual blank page
                right_page_idx = 0  # Cover page (PDF page 1)
            else:
                # Normal spread starting from page 2
                left_page_idx = self.current_page
                right_page_idx = self.current_page + 1
        else:  # right_to_left (Japanese style)
            # For right-to-left:
            # virtual_page=0 -> page 1 (cover alone on left) + blank
            # virtual_page=2 -> page 3 + page 2 (content spread)
            if self.current_page == 0:
                # Show cover alone on the left side
                left_page_idx = 0   # Cover page (PDF page 1)
                right_page_idx = -1 # Virtual blank page
            else:
                # Normal spread starting from page 2
                left_page_idx = self.current_page + 1
                right_page_idx = self.current_page
        
        # Display left page (or blank if virtual)
        if left_page_idx == -1:
            self.display_blank_page(self.left_canvas, canvas_width, canvas_height)
        elif left_page_idx < self.total_pages:
            self.display_page_on_canvas(self.left_canvas, left_page_idx, canvas_width, canvas_height)
        else:
            self.left_canvas.delete("all")
        
        # Display right page (or blank if virtual)
        if right_page_idx == -1:
            self.display_blank_page(self.right_canvas, canvas_width, canvas_height)
        elif right_page_idx < self.total_pages:
            self.display_page_on_canvas(self.right_canvas, right_page_idx, canvas_width, canvas_height)
        else:
            self.right_canvas.delete("all")
    
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
    
    def display_blank_page(self, canvas, canvas_width, canvas_height):
        """Display a blank page (virtual page)"""
        canvas.delete("all")
        # Create a subtle blank page with light border
        canvas.create_rectangle(
            10, 10, canvas_width - 10, canvas_height - 10,
            fill='#f8f8f8', outline='#e0e0e0', width=2
        )
    
    def prev_page(self):
        if not self.pdf_document or self.current_page <= 0:
            return
        
        # Handle navigation with virtual blank page
        if self.current_page == 1:
            # From first content spread (page 1) back to cover page (page 0)
            self.current_page = 0
        else:
            # Normal page going back by 2
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
        
        # Handle navigation with virtual blank page
        if self.current_page == 0:
            # From cover page (page 0) to first content spread (page 1)
            self.current_page = 1
        elif self.current_page + 2 < self.total_pages:
            # Normal page advancement by 2
            self.current_page += 2
        else:
            # Don't advance if we're at or near the end
            return
            
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
        
        # Handle status display with virtual blank page
        if self.current_page == 0:
            # Cover page display
            status = f"Cover (Page 1 of {self.total_pages})"
        else:
            # Content spread display
            if self.reading_direction == 'left_to_right':
                if self.current_page == 1:
                    # First content spread: page 2-3
                    left_page = self.current_page + 1  # Page 2
                    right_page = min(self.current_page + 2, self.total_pages)  # Page 3
                else:
                    left_page = self.current_page + 1
                    right_page = min(self.current_page + 2, self.total_pages)
            else:  # right_to_left
                if self.current_page == 1:
                    # First content spread: page 3-2
                    left_page = min(self.current_page + 2, self.total_pages)  # Page 3
                    right_page = self.current_page + 1  # Page 2
                else:
                    left_page = min(self.current_page + 2, self.total_pages)
                    right_page = self.current_page + 1
            
            # Format status message
            if self.current_page + 2 > self.total_pages:
                status = f"Page {right_page} of {self.total_pages}"
            else:
                if self.reading_direction == 'left_to_right':
                    status = f"Pages {left_page}-{right_page} of {self.total_pages}"
                else:
                    status = f"Pages {right_page}-{left_page} of {self.total_pages}"
        
        direction_text = "→" if self.reading_direction == 'left_to_right' else "←"
        
        # Add favorite indicator if current page is favorited
        favorite_indicator = ""
        current_pdf_page = self.get_actual_pdf_page(self.current_page)
        for fav in self.favorite_pages:
            if fav['page'] == current_pdf_page:
                favorite_indicator = f" ⭐ {fav['name']}"
                break
        
        self.show_status(f"{status} {direction_text}{favorite_indicator}", 2000)
    
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
                    # Convert virtual page to actual PDF page for storage
                    actual_pdf_page = self.get_actual_pdf_page(self.current_page)
                    book['last_page'] = actual_pdf_page
                    book['last_opened'] = datetime.now().isoformat()
                    book_found = True
                    print(f"DEBUG: Saving bookmark - virtual page: {self.current_page}, actual PDF page: {actual_pdf_page}")
                    break
            
            if not book_found:
                return
            
            # Save updated data
            os.makedirs(os.path.dirname(self.bookshelf_file), exist_ok=True)
            with open(self.bookshelf_file, 'w', encoding='utf-8') as f:
                json.dump(books, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"Error saving bookmark: {e}")
    
    def get_actual_pdf_page(self, virtual_page):
        """Convert virtual page number to actual PDF page number"""
        if virtual_page == 0:
            # Cover page (virtual page 0 = PDF page 0)
            return 0
        else:
            # Content pages (virtual page 1 = PDF page 1, virtual page 3 = PDF page 3, etc.)
            return virtual_page
    
    def get_virtual_page_from_pdf(self, pdf_page):
        """Convert actual PDF page number to virtual page number"""
        if pdf_page == 0:
            # Cover page (PDF page 0 = virtual page 0)
            return 0
        else:
            # Content pages - adjust for proper spread alignment
            # PDF page 1 should start at virtual page 1 (so it shows with page 2)
            return pdf_page
    
    def save_bookmark_manual(self):
        """Manually save bookmark with user feedback"""
        self.save_bookmark()
        self.show_status(f"📖 Bookmark saved at page {self.current_page + 1}", 2000)
    
    def on_closing(self):
        """Handle window closing - save bookmark with feedback"""
        if self.pdf_document and self.initial_pdf_path:
            # Show immediate feedback that bookmark is being saved
            self.show_status("📖 Saving bookmark...", 0)  # No timeout, stays until close
            self.root.update()  # Force immediate update
            
            try:
                # Save bookmark
                self.save_bookmark()
                
                # Brief pause to show the save message
                self.root.after(500, self.complete_closing)
                return  # Don't quit immediately
                
            except Exception as e:
                print(f"Error saving bookmark on close: {e}")
                # Still quit even if bookmark save fails
                
        self.root.quit()
    
    def complete_closing(self):
        """Complete the closing process after bookmark is saved"""
        # Show confirmation briefly
        self.show_status("✅ Bookmark saved!", 0)
        self.root.update()
        
        # Give user a moment to see the confirmation
        self.root.after(300, self.root.quit)
    
    def periodic_bookmark_save(self):
        """Periodically save bookmark in background"""
        if self.pdf_document and self.initial_pdf_path:
            try:
                self.save_bookmark()
                # Subtle visual feedback for periodic save (very brief)
                original_title = self.root.title()
                self.root.title(f"{original_title} 📖")
                self.root.after(1000, lambda: self.root.title(original_title))
            except Exception as e:
                print(f"Error in periodic bookmark save: {e}")
        
        # Schedule next periodic save (every 30 seconds)
        self.root.after(30000, self.periodic_bookmark_save)
    
    def on_focus_lost(self, event=None):
        """Save bookmark when window loses focus"""
        if self.pdf_document and self.initial_pdf_path:
            try:
                self.save_bookmark()
            except Exception as e:
                print(f"Error saving bookmark on focus loss: {e}")
    
    def on_window_minimize(self, event=None):
        """Save bookmark when window is minimized"""
        if self.pdf_document and self.initial_pdf_path:
            try:
                self.save_bookmark()
                # Brief title change to show save occurred
                original_title = self.root.title()
                self.root.title(f"{original_title} 📖 Saved")
                self.root.after(2000, lambda: self.root.title(original_title))
            except Exception as e:
                print(f"Error saving bookmark on minimize: {e}")
    
    def load_favorite_pages(self):
        """Load favorite pages for current book"""
        if not self.initial_pdf_path:
            return
        
        try:
            import json
            if os.path.exists(self.bookshelf_file):
                with open(self.bookshelf_file, 'r', encoding='utf-8') as f:
                    books = json.load(f)
                
                normalized_current_path = os.path.normpath(self.initial_pdf_path)
                for book in books:
                    normalized_book_path = os.path.normpath(book['path'])
                    if normalized_book_path == normalized_current_path:
                        self.favorite_pages = book.get('favorite_pages', [])
                        print(f"DEBUG: Loaded {len(self.favorite_pages)} favorite pages")
                        break
        except Exception as e:
            print(f"Error loading favorite pages: {e}")
    
    def save_favorite_pages(self):
        """Save favorite pages to bookshelf data"""
        if not self.initial_pdf_path:
            return
        
        try:
            import json
            books = []
            if os.path.exists(self.bookshelf_file):
                with open(self.bookshelf_file, 'r', encoding='utf-8') as f:
                    books = json.load(f)
            else:
                return
            
            normalized_current_path = os.path.normpath(self.initial_pdf_path)
            for book in books:
                normalized_book_path = os.path.normpath(book['path'])
                if normalized_book_path == normalized_current_path:
                    book['favorite_pages'] = self.favorite_pages
                    break
            
            os.makedirs(os.path.dirname(self.bookshelf_file), exist_ok=True)
            with open(self.bookshelf_file, 'w', encoding='utf-8') as f:
                json.dump(books, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"Error saving favorite pages: {e}")
    
    def add_favorite_page(self):
        """Add current page to favorites (シンプルで邪魔にならない)"""
        if not self.pdf_document:
            return
        
        current_pdf_page = self.get_actual_pdf_page(self.current_page)
        
        # Check if already in favorites
        for fav in self.favorite_pages:
            if fav['page'] == current_pdf_page:
                self.show_status(f"⭐ Page {current_pdf_page + 1} already in favorites", 2000)
                return
        
        # Add to favorites with minimal UI
        import uuid
        from datetime import datetime
        
        favorite = {
            'id': str(uuid.uuid4()),
            'page': current_pdf_page,
            'name': f"Page {current_pdf_page + 1}",
            'created_date': datetime.now().isoformat()
        }
        
        self.favorite_pages.append(favorite)
        self.save_favorite_pages()
        
        self.show_status(f"⭐ Added page {current_pdf_page + 1} to favorites ({len(self.favorite_pages)} total)", 2000)
    
    def toggle_favorites_panel(self):
        """Toggle favorites panel (シンプル表示)"""
        if not self.favorite_pages:
            self.show_status("No favorite pages yet. Press 'F' to add current page.", 3000)
            return
        
        # シンプルなお気に入り一覧を表示
        favorites_text = "⭐ Favorite Pages:\n"
        for i, fav in enumerate(self.favorite_pages, 1):
            favorites_text += f"{i}. {fav['name']} (p.{fav['page'] + 1})\n"
        favorites_text += "\nPress number key to jump, Esc to close"
        
        self.show_status(favorites_text, 5000)
        
        # 数字キーでジャンプできるように
        for i in range(min(9, len(self.favorite_pages))):
            self.root.bind(f'<Key-{i+1}>', lambda e, idx=i: self.jump_to_favorite(idx))
    
    def show_goto_favorite(self):
        """Show goto favorite dialog (マウス操作対応メニュー)"""
        if not self.favorite_pages:
            self.show_status("No favorite pages yet. Press 'F' to add current page.", 2000)
            return
        
        self.create_favorites_popup()
    
    def jump_to_favorite(self, index):
        """Jump to favorite page by index"""
        if 0 <= index < len(self.favorite_pages):
            favorite = self.favorite_pages[index]
            pdf_page = favorite['page']
            virtual_page = self.get_virtual_page_from_pdf(pdf_page)
            
            self.current_page = virtual_page
            self.update_display()
            self.show_status(f"⭐ Jumped to {favorite['name']}", 2000)
            
            # Clear number key bindings
            for i in range(9):
                self.root.unbind(f'<Key-{i+1}>')
    
    def create_favorites_popup(self):
        """Create favorites popup menu for mouse operation"""
        # Create popup window
        popup = tk.Toplevel(self.root)
        popup.title("⭐ Favorite Pages")
        popup.geometry("350x400")
        popup.configure(bg='#2e2e2e')
        popup.resizable(False, False)
        
        # Make it stay on top but not modal
        popup.attributes('-topmost', True)
        
        # Center the popup on main window
        popup.transient(self.root)
        
        # Position popup near cursor or center of screen
        x = self.root.winfo_x() + self.root.winfo_width() // 2 - 175
        y = self.root.winfo_y() + self.root.winfo_height() // 2 - 200
        popup.geometry(f"350x400+{x}+{y}")
        
        # Title label
        title_label = tk.Label(popup, text="⭐ Favorite Pages", 
                              font=("Arial", 14, "bold"), 
                              bg='#2e2e2e', fg='white')
        title_label.pack(pady=(10, 5))
        
        # Favorites list frame with scrollbar
        list_frame = tk.Frame(popup, bg='#2e2e2e')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Canvas for scrolling
        canvas = tk.Canvas(list_frame, bg='#404040', highlightthickness=0)
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#404040')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Add favorite items
        for i, fav in enumerate(self.favorite_pages):
            self.create_favorite_item(scrollable_frame, fav, i, popup)
        
        # Button frame
        button_frame = tk.Frame(popup, bg='#2e2e2e')
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Close button
        close_btn = tk.Button(button_frame, text="Close", 
                             command=popup.destroy,
                             bg='#666666', fg='white',
                             font=("Arial", 10), padx=20, pady=5)
        close_btn.pack(side=tk.RIGHT)
        
        # Add favorite button
        add_btn = tk.Button(button_frame, text="⭐ Add Current Page", 
                           command=lambda: [self.add_favorite_page(), popup.destroy()],
                           bg='#4CAF50', fg='white',
                           font=("Arial", 10), padx=20, pady=5)
        add_btn.pack(side=tk.LEFT)
        
        # Bind Escape key to close
        popup.bind('<Escape>', lambda e: popup.destroy())
        
        # Focus on popup
        popup.focus_set()
    
    def create_favorite_item(self, parent, favorite, index, popup_window):
        """Create a favorite item in the list"""
        item_frame = tk.Frame(parent, bg='#505050', relief=tk.RAISED, bd=1)
        item_frame.pack(fill=tk.X, padx=5, pady=2)
        
        # Left side - Page info and jump button
        left_frame = tk.Frame(item_frame, bg='#505050')
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Page number
        page_label = tk.Label(left_frame, text=f"Page {favorite['page'] + 1}", 
                             font=("Arial", 10, "bold"), 
                             bg='#505050', fg='#FFD54F')
        page_label.pack(anchor='w')
        
        # Name (editable)
        name_var = tk.StringVar(value=favorite['name'])
        name_entry = tk.Entry(left_frame, textvariable=name_var, 
                             font=("Arial", 9), bg='#404040', fg='white',
                             relief=tk.FLAT, bd=0)
        name_entry.pack(fill=tk.X, pady=(2, 0))
        
        # Date
        try:
            from datetime import datetime
            created_date = datetime.fromisoformat(favorite['created_date'])
            date_str = created_date.strftime("%m/%d %H:%M")
        except:
            date_str = "Unknown"
        
        date_label = tk.Label(left_frame, text=date_str, 
                             font=("Arial", 8), 
                             bg='#505050', fg='#cccccc')
        date_label.pack(anchor='w')
        
        # Right side - Action buttons
        right_frame = tk.Frame(item_frame, bg='#505050')
        right_frame.pack(side=tk.RIGHT, padx=5, pady=5)
        
        # Jump button
        jump_btn = tk.Button(right_frame, text="Go", 
                            command=lambda: [self.jump_to_favorite(index), popup_window.destroy()],
                            bg='#2196F3', fg='white',
                            font=("Arial", 9), padx=10, pady=2)
        jump_btn.pack(pady=1)
        
        # Edit button (save name changes)
        edit_btn = tk.Button(right_frame, text="✓", 
                            command=lambda: self.update_favorite_name(index, name_var.get()),
                            bg='#4CAF50', fg='white',
                            font=("Arial", 9), padx=5, pady=2)
        edit_btn.pack(pady=1)
        
        # Delete button
        delete_btn = tk.Button(right_frame, text="✕", 
                              command=lambda: [self.delete_favorite(index), popup_window.destroy(), self.create_favorites_popup()],
                              bg='#F44336', fg='white',
                              font=("Arial", 9), padx=5, pady=2)
        delete_btn.pack(pady=1)
        
        # Make the whole item clickable to jump
        widgets = [item_frame, left_frame, page_label, date_label]
        for widget in widgets:
            widget.bind("<Button-1>", lambda e: [self.jump_to_favorite(index), popup_window.destroy()])
            widget.bind("<Enter>", lambda e: item_frame.configure(bg='#606060'))
            widget.bind("<Leave>", lambda e: item_frame.configure(bg='#505050'))
    
    def update_favorite_name(self, index, new_name):
        """Update favorite page name"""
        if 0 <= index < len(self.favorite_pages) and new_name.strip():
            self.favorite_pages[index]['name'] = new_name.strip()
            self.save_favorite_pages()
            self.show_status(f"⭐ Updated name to '{new_name.strip()}'", 2000)
    
    def delete_favorite(self, index):
        """Delete favorite page"""
        if 0 <= index < len(self.favorite_pages):
            removed_fav = self.favorite_pages.pop(index)
            self.save_favorite_pages()
            self.show_status(f"⭐ Removed '{removed_fav['name']}' from favorites", 2000)

def main():
    import sys
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else None
    reading_direction = sys.argv[2] if len(sys.argv) > 2 else 'left_to_right'
    start_page = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    
    root = tk.Tk()
    app = FullscreenReader(root, pdf_path, reading_direction, start_page)
    root.mainloop()

if __name__ == "__main__":
    main()