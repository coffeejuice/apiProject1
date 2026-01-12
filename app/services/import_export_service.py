from sqlalchemy.orm import Session
from typing import List, Dict
from uuid import UUID, uuid4
from app.models import Block, BlockType
from app.services.block_service import generate_order_key
import re

def export_to_markdown(db: Session, document_id: UUID) -> str:
    """Export document blocks to Markdown"""
    blocks = db.query(Block).filter(
        Block.document_id == document_id,
        Block.parent_block_id == None
    ).order_by(Block.order_key).all()

    lines = []
    for block in blocks:
        lines.append(_block_to_markdown(block))
        # Recursively export children
        lines.extend(_export_children(db, block.block_id, indent=0))

    return "\n\n".join(lines)

def _block_to_markdown(block: Block) -> str:
    """Convert a single block to Markdown"""
    if block.block_type == BlockType.heading1:
        return f"# {block.text}"
    elif block.block_type == BlockType.heading2:
        return f"## {block.text}"
    elif block.block_type == BlockType.list:
        return f"- {block.text}"
    elif block.block_type == BlockType.todo:
        checked = block.props.get("checked", False)
        checkbox = "[x]" if checked else "[ ]"
        return f"- {checkbox} {block.text}"
    elif block.block_type == BlockType.code:
        lang = block.props.get("language", "")
        return f"```{lang}\n{block.text}\n```"
    elif block.block_type == BlockType.quote:
        return f"> {block.text}"
    elif block.block_type == BlockType.divider:
        return "---"
    else:  # paragraph
        return block.text

def _export_children(db: Session, parent_id: UUID, indent: int) -> List[str]:
    """Recursively export child blocks"""
    children = db.query(Block).filter(
        Block.parent_block_id == parent_id
    ).order_by(Block.order_key).all()

    lines = []
    for child in children:
        # Add indentation for nested items
        text = _block_to_markdown(child)
        if child.block_type in [BlockType.list, BlockType.todo]:
            text = "  " * (indent + 1) + text
        lines.append(text)
        lines.extend(_export_children(db, child.block_id, indent + 1))

    return lines

def import_from_markdown(markdown: str) -> List[Dict]:
    """
    Parse Markdown and return list of block data dicts.
    Returns blocks in flat structure with parent references.
    """
    lines = markdown.split("\n")
    blocks = []
    current_code_block = None
    code_lines = []

    for line in lines:
        # Handle code blocks
        if line.startswith("```"):
            if current_code_block is None:
                # Start code block
                lang = line[3:].strip()
                current_code_block = {
                    "block_id": str(uuid4()),
                    "parent_block_id": None,
                    "block_type": "code",
                    "text": "",
                    "props": {"language": lang},
                    "order_key": generate_order_key()
                }
                code_lines = []
            else:
                # End code block
                current_code_block["text"] = "\n".join(code_lines)
                blocks.append(current_code_block)
                current_code_block = None
                code_lines = []
            continue

        if current_code_block:
            code_lines.append(line)
            continue

        # Skip empty lines
        if not line.strip():
            continue

        # Parse different block types
        block = None

        # Heading 1
        if line.startswith("# "):
            block = {
                "block_id": str(uuid4()),
                "parent_block_id": None,
                "block_type": "heading1",
                "text": line[2:].strip(),
                "props": {},
                "order_key": generate_order_key()
            }

        # Heading 2
        elif line.startswith("## "):
            block = {
                "block_id": str(uuid4()),
                "parent_block_id": None,
                "block_type": "heading2",
                "text": line[3:].strip(),
                "props": {},
                "order_key": generate_order_key()
            }

        # Todo
        elif "- [ ]" in line or "- [x]" in line:
            checked = "[x]" in line
            text = re.sub(r"^[\s-]*\[.\]\s*", "", line)
            block = {
                "block_id": str(uuid4()),
                "parent_block_id": None,
                "block_type": "todo",
                "text": text,
                "props": {"checked": checked},
                "order_key": generate_order_key()
            }

        # List item
        elif line.startswith("- "):
            block = {
                "block_id": str(uuid4()),
                "parent_block_id": None,
                "block_type": "list",
                "text": line[2:].strip(),
                "props": {},
                "order_key": generate_order_key()
            }

        # Quote
        elif line.startswith("> "):
            block = {
                "block_id": str(uuid4()),
                "parent_block_id": None,
                "block_type": "quote",
                "text": line[2:].strip(),
                "props": {},
                "order_key": generate_order_key()
            }

        # Divider
        elif line.strip() in ["---", "***", "___"]:
            block = {
                "block_id": str(uuid4()),
                "parent_block_id": None,
                "block_type": "divider",
                "text": "",
                "props": {},
                "order_key": generate_order_key()
            }

        # Paragraph
        else:
            block = {
                "block_id": str(uuid4()),
                "parent_block_id": None,
                "block_type": "paragraph",
                "text": line.strip(),
                "props": {},
                "order_key": generate_order_key()
            }

        if block:
            blocks.append(block)

    return blocks
