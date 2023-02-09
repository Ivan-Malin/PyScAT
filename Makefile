COMPATH := compile_path
PROJECT_FILES := PROJECT_FILES
ICO := ICO.ico
PY64 := py -3.7
PY32 := py -3.11-32

install_packages:
	$(PY64) -m pip install -r $(PROJECT_FILES)/preferences.txt

compile:
	test -d $(COMPATH) || mkdir $(COMPATH)
	$(PY64) -m pip install pyinstaller==4.1
	$(PY64) -m PyInstaller --hidden-import subprocess --distpath $(COMPATH)/ -i $(PROJECT_FILES)/$(ICO) -F app.py --name=PyScAT64.exe
	cp PySync_default_settings.ini $(COMPATH)/PySync_default_settings.ini
	cp PySync_settings.ini $(COMPATH)/PySync_settings.ini
	test -d $(COMPATH)/logs || mkdir $(COMPATH)/logs
	


install_packages_x32:
	$(PY32) -m pip install -r $(PROJECT_FILES)/preferences32.txt

compile_x32:
	test -d $(COMPATH) || mkdir $(COMPATH)
	$(PY32) -m pip install pyinstaller
	$(PY32) -m PyInstaller --hidden-import subprocess --distpath $(COMPATH)/ -i $(PROJECT_FILES)/$(ICO) -F app.py --name=PyScAT32.exe
	cp PySync_default_settings.ini $(COMPATH)/PySync_default_settings.ini
	cp PySync_settings.ini $(COMPATH)/PySync_settings.ini
	test -d $(COMPATH)/logs || mkdir $(COMPATH)/logs