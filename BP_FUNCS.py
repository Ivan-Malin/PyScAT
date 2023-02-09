
# Файл с функциями для обработки точек останова
#
# breakpoints - 
# Лист с элементами формата 
# {
#	"ID":"3724_bp_00000017",
#	"Enabled":true,		- активна ли (стоит ли на ней останавливаться)
#	"AccessMode":4,
#	"File":"C:\\Users\\Owner\\Desktop\\AssemblerApplication1\\AssemblerApplication1\\main.asm",		- файл, на который поставили точку останова
#	"Line":26,			- строка в файле на которую поставили точку останова
#	"Column":0,			- её столбец, на которую ...
#	"Address":"18",		- !!! адрес PC, на который поставили точку останова (высчитывается atbackend и получается только с помощью getProperties)
#	"HitCount":0		- количество попаданий на точку останова
# }
#
# Замечания
# - предполагается что ID точек останова - первичный ключ
# - предполагается, что поле Address - уникально дял каждой точки останова (в противном случае, во всех функциях производим манипуляции с первой по порядку подходящей ячейкой с таким адресом)
# - все операции манипуляции с листом делаются на основе bp.ID точки останова
# - операции проверки наступления на точку останова делаются на основе board.PC и bp.Address

from DATA_FUNCS import *
import copy
import sys

def append_bp(BPs_in, bp):
	# Добавляет точку останова в лист с точками останова (если есть её дубликат - не добавляет)
	# Ввод:
	# - BPs_in	- лист точек останова
	# - bp 		- точка останова
	# Вывод:
	# - BPs 	- лист точек останова с добавленной точкой останова bp
	BPs = copy.deepcopy(BPs_in)
	if find_dict_by_key_in_dict_list(BPs, 'ID', bp['ID']) is None:	# Если не было найдено совпадений по ID
		BPs.append(bp)
	return BPs

def remove_bp(BPs_in, bp_id):
	# Удаляет точку останова из BPs_in
	# Ввод:
	# - BPs_in	- лист точек останова
	# - bp_id 	- ID точки останова
	# Вывод:
	# - BPs 	- лист точек останова с удалённой останова bp
	# BPs = []
	# for bp_in in BPs_in
	# 	if bp_in['ID'] != bp['ID']:
	# 		BPs.append(bp_in)
	return list(filter(lambda x: x['ID'] != bp_id, BPs_in))


def enable_bp(BPs_in, bp_id):
	# Включает точку останова (по ней теперь будут проводиться проверки)
	# Ввод:
	# - BPs_in	- лист точек останова
	# - bp_id 	- ID точки останова
	# Вывод:
	# - BPs 	- лист точек останова с отредактирвоанной останова bp
	BPs = []
	for bp in BPs_in:
		if bp == bp_id:
			bp["Enabled"] = True
		BPs.append(bp)
	return BPs

def disable_bp(BPs_in, bp_id):
	# Отключает точку останова (по ней теперь не будут проводиться проверки)
	# Ввод:
	# - BPs_in	- лист точек останова
	# - bp_id 	- ID точки останова
	# Вывод:
	# - BPs 	- лист точек останова с отредактирвоанной останова bp
	BPs = []
	for bp in BPs_in:
		if bp == bp_id:
			bp["Enabled"] = False
		BPs.append(bp)
	return BPs


def check_hits(BPs, PC: int):
	# Возвращает первую попавшуюся точку останова, на которую наступил PC.
	# - Если таких нет - ничего не возвращает
	# Ввод:
	# - BPs_in	- лист точек останова
	# - PC		- текущее значение PC в МК AVR
	# Вывод:
	# - bp 		- точка останова, на которую наступил PC
	for bp in BPs:
		if int(bp["Address"]) == PC:
			return bp



#------------------------------------------------------------------------------------------
# Команды для работы с автоматическим шаганием
import threading

global auto_step_thread
global Device_for_debug_local_link
global Tglobals_local_link
global clear_last_packages_link
global context_ID

# Флажок, который говорит что треду нужно остановаиться
global stop_requested
stop_requested = False


# Тред автоматического шагания
def auto_step_func():
	global Device_for_debug_local_link
	global Tglobals_local_link
	global clear_last_packages_link
	global context_ID

	global stop_requested

	while True:
		# Делаем шаг
		Device_for_debug_local_link.board.Step()		# Исполняем ровно 1 комнду

		# Получаем информацию с платы и проверяем, наступил ли МК AVR на точку останова
		PC = int.from_bytes(																		# Из значения в байтах в int
							bytearray(Device_for_debug_local_link.board.ReadRegister(['PC', None, None])),		# Значение PC в байтах
							byteorder=Device_for_debug_local_link.board.regs.endian 							# Порядок байт
						   )
		print(PC)
		Device_for_debug_local_link.bp_hit_id = check_hits(Device_for_debug_local_link.Breakpoints, PC)
		bp_hit_id = Device_for_debug_local_link.bp_hit_id

		# Если попали на точку останова - заканчиваем шагать

		# Если заканчиваем шагать
		# 0. Прерываем автоматическую потоко-передачу
		# 1. Посылаем atmel studio данные об окончании автоматического шагания и о точке останова
		# 2. Разрешаем дальше автоматическую приёмо-передачу
		# 3. заканчиваем тред
		if not (bp_hit_id is None):
			# 0.
			Tglobals_local_link.SOCKET_IO_INTERRUPTED = True
			# Ждём, когда недоотправленное сообщение с atbackend_server отпрявится на atmel_client (завершит итерацию)
			clear_last_packages_link()

			# 1.
			bp_hit_str = '{"BreakpointID":"'+bp_hit_id['ID']+'"}'
			Tglobals_local_link.atmel_client.send('E\x00RunControl\x00contextSuspended\x00'+context_ID+'\x00'+str(PC)+'\x00"Breakpoint"\x00'+bp_hit_str)

			print('\n\n\n')
			print('НАСТУПИЛИ НА ТОЧКУ ОСТАНОВА')
			print(f'PC={PC}')
			print('\n\n\n')

			# 2.
			Tglobals_local_link.SOCKET_IO_INTERRUPTED = False

			# 3.
			return True

		# Если запрошена останвока - останавливаем тред
		if stop_requested:
			print('Процесс автоагания остановлен')
			return False

		if Globals_info.exit:	# Завершаем
			sys.exit()
			return False


def start_auto_step(Device_for_debug, Tglobals, clear_last_packages, context_ID_str):
	global auto_step_thread
	global Device_for_debug_local_link
	global Tglobals_local_link
	global clear_last_packages_link
	global context_ID

	global stop_requested


	# Связываем локальные переменные пакета с глобальными переменными программы
	Device_for_debug_local_link, Tglobals_local_link, clear_last_packages_link = Device_for_debug, Tglobals, clear_last_packages
	context_ID = context_ID_str

	# Запускаем тред
	auto_step_thread = threading.Thread(target=auto_step_func, daemon=False)
	stop_requested = False
	auto_step_thread.start()


def stop_auto_step():
	global auto_step_thread
	global stop_requested
	try:
		stop_requested = True
	except Exception as e:
		print(f'Либо процесс автошагания уже остановлен, либо его ещё не запускали: {e}')