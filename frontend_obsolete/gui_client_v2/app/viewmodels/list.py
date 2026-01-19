from PySide6.QtCore import QObject, Property, Signal, Slot

class DocumentListViewModel(QObject):
    documentsChanged = Signal()
    currentDocumentChanged = Signal()

    def __init__(self, api_client):
        super().__init__()
        self.api = api_client
        self._documents = []
        self._current_doc_id = None

    @Property(list, notify=documentsChanged)
    def documents(self):
        return self._documents

    @Property(int, notify=currentDocumentChanged)
    def currentDocId(self):
        return self._current_doc_id if self._current_doc_id is not None else -1

    @Slot()
    def refresh(self):
        res = self.api.list_documents()
        if res and "documents" in res:
            self._documents = res["documents"]
            self.documentsChanged.emit()
            
            if not self._current_doc_id and self._documents:
                self._current_doc_id = self._documents[0]["process_id"]
                self.currentDocumentChanged.emit()

    @Slot(int)
    def selectDocument(self, doc_id):
        if self._current_doc_id != doc_id:
            self._current_doc_id = doc_id
            self.currentDocumentChanged.emit()
