import os
import sys
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QUrl, QCoreApplication

from app.api.client import ApiClient
from app.viewmodels.process import ProcessViewModel
from app.viewmodels.list import DocumentListViewModel
from app.viewmodels.auth import AuthViewModel

def main():
    # Set style to Windows for better visibility
    os.environ["QT_QUICK_CONTROLS_STYLE"] = "Windows"
    
    app = QGuiApplication(sys.argv)
    engine = QQmlApplicationEngine()

    # Initialize API Client
    api = ApiClient("http://localhost:8001")
    
    # Initialize ViewModels
    auth_vm = AuthViewModel(api)
    doc_list_vm = DocumentListViewModel(api)
    process_vm = ProcessViewModel(api)

    # Wire up authentication status and document list
    def on_auth_changed():
        if auth_vm.isLoggedIn:
            doc_list_vm.refresh()
        else:
            doc_list_vm.refresh() # Clear list
            # Optionally clear active document
            process_vm.doc_id = None
            process_vm.load()

    auth_vm.authStatusChanged.connect(on_auth_changed)

    # Wire up document selection
    def on_doc_changed():
        process_vm.doc_id = doc_list_vm.currentDocId
        process_vm.load()

    doc_list_vm.currentDocumentChanged.connect(on_doc_changed)

    # Expose to QML
    engine.rootContext().setContextProperty("authViewModel", auth_vm)
    engine.rootContext().setContextProperty("documentListViewModel", doc_list_vm)
    engine.rootContext().setContextProperty("processViewModel", process_vm)

    # Add import path for QML components and Theme
    qml_dir = os.path.join(os.path.dirname(__file__), "resources", "qml")
    engine.addImportPath(qml_dir)

    # Load Main QML
    qml_file = os.path.join(qml_dir, "Main.qml")
    engine.load(QUrl.fromLocalFile(os.path.abspath(qml_file)))

    # Simple Auto-login for demo (optional, can be removed now that UI exists)
    # print("Attempting demo login...")
    # if not api.login("demo_user", "password123"):
    #     print("Login failed, proceeding as guest...")
    # else:
    #     auth_vm._is_logged_in = True
    #     auth_vm.isLoggedInChanged.emit()
    #     doc_list_vm.refresh()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
