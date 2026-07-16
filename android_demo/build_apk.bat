@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ============================================
echo   🚀 AgiCode APK Builder
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
set ADB=%SDK%\platform-tools\adb.exe

set PKG=com.agicode.demo
set APP_NAME=AgiCodeDemo

echo [1/6] 清理构建目录...
if exist "%OUTPUT%" rmdir /s /q "%OUTPUT%"
mkdir "%OUTPUT%\dex"
mkdir "%OUTPUT%\apk"

echo [2/6] 编译资源 (aapt2 compile)...
cd /d "%PROJECT%"
%AAPT2% compile --dir "%PROJECT%\app\src\main\res" -o "%OUTPUT%\res.zip"
if %ERRORLEVEL% neq 0 (
    echo [错误] 资源编译失败
    exit /b 1
)

echo [3/6] 链接资源 (aapt2 link)...
%AAPT2% link "%OUTPUT%\res.zip" ^
    -I "%PLATFORM%\android.jar" ^
    --manifest "%PROJECT%\app\src\main\AndroidManifest.xml" ^
    -o "%OUTPUT%\apk\%APP_NAME%.unaligned.apk" ^
    --auto-add-overlay
if %ERRORLEVEL% neq 0 (
    echo [错误] 资源链接失败
    exit /b 1
)

echo [4/6] 编译 Java 源码...
dir /s /b "%PROJECT%\app\src\main\java\*.java" > "%OUTPUT%\sources.txt"
javac -d "%OUTPUT%\dex" ^
    -classpath "%PLATFORM%\android.jar" ^
    -encoding UTF-8 -source 17 -target 17 ^
    @%OUTPUT%\sources.txt
if %ERRORLEVEL% neq 0 (
    echo [错误] Java 编译失败
    exit /b 1
)

echo [5/6] 转换为 DEX (d8)...
cd /d "%OUTPUT%\dex"
dir /s /b *.class > "%OUTPUT%\classes.txt"
call %D8% --lib "%PLATFORM%\android.jar" ^
    --output "%OUTPUT%\dex" ^
    @%OUTPUT%\classes.txt
if %ERRORLEVEL% neq 0 (
    echo [错误] DEX 转换失败
    exit /b 1
)

echo [6/6] 打包并签名 APK...
cd /d "%OUTPUT%"
copy /y "%OUTPUT%\dex\classes.dex" "%OUTPUT%\apk\"
cd /d "%OUTPUT%\apk"

:: 生成调试密钥（如果不存在）
if not exist "%USERPROFILE%\.android\debug.keystore" (
    keytool -genkey -v -keystore "%USERPROFILE%\.android\debug.keystore" ^
        -alias androiddebugkey -storepass android -keypass android ^
        -keyalg RSA -keysize 2048 -validity 10000 ^
        -dname "CN=Android Debug,O=Android,C=US" >nul 2>&1
)

:: 使用 apksigner 签名
%APKSIGNER% sign --ks "%USERPROFILE%\.android\debug.keystore" ^
    --ks-pass pass:android ^
    --ks-key-alias androiddebugkey ^
    --key-pass pass:android ^
    --out "%OUTPUT%\%APP_NAME%.apk" ^
    "%OUTPUT%\apk\%APP_NAME%.unaligned.apk"
if %ERRORLEVEL% neq 0 (
    echo [错误] 签名失败
    exit /b 1
)

echo.
echo ============================================
echo   ✅ APK 构建成功！
echo   📁 %OUTPUT%\%APP_NAME%.apk
echo ============================================

:: 检查连接的设备
%ADB% devices 2>nul | findstr /v "List of devices attached" | findstr /v "daemon" | findstr /v "^$" >nul
if !ERRORLEVEL! equ 0 (
    echo.
    echo [可选] 检测到 Android 设备，是否安装？(Y/N)
    echo 按 Y 自动安装，按任意键跳过...
    choice /c YN /n /t 5 /d N >nul
    if !ERRORLEVEL! equ 1 (
        echo 正在安装到设备...
        %ADB% install -r "%OUTPUT%\%APP_NAME%.apk"
        if !ERRORLEVEL! equ 0 (
            echo ✅ 安装成功！请在手机上查看 AgiCode Demo
        ) else (
            echo [警告] 安装失败，请手动安装
        )
    )
)

endlocal
