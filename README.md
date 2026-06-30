# md2confluence

A desktop-friendly web utility built with [NiceGUI](https://nicegui.io/) that syncs local Markdown files with [Atlassian Confluence](https://www.atlassian.com/software/confluence).

## Features

- **Bidirectional Sync**: Push local Markdown files to Confluence or pull content from Confluence back to local files.
- **Directory Workspace**: Select any local directory. Scan and view all markdown files in a flat list or nested tree structure.
- **Automatic Status Tracking**: Compares local changes with Confluence page statuses (such as tracking modified states, unlinked pages, etc.).
- **Metadata Association**: Links markdown files directly to Confluence pages by storing the Confluence Page ID in the file's YAML frontmatter.
- **Download / Export**: Recursively download individual pages or entire page hierarchies from Confluence into a local directory.
- **Configuration Management**: Configure credentials (API tokens, Username, Host URL, Default Space Key, and Parent Page ID) with connection testing support.

## Key Libraries Used

This project relies on the following key Python libraries:

- **[NiceGUI](https://nicegui.io/)**: An easy-to-use Python-based UI framework used to build the web layout, handle user interactions, run background threads, and construct the application dashboard.
- **[markdown-to-confluence](https://github.com/leandro-lucarella-fscore/markdown-to-confluence)**: Handles the parsing of Markdown documents, converting them into Confluence Storage Format (XHTML), and pushing/publishing them to Confluence.
- **[confluence-markdown-exporter](https://github.com/HsuJihHung/confluence-markdown-exporter)**: Powers the pulling and exporting capability, translating Confluence pages back into clean Markdown files for local storage.

## Getting Started

### Prerequisites

- Python 3.8+
- Active Confluence Cloud or Server account with an API token.

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd md2confluence
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Running the App

Start the NiceGUI server by running:
```bash
python app.py
```
This will open the application in your default browser.

### Building / Packaging the App

This project uses **PyInstaller** to compile the application into a standalone executable.

1. Install PyInstaller in your Python environment:
   ```bash
   pip install pyinstaller
   ```
2. Build the project using the provided PyInstaller spec file:
   ```bash
   pyinstaller build/md2confluence.spec
   ```
3. Once completed, the standalone executable will be generated inside the `dist` directory:
   - On Windows: `dist/md2confluence.exe`
   - On macOS/Linux: `dist/md2confluence`

## How it works

1. **Configuration**: Navigate to `⚙ Config` to set up your Confluence URL, email/username, API Token, Space, and default parent page ID.
2. **Pushing Content**:
   - For a local markdown file, click `⬆ Push`.
   - The app uploads the content and writes the generated Confluence Page ID into the frontmatter of your markdown file:
     ```yaml
     ---
     confluence_id: '123456789'
     ---
     # My Document Title
     ...
     ```
3. **Pulling Content**: Click `⬇ Pull` to sync changes made directly on Confluence back into your local markdown file.
4. **Linking Pages**: Use `🔗 Change ID` to map or link a markdown file manually to a pre-existing Confluence page.
