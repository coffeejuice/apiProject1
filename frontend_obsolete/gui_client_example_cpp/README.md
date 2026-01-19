# cardmix
Final project for OTUS Basic C++ training


Build, Execution, Deploytment -> CMake -> CMake options:

-DQT_MAINTENANCE_TOOL:FILEPATH=C:/Qt/MaintenanceTool.exe
-DCMAKE_GENERATOR:STRING=Ninja
-DCMAKE_C_COMPILER:FILEPATH="C:/Program
Files/Microsoft
Visual
Studio/2022/Community/VC/Tools/MSVC/14.44.35207/bin/HostX64/x64/cl.exe"
-DQT_QMAKE_EXECUTABLE:FILEPATH=C:/Qt/6.9.2/msvc2022_64/bin/qmake.exe
-DCMAKE_PREFIX_PATH:PATH=C:/Qt/6.9.2/msvc2022_64
-DCMAKE_PROJECT_INCLUDE_BEFORE:FILEPATH=C:\Users\alext\QtProjects\cardmix\build-qtcreator\msvc-debug/.qtc/package-manager/auto-setup.cmake
-DCMAKE_BUILD_TYPE:STRING=Debug
-DCMAKE_COLOR_DIAGNOSTICS:BOOL=ON
-DCMAKE_CXX_COMPILER:FILEPATH="C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Tools/MSVC/14.44.35207/bin/HostX64/x64/cl.exe"
-DCMAKE_CXX_FLAGS_INIT:STRING=-DQT_QML_DEBUG


Run/Debug configurations -> Environmental variables:

PATH=C:\Qt\6.9.2\msvc2022_64\bin