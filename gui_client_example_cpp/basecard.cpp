#include "basecard.h"

void BaseCard::setCardType(const enum CardType type) { m_type = type; };

enum CardType BaseCard::cardType() const { return m_type; };

Image::Image() {
    setCardType(IMAGE);
}

Graphic::Graphic() {
    setCardType(EnumCardType::Graphic);
}

Process::Process() {
    setCardType(EnumCardType::Process);
}

Heat::Heat() {
    setCardType(EnumCardType::Heat);
}

Forming::Forming() {
    setCardType(EnumCardType::Forming);
}

Upset::Upset() {
    setCardType(EnumCardType::Upset);
}

Draw::Draw() {
    setCardType(EnumCardType::Draw);
}
