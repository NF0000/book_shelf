# 📚 PDF Bookshelf & Reader

A comprehensive PDF management and reading application with book-like viewing experience and bookmark functionality.

## ✨ Features

### 📖 PDF Bookshelf
- **Library Management**: Organize PDFs in a visual bookshelf interface
- **Category System**: Create custom categories (料理, 勉強, ハワイ, etc.)
- **Drag & Drop Reordering**: Custom book arrangement in "Custom (Drag & Drop)" sort mode
- **Search Functionality**: Find books by title, filename, or category
- **Bookmark System**: Visual bookmark indicators with page numbers
- **Thumbnail Previews**: Auto-generated book covers
- **Book Settings**: Customize title, reading direction, thumbnail page, and categories

### 📖 PDF Reader
- **Book-like Experience**: Double-page spread view like a real book
- **Flexible Reading**: Supports both left-to-right and right-to-left reading directions
- **Smart Navigation**: Arrow keys, space bar, page up/down, or click navigation
- **Automatic Bookmarks**: Saves reading position automatically
- **Zoom Controls**: Zoom in/out or fit to window
- **Fullscreen Mode**: Distraction-free reading experience
- **Manual Bookmark Save**: Press 'B' to save bookmark manually

## 🚀 Quick Start

1. **Launch the Application**: Run `PDF_Bookshelf.exe`
2. **Add PDFs**: Click "+ Add PDF" to import your PDF files
3. **Organize**: Set categories and customize book settings (right-click → Settings)
4. **Read**: Double-click any book to start reading from your last position
5. **Arrange**: Switch to "Custom (Drag & Drop)" sort mode to reorder books

## ⌨️ Keyboard Shortcuts

### PDF Reader
- **Navigation**: ←/→, ↑/↓, Space, Backspace, Page Up/Down
- **Zoom**: +/= (zoom in), - (zoom out), 0 (fit to window)
- **File**: O (open PDF)
- **View**: F/F11/Esc (fullscreen toggle), H/? (help)
- **Bookmark**: B (manual save)
- **Quit**: Q

### PDF Bookshelf
- **File**: Ctrl+O (add PDF)
- **Search**: Ctrl+F (focus search)
- **Refresh**: F5

## 📂 Data Storage

- **Bookshelf Data**: `data/bookshelf.json`
- **Thumbnails**: `data/thumbnails/`
- All data is stored locally and portable

## 🔧 Book Settings

Right-click any book and select "Settings" to customize:
- **Title**: Custom display name
- **Reading Direction**: Japanese (right-to-left) or Western (left-to-right) style
- **Category**: Assign to custom categories
- **Bookmark**: View current bookmark and reset if needed
- **Thumbnail Page**: Choose which page to use as cover

## 📱 System Requirements

- Windows 10/11
- No additional software required (standalone executables)

## 🎯 Tips & Tricks

1. **Organizing**: Create categories like "勉強", "料理", "ハワイ" for better organization
2. **Custom Ordering**: Use drag & drop in custom sort mode for personal arrangement
3. **Bookmarks**: Books with bookmarks show "📖 p.X" in yellow text
4. **Quick Access**: Use search to quickly find books by title or category
5. **Reading Comfort**: Toggle fullscreen (F11) for immersive reading experience

## 📋 File Structure

```
PDF_Bookshelf.exe    # Main application
PDF_Reader.exe       # PDF reading application
data/
  ├── bookshelf.json # Book database
  └── thumbnails/    # Generated book covers
```

## 🎨 Features Overview

- **Visual Library**: Beautiful thumbnail-based book organization
- **Smart Bookmarks**: Automatic position saving with visual indicators
- **Flexible Reading**: Support for various reading preferences
- **Category Management**: Custom organization system
- **Drag & Drop**: Intuitive book arrangement
- **Portable**: All data contained in local folder

Enjoy your digital reading experience! 📚✨