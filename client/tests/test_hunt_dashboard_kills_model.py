import unittest
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from client.hunt.session import MobEncounter
from client.ui.pages.hunt_dashboard import RecentKillsModel

_app = QApplication.instance() or QApplication([])


def _enc(mob="Atrox", cost=10.0, loot=20.0, shots=5):
    return MobEncounter(
        id=f"e{id(object())}",
        session_id="s",
        mob_name=mob,
        mob_name_source="ocr",
        start_time=datetime(2026, 1, 1, 12, 0, 0),
        end_time=datetime(2026, 1, 1, 12, 0, 10),
        cost=cost,
        loot_total_ped=loot,
        shots_fired=shots,
    )


class TestRecentKillsModel(unittest.TestCase):

    def test_empty(self):
        m = RecentKillsModel()
        self.assertEqual(m.rowCount(), 0)
        self.assertEqual(m.columnCount(), len(RecentKillsModel.COLS))

    def test_rows_reverse_chronological(self):
        m = RecentKillsModel()
        encs = [_enc("A"), _enc("B"), _enc("C")]
        m.set_encounters(encs)
        self.assertEqual(m.rowCount(), 3)
        self.assertEqual(
            m.data(m.index(0, RecentKillsModel.COL_MOB), Qt.ItemDataRole.DisplayRole),
            "C",
        )
        self.assertEqual(
            m.data(m.index(2, RecentKillsModel.COL_MOB), Qt.ItemDataRole.DisplayRole),
            "A",
        )

    def test_multiplier_formatting(self):
        m = RecentKillsModel()
        m.set_encounters([_enc(cost=10, loot=30)])
        mult = m.data(m.index(0, RecentKillsModel.COL_MULT), Qt.ItemDataRole.DisplayRole)
        self.assertEqual(mult, "3.00x")

    def test_tick_emits_data_changed(self):
        m = RecentKillsModel()
        m.set_encounters([_enc(), _enc()])
        signals = []
        m.dataChanged.connect(lambda a, b, r: signals.append((a.row(), b.row())))
        m.tick_time_column()
        self.assertEqual(signals, [(0, 1)])


if __name__ == "__main__":
    unittest.main()
