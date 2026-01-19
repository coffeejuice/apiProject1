#ifndef CELLMODEL_H
#define CELLMODEL_H

#include <QAbstractListModel>
#include <QQmlEngine>

class CellModel : public QAbstractListModel
{
    Q_OBJECT
    QML_ELEMENT
    QML_UNCREATABLE("CellModel is declared in C++")

    struct Cell {
        QString angle;
        QString height;
    };
    QVector<Cell> m_cells;

public:
    enum Roles {
        AngleValueRole=Qt::UserRole+1,
        HeightValueRole
    };
    explicit CellModel(QObject *parent = nullptr);

    int rowCount(const QModelIndex &parent) const override;
    QVariant data(const QModelIndex &index, int role) const override;
    Qt::ItemFlags flags(const QModelIndex &index) const override;
    QHash<int, QByteArray> roleNames() const override;
};

#endif // CELLMODEL_H
