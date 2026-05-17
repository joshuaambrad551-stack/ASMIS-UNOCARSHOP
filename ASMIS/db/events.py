"""
db/events.py
UnoCarshop ASMIS — Centralized Event Bus
Allows modules to emit and listen to data-change events
so all modules stay synchronized automatically.
"""
from PyQt5.QtCore import QObject, pyqtSignal


class EventBus(QObject):
    """
    Singleton event bus. Any module can emit a signal here
    and any other module listening will auto-refresh.
    """
    # Fired when any module's data changes
    customers_changed    = pyqtSignal()
    vehicles_changed     = pyqtSignal()
    employees_changed    = pyqtSignal()
    attendance_changed   = pyqtSignal()
    payroll_changed      = pyqtSignal()
    inventory_changed    = pyqtSignal()
    service_orders_changed = pyqtSignal()
    billing_changed      = pyqtSignal()
    insurance_changed    = pyqtSignal()
    dashboard_refresh    = pyqtSignal()   # broadcast to dashboard
    data_changed         = pyqtSignal(tuple)  # centralized broadcast of changed data areas

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # Call QObject __init__ only once
            QObject.__init__(cls._instance)
            cls._instance._wire_relays()
        return cls._instance

    def _wire_relays(self):
        self.customers_changed.connect(lambda: self.data_changed.emit(("customers",)))
        self.vehicles_changed.connect(lambda: self.data_changed.emit(("vehicles",)))
        self.employees_changed.connect(lambda: self.data_changed.emit(("employees",)))
        self.attendance_changed.connect(lambda: self.data_changed.emit(("attendance",)))
        self.payroll_changed.connect(lambda: self.data_changed.emit(("payroll",)))
        self.inventory_changed.connect(lambda: self.data_changed.emit(("inventory",)))
        self.service_orders_changed.connect(lambda: self.data_changed.emit(("service_orders",)))
        self.billing_changed.connect(lambda: self.data_changed.emit(("billing",)))
        self.insurance_changed.connect(lambda: self.data_changed.emit(("insurance",)))
        self.dashboard_refresh.connect(lambda: self.data_changed.emit(("dashboard",)))

    def publish(self, *areas):
        """
        Notify the whole application that one or more centralized data areas
        changed. Specific signals keep existing module listeners working, while
        data_changed lets cached pages refresh from the same database source.
        """
        signal_map = {
            "customers": self.customers_changed,
            "vehicles": self.vehicles_changed,
            "employees": self.employees_changed,
            "attendance": self.attendance_changed,
            "payroll": self.payroll_changed,
            "inventory": self.inventory_changed,
            "service_orders": self.service_orders_changed,
            "billing": self.billing_changed,
            "insurance": self.insurance_changed,
            "dashboard": self.dashboard_refresh,
        }
        normalized = tuple(dict.fromkeys(areas or ("dashboard",)))
        for area in normalized:
            signal = signal_map.get(area)
            if signal is not None:
                signal.emit()
        if "dashboard" not in normalized:
            self.dashboard_refresh.emit()


# Global singleton instance — import this everywhere
bus = EventBus()
