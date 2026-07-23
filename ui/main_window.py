import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QToolBar, QPushButton, QComboBox, QSpinBox, QLineEdit,
    QStatusBar, QMenuBar, QMenu, QMessageBox, QInputDialog,
    QApplication, QSizePolicy, QFrame, QTabWidget, QDialog, QDialogButtonBox,
)
from PySide6.QtCore import Qt, Slot, QSettings
from PySide6.QtGui import QAction, QKeySequence, QFont

from modbus.client import ModbusClient
from modbus.models import (
    ConnectionSettings, PollSettings, ConnectionType, Parity, ModbusFunction,
)
from utils.session import SessionManager
from utils.profiles import ProfileManager
from ui.register_view import RegisterView
from ui.packet_monitor import PacketMonitor
from ui.calculator_panel import CalculatorPanel
from ui.converter_panel import ConverterPanel
from ui.bit_tool_panel import BitToolPanel
from ui.plc_testing_panel import PLCTestingPanel
from ui.logging_panel import LoggingPanel
from ui.utility_panel import UtilityPanel


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PLC Test Utility")
        self.setMinimumSize(900, 580)
        self.resize(1100, 700)

        self._client = ModbusClient()
        self._session_mgr = SessionManager()
        self._profile_mgr = ProfileManager()
        self._dark_mode = False
        self._is_connected = False

        self._build_menu_bar()
        self._build_connection_toolbar()
        self._build_poll_toolbar()
        self._build_central_splitter()
        self._build_status_bar()
        self._connect_signals()
        self._apply_theme()
        self._restore_layout()

    def _build_menu_bar(self) -> None:
        mb = self.menuBar()
        mb.setNativeMenuBar(False)

        file_menu = mb.addMenu("&File")
        save_session_act = QAction("Save Session", self, shortcut=QKeySequence.Save)
        save_session_act.triggered.connect(self._save_session)
        file_menu.addAction(save_session_act)
        load_session_act = QAction("Load Session", self, shortcut=QKeySequence.Open)
        load_session_act.triggered.connect(self._load_session)
        file_menu.addAction(load_session_act)
        file_menu.addSeparator()
        exit_act = QAction("Exit", self, shortcut=QKeySequence.Quit)
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

        conn_menu = mb.addMenu("&Connection")
        conn_menu.addAction(QAction("Save Profile...", self, triggered=self._save_profile))
        conn_menu.addAction(QAction("Load Profile...", self, triggered=self._load_profile))

        tools_menu = mb.addMenu("&Tools")
        tools_menu.addAction(QAction("Calculator", self, triggered=lambda: self._show_tool_dialog("calc")))
        tools_menu.addAction(QAction("Converter", self, triggered=lambda: self._show_tool_dialog("conv")))
        tools_menu.addAction(QAction("Bit Tool", self, triggered=lambda: self._show_tool_dialog("bit")))
        tools_menu.addAction(QAction("PLC Test / Write", self, triggered=lambda: self._show_tool_dialog("plc")))
        tools_menu.addAction(QAction("Logging", self, triggered=lambda: self._show_tool_dialog("log")))
        tools_menu.addAction(QAction("Utilities", self, triggered=lambda: self._show_tool_dialog("util")))
        tools_menu.addSeparator()
        tools_menu.addAction(QAction("Toggle Theme", self, shortcut="Ctrl+T", triggered=self._toggle_theme))

        help_menu = mb.addMenu("&Help")
        help_menu.addAction(QAction("About", self, triggered=self._show_about))

    def _build_connection_toolbar(self) -> None:
        tb = QToolBar("Connection")
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.setObjectName("ConnectionToolbar")
        self.addToolBar(tb)

        self._connect_btn = QPushButton("Connect")
        self._connect_btn.setObjectName("btn_connect")
        self._connect_btn.setFixedHeight(24)
        self._connect_btn.clicked.connect(self._on_connect)
        tb.addWidget(self._connect_btn)

        self._disconnect_btn = QPushButton("Disconnect")
        self._disconnect_btn.setObjectName("btn_disconnect")
        self._disconnect_btn.setFixedHeight(24)
        self._disconnect_btn.setEnabled(False)
        self._disconnect_btn.clicked.connect(self._on_disconnect)
        tb.addWidget(self._disconnect_btn)

        tb.addSeparator()

        tb.addWidget(QLabel(" Type:"))
        self._type_combo = QComboBox()
        self._type_combo.addItems(["TCP", "RTU", "ASCII"])
        self._type_combo.setFixedWidth(60)
        self._type_combo.setFixedHeight(24)
        self._type_combo.currentTextChanged.connect(self._on_type_changed)
        tb.addWidget(self._type_combo)

        self._host_label = QLabel("  Host:")
        tb.addWidget(self._host_label)
        self._host_input = QLineEdit("127.0.0.1")
        self._host_input.setFixedWidth(110)
        self._host_input.setFixedHeight(24)
        tb.addWidget(self._host_input)

        self._port_label = QLabel(" Port:")
        tb.addWidget(self._port_label)
        self._port_spin = QSpinBox()
        self._port_spin.setRange(1, 65535)
        self._port_spin.setValue(502)
        self._port_spin.setFixedWidth(60)
        self._port_spin.setFixedHeight(24)
        tb.addWidget(self._port_spin)

        self._com_label = QLabel("  COM:")
        self._com_label.setVisible(False)
        tb.addWidget(self._com_label)

        self._com_combo = QComboBox()
        self._com_combo.setFixedWidth(100)
        self._com_combo.setFixedHeight(24)
        self._com_combo.setVisible(False)
        self._scan_serial_ports()
        tb.addWidget(self._com_combo)

        self._baud_label = QLabel(" Baud:")
        self._baud_label.setVisible(False)
        tb.addWidget(self._baud_label)
        self._baud_combo = QComboBox()
        self._baud_combo.addItems(["9600", "19200", "38400", "57600", "115200"])
        self._baud_combo.setCurrentText("9600")
        self._baud_combo.setFixedWidth(75)
        self._baud_combo.setFixedHeight(24)
        self._baud_combo.setVisible(False)
        tb.addWidget(self._baud_combo)

        self._parity_label = QLabel(" Parity:")
        self._parity_label.setVisible(False)
        tb.addWidget(self._parity_label)
        self._parity_combo = QComboBox()
        self._parity_combo.addItems(["None", "Even", "Odd"])
        self._parity_combo.setFixedWidth(60)
        self._parity_combo.setFixedHeight(24)
        self._parity_combo.setVisible(False)
        tb.addWidget(self._parity_combo)

        tb.addSeparator()

        tb.addWidget(QLabel(" Slave:"))
        self._slave_spin = QSpinBox()
        self._slave_spin.setRange(1, 247)
        self._slave_spin.setValue(1)
        self._slave_spin.setFixedWidth(48)
        self._slave_spin.setFixedHeight(24)
        tb.addWidget(self._slave_spin)

        tb.addSeparator()

        tb.addWidget(QLabel(" Timeout:"))
        self._timeout_spin = QSpinBox()
        self._timeout_spin.setRange(1, 60)
        self._timeout_spin.setValue(3)
        self._timeout_spin.setSuffix("s")
        self._timeout_spin.setFixedWidth(52)
        self._timeout_spin.setFixedHeight(24)
        tb.addWidget(self._timeout_spin)

    def _build_poll_toolbar(self) -> None:
        tb = QToolBar("Poll")
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.setObjectName("PollToolbar")
        self.addToolBar(tb)

        self._poll_btn = QPushButton("Start Poll")
        self._poll_btn.setObjectName("btn_poll")
        self._poll_btn.setFixedHeight(24)
        self._poll_btn.setEnabled(False)
        self._poll_btn.clicked.connect(self._on_start_poll)
        tb.addWidget(self._poll_btn)

        self._read_once_btn = QPushButton("Read Once")
        self._read_once_btn.setFixedHeight(24)
        self._read_once_btn.setEnabled(False)
        self._read_once_btn.clicked.connect(self._on_read_once)
        tb.addWidget(self._read_once_btn)

        self._stop_poll_btn = QPushButton("Stop")
        self._stop_poll_btn.setObjectName("btn_stop")
        self._stop_poll_btn.setFixedHeight(24)
        self._stop_poll_btn.setEnabled(False)
        self._stop_poll_btn.clicked.connect(self._on_stop_poll)
        tb.addWidget(self._stop_poll_btn)

        tb.addSeparator()

        tb.addWidget(QLabel(" FC:"))
        self._fc_combo = QComboBox()
        for fc in ModbusFunction:
            self._fc_combo.addItem(f"FC{fc.value:02d} {fc.name.replace('_', ' ').title()}", fc.value)
        self._fc_combo.setFixedWidth(200)
        self._fc_combo.setFixedHeight(24)
        tb.addWidget(self._fc_combo)

        tb.addWidget(QLabel(" Addr:"))
        self._addr_spin = QSpinBox()
        self._addr_spin.setRange(0, 65535)
        self._addr_spin.setFixedWidth(70)
        self._addr_spin.setFixedHeight(24)
        tb.addWidget(self._addr_spin)

        tb.addWidget(QLabel(" Qty:"))
        self._qty_spin = QSpinBox()
        self._qty_spin.setRange(1, 125)
        self._qty_spin.setValue(10)
        self._qty_spin.setFixedWidth(55)
        self._qty_spin.setFixedHeight(24)
        tb.addWidget(self._qty_spin)

        tb.addWidget(QLabel(" Interval:"))
        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(10, 60000)
        self._interval_spin.setValue(1000)
        self._interval_spin.setSuffix("ms")
        self._interval_spin.setFixedWidth(80)
        self._interval_spin.setFixedHeight(24)
        tb.addWidget(self._interval_spin)

        tb.addSeparator()
        tb.addWidget(QLabel(" Filter:"))
        self._filter_input = QLineEdit()
        self._filter_input.setPlaceholderText("address or value...")
        self._filter_input.setFixedWidth(140)
        self._filter_input.setFixedHeight(24)
        self._filter_input.textChanged.connect(
            lambda t: self._register_view.set_search(t) if hasattr(self, '_register_view') else None
        )
        tb.addWidget(self._filter_input)

    def _build_central_splitter(self) -> None:
        self._register_view = RegisterView()
        self._packet_monitor = PacketMonitor()

        self._splitter = QSplitter(Qt.Vertical)
        self._splitter.setHandleWidth(5)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.addWidget(self._register_view)
        self._splitter.addWidget(self._packet_monitor)
        self._splitter.setSizes([420, 160])
        self._splitter.setObjectName("MainSplitter")

        self.setCentralWidget(self._splitter)

    def _build_status_bar(self) -> None:
        sb = self.statusBar()
        sb.setObjectName("MainStatusBar")

        self._status_dot = QLabel("⬤")
        self._status_dot.setObjectName("status_dot")
        self._status_dot.setStyleSheet("color: #aaa;")
        sb.addWidget(self._status_dot)

        self._status_label = QLabel("Disconnected")
        self._status_label.setObjectName("status_label")
        sb.addWidget(self._status_label, 1)

        self._stats_label = QLabel("TX: 0  RX: 0  Err: 0")
        self._stats_label.setObjectName("stats_label")
        sb.addPermanentWidget(self._stats_label)

        self._rtt_label = QLabel("RTT: --")
        self._rtt_label.setObjectName("rtt_label")
        sb.addPermanentWidget(self._rtt_label)

    def _connect_signals(self) -> None:
        worker = self._client.worker
        worker.connection_changed.connect(self._on_connection_changed)
        worker.data_received.connect(self._register_view.update_data)
        worker.packet_logged.connect(self._packet_monitor.add_packet)
        worker.error_occurred.connect(self._on_error)
        worker.stats_updated.connect(self._on_stats_updated)

    def _get_connection_settings(self) -> ConnectionSettings:
        s = ConnectionSettings()
        s.connection_type = ConnectionType(self._type_combo.currentText())
        s.host = self._host_input.text()
        s.port = self._port_spin.value()
        s.com_port = self._com_combo.currentData() or self._com_combo.currentText()
        s.baud_rate = int(self._baud_combo.currentText())
        s.parity = {"None": Parity.NONE, "Even": Parity.EVEN, "Odd": Parity.ODD}[self._parity_combo.currentText()]
        s.stop_bits = 1
        s.data_bits = 8
        s.timeout = self._timeout_spin.value()
        s.slave_id = self._slave_spin.value()
        s.auto_reconnect = False
        s.retry_count = 3
        return s

    def _get_poll_settings(self) -> PollSettings:
        s = PollSettings()
        s.function_code = ModbusFunction(self._fc_combo.currentData())
        s.start_address = self._addr_spin.value()
        s.quantity = self._qty_spin.value()
        s.poll_interval_ms = self._interval_spin.value()
        s.continuous = True
        return s

    def _scan_serial_ports(self) -> None:
        import serial.tools.list_ports
        self._com_combo.clear()
        ports = list(serial.tools.list_ports.comports())
        if ports:
            for p in ports:
                self._com_combo.addItem(f"{p.device} - {p.description[:30]}", p.device)
        else:
            self._com_combo.addItem("No ports found", "")

    def _on_type_changed(self, text: str) -> None:
        serial = text in ("RTU", "ASCII")
        tcp = text == "TCP"
        for w in (self._host_label, self._host_input, self._port_label, self._port_spin):
            w.setVisible(tcp)
        for w in (self._com_label, self._com_combo, self._baud_label,
                   self._baud_combo, self._parity_label, self._parity_combo):
            w.setVisible(serial)

    def _show_tool_dialog(self, which: str) -> None:
        panels = {
            "calc": ("Calculator", CalculatorPanel),
            "conv": ("Converter", ConverterPanel),
            "bit": ("Bit Tool", BitToolPanel),
            "plc": ("PLC Test", PLCTestingPanel),
            "log": ("Logging", LoggingPanel),
            "util": ("Utilities", UtilityPanel),
        }
        title, PanelClass = panels[which]
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setMinimumSize(400, 500)
        layout = QVBoxLayout(dlg)
        panel = PanelClass()
        layout.addWidget(panel)
        if which == "plc":
            panel.write_register_requested.connect(self._on_write_register)
            panel.write_coil_requested.connect(self._on_write_coil)
        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)
        dlg.exec()

    def _apply_theme(self) -> None:
        theme_file = "dark.qss" if self._dark_mode else "light.qss"
        style_path = os.path.join(os.path.dirname(__file__), "..", "assets", theme_file)
        if os.path.exists(style_path):
            with open(style_path, encoding="utf-8") as f:
                qApp = QApplication.instance()
                if qApp:
                    qApp.setStyleSheet(f.read())

    @Slot()
    def _toggle_theme(self) -> None:
        self._dark_mode = not self._dark_mode
        self._apply_theme()

    def _restore_layout(self) -> None:
        s = QSettings("PLCTestUtility", "MainWindow")
        geo = s.value("geometry")
        state = s.value("splitterState")
        if geo:
            self.restoreGeometry(geo)
        if state:
            self._splitter.restoreState(state)

    def closeEvent(self, event) -> None:
        s = QSettings("PLCTestUtility", "MainWindow")
        s.setValue("geometry", self.saveGeometry())
        s.setValue("splitterState", self._splitter.saveState())
        self._client.cleanup()
        super().closeEvent(event)

    @Slot()
    def _on_connect(self) -> None:
        self._client.connect(self._get_connection_settings())

    @Slot()
    def _on_disconnect(self) -> None:
        self._client.disconnect()
        self._on_connection_changed(False, "Disconnected")

    @Slot()
    def _on_start_poll(self) -> None:
        self._client.start_polling(self._get_poll_settings())
        self._poll_btn.setEnabled(False)
        self._stop_poll_btn.setEnabled(True)
        self._read_once_btn.setEnabled(False)

    @Slot()
    def _on_read_once(self) -> None:
        poll = self._get_poll_settings()
        self._client.worker._poll_settings = poll
        registers = self._client.read_once()
        if registers:
            self._register_view.update_data(registers)

    @Slot()
    def _on_stop_poll(self) -> None:
        self._client.stop_polling()
        self._poll_btn.setEnabled(True)
        self._stop_poll_btn.setEnabled(False)
        self._read_once_btn.setEnabled(True)

    @Slot(bool, str)
    def _on_connection_changed(self, connected: bool, msg: str) -> None:
        self._is_connected = connected
        if connected:
            self._status_dot.setStyleSheet("color: #4CAF50;")
            self._status_label.setText(f"Connected - {msg}")
            self._connect_btn.setEnabled(False)
            self._disconnect_btn.setEnabled(True)
            self._poll_btn.setEnabled(True)
            self._read_once_btn.setEnabled(True)
        else:
            self._status_dot.setStyleSheet("color: #e53935;")
            self._status_label.setText(f"Disconnected - {msg}")
            self._connect_btn.setEnabled(True)
            self._disconnect_btn.setEnabled(False)
            self._poll_btn.setEnabled(False)
            self._read_once_btn.setEnabled(False)
            self._stop_poll_btn.setEnabled(False)

    @Slot(str)
    def _on_error(self, msg: str) -> None:
        self._packet_monitor.log_error(msg)

    @Slot(object)
    def _on_stats_updated(self, stats) -> None:
        self._stats_label.setText(
            f"TX: {stats.packets_sent}  RX: {stats.packets_received}  Err: {stats.errors}"
        )
        if hasattr(stats, 'latency_ms') and stats.latency_ms > 0:
            self._rtt_label.setText(f"RTT: {stats.latency_ms:.1f}ms")

    @Slot(int, int)
    def _on_write_register(self, address: int, value: int) -> None:
        s = self._get_connection_settings()
        self._client.write_register(address, value, s.slave_id)

    @Slot(int, bool)
    def _on_write_coil(self, address: int, value: bool) -> None:
        s = self._get_connection_settings()
        self._client.write_coil(address, value, s.slave_id)

    @Slot()
    def _save_session(self) -> None:
        name, ok = QInputDialog.getText(self, "Save Session", "Session name:")
        if ok and name:
            self._session_mgr.save(name, self._get_connection_settings(), self._get_poll_settings())
            self._status_label.setText(f"Session '{name}' saved")

    @Slot()
    def _load_session(self) -> None:
        sessions = self._session_mgr.list_sessions()
        if not sessions:
            QMessageBox.information(self, "Load Session", "No saved sessions found.")
            return
        name, ok = QInputDialog.getItem(self, "Load Session", "Select:", sessions, 0, False)
        if ok and name:
            try:
                conn, poll = self._session_mgr.load(name)
                self._apply_connection_settings(conn)
                self._apply_poll_settings(poll)
                self._status_label.setText(f"Session '{name}' loaded")
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    def _apply_connection_settings(self, s: ConnectionSettings) -> None:
        self._type_combo.setCurrentText(s.connection_type.value)
        self._host_input.setText(s.host)
        self._port_spin.setValue(s.port)
        self._slave_spin.setValue(s.slave_id)
        self._timeout_spin.setValue(s.timeout)

    def _apply_poll_settings(self, s: PollSettings) -> None:
        idx = self._fc_combo.findData(s.function_code.value)
        if idx >= 0:
            self._fc_combo.setCurrentIndex(idx)
        self._addr_spin.setValue(s.start_address)
        self._qty_spin.setValue(s.quantity)
        self._interval_spin.setValue(s.poll_interval_ms)

    def _save_profile(self) -> None:
        name, ok = QInputDialog.getText(self, "Save Profile", "Profile name:")
        if ok and name:
            self._profile_mgr.save(name, self._get_connection_settings(), self._get_poll_settings())

    def _load_profile(self) -> None:
        profiles = self._profile_mgr.list_profiles()
        if not profiles:
            QMessageBox.information(self, "Load Profile", "No profiles found.")
            return
        name, ok = QInputDialog.getItem(self, "Load Profile", "Select:", profiles, 0, False)
        if ok and name:
            conn, poll = self._profile_mgr.load(name)
            self._apply_connection_settings(conn)
            self._apply_poll_settings(poll)

    def _show_about(self) -> None:
        QMessageBox.about(
            self, "About PLC Test Utility",
            "PLC Test Utility v1.0.0\n\nBuilt with Python + PySide6 + pymodbus"
        )
