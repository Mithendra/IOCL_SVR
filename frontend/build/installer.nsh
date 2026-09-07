; electron-builder NSIS hooks for SVR-IOCL Station.
; The installer runs elevated (build.nsis.perMachine = true), so these PowerShell
; steps have the admin rights they need to (de)register the two Windows Services.
;
;   first-run.ps1  - migrations, machine-wide config, service register + start,
;                    per-user Startup shortcut  (installer/first-run.ps1)
;   uninstall.ps1  - stop + delete the services, remove the shortcut; the data
;                    tree under C:\ProgramData\SVR-IOCL is deliberately kept.
;
; Both scripts are shipped to $INSTDIR\installer\ via build.extraFiles.

!macro customInstall
  DetailPrint "SVR-IOCL: running first-run setup (services, migrations, config)..."
  nsExec::ExecToLog 'powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$INSTDIR\installer\first-run.ps1" -InstallDir "$INSTDIR"'
  Pop $0
  DetailPrint "SVR-IOCL: first-run.ps1 exit code $0"
  ${If} $0 != 0
    MessageBox MB_ICONEXCLAMATION|MB_OK "SVR-IOCL post-install setup reported a problem (code $0).$\r$\nOpen services.msc to check SVR-IOCL-Backend / SVR-IOCL-Scheduler, or re-run installer\first-run.ps1 as Administrator."
  ${EndIf}
!macroend

!macro customUnInstall
  DetailPrint "SVR-IOCL: removing Windows Services..."
  nsExec::ExecToLog 'powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$INSTDIR\installer\uninstall.ps1" -InstallDir "$INSTDIR"'
  Pop $0
  DetailPrint "SVR-IOCL: uninstall.ps1 exit code $0"
  ${If} $0 == 3
    MessageBox MB_ICONEXCLAMATION|MB_OK "SVR-IOCL teardown did not fully complete (code 3).$\r$\nA Windows Service is likely 'marked for deletion' - reboot to finish removing it, or re-run installer\uninstall.ps1 as Administrator."
  ${EndIf}
!macroend
