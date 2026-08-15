@echo off
echo ============================================
echo  WITNESS v2 - one-time setup
echo ============================================
pip install "opencv-python<5" Pillow mss pywin32 psutil anthropic pyttsx3 SpeechRecognition sounddevice numpy edge-tts
if %errorlevel% neq 0 (
    echo.
    echo Something failed above. If it mentions opencv, that's OK -
    echo the app runs without the camera library.
)
echo.
echo Installing optional drag-and-drop support for the video calendar...
pip install tkinterdnd2
if %errorlevel% neq 0 (
    echo.
    echo tkinterdnd2 failed to install - that's OK too. The video
    echo calendar still works fully, just via the "Add Video..." button
    echo instead of drag-and-drop.
)
echo.
echo Installing the PySide6 visual interface...
pip install PySide6
if %errorlevel% neq 0 (
    echo.
    echo PySide6 failed to install. The original Tkinter app still works
    echo through start_witness.bat, but start_witness_qt.bat needs PySide6.
)
echo.
echo.
echo Installing optional Stripe revenue sync support...
pip install stripe
if %errorlevel% neq 0 (
    echo.
    echo stripe failed to install - that's OK too, revenue tracking
    echo just falls back to notes-based extraction until it's installed.
)
echo.
echo Done. Double-click start_witness.bat to run WITNESS.
pause
