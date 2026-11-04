@echo off
cd /d "%~dp0"
echo ======================================================== >> booking.log
echo [%date% %time%] Starting BuildingLink Automated Booking >> booking.log
echo ======================================================== >> booking.log
py buildinglink_bot.py >> booking.log 2>&1
echo [%date% %time%] Process finished with exit code %errorlevel% >> booking.log

