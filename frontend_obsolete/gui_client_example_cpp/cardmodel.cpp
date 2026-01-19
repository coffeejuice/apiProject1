#include "cardmodel.h"

CardModel::CardModel() {}

int CardModel::rowCount(const QModelIndex &parent) const {
    return (parent.isValid()) ? 0 : static_cast<int>(m_cards.size());
}

QVariant CardModel::data(const QModelIndex &index, int role) const {
    if (!checkIndex(index, CheckIndexOption::IndexIsValid) || !index.isValid()) return QVariant();

    const auto& c = m_cards.at(index.row());
    switch (role) {
        case CardTypeRole:      return c.cardType();
        case CellModelRole:     return QVariant::fromValue(static_cast<QObject*>( c.cellModel() ));
        default:                return QVariant();
    }
}

bool CardModel::setData(const QModelIndex &index, const QVariant &value, int role) {
    return true;
}

Qt::ItemFlags CardModel::flags(const QModelIndex &index) const {
    return QAbstractListModel::flags(index) | Qt::ItemIsEditable;
}

QHash<int, QByteArray> CardModel::roleNames() const {
    QHash<int, QByteArray> mapping {
        {Roles::CardTypeRole,   "cardType"},
        {Roles::CellModelRole,  "cellModel"},
    };
    return mapping;
}

// ====================================================================

void CardModel::BaseCard::setCardType(const enum CardType type) { m_type = type; }

void CardModel::BaseCard::setCellModel(CellModel* m) { m_cell_model = m; }

CellModel* CardModel::BaseCard::cellModel() const { return m_cell_model; }

enum CardModel::CardType CardModel::BaseCard::cardType() const { return m_type; }



CardModel::Image::Image() {
    setCardType(IMAGE);
}

CardModel::Graphic::Graphic() {
    setCardType(GRAPHIC);
}

CardModel::Document::Document() {
    setCardType(DOCUMENT);
}

CardModel::Heat::Heat() {
    setCardType(HEAT);
}

CardModel::Block::Block() {
    setCardType(BLOCK);
}

CardModel::Upset::Upset() {
    setCardType(UPSET);
}

CardModel::Draw::Draw() {
    setCardType(DRAW);
}
