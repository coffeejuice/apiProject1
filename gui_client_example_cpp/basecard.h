#pragma once
#ifndef BASECARD_H
#define BASECARD_H

enum class EnumCardType {
    Image,
    Graphic,
    Process,
    Heat,
    Forming,
    Upset,
    Draw
};

class BaseCard {
    enum CardType m_type;
protected:
    void setCardType(const enum CardType type);
public:
    enum CardType cardType() const;
};

class Image : public BaseCard {
public:
    Image();

};

class Graphic : public BaseCard {
public:
    Graphic();

};

class Process : public BaseCard {
public:
    Process();

};

class Heat : public BaseCard {
public:
    Heat();

};

class Forming : public BaseCard {
public:
    Forming();

};

class Upset : public BaseCard {
public:
    Upset();

};

class Draw : public BaseCard {
public:
    Draw();

};

#endif // BASECARD_H
