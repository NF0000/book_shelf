import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import fitz  # PyMuPDF
import os
import json
import hashlib
import threading
from datetime import datetime
import subprocess
import sys
import io

class PDFBookshelf:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF Bookshelf")
        self.root.geometry("1200x800")
        self.root.configure(bg='#2e2e2e')
        
        # Handle data directory paths for both .exe and Python script execution
        if getattr(sys, 'frozen', False):
            # Running as .exe - data folder should be next to executable
            base_path = os.path.dirname(sys.executable)
        else:
            # Running as Python script
            base_path = os.path.dirname(os.path.abspath(__file__))
        
        self.data_dir = os.path.join(base_path, "data")
        self.thumbnails_dir = os.path.join(self.data_dir, "thumbnails")
        self.bookshelf_file = os.path.join(self.data_dir, "bookshelf.json")
        
        self.books = []
        self.book_frames = []
        self.thumbnail_cache = {}
        self.categories = set(['All', 'Uncategorized'])  # Default categories
        self.current_category = 'All'
        self.sort_mode = 'recent'  # 'recent', 'added', 'title', 'custom'
        self.dragging_book = None
        self.drag_data = {}
        
        self.setup_ui()
        self.load_bookshelf_data()
        self.bind_keys()
    
    def setup_ui(self):
        # Title and toolbar
        title_frame = tk.Frame(self.root, bg='#2e2e2e', height=60)
        title_frame.pack(fill=tk.X, padx=20, pady=(20, 10))
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(
            title_frame,
            text="📚 My PDF Library",
            font=("Arial", 18, "bold"),
            bg='#2e2e2e',
            fg='white'
        )
        title_label.pack(side=tk.LEFT, pady=15)
        
        # Category and Add button frame
        button_frame = tk.Frame(title_frame, bg='#2e2e2e')
        button_frame.pack(side=tk.RIGHT, pady=10)
        
        # Category dropdown
        self.category_var = tk.StringVar(value='All')
        self.category_dropdown = ttk.Combobox(
            button_frame,
            textvariable=self.category_var,
            values=list(self.categories),
            state="readonly",
            width=15,
            font=("Arial", 10)
        )
        self.category_dropdown.pack(side=tk.LEFT, padx=(0, 10))
        self.category_dropdown.bind('<<ComboboxSelected>>', self.on_category_change)
        
        # Manage categories button
        self.manage_cat_button = tk.Button(
            button_frame,
            text="📁",
            command=self.manage_categories,
            font=("Arial", 12),
            bg='#FF9800',
            fg='white',
            relief=tk.FLAT,
            padx=8,
            pady=8
        )
        self.manage_cat_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Add book button
        self.add_button = tk.Button(
            button_frame,
            text="+ Add PDF",
            command=self.add_pdf,
            font=("Arial", 12),
            bg='#4CAF50',
            fg='white',
            relief=tk.FLAT,
            padx=20,
            pady=8
        )
        self.add_button.pack(side=tk.LEFT)
        
        # Search and Sort bar
        control_frame = tk.Frame(title_frame, bg='#2e2e2e')
        control_frame.pack(side=tk.RIGHT, padx=(0, 20), pady=10)
        
        # Sort dropdown
        sort_frame = tk.Frame(control_frame, bg='#2e2e2e')
        sort_frame.pack(side=tk.LEFT, padx=(0, 15))
        
        tk.Label(sort_frame, text="Sort:", font=("Arial", 10), bg='#2e2e2e', fg='white').pack(side=tk.LEFT)
        
        self.sort_var = tk.StringVar(value='recent')
        self.sort_dropdown = ttk.Combobox(
            sort_frame,
            textvariable=self.sort_var,
            values=[
                ('recent', 'Recently Opened'),
                ('added', 'Date Added'),
                ('title', 'Title A-Z'),
                ('custom', 'Custom Order (Drag & Drop)')
            ],
            state="readonly",
            width=20,
            font=("Arial", 9)
        )
        
        # Set display values
        sort_values = ['Recent', 'Date Added', 'Title A-Z', 'Custom (Drag & Drop)']
        self.sort_dropdown.config(values=sort_values)
        self.sort_dropdown.set('Recent')
        
        self.sort_dropdown.pack(side=tk.LEFT, padx=(5, 0))
        self.sort_dropdown.bind('<<ComboboxSelected>>', self.on_sort_change)
        
        # Search bar
        search_frame = tk.Frame(control_frame, bg='#2e2e2e')
        search_frame.pack(side=tk.LEFT)
        
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.on_search_change)
        
        self.search_entry = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            font=("Arial", 11),
            width=20,
            bg='#404040',
            fg='white',
            insertbackground='white',
            relief=tk.FLAT
        )
        self.search_entry.pack(side=tk.LEFT, ipady=5)
        
        search_label = tk.Label(
            search_frame,
            text="🔍",
            font=("Arial", 14),
            bg='#2e2e2e',
            fg='white'
        )
        search_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # Main scrollable area
        self.create_scrollable_area()
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("🔤 本を並び替えるには「Sort」を「Custom (Drag & Drop)」に変更してください")
        
        status_frame = tk.Frame(self.root, bg='#404040', height=30)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        status_frame.pack_propagate(False)
        
        self.status_label = tk.Label(
            status_frame,
            textvariable=self.status_var,
            font=("Arial", 10),
            bg='#404040',
            fg='white'
        )
        self.status_label.pack(side=tk.LEFT, padx=10, pady=5)
        
        self.book_count_label = tk.Label(
            status_frame,
            text="0 books",
            font=("Arial", 10),
            bg='#404040',
            fg='white'
        )
        self.book_count_label.pack(side=tk.RIGHT, padx=10, pady=5)
    
    def create_scrollable_area(self):
        # Create canvas and scrollbar for scrolling
        canvas_frame = tk.Frame(self.root, bg='#2e2e2e')
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        self.canvas = tk.Canvas(canvas_frame, bg='#2e2e2e', highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        
        self.scrollable_frame = tk.Frame(self.canvas, bg='#2e2e2e')
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # Bind mouse wheel to canvas
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)
    
    def on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    
    def bind_keys(self):
        self.root.bind('<Control-o>', lambda e: self.add_pdf())
        self.root.bind('<Control-f>', lambda e: self.search_entry.focus())
        self.root.bind('<F5>', lambda e: self.refresh_bookshelf())
        self.root.focus_set()
    
    def get_file_hash(self, filepath):
        """Generate unique hash for file"""
        hasher = hashlib.md5()
        hasher.update(filepath.encode())
        return hasher.hexdigest()
    
    def generate_thumbnail(self, pdf_path, book_id, page_num=None):
        """Generate thumbnail for specified PDF page"""
        try:
            # Ensure thumbnails directory exists
            os.makedirs(self.thumbnails_dir, exist_ok=True)
            
            thumbnail_path = os.path.join(self.thumbnails_dir, f"{book_id}.png")
            
            # Skip if thumbnail already exists and is recent
            if os.path.exists(thumbnail_path):
                return thumbnail_path
            
            # Open PDF and get specified page
            doc = fitz.open(pdf_path)
            if len(doc) == 0:
                doc.close()
                return None
            
            # Get page number from book data if not specified
            if page_num is None:
                # Find book data to get thumbnail page
                book_data = next((book for book in self.books if book['id'] == book_id), None)
                page_num = book_data.get('thumbnail_page', 0) if book_data else 0
            
            # Ensure page number is valid
            page_num = max(0, min(page_num, len(doc) - 1))
            page = doc[page_num]
            
            # Use lower resolution for faster generation
            mat = fitz.Matrix(0.3, 0.3)  # Reduced scale for faster processing
            pix = page.get_pixmap(matrix=mat)
            
            # Convert to PIL Image
            img_data = pix.tobytes("ppm")
            pil_image = Image.open(io.BytesIO(img_data))
            
            # Resize to standard thumbnail size
            pil_image.thumbnail((150, 200), Image.Resampling.LANCZOS)
            
            # Save thumbnail with optimization
            pil_image.save(thumbnail_path, "PNG", optimize=True)
            doc.close()
            
            return thumbnail_path
            
        except Exception as e:
            print(f"Error generating thumbnail for {book_id}: {e}")
            # Create a default placeholder image
            try:
                placeholder = Image.new('RGB', (150, 200), '#666666')
                placeholder_path = os.path.join(self.thumbnails_dir, f"{book_id}.png")
                placeholder.save(placeholder_path, "PNG")
                return placeholder_path
            except:
                return None
    
    def add_pdf(self):
        """Add new PDF to bookshelf"""
        file_paths = filedialog.askopenfilenames(
            title="Select PDF files",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        
        if not file_paths:
            return
        
        self.status_var.set("Adding PDFs...")
        self.root.update()
        
        for file_path in file_paths:
            if not os.path.exists(file_path):
                continue
            
            # Check if already exists
            if any(book['path'] == file_path for book in self.books):
                continue
            
            # Generate book data
            book_id = self.get_file_hash(file_path)
            filename = os.path.basename(file_path)
            title = os.path.splitext(filename)[0]
            
            # Get PDF info
            try:
                doc = fitz.open(file_path)
                page_count = len(doc)
                doc.close()
            except:
                page_count = 0
            
            book_data = {
                'id': book_id,
                'title': title,
                'path': file_path,
                'filename': filename,
                'pages': page_count,
                'added_date': datetime.now().isoformat(),
                'last_opened': None,
                'last_page': 0,
                'thumbnail_page': 0,
                'reading_direction': 'right_to_left',  # 'right_to_left' or 'left_to_right'
                'category': 'Uncategorized',  # Default category
                'custom_order': len(self.books)  # For custom sorting
            }
            
            self.books.append(book_data)
            
            # Generate thumbnail in background
            threading.Thread(
                target=self.generate_thumbnail_async,
                args=(file_path, book_id),
                daemon=True
            ).start()
        
        self.save_bookshelf_data()
        self.refresh_bookshelf()
        self.status_var.set(f"Added {len(file_paths)} PDF(s)")
    
    def generate_thumbnail_async(self, pdf_path, book_id):
        """Generate thumbnail asynchronously"""
        thumbnail_path = self.generate_thumbnail(pdf_path, book_id)
        if thumbnail_path:
            # Update UI on main thread
            self.root.after(0, lambda: self.update_book_thumbnail(book_id, thumbnail_path))
    
    def update_book_thumbnail(self, book_id, thumbnail_path):
        """Update book thumbnail in UI"""
        if thumbnail_path and os.path.exists(thumbnail_path):
            try:
                image = Image.open(thumbnail_path)
                photo = ImageTk.PhotoImage(image)
                self.thumbnail_cache[book_id] = photo
                
                # Find and update the corresponding book frame
                for frame_data in self.book_frames:
                    if frame_data['book_id'] == book_id:
                        frame_data['image_label'].configure(image=photo)
                        break
            except Exception as e:
                print(f"Error updating thumbnail: {e}")
    
    def create_book_frame(self, book, row, col):
        """Create UI frame for a single book"""
        book_frame = tk.Frame(self.scrollable_frame, bg='#404040', relief=tk.RAISED, bd=1)
        book_frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
        
        # Configure grid weight
        self.scrollable_frame.grid_rowconfigure(row, weight=0)
        self.scrollable_frame.grid_columnconfigure(col, weight=1)
        
        # Thumbnail
        thumbnail_path = os.path.join(self.thumbnails_dir, f"{book['id']}.png")
        
        if os.path.exists(thumbnail_path) and book['id'] not in self.thumbnail_cache:
            try:
                image = Image.open(thumbnail_path)
                photo = ImageTk.PhotoImage(image)
                self.thumbnail_cache[book['id']] = photo
            except:
                photo = None
        else:
            photo = self.thumbnail_cache.get(book['id'])
        
        if not photo:
            # Create placeholder
            placeholder = Image.new('RGB', (150, 200), '#666666')
            photo = ImageTk.PhotoImage(placeholder)
        
        image_label = tk.Label(book_frame, image=photo, bg='#404040')
        image_label.pack(pady=(10, 5))
        
        # Title
        title_label = tk.Label(
            book_frame,
            text=book['title'][:30] + "..." if len(book['title']) > 30 else book['title'],
            font=("Arial", 10, "bold"),
            bg='#404040',
            fg='white',
            wraplength=140
        )
        title_label.pack(pady=(0, 5))
        
        # Pages info with bookmark status
        last_page = book.get('last_page', 0)
        # Debug: Check if bookmark exists
        if last_page > 0:
            pages_text = f"{book['pages']} pages • 📖 p.{last_page + 1}"
            info_color = '#FFD54F'  # Yellow for bookmarked books
        else:
            pages_text = f"{book['pages']} pages"
            info_color = '#cccccc'
        
        info_label = tk.Label(
            book_frame,
            text=pages_text,
            font=("Arial", 9),
            bg='#404040',
            fg=info_color
        )
        info_label.pack(pady=(0, 10))
        
        # Store frame data
        frame_data = {
            'frame': book_frame,
            'book_id': book['id'],
            'book': book,
            'image_label': image_label
        }
        self.book_frames.append(frame_data)
        
        # Bind events
        widgets = [book_frame, image_label, title_label, info_label]
        for widget in widgets:
            widget.bind("<Double-Button-1>", lambda e, b=book: self.on_double_click(e, b))
            widget.bind("<Button-3>", lambda e, b=book: self.show_context_menu(e, b))
            widget.bind("<Button-2>", lambda e, b=book: self.show_book_settings(b))  # Middle click for settings
            widget.bind("<Enter>", lambda e, f=book_frame: f.configure(bg='#505050'))
            widget.bind("<Leave>", lambda e, f=book_frame: f.configure(bg='#404040'))
            
            # Drag and drop events
            widget.bind("<Button-1>", lambda e, b=book, f=book_frame: self.on_drag_start(e, b, f))
            widget.bind("<B1-Motion>", lambda e, b=book, f=book_frame: self.on_drag_motion(e, b, f))
            widget.bind("<ButtonRelease-1>", lambda e, b=book, f=book_frame: self.on_drag_end(e, b, f))
    
    def on_double_click(self, event, book):
        """Handle double click - distinguish from drag"""
        if not self.drag_data.get('moved', False):
            self.open_book(book)
        # Reset drag data
        self.drag_data = {}
    
    def on_drag_start(self, event, book, frame):
        """Handle drag start"""
        if self.sort_mode != 'custom':
            # Show helpful message if not in custom sort mode
            self.status_var.set("💡 本を並び替えるには「Sort」を「Custom (Drag & Drop)」に変更してください")
            return
        
        self.dragging_book = book
        self.drag_data = {
            'start_x': event.x_root,
            'start_y': event.y_root,
            'moved': False,
            'frame': frame,
            'original_bg': frame.cget('bg')
        }
    
    def on_drag_motion(self, event, book, frame):
        """Handle drag motion"""
        if self.sort_mode != 'custom' or not self.dragging_book:
            return
        
        # Check if we've moved enough to consider it a drag
        if not self.drag_data['moved']:
            dx = abs(event.x_root - self.drag_data['start_x'])
            dy = abs(event.y_root - self.drag_data['start_y'])
            if dx > 5 or dy > 5:  # Threshold for drag detection
                self.drag_data['moved'] = True
                # Change appearance to indicate dragging
                frame.configure(bg='#FFB74D', relief=tk.RAISED, bd=3)  # Orange highlight for dragging book
                self.root.configure(cursor='hand2')
                # Update status
                self.status_var.set("📦 ドラッグ中... 他の本の上でドロップしてください")
        
        if self.drag_data['moved']:
            # Visual feedback - find target position
            target_frame = self.get_drop_target(event.x_root, event.y_root)
            if target_frame and target_frame != frame:
                # Highlight potential drop target
                for frame_data in self.book_frames:
                    if frame_data['frame'] == target_frame:
                        target_frame.configure(bg='#81C784', relief=tk.RAISED, bd=2)  # Green highlight for drop target
                    elif frame_data['frame'] != frame:
                        frame_data['frame'].configure(bg='#404040', relief=tk.RAISED, bd=1)  # Reset other frames
            else:
                # Reset all other frames if no valid target
                for frame_data in self.book_frames:
                    if frame_data['frame'] != frame:
                        frame_data['frame'].configure(bg='#404040', relief=tk.RAISED, bd=1)
    
    def on_drag_end(self, event, book, frame):
        """Handle drag end"""
        if self.sort_mode != 'custom' or not self.dragging_book:
            return
        
        # Reset cursor
        self.root.configure(cursor='')
        
        if self.drag_data.get('moved', False):
            # Find drop target
            target_frame = self.get_drop_target(event.x_root, event.y_root)
            target_book = None
            
            for frame_data in self.book_frames:
                if frame_data['frame'] == target_frame:
                    target_book = frame_data['book']
                    break
            
            if target_book and target_book != book:
                self.reorder_books(book, target_book)
                self.status_var.set(f"✅ 「{book['title'][:20]}」を移動しました")
            else:
                self.status_var.set("❌ 無効な位置です - 他の本の上でドロップしてください")
        else:
            # Was not a drag, restore normal status
            self.status_var.set("✋ カスタムソートモード - 本をドラッグして並び替えできます")
        
        # Reset all frame colors and borders
        for frame_data in self.book_frames:
            frame_data['frame'].configure(bg='#404040', relief=tk.RAISED, bd=1)
        
        # Reset drag state
        self.dragging_book = None
        self.drag_data = {}
    
    def get_drop_target(self, x, y):
        """Find the frame under the cursor"""
        for frame_data in self.book_frames:
            frame = frame_data['frame']
            try:
                fx = frame.winfo_rootx()
                fy = frame.winfo_rooty()
                fw = frame.winfo_width()
                fh = frame.winfo_height()
                
                if fx <= x <= fx + fw and fy <= y <= fy + fh:
                    return frame
            except:
                continue
        return None
    
    def reorder_books(self, dragged_book, target_book):
        """Reorder books in custom sort mode"""
        # Find current positions
        dragged_idx = None
        target_idx = None
        
        # Get the currently filtered and sorted books
        current_books = self.get_sorted_books()
        
        for i, book in enumerate(current_books):
            if book['id'] == dragged_book['id']:
                dragged_idx = i
            if book['id'] == target_book['id']:
                target_idx = i
        
        if dragged_idx is not None and target_idx is not None:
            # Reorder custom_order values
            if dragged_idx < target_idx:
                # Moving forward
                for i, book in enumerate(current_books):
                    if dragged_idx < i <= target_idx:
                        book['custom_order'] = i - 1
                    elif i == dragged_idx:
                        book['custom_order'] = target_idx
            else:
                # Moving backward
                for i, book in enumerate(current_books):
                    if target_idx <= i < dragged_idx:
                        book['custom_order'] = i + 1
                    elif i == dragged_idx:
                        book['custom_order'] = target_idx
            
            self.save_bookshelf_data()
            self.refresh_bookshelf()
    
    def open_book(self, book):
        """Open PDF in fullscreen reader"""
        if not os.path.exists(book['path']):
            messagebox.showerror("Error", f"File not found: {book['path']}")
            return
        
        # Update last opened
        book['last_opened'] = datetime.now().isoformat()
        self.save_bookshelf_data()
        
        # Launch fullscreen reader with reading direction and bookmark
        try:
            reading_direction = book.get('reading_direction', 'right_to_left')
            start_page = book.get('last_page', 0)
            
            # Check if we're running as an executable or Python script
            if getattr(sys, 'frozen', False):
                # Running as .exe, use PDF_Reader.exe
                reader_exe = os.path.join(os.path.dirname(sys.executable), "PDF_Reader.exe")
                subprocess.Popen([
                    reader_exe,
                    book['path'], 
                    reading_direction, 
                    str(start_page)
                ])
            else:
                # Running as Python script
                subprocess.Popen([
                    sys.executable, 
                    "fullscreen_reader.py", 
                    book['path'], 
                    reading_direction, 
                    str(start_page)
                ])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open reader: {e}")
    
    def show_context_menu(self, event, book):
        """Show context menu for book"""
        context_menu = tk.Menu(self.root, tearoff=0)
        context_menu.add_command(label="Open", command=lambda: self.open_book(book))
        context_menu.add_command(label="Settings", command=lambda: self.show_book_settings(book))
        context_menu.add_command(label="Properties", command=lambda: self.show_properties(book))
        context_menu.add_separator()
        context_menu.add_command(label="Remove", command=lambda: self.remove_book(book))
        
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()
    
    def show_book_settings(self, book):
        """Show book settings dialog"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title(f"Settings - {book['title'][:30]}...")
        settings_window.geometry("500x600")
        settings_window.configure(bg='#2e2e2e')
        
        # Make it modal
        settings_window.transient(self.root)
        settings_window.grab_set()
        
        # Create notebook for tabs
        notebook = ttk.Notebook(settings_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # General settings tab
        general_frame = tk.Frame(notebook, bg='#2e2e2e')
        notebook.add(general_frame, text="General")
        
        # Title setting
        tk.Label(general_frame, text="Title:", font=("Arial", 12), bg='#2e2e2e', fg='white').pack(anchor='w', pady=(20, 5))
        title_var = tk.StringVar(value=book['title'])
        title_entry = tk.Entry(general_frame, textvariable=title_var, font=("Arial", 11), width=50, bg='#404040', fg='white')
        title_entry.pack(fill='x', pady=(0, 20))
        
        # Reading direction setting
        tk.Label(general_frame, text="Reading Direction:", font=("Arial", 12), bg='#2e2e2e', fg='white').pack(anchor='w', pady=(0, 5))
        direction_var = tk.StringVar(value=book.get('reading_direction', 'right_to_left'))
        
        direction_frame = tk.Frame(general_frame, bg='#2e2e2e')
        direction_frame.pack(fill='x', pady=(0, 20))
        
        tk.Radiobutton(direction_frame, text="Right to Left (Japanese style)", variable=direction_var, 
                      value='right_to_left', bg='#2e2e2e', fg='white', selectcolor='#404040',
                      font=("Arial", 10)).pack(anchor='w')
        tk.Radiobutton(direction_frame, text="Left to Right (Western style)", variable=direction_var, 
                      value='left_to_right', bg='#2e2e2e', fg='white', selectcolor='#404040',
                      font=("Arial", 10)).pack(anchor='w')
        
        # Category setting
        tk.Label(general_frame, text="Category:", font=("Arial", 12), bg='#2e2e2e', fg='white').pack(anchor='w', pady=(20, 5))
        category_var = tk.StringVar(value=book.get('category', 'Uncategorized'))
        
        categories_list = sorted([cat for cat in self.categories if cat != 'All'])
        category_dropdown = ttk.Combobox(general_frame, textvariable=category_var, 
                                        values=categories_list, state="readonly", 
                                        font=("Arial", 10))
        category_dropdown.pack(fill='x', pady=(0, 20))
        
        # Bookmark section
        bookmark_frame = tk.Frame(general_frame, bg='#2e2e2e')
        bookmark_frame.pack(fill='x', pady=(10, 20))
        
        # Bookmark status
        last_page = book.get('last_page', 0)
        bookmark_text = f"Current bookmark: Page {last_page + 1}" if last_page > 0 else "No bookmark set"
        tk.Label(bookmark_frame, text="📖 Bookmark:", font=("Arial", 12), bg='#2e2e2e', fg='white').pack(anchor='w', pady=(0, 5))
        bookmark_status_label = tk.Label(bookmark_frame, text=bookmark_text, font=("Arial", 10), 
                                        bg='#2e2e2e', fg='#FFD54F' if last_page > 0 else '#cccccc')
        bookmark_status_label.pack(anchor='w', pady=(0, 10))
        
        # Reset bookmark button
        def reset_bookmark():
            if messagebox.askyesno("Reset Bookmark", "Are you sure you want to reset the bookmark? This will make the book start from page 1 next time."):
                book['last_page'] = 0
                bookmark_status_label.config(text="No bookmark set", fg='#cccccc')
                messagebox.showinfo("Bookmark Reset", "Bookmark has been reset successfully!")
        
        reset_button = tk.Button(bookmark_frame, text="🔄 Reset Bookmark", command=reset_bookmark,
                               bg='#FF5722', fg='white', font=("Arial", 10), padx=15, pady=5)
        reset_button.pack(anchor='w')
        
        # Thumbnail settings tab
        thumbnail_frame = tk.Frame(notebook, bg='#2e2e2e')
        notebook.add(thumbnail_frame, text="Thumbnail")
        
        tk.Label(thumbnail_frame, text="Thumbnail Page:", font=("Arial", 12), bg='#2e2e2e', fg='white').pack(anchor='w', pady=(20, 5))
        
        # Page selection frame
        page_frame = tk.Frame(thumbnail_frame, bg='#2e2e2e')
        page_frame.pack(fill='x', pady=(0, 10))
        
        current_thumb_page = book.get('thumbnail_page', 0)
        page_var = tk.IntVar(value=current_thumb_page + 1)  # Display 1-based page numbers
        
        tk.Label(page_frame, text="Page:", bg='#2e2e2e', fg='white').pack(side='left')
        page_spinbox = tk.Spinbox(page_frame, from_=1, to=book['pages'], textvariable=page_var,
                                 width=10, bg='#404040', fg='white', font=("Arial", 10))
        page_spinbox.pack(side='left', padx=(5, 10))
        
        # Thumbnail preview
        preview_frame = tk.Frame(thumbnail_frame, bg='#404040', relief=tk.RAISED, bd=2)
        preview_frame.pack(pady=20)
        
        # Create preview label
        preview_label = tk.Label(preview_frame, text="Loading preview...", bg='#404040', fg='white', 
                                width=20, height=10)
        preview_label.pack(padx=10, pady=10)
        
        # Store references to prevent garbage collection
        preview_images = {}
        
        def update_thumbnail_preview(*args):
            """Update thumbnail preview when page changes"""
            try:
                page_num = page_var.get() - 1  # Convert to 0-based
                print(f"Updating preview for page {page_num + 1}")  # Debug
                
                if 0 <= page_num < book['pages']:
                    # Generate preview thumbnail
                    doc = fitz.open(book['path'])
                    page = doc[page_num]
                    mat = fitz.Matrix(0.5, 0.5)  # Scale for preview
                    pix = page.get_pixmap(matrix=mat)
                    
                    img_data = pix.tobytes("ppm")
                    pil_image = Image.open(io.BytesIO(img_data))
                    
                    # Resize to fit preview area
                    pil_image.thumbnail((150, 200), Image.Resampling.LANCZOS)
                    
                    # Create PhotoImage
                    photo = ImageTk.PhotoImage(pil_image)
                    
                    # Store reference to prevent garbage collection
                    preview_images[page_num] = photo
                    
                    # Update label
                    preview_label.configure(image=photo, text="")
                    preview_label.image = photo
                    
                    doc.close()
                    print(f"Preview updated successfully for page {page_num + 1}")  # Debug
                else:
                    preview_label.configure(text="Invalid page", image="")
                    print(f"Invalid page number: {page_num + 1}")  # Debug
                    
            except Exception as e:
                preview_label.configure(text=f"Error loading preview", image="")
                print(f"Error updating preview: {e}")  # Debug
        
        # Update preview when page changes
        page_var.trace('w', update_thumbnail_preview)
        
        # Generate initial preview
        settings_window.after(100, update_thumbnail_preview)
        
        # Buttons
        button_frame = tk.Frame(settings_window, bg='#2e2e2e')
        button_frame.pack(fill='x', padx=20, pady=(0, 20))
        
        def save_settings():
            """Save book settings"""
            book['title'] = title_var.get().strip() or book['filename']
            book['reading_direction'] = direction_var.get()
            book['category'] = category_var.get()
            old_thumb_page = book.get('thumbnail_page', 0)
            new_thumb_page = page_var.get() - 1  # Convert to 0-based
            book['thumbnail_page'] = new_thumb_page
            
            # Regenerate thumbnail if page changed
            if old_thumb_page != new_thumb_page:
                # Remove old thumbnail
                old_thumbnail = os.path.join(self.thumbnails_dir, f"{book['id']}.png")
                if os.path.exists(old_thumbnail):
                    os.remove(old_thumbnail)
                
                # Generate new thumbnail
                threading.Thread(
                    target=self.generate_thumbnail_async,
                    args=(book['path'], book['id']),
                    daemon=True
                ).start()
            
            self.save_bookshelf_data()
            self.refresh_bookshelf()
            settings_window.destroy()
            messagebox.showinfo("Settings", "Book settings saved successfully!")
        
        def cancel_settings():
            settings_window.destroy()
        
        tk.Button(button_frame, text="Cancel", command=cancel_settings, bg='#666', fg='white', 
                 padx=20, font=("Arial", 10)).pack(side='right', padx=(10, 0))
        tk.Button(button_frame, text="Save", command=save_settings, bg='#4CAF50', fg='white', 
                 padx=20, font=("Arial", 10)).pack(side='right')

    def show_properties(self, book):
        """Show book properties dialog"""
        props_window = tk.Toplevel(self.root)
        props_window.title("Book Properties")
        props_window.geometry("450x350")
        props_window.configure(bg='#2e2e2e')
        
        # Make it modal
        props_window.transient(self.root)
        props_window.grab_set()
        
        # Format bookmark info
        last_page = book.get('last_page', 0)
        bookmark_info = f"Page {last_page + 1}" if last_page > 0 else "No bookmark"
        
        info_text = f"""Title: {book['title']}
Filename: {book['filename']}
Path: {book['path']}
Pages: {book['pages']}
Reading Direction: {book.get('reading_direction', 'right_to_left').replace('_', ' ').title()}
Thumbnail Page: {book.get('thumbnail_page', 0) + 1}
Current Bookmark: {bookmark_info}
Added: {book['added_date'][:19].replace('T', ' ')}
Last Opened: {book['last_opened'][:19].replace('T', ' ') if book['last_opened'] else 'Never'}"""
        
        text_widget = tk.Text(
            props_window,
            wrap=tk.WORD,
            font=("Arial", 10),
            bg='#404040',
            fg='white',
            padx=10,
            pady=10
        )
        text_widget.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        text_widget.insert(1.0, info_text)
        text_widget.configure(state=tk.DISABLED)
    
    def remove_book(self, book):
        """Remove book from bookshelf"""
        if messagebox.askyesno("Confirm", f"Remove '{book['title']}' from bookshelf?"):
            self.books = [b for b in self.books if b['id'] != book['id']]
            
            # Remove thumbnail
            thumbnail_path = os.path.join(self.thumbnails_dir, f"{book['id']}.png")
            if os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
            
            self.save_bookshelf_data()
            self.refresh_bookshelf()
    
    def on_search_change(self, *args):
        """Handle search input changes"""
        self.refresh_bookshelf()
    
    def on_category_change(self, event=None):
        """Handle category selection change"""
        self.current_category = self.category_var.get()
        self.refresh_bookshelf()
    
    def on_sort_change(self, event=None):
        """Handle sort mode change"""
        # Map display values to internal values
        display_to_internal = {
            'Recent': 'recent',
            'Date Added': 'added', 
            'Title A-Z': 'title',
            'Custom (Drag & Drop)': 'custom'
        }
        
        display_value = self.sort_var.get()
        self.sort_mode = display_to_internal.get(display_value, 'recent')
        
        if self.sort_mode == 'custom':
            # Show detailed info about drag and drop
            self.status_var.set("✋ カスタムソートモード - 本をドラッグして並び替えできます")
        else:
            self.status_var.set("Ready")
        self.refresh_bookshelf()
    
    def manage_categories(self):
        """Show category management dialog"""
        cat_window = tk.Toplevel(self.root)
        cat_window.title("Manage Categories")
        cat_window.geometry("400x500")
        cat_window.configure(bg='#2e2e2e')
        
        # Make it modal
        cat_window.transient(self.root)
        cat_window.grab_set()
        
        # Title
        tk.Label(cat_window, text="Manage Categories", font=("Arial", 14, "bold"),
                bg='#2e2e2e', fg='white').pack(pady=(20, 10))
        
        # Category list frame
        list_frame = tk.Frame(cat_window, bg='#2e2e2e')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Listbox with scrollbar
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        category_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set,
                                     bg='#404040', fg='white', font=("Arial", 11),
                                     selectbackground='#666')
        category_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=category_listbox.yview)
        
        # Populate categories (exclude 'All')
        user_categories = [cat for cat in sorted(self.categories) if cat != 'All']
        for cat in user_categories:
            category_listbox.insert(tk.END, cat)
        
        # Add new category frame
        add_frame = tk.Frame(cat_window, bg='#2e2e2e')
        add_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Label(add_frame, text="New Category:", bg='#2e2e2e', fg='white').pack(anchor='w')
        new_cat_var = tk.StringVar()
        new_cat_entry = tk.Entry(add_frame, textvariable=new_cat_var, bg='#404040', fg='white')
        new_cat_entry.pack(fill='x', pady=(5, 10))
        
        def add_category():
            new_cat = new_cat_var.get().strip()
            if new_cat and new_cat not in self.categories:
                self.categories.add(new_cat)
                category_listbox.insert(tk.END, new_cat)
                new_cat_var.set("")
                self.update_category_dropdown()
        
        def delete_category():
            selection = category_listbox.curselection()
            if selection:
                cat_name = category_listbox.get(selection[0])
                if cat_name != 'Uncategorized':  # Can't delete default category
                    # Move books from deleted category to Uncategorized
                    for book in self.books:
                        if book.get('category') == cat_name:
                            book['category'] = 'Uncategorized'
                    
                    self.categories.discard(cat_name)
                    category_listbox.delete(selection[0])
                    self.update_category_dropdown()
                    self.save_bookshelf_data()
                else:
                    messagebox.showwarning("Warning", "Cannot delete the 'Uncategorized' category.")
        
        # Buttons
        button_frame = tk.Frame(add_frame, bg='#2e2e2e')
        button_frame.pack(fill='x', pady=10)
        
        tk.Button(button_frame, text="Add", command=add_category, bg='#4CAF50', fg='white',
                 padx=20).pack(side=tk.LEFT)
        tk.Button(button_frame, text="Delete Selected", command=delete_category, bg='#F44336', fg='white',
                 padx=20).pack(side=tk.LEFT, padx=(10, 0))
        
        # Close button
        tk.Button(cat_window, text="Close", command=cat_window.destroy, bg='#666', fg='white',
                 padx=30, pady=10).pack(pady=20)
        
        new_cat_entry.focus()
    
    def update_category_dropdown(self):
        """Update category dropdown values"""
        categories_list = ['All'] + sorted([cat for cat in self.categories if cat != 'All'])
        self.category_dropdown.config(values=categories_list)
    
    def get_sorted_books(self):
        """Get filtered and sorted books (used for drag and drop)"""
        # Filter books based on search and category
        search_term = self.search_var.get().lower()
        current_cat = self.current_category
        
        filtered_books = []
        for book in self.books:
            # Category filter
            book_category = book.get('category', 'Uncategorized')
            if current_cat != 'All' and book_category != current_cat:
                continue
            
            # Search filter
            if search_term:
                if (search_term in book['title'].lower() or 
                    search_term in book['filename'].lower() or
                    search_term in book_category.lower()):
                    filtered_books.append(book)
            else:
                filtered_books.append(book)
        
        return self.sort_books(filtered_books)
    
    def sort_books(self, books):
        """Sort books based on current sort mode"""
        if self.sort_mode == 'recent':
            return sorted(books, key=lambda x: (
                x['last_opened'] or '1900-01-01T00:00:00',
                x['added_date']
            ), reverse=True)
        elif self.sort_mode == 'added':
            return sorted(books, key=lambda x: x['added_date'], reverse=True)
        elif self.sort_mode == 'title':
            return sorted(books, key=lambda x: x['title'].lower())
        elif self.sort_mode == 'custom':
            return sorted(books, key=lambda x: x.get('custom_order', 999))
        else:
            return books
    
    def refresh_bookshelf(self):
        """Refresh the bookshelf display"""
        # Clear existing frames
        for frame_data in self.book_frames:
            frame_data['frame'].destroy()
        self.book_frames.clear()
        
        # Filter books based on search and category
        search_term = self.search_var.get().lower()
        current_cat = self.current_category
        
        filtered_books = []
        for book in self.books:
            # Category filter
            book_category = book.get('category', 'Uncategorized')
            if current_cat != 'All' and book_category != current_cat:
                continue
            
            # Search filter
            if search_term:
                if (search_term in book['title'].lower() or 
                    search_term in book['filename'].lower() or
                    search_term in book_category.lower()):
                    filtered_books.append(book)
            else:
                filtered_books.append(book)
        
        # Sort books based on sort mode
        filtered_books = self.sort_books(filtered_books)
        
        # Create grid of books
        cols = 5  # Number of columns
        for i, book in enumerate(filtered_books):
            row = i // cols
            col = i % cols
            self.create_book_frame(book, row, col)
        
        # Update status
        total_books = len(self.books)
        shown_books = len(filtered_books)
        
        if search_term:
            self.status_var.set(f"Showing {shown_books} of {total_books} books")
        else:
            self.status_var.set("Ready")
        
        self.book_count_label.configure(text=f"{total_books} books")
        
        # Update canvas scroll region
        self.root.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    
    def load_bookshelf_data(self):
        """Load bookshelf data from JSON file"""
        try:
            if os.path.exists(self.bookshelf_file):
                with open(self.bookshelf_file, 'r', encoding='utf-8') as f:
                    self.books = json.load(f)
        except Exception as e:
            print(f"Error loading bookshelf data: {e}")
            self.books = []
        
        # Update categories from loaded books and ensure defaults
        for book in self.books:
            if 'category' not in book:
                book['category'] = 'Uncategorized'
            self.categories.add(book['category'])
        
        self.update_category_dropdown()
        self.refresh_bookshelf()
    
    def save_bookshelf_data(self):
        """Save bookshelf data to JSON file"""
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            with open(self.bookshelf_file, 'w', encoding='utf-8') as f:
                json.dump(self.books, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving bookshelf data: {e}")

def main():
    root = tk.Tk()
    app = PDFBookshelf(root)
    root.mainloop()

if __name__ == "__main__":
    main()