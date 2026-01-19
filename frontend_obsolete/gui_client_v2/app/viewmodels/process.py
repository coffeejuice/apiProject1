from PySide6.QtCore import QObject, Property, Signal, Slot
from .block import BlockViewModel, TextBlockViewModel
from ..core.registry import BlockRegistry

class ProcessViewModel(QObject):
    dataChanged = Signal()
    blocksChanged = Signal()

    def __init__(self, api_client, doc_id=None):
        super().__init__()
        self.api = api_client
        self.doc_id = doc_id
        self._data = {}
        self._blocks = [] 

    @Property(str, notify=dataChanged)
    def title(self):
        return self._data.get("title", "Untitled")

    @Property(list, notify=blocksChanged)
    def blocks(self):
        return self._blocks

    @Slot()
    def load(self):
        if not self.doc_id:
            print("ProcessViewModel.load: no doc_id")
            return

        print(f"ProcessViewModel.load: loading document {self.doc_id}")
        doc_res = self.api.get_document(self.doc_id)
        if doc_res:
            self._data = doc_res
            self.dataChanged.emit()
            print(f"Document loaded: {doc_res.get('title', 'Untitled')}")

        blocks_res = self.api.get_blocks(self.doc_id)
        print(f"Got blocks response: {blocks_res}")
        if blocks_res is not None:
            self._blocks = []
            for bdata in blocks_res:
                print(f"Creating block: {bdata.get('block_type')} - {bdata.get('block_id')}")
                vm = BlockRegistry.create_viewmodel(bdata.get("block_type"), bdata)
                if vm:
                    vm.parent = self # Link back to process for sync
                    self._blocks.append(vm)
            print(f"Loaded {len(self._blocks)} blocks")
            self.blocksChanged.emit()

    @Slot(str, str)
    def insertBlock(self, block_type, text=""):
        print(f"insertBlock called: block_type={block_type}, text={text}")
        if not self.doc_id:
            print("insertBlock: no doc_id")
            return

        import time, random, uuid
        order_key = f"{int(time.time() * 1000):020d}-{random.randint(1000, 9999)}"
        new_id = str(uuid.uuid4())

        # Create block with some default cells for demonstration
        block_data = {
            "block_id": new_id,
            "parent_block_id": None,
            "order_key": order_key,
            "block_type": block_type,
            "text": text,
            "props": {},
            "cells": [
                {"angle": "90", "height": "100"},
                {"angle": "45", "height": "150"}
            ]
        }

        op = {
            "op_type": "insert_block",
            "data": block_data
        }

        print(f"Committing block: {new_id}")
        res = self.api.commit(self.doc_id, self._data.get("current_rev_number", 0), [op])
        print(f"Commit response: {res}")
        if res and res.get("success"):
            self._data["current_rev_number"] = res["new_rev_number"]
            print("Block created successfully, reloading...")
            self.load() # Refresh blocks
        else:
            print(f"Failed to create block: {res}")

    @Slot(int)
    def removeBlock(self, index):
        """Remove block at specified index"""
        if 0 <= index < len(self._blocks):
            block_id = self._blocks[index].block_id

            op = {
                "op_type": "delete_block",
                "data": {
                    "block_id": block_id
                }
            }

            res = self.api.commit(self.doc_id, self._data.get("current_rev_number", 0), [op])
            if res and res.get("success"):
                self._data["current_rev_number"] = res["new_rev_number"]
                self.load() # Refresh blocks

    def sync_block(self, block_id, text):
        op = {
            "op_type": "update_text",
            "data": {
                "block_id": block_id,
                "text": text
            }
        }
        res = self.api.commit(self.doc_id, self._data.get("current_rev_number", 0), [op])
        if res and res.get("success"):
            self._data["current_rev_number"] = res["new_rev_number"]
