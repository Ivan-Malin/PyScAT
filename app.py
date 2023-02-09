from subprocess import Popen, PIPE, CREATE_NEW_CONSOLE
import os
import PySimpleGUI as sg
import configparser
import threading
import tcpspy2
from DEBUG_HANDLER import Globals_info
import time
import sys

time.sleep(1)


def read_config(config_path='PySync_settings.ini'):
	config = configparser.ConfigParser()
	config.read(config_path)
	return config

def write_config(config_object, config_path='PySync_settings.ini'):
	with open(config_path, 'w') as configfile:
		config_object.write(configfile)


config = read_config()


# Запускаем окно
sg.theme('SystemDefaultForReal')   # Add a touch of color
# All the stuff inside your window.
# layout = [  [sg.Text('Параметры отладчика', key='-EXPAND-', pad=(200, 20))],
#             [sg.Text('Enter something on Row 2'), sg.InputText()],
#             [sg.Button('Ok'), sg.Button('Cancel')] ]
layout = [  [sg.Text('COM порт         ', size = (17,1)), sg.InputText(config['Serial']['COM'],			key=0)],
			[sg.Text('Baud rate        ', size = (17,1)), sg.InputText(config['Serial']['Baud_rate'],	key=1)],
			[sg.Text(' ', size = (17,1))],
			[sg.Text('Путь до atbackend', size = (17,1)), sg.InputText(config['atbackend']['path'],		key=2)],
			[sg.Text(' ', size = (17,1))],
			[sg.Text('Порт atmel studio', size = (17,1)), sg.InputText(config['TCP']['atmel_port'],		key=3)],
			[sg.Text('Порт atbackend   ', size = (17,1)), sg.InputText(config['TCP']['atbackend_port'],	key=4)],
			[sg.Text(' ', size = (17,1))],
			[sg.Button('Сохранить настройки'), sg.Button('Сбросить настройки')],
			[sg.Button('Запустить отладчик', key='-RUN-')] ]

window = sg.Window('PyScAT', layout=layout)	#PySynchAT

# Состояние кнопки -RUN- (запущен ли отладчик или нет)
RUNNING = False

# Обрабатываем события нажатия на кнопки
while True:
	event, values = window.read()		# Обновляется во время нажатися на кнопку

	if   event == sg.WIN_CLOSED or event == 'Cancel': # if user closes window or clicks cancel
		break

	elif event=='Сохранить настройки':
		config['Serial'] = {}
		config['Serial']['COM']			= values[0]
		config['Serial']['Baud_rate']	= values[1]
		config['atbackend'] = {}
		config['atbackend']['path']		= values[2]
		config['TCP'] = {}
		config['TCP']['atmel_port']		= values[3]
		config['TCP']['atbackend_port']	= values[4]
		write_config(config)

	elif event=='Сбросить настройки':
		config = read_config('PySync_default_settings.ini')
		window[0].update(config['Serial']['COM']		)
		window[1].update(config['Serial']['Baud_rate']	)
		window[2].update(config['atbackend']['path']	)
		window[3].update(config['TCP']['atmel_port']	)
		window[4].update(config['TCP']['atbackend_port'])

	elif (event=='-RUN-') and not RUNNING:
		print('starting debugger')
		RUNNING = True
		# Запускаем отладку
		#atbackend_process	= Popen([config['atbackend']['path'], f"/connection-port={config['TCP']['atbackend_port']}"], creationflags=CREATE_NEW_CONSOLE)
		#os.startfile('"{}" '.format(config['atbackend']['path'].replace('\\','/'))+f"/connection-port={config['TCP']['atbackend_port']}")
		#os.startfile('"{}" '.format(config['atbackend']['path'])+f"/connection-port={config['TCP']['atbackend_port']}")
		atbackend_process	= Popen([config['atbackend']['path'], f"/connection-port={config['TCP']['atbackend_port']}"])
		COM				= values[0]
		Baud_rate		= values[1]
		atbackend_path	= values[2]
		atmel_port		= values[3]
		atbackend_port	= values[4]
		#syncher_process		= Popen(['py', '-3.7', 'tcpspy2.py', f'--COM={COM} --Baud_rate={Baud_rate} --atbackend_path="{atbackend_path}" --atmel_port={atmel_port} --atbackend_port={atbackend_port}'], creationflags=CREATE_NEW_CONSOLE)
		#os.startfile(f'py -3.7 tcpspy2.py --COM={COM} --Baud_rate={Baud_rate} --atbackend_path="{atbackend_path}" --atmel_port={atmel_port} --atbackend_port={atbackend_port}')
		#syncher_process	= Popen(f'py -3.7 tcpspy2.py --COM={COM} --Baud_rate={Baud_rate} --atbackend_path="{atbackend_path}" --atmel_port={atmel_port} --atbackend_port={atbackend_port}')

		# Запускаем тред синхронизатора
		Globals_info.exit = False
		Globals_info.COM	  = COM
		Globals_info.BAUDRATE = Baud_rate
		Globals_info.atmel_port		= int(atmel_port)
		Globals_info.atbackend_port = int(atbackend_port)
		syncher_thread = threading.Thread(target=tcpspy2.main, daemon=False)
		syncher_thread.start()

		window['-RUN-'].update('Отключить отладчик')



	elif (event=='-RUN-') and RUNNING:
		RUNNING = False
		print('stoping debugger')
		# Завершаем отладку
		atbackend_process.kill()
		#syncher_process.kill()
		Globals_info.exit = True

		os.startfile('app.bat')
		sys.exit()

		window['-RUN-'].update('Запустить отладчик')



	print('You entered ', values[0])
	print(values)
	print(event)
	#print(layout[6][0].__dir__())


# process = Popen([args.atbackend_path, f'/connection-port={args.atbackend_port}'], creationflags=CREATE_NEW_CONSOLE)

window.close()