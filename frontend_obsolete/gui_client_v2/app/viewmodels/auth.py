from PySide6.QtCore import QObject, Property, Signal, Slot
from app.api.client import ApiClient

class AuthViewModel(QObject):
    authStatusChanged = Signal()
    isLoggedInChanged = Signal()
    errorMessageChanged = Signal()
    usernameChanged = Signal()
    passwordChanged = Signal()

    def __init__(self, api_client: ApiClient):
        super().__init__()
        self._api = api_client
        self._username = "demo_user"
        self._password = "password123"
        self._is_logged_in = False
        self._error_message = ""

    @Property(str, notify=usernameChanged)
    def username(self):
        return self._username

    @username.setter
    def username(self, value):
        if self._username != value:
            self._username = value
            self.usernameChanged.emit()

    @Property(str, notify=passwordChanged)
    def password(self):
        return self._password

    @password.setter
    def password(self, value):
        if self._password != value:
            self._password = value
            self.passwordChanged.emit()

    @Property(bool, notify=isLoggedInChanged)
    def isLoggedIn(self):
        return self._is_logged_in

    @Property(str, notify=errorMessageChanged)
    def errorMessage(self):
        return self._error_message

    @Slot()
    def login(self):
        self._error_message = ""
        self.errorMessageChanged.emit()
        
        success = self._api.login(self._username, self._password)
        if success:
            self._is_logged_in = True
            self._error_message = ""
            self.isLoggedInChanged.emit()
            self.errorMessageChanged.emit()
            self.authStatusChanged.emit()
        else:
            self._is_logged_in = False
            self._error_message = "Invalid username or password"
            self.isLoggedInChanged.emit()
            self.errorMessageChanged.emit()

    @Slot()
    def logout(self):
        self._is_logged_in = False
        self._username = ""
        self._password = ""
        self.isLoggedInChanged.emit()
        self.usernameChanged.emit()
        self.passwordChanged.emit()
        self.authStatusChanged.emit()
