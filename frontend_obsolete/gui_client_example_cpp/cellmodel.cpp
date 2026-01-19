#include "cellmodel.h"

CellModel::CellModel(QObject *parent)
    : QAbstractListModel{parent}
{}

int CellModel::rowCount(const QModelIndex &parent) const {
    return (parent.isValid()) ? 0 : static_cast<int>(m_cells.size());
}

QVariant CellModel::data(const QModelIndex &index, int role) const {
    if (!checkIndex(index, CheckIndexOption::IndexIsValid) || !index.isValid()) return QVariant();

    const auto& c = m_cells.at(index.row());

    switch (role) {
        case AngleValueRole:        return c.angle;
        case HeightValueRole:       return c.height;
        default:                    return QVariant();
    }
}

Qt::ItemFlags CellModel::flags(const QModelIndex &index) const {
    return QAbstractListModel::flags(index) | Qt::ItemIsEditable;
}

QHash<int, QByteArray> CellModel::roleNames() const {
    QHash<int, QByteArray> mapping {
        {Roles::AngleValueRole, "angleValue"},
        {Roles::HeightValueRole, "heightValue"},
    };
    return mapping;
}
