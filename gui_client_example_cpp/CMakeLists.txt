cmake_minimum_required(VERSION 3.16)

project(cardmix VERSION 0.1 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Qt6 REQUIRED COMPONENTS Quick)
find_package(Qt6 REQUIRED COMPONENTS Core)

qt_standard_project_setup(REQUIRES 6.8)

qt_add_executable(appcardmix
    main.cpp
)

qt_add_qml_module(appcardmix
    URI cardmix
    QML_FILES
        Main.qml
        CardView.qml
        Draw.qml
        Cell.qml
        EditText.qml
    SOURCES
        cardmodel.h
        cardmodel.cpp
        cellmodel.h
        cellmodel.cpp
        # basecard.h
        # basecard.cpp
    RESOURCES
        assets/image0.jpg
        assets/image1.jpg
        assets/image2.jpg
        assets/image3.jpg
        assets/image4.jpg
        assets/image5.jpg
        assets/image6.jpg
        assets/image7.jpg
        assets/image8.jpg
        assets/image9.jpg
        assets/document.svg
        assets/edit.svg
        assets/find_in_folder.svg
        assets/blocktype_unknown_yellow_inkspace.svg
        assets/fire.svg
        assets/red_danger.svg
        assets/check_list_bw.svg
        assets/plus.svg
        assets/dots.svg
        assets/rectangle_off.svg
        assets/rectangle_on.svg
        assets/square_off.svg
        assets/square_on.svg
        assets/octagon_off.svg
        assets/octagon_on.svg
        assets/polygon16_off.svg
        assets/polygon16_on.svg
        assets/round_off.svg
        assets/round_on.svg
        assets/square_chamfers_sharp_off.svg
        assets/square_chamfers_sharp_on.svg
        assets/square_chamfers_equal_off.svg
        assets/square_chamfers_equal_on.svg
        assets/square_chamfers_different_off.svg
        assets/square_chamfers_different_on.svg
        assets/feather.svg
        assets/pencil.svg
        assets/folder.svg
        assets/folder_search.svg
        assets/house.svg
)

# Qt for iOS sets MACOSX_BUNDLE_GUI_IDENTIFIER automatically since Qt 6.1.
# If you are developing for iOS or macOS you should consider setting an
# explicit, fixed bundle identifier manually though.
set_target_properties(appcardmix PROPERTIES
#    MACOSX_BUNDLE_GUI_IDENTIFIER com.example.appcardmix
    MACOSX_BUNDLE_BUNDLE_VERSION ${PROJECT_VERSION}
    MACOSX_BUNDLE_SHORT_VERSION_STRING ${PROJECT_VERSION_MAJOR}.${PROJECT_VERSION_MINOR}
    MACOSX_BUNDLE TRUE
    WIN32_EXECUTABLE TRUE
)

target_link_libraries(appcardmix
    PRIVATE Qt6::Quick
)
target_link_libraries(appcardmix PRIVATE Qt6::Core)

include(GNUInstallDirs)
install(TARGETS appcardmix
    BUNDLE DESTINATION .
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)
