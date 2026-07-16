@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ============================================
echo   🚀 AgiCode APK Builder v2
echo ============================================
echo.

set SDK=D:\Android\Sdk
set BUILD_TOOLS=%SDK%\build-tools\35.0.0
set PLATFORM=%SDK%\platforms\android-35
set PROJECT=D:\AgiCode\android_demo
set OUTPUT=%PROJECT%\build

set AAPT2=%BUILD_TOOLS%\aapt2.exe
set D8=%BUILD_TOOLS%\d8.bat
set APKSIGNER=%BUILD_TOOLS%\apksigner.bat
set ZIPALIGN=%BUILD_TOOLS%\zipalign.exe
set ADB=%SDK%\platform-tools\adb.exe

set APP_NAME=AgiCodeDemo

echo [1/6] 清理构建目录...
if exist "%OUTPUT%" rmdir /s /q "%OUTPUT%"
mkdir "%OUTPUT%\obj"
mkdir "%OUTPUT%\apk"

echo [2/6] 编译资源 (aapt2 compile)...
cd /d "%PROJECT%"
%AAPT2% compile --dir "%PROJECT%\app\src\main\res" -o "%OUTPUT%\obj\res.zip"
if %ERRORLEVEL% neq 0 (
    echo [错误] 资源编译失败
    exit /b 1
)

echo [3/6] 链接资源生成 APK...
%AAPT2% link "%OUTPUT%\obj\res.zip" ^
    -I "%PLATFORM%\android.jar" ^
    --manifest "%PROJECT%\app\src\main\AndroidManifest.xml" ^
    -o "%OUTPUT%\apk\%APP_NAME%.unaligned.apk" ^
    --auto-add-overlay
if %ERRORLEVEL% neq 0 (
    echo [错误] 资源链接失败
    exit /b 1
)

echo [4/6] 编译 Java 源码并转 DEX...
dir /s /b "%PROJECT%\app\src\main\java\*.java" > "%OUTPUT%\obj\sources.txt"
javac -d "%OUTPUT%\obj\classes" ^
    -classpath "%PLATFORM%\android.jar" ^
    -encoding UTF-8 ^
    -source 17 -target 17 ^
    @%OUTPUT%\obj\sources.txt
if %ERRORLEVEL% neq 0 (
    echo [错误] Java 编译失败
    exit /b 1
)

dir /s /b "%OUTPUT%\obj\classes\*.class" > "%OUTPUT%\obj\classes.txt"
call %D8% --lib "%PLATFORM%\android.jar" ^
    --output "%OUTPUT%\obj" ^
    --min-api 26 ^
    @%OUTPUT%\obj\classes.txt
if %ERRORLEVEL% neq 0 (
    echo [错误] DEX 转换失败
    exit /b 1
)

echo [5/6] 添加 DEX 到 APK...
cd /d "%OUTPUT%\apk"
if not exist "classes.dex" (
    copy /y "%OUTPUT%\obj\classes.dex" "%OUTPUT%\apk\classes.dex"
)
:: 使用 zip 添加 classes.dex 到 APK
cd /d "%OUTPUT%\apk"
powershell -Command "Add-Type -A 'System.IO.Compression.FileSystem'; $zip=[System.IO.Compression.ZipFile]::Open('AgiCodeDemo.unaligned.apk','Update'); [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip,'classes.dex','classes.dex'); $zip.Dispose()"
if %ERRORLEVEL% neq 0 (
    echo [警告] PowerShell zip 添加失败，尝试备用方法...
    copy /b AgiCodeDemo.unaligned.apk + classes.dex AgiCodeDemo.temp.apk
    move /y AgiCodeDemo.temp.apk AgiCodeDemo.unaligned.apk
)

echo [6/6] 对齐并签名...
:: zipalign
if exist "%ZIPALIGN%" (
    %ZIPALIGN% -f -p 4 "%OUTPUT%\apk\%APP_NAME%.unaligned.apk" "%OUTPUT%\%APP_NAME%.unsigned.apk"
) else (
    copy /y "%OUTPUT%\apk\%APP_NAME%.unaligned.apk" "%OUTPUT%\%APP_NAME%.unsigned.apk"
)

:: 生成调试密钥（如果不存在）
if not exist "%USERPROFILE%\.android\debug.keystore" (
    keytool -genkey -v -keystore "%USERPROFILE%\.android\debug.keystore" ^
        -alias androiddebugkey -storepass android -keypass android ^
        -keyalg RSA -keysize 2048 -validity 10000 ^
        -dname "CN=Android Debug,O=Android,C=US" >nul 2>&1
)

:: 签名
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

:: 验证 APK
%APKSIGNER% verify "%OUTPUT%\%APP_NAME%.apk" 2>&1
if %ERRORLEVEL% equ 0 (
    echo   ✅ APK 签名验证通过！
) else (
    echo   ⚠️ 签名验证失败
)

:: 安装到设备
echo.
echo 正在安装到设备...
%ADB% install -r -t "%OUTPUT%\%APP_NAME%.apk" 2>&1
if %ERRORLEVEL% equ 0 (
    echo ✅ 安装成功！
    echo 启动应用...
    %ADB% shell am start -n com.agicode.demo/.MainActivity
) else (
    echo ⚠️ 安装失败，请在手机上确认安装
    echo 尝试再次安装...
    %ADB% install -r "%OUTPUT%\%APP_NAME%.apk"
)

endlocal
