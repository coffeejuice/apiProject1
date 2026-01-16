#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include "cardmodel.h"

int main(int argc, char *argv[])
{
    QGuiApplication app(argc, argv);

    qputenv("QT_QUICK_CONTROLS_STYLE", QByteArray("Windows"));  // 👇 Set Windows style globally

    QQmlApplicationEngine engine;
    QObject::connect(
        &engine,
        &QQmlApplicationEngine::objectCreationFailed,
        &app,
        []() { QCoreApplication::exit(-1); },
        Qt::QueuedConnection);

    CardModel m;
    engine.setInitialProperties({
        {"cardModel", QVariant::fromValue(&m)}
    });

    engine.loadFromModule("cardmix", "Main");

    return app.exec();
}
