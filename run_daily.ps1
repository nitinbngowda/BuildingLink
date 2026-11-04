Set-Location $PSScriptRoot
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"========================================================" | Out-File -FilePath "booking.log" -Append
"[$timestamp] Starting BuildingLink Automated Booking" | Out-File -FilePath "booking.log" -Append
"========================================================" | Out-File -FilePath "booking.log" -Append
py buildinglink_bot.py *>> booking.log
"[$((Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))] Finished with code $LASTEXITCODE" | Out-File -FilePath "booking.log" -Append

