@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ============================================
echo   🚀 AgiBeauty APK Builder
echo ============================================
echo.

set SDK=D:\Android\Sdk
set BUILD_TOOLS=%SDK%\build-tools\35.0.0
set PLATFORM=%SDK%\platforms\android-35
set PROJECT=D:\AgiCode\beauty_camera
set OUTPUT=%PROJECT%\build

set AAPT2=%BUILD_TOOLS%\aapt2.exe
set D8=%BUILD_TOOLS%\d8.bat
set APKSIGNER=%BUILD_TOOLS%\apksigner.bat
set ZIPALIGN=%BUILD_TOOLS%\zipalign.exe
set ADB=%SDK%\platform-tools\adb.exe

set APP_NAME=AgiBeauty

echo [1/8] 清理构建目录...
if exist "%OUTPUT%" rmdir /s /q "%OUTPUT%"
mkdir "%OUTPUT%\obj"
mkdir "%OUTPUT%\apk"

echo [2/8] 编译资源 (aapt2 compile)...
cd /d "%PROJECT%"
%AAPT2% compile --dir "%PROJECT%\app\src\main\res" -o "%OUTPUT%\obj\res.zip"
if %ERRORLEVEL% neq 0 (
    echo [错误] 资源编译失败
    exit /b 1
)

echo [3/8] 链接资源生成 APK...
%AAPT2% link "%OUTPUT%\obj\res.zip" ^
    -I "%PLATFORM%\android.jar" ^
    --manifest "%PROJECT%\app\src\main\AndroidManifest.xml" ^
    --java "%OUTPUT%\gen" ^
    -o "%OUTPUT%\apk\%APP_NAME%.unaligned.apk" ^
    --auto-add-overlay
if %ERRORLEVEL% neq 0 (
    echo [错误] 资源链接失败
    exit /b 1
)

echo [4/8] 编译 Java 源码...
dir /s /b "%PROJECT%\app\src\main\java\*.java" > "%OUTPUT%\obj\sources.txt"
javac -d "%OUTPUT%\obj\classes" ^
    -classpath "%PLATFORM%\android.jar";"%OUTPUT%\gen";"%OUTPUT%\gen" ^
    -encoding UTF-8 ^
    -source 17 -target 17 ^
    @%OUTPUT%\obj\sources.txt
if %ERRORLEVEL% neq 0 (
    echo [错误] Java 编译失败
    exit /b 1
)

echo [5/8] 转换为 DEX (d8)...
dir /s /b "%OUTPUT%\obj\classes\*.class" > "%OUTPUT%\obj\classes.txt"
call %D8% --lib "%PLATFORM%\android.jar" ^
    --output "%OUTPUT%\obj" ^
    --min-api 26 ^
    @%OUTPUT%\obj\classes.txt
if %ERRORLEVEL% neq 0 (
    echo [错误] DEX 转换失败
    exit /b 1
)

echo [6/8] 添加 DEX 到 APK...
copy /y "%OUTPUT%\obj\classes.dex" "%OUTPUT%\apk\classes.dex"
cd /d "%OUTPUT%\apk"
powershell -Command "Add-Type -A 'System.IO.Compression.FileSystem'; $zip=[System.IO.Compression.ZipFile]::Open('%APP_NAME%.unaligned.apk','Update'); [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip,'classes.dex','classes.dex'); $zip.Dispose()"
if %ERRORLEVEL% neq 0 (
    echo [警告] 添加 DEX 失败
    copy /b %APP_NAME%.unaligned.apk + classes.dex %APP_NAME%.temp.apk
    move /y %APP_NAME%.temp.apk %APP_NAME%.unaligned.apk
)

echo [7/8] 对齐并签名...
if exist "%ZIPALIGN%" (
    %ZIPALIGN% -f -p 4 "%OUTPUT%\apk\%APP_NAME%.unaligned.apk" "%OUTPUT%\%APP_NAME%.unsigned.apk"
) else (
    copy /y "%OUTPUT%\apk\%APP_NAME%.unaligned.apk" "%OUTPUT%\%APP_NAME%.unsigned.apk"
)

if exist "%ZIPALIGN%" (
    %ZIPALIGN% -f -p 4 "%OUTPUT%\apk\%APP_NAME%.unaligned.apk" "%OUTPUT%\%APP_NAME%.unsigned.apk"
) else (
    copy /y "%OUTPUT%\apk\%APP_NAME%.unaligned.apk" "%OUTPUT%\%APP_NAME%.unsigned.apk"
)

if exist "%ZIPALIGN%" (
    %ZIPALIGN% -f -p 4 "%OUTPUT%\apk\%APP_NAME%.unaligned.apk" "%OUTPUT%\%APP_NAME%.unsigned.apk"
) else (
    copy /y "%OUTPUT%\apk\%APP_NAME%.unaligned.apk" "%OUTPUT%\%APP_NAME%.unsigned.apk"
)

if not exist "%USERPROFILE%\.android\debug.keystore" (
    keytool -genkey -v -keystore "%USERPROFILE%\.android\debug.keystore" ^
        -alias androiddebugkey -storepass android -keypass android ^
        -keyalg RSA -keysize 2048 -validity 10000 ^
        -dname "CN=Android Debug,O=Android,C=US" >nul 2>&1
)

%APKSIGNER% sign --ks "%USERPROFILE%\.android\debug.keystore" ^
    --ks-pass pass:android ^
    --ks-key-alias androiddebugkey ^
    --key-pass pass:android ^
    --out "%OUTPUT%\%APP_NAME%.apk" ^
    "%OUTPUT%\%APP_NAME%.unsigned.apk"
if %ERRORLEVEL% neq 0 (
    echo [错误] 签名失败
    exit /b 1
)

echo.
echo ============================================
echo   ✅ APK 构建成功！
echo   📁 %OUTPUT%\%APP_NAME%.apk
echo ============================================

%APKSIGNER% verify "%OUTPUT%\%APP_NAME%.apk" 2>&1
if %ERRORLEVEL% equ 0 (
    echo   ✅ APK 签名验证通过！
) else (
    echo   ⚠️ 签名验证失败
)

echo.
echo 正在安装到设备...
%ADB% install -r -t "%OUTPUT%\%APP_NAME%.apk" 2>&1
if %ERRORLEVEL% equ 0 (
    echo ✅ 安装成功！
    echo 启动应用...
    %ADB% shell am start -n com.agicode.beauty/.MainActivity
) else (
    echo ⚠️ 安装失败，请在手机上确认安装
    %ADB% install -r "%OUTPUT%\%APP_NAME%.apk"
)

endlocal
