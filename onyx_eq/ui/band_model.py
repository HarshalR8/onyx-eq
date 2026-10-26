"""List model of bands for QML. Row-level updates keep delegates (and in-progress drags) alive."""
from __future__ import annotations

from PySide6.QtCore import QAbstractListModel, QByteArray, QModelIndex, Qt

from ..core.models import Band


class BandModel(QAbstractListModel):
    TypeRole = Qt.UserRole + 1
    TypeNameRole = Qt.UserRole + 2
    FreqRole = Qt.UserRole + 3
    GainRole = Qt.UserRole + 4
    QRole = Qt.UserRole + 5
    EnabledRole = Qt.UserRole + 6
    HasGainRole = Qt.UserRole + 7

    _ROLES = {
        TypeRole: b"bandType",
        TypeNameRole: b"typeName",
        FreqRole: b"freq",
        GainRole: b"gain",
        QRole: b"q",
        EnabledRole: b"bandEnabled",
        HasGainRole: b"hasGain",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bands: list[Band] = []

    def roleNames(self):
        return {k: QByteArray(v) for k, v in self._ROLES.items()}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._bands)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._bands):
            return None
        b = self._bands[index.row()]
        if role == self.TypeRole:
            return b.type.value
        if role == self.TypeNameRole:
            return b.type.display_name
        if role == self.FreqRole:
            return b.freq
        if role == self.GainRole:
            return b.gain
        if role == self.QRole:
            return b.q
        if role == self.EnabledRole:
            return b.enabled
        if role == self.HasGainRole:
            return b.type.has_gain
        return None

    def sync(self, bands: tuple[Band, ...]) -> None:
        """Apply the smallest change that turns the model into `bands`."""
        old = self._bands
        new = list(bands)
        if len(new) == len(old):
            for i, (a, b) in enumerate(zip(old, new)):
                if a != b:
                    self._bands[i] = b
                    idx = self.index(i)
                    self.dataChanged.emit(idx, idx)
            return
        if len(new) == len(old) + 1 and new[:-1] == old:
            self.beginInsertRows(QModelIndex(), len(old), len(old))
            self._bands = new
            self.endInsertRows()
            return
        if len(new) == len(old) - 1:
            for i in range(len(old)):
                if old[:i] + old[i + 1:] == new:
                    self.beginRemoveRows(QModelIndex(), i, i)
                    self._bands = new
                    self.endRemoveRows()
                    return
        self.beginResetModel()
        self._bands = new
        self.endResetModel()
