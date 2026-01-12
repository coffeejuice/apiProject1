from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from app.models import Block, BlockType

def get_root_blocks(db: Session, document_id: UUID) -> List[Block]:
    return db.query(Block).filter(
        Block.document_id == document_id,
        Block.parent_block_id == None
    ).order_by(Block.order_key).all()

def get_block_children(db: Session, block_id: UUID) -> List[Block]:
    block = db.query(Block).filter(Block.block_id == block_id).first()
    if not block:
        return []

    return db.query(Block).filter(
        Block.document_id == block.document_id,
        Block.parent_block_id == block_id
    ).order_by(Block.order_key).all()

def generate_order_key() -> str:
    """Generate a sortable order key using timestamp + random suffix"""
    import time
    import random
    timestamp = int(time.time() * 1000000)
    suffix = random.randint(1000, 9999)
    return f"{timestamp:020d}-{suffix}"
