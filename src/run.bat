@REM echo off
echo %1
IF "%1" == "self" GOTO SELF
IF "%1" == "compn" GOTO COMPN
GOTO End1

:SELF
python -m trigger_designer.main "C:\Projects\TriggerEditor\savedfiles\0. All Node- Test.tds"
GOTO :EOF

:COMPN
python -m trigger_designer.main "C:\Users\KASHVINCHANDRASAN\Desktop\Personal\Github\TriggerEditor\savedfiles\0. All Node- Test.tds"
GOTO :EOF

:End1
python -m trigger_designer.main 
GOTO :EOF