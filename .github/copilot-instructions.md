# Photo Metadata Extractor: Project Rules

## Technical Stack Constraints
- **Backend:** Flask (Python 3.10+). Use `Pillow` for primary parsing, `piexif` for RAW/low-level.
- **Frontend:** Vanilla JS/CSS/HTML only. No React/Vue. Use CSS Grid/Flexbox.
- **Mapping:** Leaflet.js via CDN.

## Development Standards
- **DRY Logic:** Parsing logic must reside in `extractor.py`, not `app.py`.
- **Naming:** CamelCase for JS, snake_case for Python.
- **Security:** - No `os.save()` to disk. Keep uploads in-memory using `io.BytesIO`.
    - Sanitise all filenames before processing.
- **Error Handling:** Every API response must include a `status` (success/error) and a descriptive `message`.

## AI Interaction Patterns
- Before generating code, propose the file structure or algorithm logic.
- When generating CSS, use variables (`--primary-color`) defined in `:root`.
- When writing Python, provide type hints (e.g., `def parse(data: bytes) -> dict:`).