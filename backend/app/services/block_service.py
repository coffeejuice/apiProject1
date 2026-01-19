from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List, Optional
from uuid import UUID
from app.models.document.block import Block, BlockType

def get_root_blocks(db: Session, process_id: int) -> List[Block]:
    return list(db.execute(select(Block).filter(
        Block.process_id == process_id,
        Block.parent_block_id == None
    ).order_by(Block.order_key)).scalars().all())

def get_block_children(db: Session, block_id: UUID) -> List[Block]:
    block = db.execute(select(Block).filter(Block.block_id == block_id)).scalars().first()
    if not block:
        return []

    return list(db.execute(select(Block).filter(
        Block.process_id == block.process_id,
        Block.parent_block_id == block_id
    ).order_by(Block.order_key)).scalars().all())

def generate_order_key() -> str:
    """Generate a sortable order key using timestamp + random suffix"""
    import time
    import random
    timestamp = int(time.time() * 1000000)
    suffix = random.randint(1000, 9999)
    return f"{timestamp:020d}-{suffix}"
