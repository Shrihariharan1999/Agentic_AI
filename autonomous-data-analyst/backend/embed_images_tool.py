"""Tool for writing documents with embedded images."""

from langchain_core.tools import tool
from pathlib import Path
import base64
import markdown

WORKSPACE_DIR = Path(__file__).resolve().parent.parent / "workspace"
CHARTS_DIR = Path(__file__).resolve().parent / "charts"
REPORTS_DIR = WORKSPACE_DIR / "reports"

REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _find_chart(filename: str) -> Path | None:
    """Find a chart file by name in various locations."""
    candidates = [
        CHARTS_DIR / filename,
        CHARTS_DIR / filename if not filename.endswith(".png") else CHARTS_DIR / f"{filename}.png",
        WORKSPACE_DIR / "charts" / filename,
    ]
    
    for path in candidates:
        if path.exists() and path.is_file():
            return path
    
    return None


def _image_to_base64(image_path: Path) -> str:
    """Convert image to base64 data URI."""
    with open(image_path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode()
    
    if image_path.suffix.lower() == ".png":
        mime = "image/png"
    elif image_path.suffix.lower() in {".jpg", ".jpeg"}:
        mime = "image/jpeg"
    else:
        mime = "image/png"
    
    return f"data:{mime};base64,{b64}"


@tool
def write_document_with_images(
    document_name: str,
    content: str,
    image_files: list[str] | None = None,
    format: str = "md"
) -> str:
    """Write analysis document with embedded images.
    
    Args:
        document_name: Document name (e.g., "Loan Analysis Report")
        content: Document content (text/markdown/html)
        image_files: List of chart filenames to embed (e.g., ["chart_abc123.png"])
        format: Document format - md (markdown), html, txt (default: md)
    
    Returns:
        Success message with file path
        
    Examples:
        - write_document_with_images("Analysis", "# Report\\n\\nFindings...", ["chart_1.png"], "md")
        - write_document_with_images("Report", "<html>...</html>", ["chart_1.png", "chart_2.png"], "html")
    """
    
    image_files = image_files or []
    
    # Sanitize document name
    safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in document_name)
    safe_name = safe_name.strip(" -_") or "report"
    
    print(f"\n[DOCUMENT] Writing: {safe_name}.{format}")
    if image_files:
        print(f"[DOCUMENT] Embedding {len(image_files)} image(s): {', '.join(image_files)}")
    
    # HTML format with embedded base64 images
    if format == "html":
        images_html = ""
        
        for img_file in image_files:
            img_path = _find_chart(img_file)
            if img_path:
                b64_uri = _image_to_base64(img_path)
                images_html += f'<p><img src="{b64_uri}" style="max-width:100%;height:auto;border:1px solid #ddd;margin:10px 0;"></p>\n'
                print(f"  ✅ Embedded: {img_file}")
            else:
                print(f"  ⚠️  Chart not found: {img_file}")
        
        rendered_content = markdown.markdown(
            content,
            extensions=["extra", "sane_lists"],
        )

        html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{safe_name}</title>
<style>
    body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
    h1, h2, h3 {{ color: #333; }}
    img {{ border-radius: 4px; }}
</style>
</head>
<body>
{rendered_content}
{images_html}
</body>
</html>"""
        
        file_path = REPORTS_DIR / f"{safe_name}.html"
        file_path.write_text(html_content, encoding="utf-8")
        
    # Markdown format with image references
    elif format == "md":
        markdown_images = ""
        
        for img_file in image_files:
            img_path = _find_chart(img_file)
            if img_path:
                # For markdown, reference the file path
                rel_path = f"../backend/charts/{img_file}"
                markdown_images += f"![{img_file}]({rel_path})\n\n"
                print(f"  ✅ Referenced: {img_file}")
            else:
                print(f"  ⚠️  Chart not found: {img_file}")
        
        markdown_content = content
        if markdown_images:
            markdown_content += "\n\n## Visualizations\n\n" + markdown_images
        
        file_path = REPORTS_DIR / f"{safe_name}.md"
        file_path.write_text(markdown_content, encoding="utf-8")
    
    # Plain text format
    else:
        text_content = content
        
        if image_files:
            text_content += "\n\n## Visualizations\n"
            for img_file in image_files:
                img_path = _find_chart(img_file)
                if img_path:
                    print(f"  ✅ Referenced: {img_file}")
                    text_content += f"\n- Chart: {img_file}"
                else:
                    print(f"  ⚠️  Chart not found: {img_file}")
        
        file_path = REPORTS_DIR / f"{safe_name}.txt"
        file_path.write_text(text_content, encoding="utf-8")
    
    print(f"[DOCUMENT] ✅ Saved to: workspace/reports/{file_path.name}\n")
    
    return f"Document '{file_path.name}' created successfully with {len(image_files)} image(s) embedded."
