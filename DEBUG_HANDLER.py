import threading
from copy import deepcopy
import glob
from   avrdevice import Memory
from   avrdevice import *
from DATA_FUNCS import *
from BP_FUNCS	import *
import subprocess
from   base64 import b64encode as b64encode
from   base64 import b64decode as b64decode
global GLOBAL_PRINT_DEBUG ; GLOBAL_PRINT_DEBUG  = True
global GLOBAL_PRINT_DEBUG1; GLOBAL_PRINT_DEBUG1 = True



# Я не понимаю почему, но обычные глобальные переменные в тредах просто побитово дублируются
# Поэтому мы создаём объект, в котором будут хранится ссылки на объекты
# Уж если ссылки продублируются, то ничего плохого не случится,
# всё равно использовать будем область памяти, а не сами ссылки
class Tglobals_class:
	# Thread shared globals
	def __init__(self):
		self.LAST_RECV_PACKET = ''         # последний пакет, принятый с сервера
		self.SOCKET_IO_INTERRUPTED = False # прервали ли мы основную работу сокета, чтобы подменить нужные нам сообщения
		self.atbackend_server = None
		self.atmel_client = None
global Tglobals
Tglobals = Tglobals_class()

#global Tglobals.atbackend_server
#global Tglobals.atmel_client

#Tglobals.atbackend_server = None
#Tglobals.atmel_client = None



class Globals_info:
	# Глобальные переменные. содержащие наиболее общую информацию, необходимую для работы программы
	atbackend_filename = ''
	avr_dude_filename  = ''
	#programmator = ''
	COM = 'COM3'
	BAUDRATE = 76800
	exit = False 			# Флаг, означающий что программа должна завершиться

	# Скорее всего, как и в Arduino ide, команда на прошивку отдаётся, как будто это программатор avrisp mkii
	# на место параметров прошивки ({},{},...)
	# - название платы (как в avr-dude)
	# - название файла с бинарниками
	command_to_flash_with_preinstalled_bootloader  = '... {} ... {} ...'


class Hardware_software_debugger_interface:
	"""
	Класс, содержащий
	- подробную информацию о текущем запущенном процессе в atbackend
		- DeviceID, ProcessID, - уникальные названия текущего устройства, процесса в atbackend
		  RunControlId        и управляющего процессом (управляющий содержит информацию о том что можно делать клиенту и что нет, то есть его права)
		- Memory_info, Registers_info - 
	- интерфейс платы AVR с промежуточным виртуальным буффером - avrdevice
		- board - Интерфейс, содержащий
			- coreRegisterSpaceSize, ioSpaceSize - информацию о том, как разделена память data/SRAM (сколько байт ушло на РОН и сколько байт ушло на РВВ)
			- data, flash, eeprom, regs          - виртуальную копию различных адресных пространств МК, а так же служебных регистров
												   и информацию о них
			- WriteArray(), WriteArray_DifferentOnly() - функции записи в адресные пространства (по их названию)
			- 
	"""
	def __init__(
				 self,
				 COM = Globals_info.COM,
				 BAUDRATE = Globals_info.BAUDRATE
				):
		self.board      = None         # AvrDevice class
		self.prog 		= None

		self.COM = COM
		self.BAUDRATE = BAUDRATE

		# Информация, специфичная для приложения-симулятора (нужна для протокола)
		self.DeviceId       = ''
		self.ProcessID      = ''
		self.RunControlId   = ''
		self.Memory_info    = None 		#          "prog" : {"ID":"Mem_prog_8","BigEndian":false,"AddressSize":2,"StartBound":0,"EndBound":32767}, ...
		self.Registers_info = None 		# "CYCLE_COUNTER" : {"ID":"Reg_CYCLE_COUNTER_1","ProcessID":"Proc_1","Size":8}, ...
		# Как только к нам поступит информация о Registers_info, мы сможем уже полноценно инициализировать наше устройство
		# Потому что Registers_info поуступает только после Memory_info
		self.Line_position  = []		# Текущая позиция в программе формата ["Proc_1":58083:14]
										# Нужно только для atbackend потому что atmel studio воспринимает эту строку только с нулями
										# - ["Proc_1":0:14]

		self.Breakpoints 	= []		# Лист с элементами формата 
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
										# Предполагается, что поле ID - первичный ключ и ни одна пара записей не должна содержать одинаковые ID
										# 
										# - навряд ли будет такого формата, но возможно
										# {
										#	"ContextIds":["Proc_1"],	- к каким контекстам принадлежит
										#	"AccessMode":4,
										#	"ID":"3724_bp_0000001b",	- ID точки останова
										#	"Enabled":true,				- включена ли или нет
										#	"IgnoreCount":1,			- количество игнорирований
										#	"IgnoreType":"always",		- игнорировать ли?
										#	"Location":"10"				- позиция PC точки останова
										# }
		self.bp_hit_id		= None		# ID точки останова на которую наступил МК AVR
										# - если он ни на что не наступил, или наступил но во время предыдущей команды, то bp_hit_id=None

		self.Expression_variables = []	# Лист с элементами формата
										# {
										#  "ID":"expr_3",				- ID выражения
										#  "Name":"byte{registers}@R16" - его содержание для последующего присвоения. 
										#								  !!! Пока что присваиваем только регистрам
										# }
										#
										# Хранит переменные и ID выражения по которым к ним можно присвоить значение

	def Try_to_flash(self, obj_filename, have_preinstalled_bootloader=True):
		'''
		Основано на том факте, что .hex файлы в avr-sim находятся в той же папке (папке debug), что и объектные файлы
		'''
		# Получаем множество адресов и названий .hex файлов, которые выглядят как то, что нам нужно зашить в плату
		# Processes getContext "Proc_1"
		hex_filenames = glob.glob( obj_filename[:-len(obj_filename.split('\\')[-1])] + '*.hex' )
		assert(len(hex_filenames)>0 , f'There is no hex files inside object file {obj_filename} directory')
		assert(len(hex_filenames)==1, f'There is more than 1 hex file inside object file {obj_filename} directory')

		# Получаем название и адрес первого .hex файла
		hex_filename = hex_filenames[0]
		prog = open(hex_filename,'r').read()

		# На нашей плате прямо сейчас стоит не он (этот prog), то прошиваем плату этим .hex файлов (prog)
		if prog != self.prog:
			#avr_logger.info(f'Flashing program {hex_filename} to port {self.COM}:\n{prog}')
			self.prog = prog
			#!!!subprocess.call([ Globals_info.command_to_flash_with_preinstalled_bootloader.format(self.board_name, hex_filename) ])
			#avr_logger.info(f'Program flashed to port {self.COM}')
		else:
			avr_logger.info(f'Device does already have {hex_filename} program:\n{prog}')

global Device_for_debug




def printf(*args,**kwargs):
	# Функция вывода на экран строки, если в данный момент утверждение GLOBAL_PRINT_DEBUG справедливо
	if GLOBAL_PRINT_DEBUG:
		print(*args,**kwargs)

def printf1(*args,**kwargs):
	# Функция вывода на экран строки, если в данный момент утверждение GLOBAL_PRINT_DEBUG1 справедливо
	if GLOBAL_PRINT_DEBUG1:
		print(*args,**kwargs)



def init_device():
	global Device_for_debug
	global Globals_info
	# Создаём устройство
	print(f"Globals_info.COM end {Globals_info.COM}")
	Device_for_debug = Hardware_software_debugger_interface(
															COM = Globals_info.COM,
															BAUDRATE = Globals_info.BAUDRATE
														   )


# Функции по работе с потоками данных
def clear_last_packages():
	"""
	Функция отправки последних сообщений, что остались после остановки потоков (тредов) автоматического приёма-передачи
	"""
	timeout_iterations = 1000
	global Tglobals
	# Ждём, когда недоотправленное сообщение с atbackend_server отпрявится на atmel_client (завершит итерацию)
	i = 0
	while Tglobals.atbackend_server.bigbuff.qsize()>0:
		print(f'Waiting {Tglobals.atbackend_server.bigbuff} {Tglobals.atbackend_server.bigbuff.qsize()} {Tglobals.atbackend_server.last_packet}')
		i += 1
		if i>timeout_iterations:
			Tglobals.atbackend_server.send(Tglobals.atbackend_server.last_packet)
	# Отправляем оставшиеся пакеты, чтобы окончательно очистить буфер
	s = None
	while s!='':
		s = Tglobals.atbackend_server.read_packet_str()
		if s!='':
			Tglobals.atmel_client.send(s)

def get_current_line_params(recv):
	"""
	Функция получения параметров строки, на которой в данный момент стоит atbackend
	- получает по средствам
	  - общения с atbackend
	  - на основе данных Device_for_debug.board
	!!! Предполагается что потоки автоматического приёма-передачи остановлены

	1. Отсылаем PC
	2. На основе PC получаем абстрактную позицию atbackend
	3. На основе абстрактной позиции atbackend получаем параметры строки, на которой сейчас стоим
	"""
	global Tglobals
	global Device_for_debug
	# 0. Парсим исходные данные (для получения текущего номера команды)
	recv_args = recv.split('\x00')

	# 1. Отправляем значение PC
	#  Устанавливаем аргементы
	regname = 'PC'
	REG_ID = Device_for_debug.Registers_info[regname]['ID']

	#  Получаем данные с платы.
	data = bytearray(Device_for_debug.board.ReadRegister([regname, None, None]))
	data = f'"{b64encode(data).decode()}"'

	#  Отправляем данные на atbackend
	#  C 74 Registers set "Reg_R0_49" "AQ=="
	Tglobals.atbackend_server.send('C\x00{}\x00Registers\x00set\x00"{}"\x00{}'.format(recv_args[1],  REG_ID,  data))
	Tglobals.atbackend_server.rev_offset    += 1	# Теперь atbackend будет получать команду с номером на 1 меньший, чем он ожидает
	Tglobals.atmel_client.offset 			-= 1	# Теперь atbackend будет оправлять нам в ответ команды с номером на 1 команду больше

	#  Считываем её развёрнутый ответ на поставленную нами (.py) задачу
	dumb_result = 'None'
	while not dumb_result.startswith("R"):
		dumb_result = Tglobals.atbackend_server.read_packet_str()


	# 2. Узнаём абстрактную позицию по текущей позиции PC
	#  Отправляем запрос на получение позиции (PC мы отправили заранее)
	#   C 26 StackTrace getChildren "Proc_1"
	Tglobals.atbackend_server.send('C\x00{}\x00StackTrace\x00getChildren\x00"{}"'.format(recv_args[1],  Device_for_debug.ProcessID))
	Tglobals.atbackend_server.rev_offset    += 1	# Теперь atbackend будет получать команду с номером на 1 меньший, чем он ожидает
	Tglobals.atmel_client.offset 			-= 1	# Теперь atbackend будет оправлять нам в ответ команды с номером на 1 команду больше

	#  Считываем её развёрнутый ответ на поставленную нами (.py) задачу
	result = 'None'
	while not result.startswith("R"):	# R 26  ["Proc_1:0:16"]
		result = Tglobals.atbackend_server.read_packet_str()
		print(f'DUMB {result}')
	args = result.split('\x00')
	current_program_position = json.loads(args[3])[0].split(':')[2]		# Текущая позиция в программе

	# 3. По абстрактной позиции получаем текущий файл и позицию в нём (на котором мы сейчас стоим)
	#  Отправляем запрос на получение файла и строки в нём
	#   C 27 LineNumbers mapToSource "Proc_1" 16 18
	Tglobals.atbackend_server.send('C\x00{}\x00LineNumbers\x00mapToSource\x00"{}"\x00{}\x00{}'.format(recv_args[1],  Device_for_debug.ProcessID, current_program_position, current_program_position))
	Tglobals.atbackend_server.rev_offset    += 1	# Теперь atbackend будет получать команду с номером на 1 меньший, чем он ожидает
	Tglobals.atmel_client.offset 			-= 1	# Теперь atbackend будет оправлять нам в ответ команды с номером на 1 команду больше

	result = 'None'
	while not result.startswith("R"):	# R 604  [{"SLine":20,"ELine":20,"File":"C:\\Users\\Owner\\Desktop\\AssemblerApplication1\\AssemblerApplication1\\main.asm","SAddr":"14","EAddr":"15","IsStmt":1}]
		result = Tglobals.atbackend_server.read_packet_str()
		print(f'DUMB {result}')
	args = result.split('\x00')
	line_params = json.loads(args[3])		# Текущая позиция в файле и строке

	return line_params



#!!!
def handle_atmel_requests(recv):
	# Подслушиваем запрос recv от Atmel Studio
	# Если к контексту atbackend обращаются на чтение, то предварительно этот контекст синхронизируем с контекстом физической (avrdevice) платы
	# Если к контексту atbackend обращаются на запись, то предварительно записываем в физическую плату и получаем ответ. И только этот ответ уже записываем в контекст atbackend
	# (при необходимости просим треды передать нам управление потоками данных_
	
	recv = handle_input_control(recv)
	recv = handle_memory_requests(recv)
	
	#print(f'FINAL RECV {recv}')
	return recv

def handle_input_control(recv):
	# Обрабатываем запросы на управление симулятором от atmel studio
	# т.е.
	# Если Atmel Studio каким-либо образом пытается управлять виртуальной платой
	#  - то все запросы на управления виртуальной платой мы превращаем в реальные (передаём их реальной плате)
	#  - передавать дальше их на ATbacakend не имеет смысла. Поэтому на выходе new_recv после обработки будет пустой
	#  - однако, дальше в ATbackend наверняка последует запрос на получение текущей позиции (PC)
	#    поэтому текущее значение PC мы отправляем в ATbackend

	recv_args = recv.split('\x00')

	if len(recv_args)>=3: # если стррока похожа на C\x00[номер]\x00RunControl\x00...
		if   recv_args[2] == 'RunControl':
			if  recv_args[3] == 'resume': # C 31 RunControl resume "RunCtrl_15" 16 0
									# Ответ:
									# R 31
									# E RunControl contextResumed "RunCtrl_15"
									# E RunControl contextSuspended "RunCtrl_15" 0 "Step" {}
									#											 0 - значение PC после шага (в формате int)
									# Формат:
									# C 31 RunControl resume "RunCtrl_15" КОД_КОМАНДЫ 0
									# КОД_КОМАНДЫ:
									#	16 - start (start debug or start after pause)
									#	4  - step
									#	2  - disassembly line step (step from NOP)
									#	0  - automatic step

				# Во время RunControl resume STEP нам нужно
				# 0. Прервать приёмо-передачу
				# 1. Самим сделать шаг
				# 2. Проверяем на точки останова
				#    2.1 Если попали - возвращаем сообщение о попадании на точку останвоа
				#    2.2 Если всё хорошо - возвращаем сообщение об удачно сделанном шаге
				# 3. Передать далее пустую строку (то есть команду мы исполнили полностью заместо atbackend)
				if (recv_args[5] == '2'):
					print(f"NOP PC={bytearray(Device_for_debug.board.ReadRegister(['PC', None, None]))}")
				if  (recv_args[5] == '16') or (recv_args[5] == '4') or (recv_args[5] == '2'):
					# 0.
					Tglobals.SOCKET_IO_INTERRUPTED = True
					# Ждём, когда недоотправленное сообщение с atbackend_server отпрявится на atmel_client (завершит итерацию)
					clear_last_packages()
					print('INTERRUPT I/O on RunControl resume STEP from AS')
					avr_logger.info('INTERRUPT I/O on RunControl resume STEP from AS')

					# 1.
					if not (recv_args[5] == '16'):	# Если не первый запуск
						Device_for_debug.board.Step()		# Исполняем ровно 1 комнду
					PC = int.from_bytes(																		# Из значения в байтах в int
										bytearray(Device_for_debug.board.ReadRegister(['PC', None, None])),		# Значение PC в байтах
										byteorder=Device_for_debug.board.regs.endian 							# Порядок байт
									   )
					# 2.
					line_number = int(recv_args[1])
					context_ID = recv_args[4]

					#send =  f'R\x00{line_number}\n'
					#send += f'E\x00RunControl\x00contextResumed\x00{context_ID}\n'
					#send += 'E\x00RunControl\x00contextSuspended\x00'+context_ID+'\x00'+str(PC+2)+'\x00"Step"\x00{}'
					#Tglobals.atmel_client.send(send)


					print()
					print()
					# ---Узнаём позицию в программе и проверяем, не упёрлись ли мы в точку останова--------------------------
					#line_params = get_current_line_params(recv)
					#print(line_params)
					print()
					print()

					#!!!
					Tglobals.atmel_client.send_without_offset(f'R\x00{line_number}')		# Отправляем без смещения, т.к. смещение возникает только при передачи данных мужде atbackend и atmel studio
					Tglobals.atmel_client.send(f'E\x00RunControl\x00contextResumed\x00{context_ID}')

					Device_for_debug.bp_hit_id = check_hits(Device_for_debug.Breakpoints, PC)	# Точка останова на которую наткнулись
					bp_hit_id = Device_for_debug.bp_hit_id

					if not (bp_hit_id is None):	# Если попали на точку останова И ЭТО НЕ ПЕРВЫЙ ЗАПУСК !!!
						# 2.1
						# E RunControl contextSuspended "RunCtrl_1" 14 "Breakpoint" {"BreakpointID":"11964_bp_0000002c"}
						bp_hit_str = '{"BreakpointID":"'+bp_hit_id['ID']+'"}'
						Tglobals.atmel_client.send('E\x00RunControl\x00contextSuspended\x00'+context_ID+'\x00'+str(PC)+'\x00"Breakpoint"\x00'+bp_hit_str)
					else:
						# 2.2
						# E RunControl contextSuspended "RunCtrl_1" 12 "Step" {}
						Tglobals.atmel_client.send('E\x00RunControl\x00contextSuspended\x00'+context_ID+'\x00'+str(PC)+'\x00"Step"\x00{}')

					Tglobals.atbackend_server.rev_offset    -= 1	# Теперь atbackend будет получать команду с номером на 1 большую, чем он ожидает
					Tglobals.atmel_client.offset 			+= 1	# Теперь atbackend будет оправлять нам в ответ команды с номером на 1 команду меньше
					print('Команда STEP исполнена заместо atbackend')
					avr_logger.info('Команда STEP исполнена заместо atbackend')
					if not (bp_hit_id is None):
						print(f'R\x00{line_number}')
						print(f'E\x00RunControl\x00contextResumed\x00{context_ID}')
						print('E\x00RunControl\x00contextSuspended\x00'+context_ID+'\x00'+str(PC)+'\x00"Breakpoint"\x00'+bp_hit_str)

					# 3.
					#!!!
					recv = ''
					recv_args = recv.split('\x00')
					Tglobals.SOCKET_IO_INTERRUPTED = False
					return recv


				# При запросе на автоматическое шагание нужнго
				# 0. Прервать поток автоматической приёмо-передачи
				# 1. Спарсить данные
				# 2. На основе них отослать atmel studio информацию об успешном запуске
				# 3. Запустить тред (может выдать информацию об останове практически моментально)
				# 4. Передать дальше пустую команду atbackend (мы уже него исполнили эту команду)
				if  (recv_args[5] == '0'):
					# 0.
					Tglobals.SOCKET_IO_INTERRUPTED = True
					# Ждём, когда недоотправленное сообщение с atbackend_server отпрявится на atmel_client (завершит итерацию)
					clear_last_packages()
					print('INTERRUPT I/O on RunControl auto STEP from AS')
					avr_logger.info('INTERRUPT I/O on RunControl auto STEP from AS')

					# 1.
					line_number = int(recv_args[1])
					context_ID = recv_args[4]
					# 2.
					Tglobals.atmel_client.send_without_offset(f'R\x00{line_number}')		# Отправляем без смещения, т.к. смещение возникает только при передачи данных мужде atbackend и atmel studio
					Tglobals.atmel_client.send(f'E\x00RunControl\x00contextResumed\x00{context_ID}')
					Tglobals.atbackend_server.rev_offset    -= 1	# Теперь atbackend будет получать команду с номером на 1 большую, чем он ожидает
					Tglobals.atmel_client.offset 			+= 1	# Теперь atbackend будет оправлять нам в ответ команды с номером на 1 команду меньше

					# 3.
					start_auto_step(Device_for_debug, Tglobals, clear_last_packages, context_ID)

					# 4.
					#!!!
					recv = ''
					recv_args = recv.split('\x00')
					Tglobals.SOCKET_IO_INTERRUPTED = False
					return recv


			# Если поступает запрос на остановку автоматического шагания
			# 0. Прерываем поток автоматической приёмо-передачи
			# 1. Останавливаем тред автоматического шагания 	(!!! очень опасно, т.к. не всегда можем снова вернуться на точку синхронизации МК AVR)
			# 2. Возвращаем ответ об успешной остановке
			# 3. Отдаём atbackend ничего на исполнение
			if  recv_args[3] == 'suspend':	# C 40 RunControl suspend "RunCtrl_1"
				# 0.
				Tglobals.SOCKET_IO_INTERRUPTED = True
				# Ждём, когда недоотправленное сообщение с atbackend_server отпрявится на atmel_client (завершит итерацию)
				clear_last_packages()
				print('INTERRUPT I/O on RunControl auto STEP from AS')
				avr_logger.info('INTERRUPT I/O on RunControl auto STEP from AS')

				# 1.
				stop_auto_step()

				# 2.
				line_number = int(recv_args[1])
				context_ID = recv_args[4]
				PC = int.from_bytes(																		# Из значения в байтах в int
										bytearray(Device_for_debug.board.ReadRegister(['PC', None, None])),		# Значение PC в байтах
										byteorder=Device_for_debug.board.regs.endian 							# Порядок байт
									   )

				# 3.
				Tglobals.atmel_client.send_without_offset(f'R\x00{line_number}')		# Отправляем без смещения, т.к. смещение возникает только при передачи данных мужде atbackend и atmel studio
				Tglobals.atmel_client.send('E\x00RunControl\x00contextSuspended\x00'+context_ID+'\x00'+str(PC)+'\x00"Suspended"\x00{}')
				Tglobals.atbackend_server.rev_offset    -= 1	# Теперь atbackend будет получать команду с номером на 1 большую, чем он ожидает
				Tglobals.atmel_client.offset 			+= 1	# Теперь atbackend будет оправлять нам в ответ команды с номером на 1 команду меньше

				# 4.
				#!!!
				recv = ''
				recv_args = recv.split('\x00')
				Tglobals.SOCKET_IO_INTERRUPTED = False
				return recv


			if  True:
				recv = recv


		elif recv_args[2] == 'Breakpoints':
			# # Если atmel studio просит Breakpoints getProperties
			# #  то это значит, что командой ранее он их изменил
			# # соответственно самый простой способ держать последнюю информацию о точках останова
			# #  - получать все свойства каждой из точек останова самому каждый раз когда тот просит Breakpoints getProperties
			# if  recv_args[3] == 'getProperties':
			# 	# 0.
			# 	Tglobals.SOCKET_IO_INTERRUPTED = True
			# 	# Ждём, когда недоотправленное сообщение с atbackend_server отпрявится на atmel_client (завершит итерацию)
			# 	clear_last_packages()
			# 	print('INTERRUPT I/O on RunControl resume STEP from AS')
			# 	avr_logger.info('INTERRUPT I/O on RunControl resume STEP from AS')

			# 	# 1.
			# 	Tglobals.atbackend_server.send(f'C\x00{recv_args[2]}\x00Breakpoints\x00getIDs\x00{0}')
			# 	Tglobals.atbackend_server.rev_offset    += 1	# Теперь atbackend будет получать команду с номером на 1 меньшую, чем он ожидает
			# 	Tglobals.atmel_client.offset 			-= 1	# Теперь atbackend будет оправлять нам в ответ команды с номером на 1 команду больше

			# 	# Считываем её развёрнутый ответ на поставленную нами (.py) задачу
			# 	dumb_result = 'None'
			# 	#while not dumb_result.startswith("R\x00{}".format(recv_args[1])):
			# 	print()
			# 	print(f'C\x00{recv_args[2]}\x00Breakpoints\x00getIDs\x00{0}')
			# 	while not dumb_result.startswith("R"):
			# 		dumb_result = Tglobals.atbackend_server.read_packet_str()
			# 		print(dumb_result)
			# 	print()

			# 	# 3.
			# 	#!!!
			# 	recv = recv
			# 	recv_args = recv.split('\x00')
			# 	Tglobals.SOCKET_IO_INTERRUPTED = False

			# Во время Breakpoints add нам нужно
			# 0. Прерывать приёмо-передачу
			# 1. Пропустить дальше Breakpoints add, чтобы получить более развёрнутую информацию о данной точке
			# 2. Спарсить данные
			# 3. Получить информацию о точке останова
			# 4. Добавить её в общий список точек останова дейвайса
			# 5. Передать дальше пустой пакет на исполнение (ничего)
			if  recv_args[3] == 'add': # C 973 Breakpoints add {"ContextIds":["Proc_6"],"AccessMode":4,"ID":"3724_bp_0000001b","Enabled":true,"IgnoreCount":1,"IgnoreType":"always","Location":"10"}
				# 0.
				Tglobals.SOCKET_IO_INTERRUPTED = True
				clear_last_packages()	# Ждём, когда недоотправленное сообщение с atbackend_server отпрявится на atmel_client (завершит итерацию)
				print('INTERRUPT I/O on Breakpoints add from AS')
				avr_logger.info('INTERRUPT I/O on Breakpoints add from AS')

				# 1.
				# Добавляем точку останова, как этого и хотел atbackend
				Tglobals.atbackend_server.send(recv)
				dumb_result = 'None'
				while not dumb_result.startswith("R"): # R 1347
					dumb_result = Tglobals.atbackend_server.read_packet_str()
					Tglobals.atmel_client.send(dumb_result)
				
				recv_args[1] = str(int(recv_args[1])+1) # Теперь номер команды на 1 команду больше

				# 2.
				# Парсим данные исходного пакета
				ID = json.loads(recv_args[4])["ID"]

				# 3.
				# Получаем параметры добавленной точки останова
				Tglobals.atbackend_server.send(f'C\x00{recv_args[1]}\x00Breakpoints\x00getProperties\x00"{ID}"')
				Tglobals.atbackend_server.rev_offset    += 1	# Теперь atbackend будет получать команду с номером на 1 меньшую, чем он ожидает
				Tglobals.atmel_client.offset 			-= 1	# Теперь atbackend будет оправлять нам в ответ команды с номером на 1 команду больше
				
				# Считываем её развёрнутый ответ на поставленную нами (.py) задачу
				result = 'None'
				while not result.startswith("R"): # R 1347  {"ID":"3724_bp_00000030","Enabled":true,"AccessMode":4,"File":"","Line":-1,"Column":-1,"Address":"10","HitCount":0}
					result = Tglobals.atbackend_server.read_packet_str()
				print(result)
				args = result.split('\x00')
				bp = json.loads(args[3])
				print(bp)

				# 4.
				# Добавляем точки останова
				if Device_for_debug.Breakpoints != append_bp(Device_for_debug.Breakpoints, bp):
					print("bp added")
				else:
					print("Breakpoints wasn't changed")

				Device_for_debug.Breakpoints = append_bp(Device_for_debug.Breakpoints, bp)
				print(Device_for_debug.Breakpoints)
				print()
				print()

				# 5.
				#!!!
				recv = ''
				recv_args = recv.split('\x00')
				Tglobals.SOCKET_IO_INTERRUPTED = False
				return recv

			# Если поступает Breakpoints remove надо
			# 1. Просто удалить все точки останова что просит atmel studio
			if  recv_args[3] == 'remove':	# C 1900 Breakpoints remove ["3724_bp_00000060"]
				BPs = json.loads(recv_args[4])
				for bp in BPs:
					Device_for_debug.Breakpoints = remove_bp(Device_for_debug.Breakpoints, bp)
				print('bps removed')
				print(Device_for_debug.Breakpoints)
				print()
				print()

			# Если поступает Breakpoints disable надо
			# 1. Просто деактивировать все точки останова что просит atmel studio
			if  recv_args[3] == 'disable':	# C 1753 Breakpoints disable ["3724_bp_0000005f"]
				BPs = json.loads(recv_args[4])
				for bp in BPs:
					Device_for_debug.Breakpoints = disable_bp(Device_for_debug.Breakpoints, bp)
				print('bps disabled')
				print(Device_for_debug.Breakpoints)
				print()
				print()

			# Если поступает Breakpoints enable надо
			# 1. Просто активировать все точки останова что просит atmel studio
			if  recv_args[3] == 'enable':	# C 1753 Breakpoints disable ["3724_bp_0000005f"]
				BPs = json.loads(recv_args[4])
				for bp in BPs:
					Device_for_debug.Breakpoints = enable_bp(Device_for_debug.Breakpoints, bp)
				print('bps enadled')
				print(Device_for_debug.Breakpoints)
				print()
				print()

		else:
			recv = recv
	Tglobals.SOCKET_IO_INTERRUPTED = False
	return recv




def handle_memory_requests(recv):
	global Device_for_debug
	global Tglobals
	#global Tglobals.atbackend_server
	#global Tglobals.atmel_client


	recv_args = recv.split('\x00')

	if len(recv_args)>=3:
		#print(recv,'RECIEVED ARGUEMENTS', 'AAAAAAAAAAA\n'.join(recv_args))
		if   recv_args[2] == 'Memory':

			# Во время Memory get нам нужно
			# 0. Прервать приёмо-передачу
			# 1. Спарсить данные из пакета
			# 2. Самим получить данные с платы МК AVR
			# 3. Записать их в контекст atbackend
			# 4. Теперь с обновлёнными данными в СИМУЛЯТОРЕ (atbackend), передать ему запрос на получение этих обновлённых данных (то есть отпустить неизменённый запрос на чтение дальше по потоку)
			if  recv_args[3] ==  'get':	# C 374 Memory get "Mem_data_145" 36 1 1 0
										# R 374 "AA=="  []
				# 0.
				Tglobals.SOCKET_IO_INTERRUPTED = True
				# Ждём, когда недоотправленное сообщение с atbackend_server отпрявится на atmel_client (завершит итерацию)
				clear_last_packages()
				print('INTERRUPT I/O on Memory get from AS')
				avr_logger.info('INTERRUPT I/O on Memory get from AS')




				# 1.
				# Парсим данные
				MEM_ID        = recv_args[4].replace('"','')
				start_address      = int(recv_args[5])
				number_of_elements = int(recv_args[7])
				count_id           = int(recv_args[8])

				memspace = find_by_another_key(Device_for_debug.Memory_info,'ID',MEM_ID)['IDKEY']	# Находим название адресного пространства по его 'ID' ('IDKEY' - служебное название ключа)
				
				print(MEM_ID,
					  hex(start_address),
					  hex(number_of_elements),
					  hex(count_id),
					  memspace)

				max_address = find_by_another_key(Device_for_debug.Memory_info,'ID',MEM_ID)["EndBound"]	# Получаем максимально допустимый адрес в адресной сетке
				start_address = start_address			# Урезаем лишнее, что вылезает за пределы адресной сетки (прокрутились)
				number_of_elements = number_of_elements		# Находим реальное количество элементов: зависит от режима, выбранного в count_id



				# 2.
				# Получаем данные с платы. data: str  ("AAA==")
				data = bytearray(Device_for_debug.board.ReadArray(memspace, start_address, number_of_elements, 1))
				print('b ',data)	# Сырые данные (bytes в формате str)
				data = f'"{b64encode(data).decode()}"' # Обновляем нашу информацию о памяти МК AVR в заданном диапазоне адресов и получаем новые значения ВСЕХ ячеек этого диапазона
				print('b64 ',data)	# Сконвертированные данные (base64 в формате str)

				print('Got Memory from board\n{}\nby arguements\n(memspace={}, start_address={}, number_of_elements={})'.format(Device_for_debug.board.name, memspace, hex(start_address), hex(number_of_elements)))
				avr_logger.info('Got Memory from board\n{}\nby arguements\n(memspace={}, start_address={}, number_of_elements={})'.format(Device_for_debug.board.name, memspace, hex(start_address), hex(number_of_elements)))

				


				# 3.
				# Отправляем данные на atbackend
				# Memory set "[ID]" [start_address] 1 [number_of_elements] 0 "[байтмассив_формата_base64]"
				Tglobals.atbackend_server.send('C\x00{}\x00Memory\x00set\x00"{}"\x00{}\x001\x00{}\x00{}\x00{}'.format(recv_args[1],  MEM_ID,  start_address, number_of_elements, count_id, data))
				Tglobals.atbackend_server.rev_offset    += 1	# Теперь atbackend будет получать команду с номером на 1 меньший, чем он ожидает
				Tglobals.atmel_client.offset -= 1	# Теперь atbackend будет оправлять нам в ответ команды с номером на 1 команду больше

				# Считываем её развёрнутый ответ на поставленную нами (.py) задачу
				dumb_result = 'None'
				#while not dumb_result.startswith("R\x00{}".format(recv_args[1])):
				while not dumb_result.startswith("R"):
					dumb_result = Tglobals.atbackend_server.read_packet_str()
					print(f'DUMB {dumb_result}')
				print(f'Sended board memory to ATbackend, it responded with {dumb_result}') # просто пустышка, чтобы не отправлять пустое сообщение клиенту - его надо прочитать и убрать тем самым не передавать его в наш буфер
				avr_logger.info(f'Sended board memory to ATbackend, it responded with {dumb_result}')



				# Сообщаем об успешной записи
				if len(data)>0:
					printf(f'atbackend memory updated by avrdevice.py:\n{memspace}\n{data}\n')
					avr_logger.info(f'atbackend memory updated by avrdevice.py:\n{memspace}\n{data}\n')

				# 4.
				# Передаём данные дальше
				recv = recv
				recv_args = recv.split('\x00')
				#avr_logger.info(f'Device state: {Device_for_debug.board}')
				Tglobals.SOCKET_IO_INTERRUPTED = False


			# Так получается, что одна и та же команда может удовлетворять разным фильтрам (принадлежать разным командным группам одновременно)
			# Поэтому вместо elif стоит if

			# Во время Memory set нам нужно
			# 0. Прервать приёмо-передачу
			# 1. Спарсить данные из пакета
			# 2. Залить эти данные на плату и получить ответ о заливке
			# 3. Залить полученные с платы данные в контекст atbackend
			# 4. Передать ответ atmel-studio о залитых данных (как будто atbaclend на самом деле залил в себя не наши данные, а исходные)
			if  recv_args[3] ==  'set':	# C 543 Memory set "Mem_data_40" 256 1 8 0 "EgAAAAAAABA="
										# E Memory memoryChanged "Mem_data_40" [{"addr":256,"size":8}]
										# R 543  []
				# 0.
				# Останавливаем приёмо-передачу
				Tglobals.SOCKET_IO_INTERRUPTED = True
				clear_last_packages()
				print('INTERRUPT I/O on Memory set to AS')
				avr_logger.info('INTERRUPT I/O on Memory set to AS')

				# 1.
				# Парсим данные
				MEM_ID        = recv_args[4].replace('"','')
				start_address      = int(recv_args[5])
				number_of_elements = int(recv_args[7])
				count_id           = int(recv_args[8])
				data_in			   = b64decode(recv_args[9].encode())	# Переводим литерал байтов в байты base64, а потом декодируем их в обычные байты (base8)

				memspace = find_by_another_key(Device_for_debug.Memory_info,'ID',MEM_ID)['IDKEY']	# Находим название адресного пространства по его 'ID' ('IDKEY' - служебное название ключа)
				print(MEM_ID,
					  hex(start_address),
					  hex(number_of_elements),
					  hex(count_id),
					  data_in,
					  memspace)

				# 2.
				# Заливаем данные на плату и получаем ответ
				data_out = bytearray(Device_for_debug.board.WriteArray(memspace, data_in, start_address, number_of_elements, 1))

				# 3.
				# Заливаем содержимое платы в контекст atbackend
				# Просто переписать уже существующий пакет будет удобнее всего
				assert len(data_out)==number_of_elements, "Length of writed memory and memory-to-write don't match" # !!! Если длина записанных данных и длина данных, которые должны были записаться, различаются, то что-то пошло не так
				recv_args[8] = str(len(data_out))
				recv_args[9] = f'"{b64encode(data_out).decode()}"'	# Вместо тех данных, что должны были быть залиты в идеале передаём те данные, что реально залиты

				# 4.
				# Передаём данные дальше
				recv = '\x00'.join(recv_args)	# Обновили пакет в соответствии с новыми данными для заливки на atbackend 		#!!! На этом моменте могут возникнуть несостыковки если далее какой-либо из обработчиков пакетов попытается этот пакет ещё раз обработать
				Tglobals.SOCKET_IO_INTERRUPTED = False





		elif recv_args[2] == 'Registers':

			# Во время Reigstrs set нам нужно
			# 0. Прервать приёмо-передачу
			# 1. Спарсить данные из пакета
			# 2. Залить эти данные на плату и получить ответ о заливке
			# 3. Залить полученные с платы данные в контекст atbackend
			# 4. Передать ответ atmel-studio о залитых данных (как будто atbaclend на самом деле залил в себя не наши данные, а исходные)
			if  recv_args[3] ==  'set':	# C 74 Registers set "Reg_R0_49" "AQ=="
										# R 74

				# 0.
				# Останавливаем приёмо-передачу
				Tglobals.SOCKET_IO_INTERRUPTED = True
				clear_last_packages()
				print('INTERRUPT I/O on Registers set to AS')
				avr_logger.info('INTERRUPT I/O on Registers set to AS')

				# 1.
				# Парсим данные
				REG_ID        = recv_args[4].replace('"','')
				data_in		  = b64decode(recv_args[5].encode())	# Переводим литерал байтов в байты base64, а потом декодируем их в обычные байты (base8)

				regname = find_by_another_key(Device_for_debug.Registers_info,'ID',REG_ID)['IDKEY']	# Находим название адресного пространства по его 'ID' ('IDKEY' - служебное название ключа. В данном случае ключевое поле - имя регистра)
				print(REG_ID,
					  data_in,
					  regname)

				# 2.
				# Заливаем данные на плату и получаем ответ
				data_out = bytearray(Device_for_debug.board.WriteRegister(data_in, regname))

				# 3.
				# Заливаем содержимое платы в контекст atbackend
				# Просто переписать уже существующий пакет будет удобнее всего
				recv_args[5] = f'"{b64encode(data_out).decode()}"'	# Вместо тех данных, что должны были быть залиты в идеале передаём те данные, что реально залиты

				# 4.
				# Передаём данные дальше
				recv = '\x00'.join(recv_args)	# Обновили пакет в соответствии с новыми данными для заливки на atbackend 		#!!! На этом моменте могут возникнуть несостыковки если далее какой-либо из обработчиков пакетов попытается этот пакет ещё раз обработать
				Tglobals.SOCKET_IO_INTERRUPTED = False
			
			# Таких пакетов просто нет
			# if  recv_args[3] ==  'setm':  # R 374 "AA=="  []
			# 	#recv_args[4]
			# 	#Device_for_debug.Memory_info
			# 	...
			
			# Таких пакетов просто нет
			# if  recv_args[3] ==  'get':  # R 374 "AA=="  []
			# 	#recv_args[4]
			# 	#Device_for_debug.Memory_info
			# 	...

			# Во время Registers getm нам нужно
			# Сделать всё тоже самое что и для memory get но только для той области в которой лежат регистры
			#!!! setm имеет тот же формат что и getm (и требует тех же действий от нас чтобы всё работало как надо - синхронизированно с платой МК AVR)
			#!!! хак, который работает только на платах с регистрами в SRAM 0x00-0x20. Для остальных выдаст ошибку
			# 0. Прервать приёмо-передачу
			# Для каждого регистра из операнда REG_INFOS_WITH_IDS исходной команды
			# 	1. Спарсить его название
			# 	2. Самим прочитать данные с платы МК AVR (полностью)
			# 3. Записать регистр в контекст atbackend по ID регистров
			# 4. Теперь с обновлёнными данными в СИМУЛЯТОРЕ (atbackend), передать ему запрос на получение этих обновлённых данных (то есть отпустить неизменённый запрос на чтение дальше по потоку)
			if  (recv_args[3] ==  'getm') or (recv_args[3] ==  'setm'):	# C 24 Registers getm [["Reg_CYCLE_COUNTER_1",0,8],["Reg_PC_2",0,4],["Reg_SREG_3",0,1],["Reg_FP_4",0,2],["Reg_X_5",0,2],["Reg_Y_6",0,2],["Reg_Z_7",0,2],["Reg_SP_8",0,2],["Reg_R0_9",0,1],["Reg_R1_10",0,1],["Reg_R2_11",0,1],["Reg_R3_12",0,1],["Reg_R4_13",0,1],["Reg_R5_14",0,1],["Reg_R6_15",0,1],["Reg_R7_16",0,1],["Reg_R8_17",0,1],["Reg_R9_18",0,1],["Reg_R10_19",0,1],["Reg_R11_20",0,1],["Reg_R12_21",0,1],["Reg_R13_22",0,1],["Reg_R14_23",0,1],["Reg_R15_24",0,1],["Reg_R16_25",0,1],["Reg_R17_26",0,1],["Reg_R18_27",0,1],["Reg_R19_28",0,1],["Reg_R20_29",0,1],["Reg_R21_30",0,1],["Reg_R22_31",0,1],["Reg_R23_32",0,1],["Reg_R24_33",0,1],["Reg_R25_34",0,1],["Reg_R26_35",0,1],["Reg_R27_36",0,1],["Reg_R28_37",0,1],["Reg_R29_38",0,1],["Reg_R30_39",0,1],["Reg_R31_40",0,1]]
											# R 24  "AAAAAAAAAAAAAAAAAAAAAAAAAAAA/wgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="
				# 0.
				Tglobals.SOCKET_IO_INTERRUPTED = True
				# Ждём, когда недоотправленное сообщение с atbackend_server отпрявится на atmel_client (завершит итерацию)
				clear_last_packages()
				print('INTERRUPT I/O on Registers getm from AS')
				avr_logger.info('INTERRUPT I/O on Registers getm from AS')


				# 1.
				# Парсим данные
				REG_INFOS_WITH_IDS       = json.loads(recv_args[4])

				#reginfos_joined = join_ld_to_list(REG_INFOS_WITH_IDS, Device_for_debug.Registers_info, 0, 'ID', ['Name']) # Джойним 0 поле с полем 'ID'. В результате джойна с листом из правой части (словаря) оставляем только поле 'Name'
				#regnames = [reginfo_joined[1] for reginfo_joined in reginfos_joined]	 # Оставляем только поле 'Name'

				risj = join_ld_to_list(REG_INFOS_WITH_IDS, Device_for_debug.Registers_info, 0, 'ID', ['Name'])	# Reg InfoS Joined
				reginfos = [[rij[3],rij[1],rij[2]] for rij in risj]
				
				print(REG_INFOS_WITH_IDS,
					  reginfos)

				data = bytearray()
				for i in range(len(reginfos)):
					regname 	= reginfos[i][0]
					start_byte	= reginfos[i][1]
					end_byte	= reginfos[i][2]
					# 2.
					# Получаем данные с платы.
					data += bytearray(Device_for_debug.board.ReadRegister([regname, start_byte, end_byte]))
					print(reginfos[i], data)
					#///print('b ',data)	# Сырые данные (bytes в формате str)

				# Предобразуем в строку "base64"
				data = f'"{b64encode(data).decode()}"' # Срдержит данные всех требуемых регистров
				#///print('b64 ',data)	# Сконвертированные данные (base64 в формате str)

				#///print('Got Register from board\n{}\nby arguement\n(regname={})'.format(Device_for_debug.board.name, regname))
				#///avr_logger.info('Got Register from board\n{}\nby arguement\n(regname={})'.format(Device_for_debug.board.name, regname))
				


				# 3.
				# Отправляем данные на atbackend
				# C 74 Registers set "Reg_R0_49" "AQ=="
				#!!!REG_ID = REG_INFOS_WITH_IDS[i][0]
				#///if "Reg_PC" in REG_ID:
				#///	print(f"WHY PC IS SO LENGTH data={bytearray(Device_for_debug.board.ReadRegister([regname, None, None]))} len={len(bytearray(Device_for_debug.board.ReadRegister([regname, None, None])))}")
				Tglobals.atbackend_server.send('C\x00{}\x00Registers\x00setm\x00{}\x00{}'.format(recv_args[1],  recv_args[4],  data))
				Tglobals.atbackend_server.rev_offset    += 1	# Теперь atbackend будет получать команду с номером на 1 меньший, чем он ожидает
				Tglobals.atmel_client.offset -= 1	# Теперь atbackend будет оправлять нам в ответ команды с номером на 1 команду больше

				# Считываем её развёрнутый ответ на поставленную нами (.py) задачу
				dumb_result = 'None'
				#while not dumb_result.startswith("R\x00{}".format(recv_args[1])):
				while not dumb_result.startswith("R"):
					dumb_result = Tglobals.atbackend_server.read_packet_str()
					#///print(f'DUMB {dumb_result}')
				#///print(f'Sended board memory to ATbackend, it responded with {dumb_result}') # просто пустышка, чтобы не отправлять пустое сообщение клиенту - его надо прочитать и убрать тем самым не передавать его в наш буфер
				#///avr_logger.info(f'Sended board memory to ATbackend, it responded with {dumb_result}')



				# Сообщаем об успешной записи
				#///if len(data)>0:
					#///printf(f'atbackend register updated by avrdevice.py:\nregname={regname}\nregdata={data}')
					#///avr_logger.info(f'atbackend register updated by avrdevice.py:\nregname={regname}\nregdata={data}')
				printf(f'atbackend registers updated by avrdevice.py:\nreginfos={REG_INFOS_WITH_IDS}')
				avr_logger.info(f'atbackend registers updated by avrdevice.py:\nreginfos={REG_INFOS_WITH_IDS}')
				# 4.
				# Передаём данные дальше
				recv = recv
				recv_args = recv.split('\x00')
				#avr_logger.info(f'Device state: {Device_for_debug.board}')
				Tglobals.SOCKET_IO_INTERRUPTED = False

		# Команды получения информации об отладке. Высчитываются внутри atbackend на основании контекста atbackend-симулятора-платы
		if   recv_args[2] == 'StackTrace':
			# Во время StackTrace getChildren
			# то есть получения текущей позиции программы
			# нам нужно
			# 0. Прервать приёмо-передачу
			# 1. Установить аргументы чтения и записи чтобы обратиться к регистру PC
			# 2. Самим прочитать данные с платы МК AVR (полностью)
			# 3. Записать регистр PC в контекст atbackend по ID регистра PC
			# 4. Получаем ответ сами, так же передаём его в atmel studio
			# 5. Парсим его и записываем в контекст нашего симулятора
			# 6. Передам дальше на исполнение пустую строку
			if  recv_args[3] ==  'getChildren': # C 288 StackTrace getChildren "Proc_1"
												# R 288  ["Proc_1:58083:6"]
												# - где R 845  ["Proc_3:[хз что]:[PC]"]
				# 0.
				Tglobals.SOCKET_IO_INTERRUPTED = True
				# Ждём, когда недоотправленное сообщение с atbackend_server отпрявится на atmel_client (завершит итерацию)
				clear_last_packages()
				print('INTERRUPT I/O on Registers getm from AS')
				avr_logger.info('INTERRUPT I/O on Registers getm from AS')


				# 1.
				# Устанавливаем аргументы
				regname = 'PC'
				REG_ID = Device_for_debug.Registers_info[regname]['ID']
				
				# 2.
				# Получаем данные с платы.
				data = bytearray(Device_for_debug.board.ReadRegister([regname, None, None]))
				#///print('b ',data)	# Сырые данные (bytes в формате str)
				# Переводим в формат base64
				data = f'"{b64encode(data).decode()}"' # 
				#///print('b64 ',data)	# Сконвертированные данные (base64 в формате str)

				#///print('Got Register from board\n{}\nby arguement\n(regname={})'.format(Device_for_debug.board.name, regname))
				#///avr_logger.info('Got Register from board\n{}\nby arguement\n(regname={})'.format(Device_for_debug.board.name, regname))
				


				# 3.
				# Отправляем данные на atbackend
				# C 74 Registers set "Reg_R0_49" "AQ=="
				Tglobals.atbackend_server.send('C\x00{}\x00Registers\x00set\x00"{}"\x00{}'.format(recv_args[1],  REG_ID,  data))
				Tglobals.atbackend_server.rev_offset    += 1	# Теперь atbackend будет получать команду с номером на 1 меньший, чем он ожидает
				Tglobals.atmel_client.offset -= 1	# Теперь atbackend будет оправлять нам в ответ команды с номером на 1 команду больше

				# Считываем её развёрнутый ответ на поставленную нами (.py) задачу
				dumb_result = 'None'
				#while not dumb_result.startswith("R\x00{}".format(recv_args[1])):
				while not dumb_result.startswith("R"):
					dumb_result = Tglobals.atbackend_server.read_packet_str()
					#///print(f'DUMB {dumb_result}')
				#///print(f'Sended board memory to ATbackend, it responded with {dumb_result}') # просто пустышка, чтобы не отправлять пустое сообщение клиенту - его надо прочитать и убрать тем самым не передавать его в наш буфер
				#///avr_logger.info(f'Sended board memory to ATbackend, it responded with {dumb_result}')



				# Сообщаем об успешной записи
				#///if len(data)>0:
					#///printf(f'atbackend register updated by avrdevice.py:\nregname={regname}\nregdata={data}')
					#///avr_logger.info(f'atbackend register updated by avrdevice.py:\nregname={regname}\nregdata={data}')
				printf(f'atbackend register PC updated by avrdevice.py:\ndata64={data}')
				avr_logger.info(f'atbackend register PC updated by avrdevice.py:\ndata64={data}')

				# 4.
				# Получаем ответ сами, чтобы получить текущую позицию в программе
				Tglobals.atbackend_server.send(recv)
				result = 'None'
				while not result.startswith("R"):	# R 288  ["Proc_1:58083:6"]
					result = Tglobals.atbackend_server.read_packet_str()
					Tglobals.atmel_client.send(result)

				# 5.
				# Парсим данные и записываем позицию программы в контекст нашего отладчика
				print(result, result.split('\x00'))
				args = result.split('\x00')
				Device_for_debug.Line_position = json.loads(args[3])

				# 6.
				# Передаём далье пустую строку
				recv = ''
				recv_args = recv.split('\x00')
				Tglobals.SOCKET_IO_INTERRUPTED = False
				return recv



		# Запросы на управление отладкой как таковой
		if   recv_args[2] == 'Processes':

			# Во время Processes compute
			# !!!
			# Надо остановить все запущенные треды, что должны работать только во время отладки
			if  recv_args[3] ==  'terminate':		# C 609 Processes terminate "Proc_10"
				#print('\n\n\n')
				#print('ОСТАНАВЛИВАЕМ ВСЕ ПРОЦЕССЫ')
				#print('\n\n\n')
				stop_auto_step()




		# Запросы на вычисление выражений
		if   recv_args[2] == 'Expressions':

			# Во время Expressions compute могут быть разные ситуации
			if  recv_args[3] ==  'compute': # C 2423 Expressions compute "Proc_1:0:0" "C" "$pc=0x0"
											# R 2404  "AAAAAA==" {"ID":"expr_49","ParentID":"Proc_1:0:4","Language":"C","Expression":"$pc=0x0","FormatString":"","Bits":0,"Size":4,"Type":"Sym62","CanAssign":true}
											#   {"Class":1,"Type":"Sym62","BigEndian":false}
											#   {"ID":"Sym62","ID":"Sym62","Name":"dword@PC","Class":4,"TypeClass":1,"Size":4,"Length":0,"Offset":0,"Address":0,"MultiLocation":false}
				# Во время Expressions compute

				# Заменить "Proc_1:0:0" на текущую позицию в программе, котору нам ранее сказал atbackend
				#Line_position 

				# Если это выражение - просто получение информации о ячейке для последующего её изменения
				# то нужно
				# 0. Прервать потоки автоматической приёмо-передачи
				# 1. Передать запрос чтобы получить информацию о ячейке
				# 2. По ответу на запрос (спарсить) узнать что это за ячейка (пока что только регистры)
				# 3. Запомнить ID выражения и название
				# 4. Если это наш регистр - то получить с него данные и отдать atbackend и atmel studio свежую информацию с платы
				# 5. Продолжить потоки (пустить пустую команду дальше)
				if not ('=' in recv_args[6]):	# C 99 Expressions compute "Proc_2:0:0" "C" "r16"
												# R 99  "AA==" {"ID":"expr_9","ParentID":"Proc_2:0:0","Language":"C","Expression":"r16","FormatString":"","Bits":0,"Size":1,"Type":"Sym14","CanAssign":true}
												#              {"Class":1,"Type":"Sym14","BigEndian":false}
												#              {"ID":"Sym14","ID":"Sym14","Name":"byte{registers}@R16","Class":4,"TypeClass":1,"Size":1,"Length":0,"Offset":0,"Address":0,"MultiLocation":false}
					# 0.
					Tglobals.SOCKET_IO_INTERRUPTED = True
					# Ждём, когда недоотправленное сообщение с atbackend_server отпрявится на atmel_client (завершит итерацию)
					clear_last_packages()

					# 1.
					# Передаём запрос на вычисление выражения, чтобы получить ID его регистрации
					Tglobals.atbackend_server.send(recv)
					result = 'None'
					while not result.startswith("R"): 	# R 99  "AA==" {"ID":"expr_9","ParentID":"Proc_2:0:0","Language":"C","Expression":"r16","FormatString":"","Bits":0,"Size":1,"Type":"Sym14","CanAssign":true}
														#              {"Class":1,"Type":"Sym14","BigEndian":false}
														#              {"ID":"Sym14","ID":"Sym14","Name":"byte{registers}@R16","Class":4,"TypeClass":1,"Size":1,"Length":0,"Offset":0,"Address":0,"MultiLocation":false}
						result = Tglobals.atbackend_server.read_packet_str()
						# Пока не передаём окончательный ответ. Потом возможно его придётся изменить
						if not result.startswith("R"):
							Tglobals.atmel_client.send(result)
					recv_args[1] = str(int(recv_args[1])+1)

					# 2.
					# Парсим данные
					args = result.split('\x00')
					# Если таких данных нет, то дальше можно не стараться
					try:
						expr_ID = json.loads(args[4])["ID"]
						name    = json.loads(args[6])["Name"]

						# 3.
						# Если в последующем в неё будут записывать, то запоминаем её
						if json.loads(args[4])["CanAssign"] == True:
							Device_for_debug.Expression_variables.append({"ID":expr_ID, "Name":name})
							print(f'Добавлено новое выражение {(expr_ID, name)}')
							print(Device_for_debug.Expression_variables)

						# 4.
						# Если это регистр - то обновляем данные
						# !!! Так как нам пока известно только как работать с регистрами
						var_name = name.split("@")[1]
						if var_name.startswith("R"):
							regname = var_name
							REG_ID = Device_for_debug.Registers_info[regname]['ID']

							#  4.1
							#  Получаем информацию с платы
							data = bytearray(Device_for_debug.board.ReadRegister([regname, None, None]))
							data = f'"{b64encode(data).decode()}"' # 

							#  4.2
							#  Обновляем контекст atbackend
							Tglobals.atbackend_server.send('C\x00{}\x00Registers\x00set\x00"{}"\x00{}'.format(recv_args[1],  REG_ID,  data))
							Tglobals.atbackend_server.rev_offset    += 1	# Теперь atbackend будет получать команду с номером на 1 меньший, чем он ожидает
							Tglobals.atmel_client.offset 			-= 1	# Теперь atbackend будет оправлять нам в ответ команды с номером на 1 команду большеTglobals.atmel_client.offset -= 1
							#  Получаем развёрнутый ответ от atbackend
							dumb_result = 'None'
							while not dumb_result.startswith("R"): 	# R 99
								dumb_result = Tglobals.atbackend_server.read_packet_str()

							#  4.3
							#  изменяем пакет с ответом, чтобы передать на atmel studio свежую информацию
							#!!!
							args[1] = str(int(args[1])+1) #  !!! вычитаем 1 потому что мы применили смещение до того, как отправили ответ
							args[3] = data
							result = '\x00'.join(args)

					except Exception as e:
						print(f'Либо это не наш регистр,  либо просто что-то пошло не так и выдало ошибку: {e}')

					Tglobals.atmel_client.send(result)

					# 5.
					# Так как команда уже исполнена, то дальше посылаем пустую команду
					recv = ''
					recv_args = recv.split('\x00')
					Tglobals.SOCKET_IO_INTERRUPTED = False

					return recv



				if '=' in recv_args[6]:
					# Разрешаем такие запросы только в слуае
					# C 2015 Expressions compute "Proc_8:58083:14" "C" "*((unsigned char*) 59)=4"
					# то есть присвоения конкретным яейкам памяти
					# Реализуется во время
					# - присвоения портам I/O в отдельном окне

					# Во время таких запросов
					# 0. Останавливаем приёмо-передачу
					# 1. Парсим данные запроса
					# 2. Записываем данные в МК AVR на основе этих данных
					# 3. Перезаписываем запрос, чтобы он содержал новые данные, полученные с МК AVR 	!!! МОЖЕТ НЕ СРАБОТАТЬ, Т.К. atbackend МОЖЕТ САМ ПРОВОДИТЬ ПРОВЕРКУ С РВВ
					# 4. передаём его дальше
					if "*((unsigned char*) " in recv_args[6]:
						# 0.
						Tglobals.SOCKET_IO_INTERRUPTED = True
						# Ждём, когда недоотправленное сообщение с atbackend_server отпрявится на atmel_client (завершит итерацию)
						clear_last_packages()

						# 1.
						# Получаем адрес фчейки SRAM
						row_expression = recv_args[6].replace('*((unsigned char*) ',"").replace(')','').replace('"','')
						print(row_expression)
						SRAM_addr = int(row_expression.split('=')[0])
						SRAM_val  = int(row_expression.split('=')[1])
						data_in   = bytearray([SRAM_val])

						# 2.
						# Получаем данные с ячейки МК AVR
						data_out = bytearray(Device_for_debug.board.WriteArray('data', data_in, SRAM_addr, 1, 1))[0]	# !!! Всего 1 байт и он храним новое значение ячейки

						# 3.
						# Теперь запрос должен содержать значение данных с МК AVR (вместо исходных)
						recv_args[6] = recv_args[6].replace(f"={row_expression.split('=')[1]}", f"={data_out}")
						recv = '\x00'.join(recv_args)

						# 4.
						Tglobals.SOCKET_IO_INTERRUPTED = False

					else:
						#!!! Не разрешаем такие запросы, потому что они нарушают саму концепцию нашего .py отладчика
						recv_args[6] = f'"prohibited request"'
						recv = '\x00'.join(recv_args)


				# regname = 'PC'
				# REG_ID = Device_for_debug.Registers_info[regname]['ID']

				# for i in range(20):
				# 	print('ЮНОША ПИШЕМ')

				# data = eval(input())
				# #///print('b ',data)	# Сырые данные (bytes в формате str)
				# data = f'"{b64encode(data).decode()}"' # Обновляем нашу информацию о памяти МК AVR в заданном диапазоне адресов и получаем новые значения ВСЕХ ячеек этого диапазона

				# MEM_ID = Device_for_debug.Memory_info['prog']['ID']
				# Tglobals.atbackend_server.send('C\x00{}\x00Memory\x00set\x00"{}"\x00{}\x001\x00{}\x00{}\x00{}'.format(recv_args[1],  MEM_ID,  0, 1, 0, data))
				# Tglobals.atbackend_server.rev_offset    += 1
				# Tglobals.atmel_client.offset -= 1

				# # Считываем её развёрнутый ответ на поставленную нами (.py) задачу
				# dumb_result = 'None'
				# #while not dumb_result.startswith("R\x00{}".format(recv_args[1])):
				# while not dumb_result.startswith("R"):
				# 	dumb_result = Tglobals.atbackend_server.read_packet_str()
				# 	print(f'DUMB {dumb_result}')


				# send = 'E\x00Memory\x00memoryChanged\x00"'+MEM_ID+'"\x00[{"addr":0,"size":1}]'
				# Tglobals.atmel_client.send(send)

				# recv = recv
				# Tglobals.SOCKET_IO_INTERRUPTED = False

			# Если получили команду о присвоении некоторому выражению числа
			# то нужно
			# 0. Прервать потоки автоматической приёмо-передачи
			# 1. Получить его переменную и значение что нужно присвоить
			# 2. Записать в неё в МК AVR
			# 3. Изменить исходный пакет чтобы передать это значение atbackend
			#    и продолжить приёмо-передачу
			if  recv_args[3] ==  'assign':	# C 102 Expressions assign "expr_11" "12"
				# 0.
				Tglobals.SOCKET_IO_INTERRUPTED = True
				# Ждём, когда недоотправленное сообщение с atbackend_server отпрявится на atmel_client (завершит итерацию)
				clear_last_packages()

				# 1.
				# Получаем информацию о выражении (парсим)
				expr_ID  = recv_args[4][1:-1]
				name 	 = find_dict_by_key_in_dict_list(Device_for_debug.Expression_variables, "ID", expr_ID)["Name"]
				var_name = name.split("@")[1]	# По названию выражения получаем название переменной
				#expr_val = int(recv_args[5][1:-1])		#!!! Не вставляем eval потому что слишком небезопасно
				
				# Если это РОН, то записываем в него
				if var_name.startswith("R"):
					try:
						expr_val = eval(recv_args[5][1:-1])

						# 2.
						# Записали и прочитали результат
						data_out = bytearray(Device_for_debug.board.WriteRegister(bytearray([expr_val]), var_name))	# Всего 1 байт
						print("expr_val",expr_val,bytearray([expr_val]),var_name, Device_for_debug.board.WriteRegister(bytearray([expr_val]), var_name))

						# 3.
						# Изменяем пакеты, чтобы записать в atbackend значения с МК AVR
						recv_args[5] = f'"{data_out[0]}"'	# !!! Записали и прочитали всего 1 байт
						recv = '\x00'.join(recv_args)
						print(f'В выражение записано новое значение регистра {recv}')
						print(Device_for_debug.Expression_variables)
					except Exception as e:
						print(f"Слишком сложное выражение, которое питон не может исполнить ({e}): {recv_args}")

				Tglobals.SOCKET_IO_INTERRUPTED = False

			# Если получили команду об удалении некоторого выражения
			# то нужно
			# 1. Получить его ID
			# 2. Просто его удалить
			if  recv_args[3] ==  'dispose':	# C 53 Expressions dispose "expr_6"
				# 1.
				expr_ID = recv_args[4]
				# 2.
				Device_for_debug.Expression_variables = list(filter(lambda x: x['ID'] != expr_ID, Device_for_debug.Expression_variables))

				print(f'Удалено выражение {recv_args[4]}')
				print(Device_for_debug.Expression_variables)



	return recv

#!!!
def process_atbackend_info(send):
	# Обрабатываем получаемую информацию от atbackend (всего лишь слушаем!!!)
	init_simulator(send)	# Инициализируем вирутальую плату МК AVR
	#sync_breakpoints(send)	# Считываем нынешнее значение точек останова
	#listen_for_memory_change(send)


def init_simulator(send):
	# Проверяем запросы на предмет инициализирующих пакетов.
	# Если таковые имеются, инициализируем Device_for_debug по данным в них
	global Device_for_debug
	args = send.split('\x00')

	if len(args)>=3:
		if   args[1] == 'Device':
			if   args[2] == 'contextAdded': # E Device contextAdded [{"ID":"SimDev_1","Name":"ATmega328P","Session":0,"MemoryIDs":[],"RunControlID":""}]
				device_info = json.loads(args[3])[0]
				Device_for_debug.DeviceId   = device_info['ID']
				Device_for_debug.board_name = device_info['Name']

				avr_logger.info(f'Device name added:\nName: {Device_for_debug.board_name}\nID: {Device_for_debug.DeviceId}')

		elif args[1] == 'Processes':
			if   args[2] == 'contextAdded': # E Processes contextAdded [{"ID":"Proc_1","Name":"C:\\Users\\Owner\\Desktop\\AssemblerApplication1\\AssemblerApplication1\\Debug\\AssemblerApplication1.obj","RunControlId":"RunCtrl_1","Signature":"0x1e950f"}]
				# Запросы с такими ответами atackend'у обычно посылают во время старта дебага проекта
				# В ответе на них как обращаться к симулятору и какая на нём сейчас стоит программа
				proc_info = json.loads(args[3])[0]
				Device_for_debug.RunControlId = proc_info['RunControlId']
				Device_for_debug.ProcessID    = proc_info['ID']
				#!!!
				#Device_for_debug.Try_to_flash(proc_info['Name'], have_preinstalled_bootloader=True)

				avr_logger.info(f'Process intialized:\nRunControlId: {Device_for_debug.RunControlId}\nProcessID: {Device_for_debug.ProcessID}\nprog:\n{Device_for_debug.prog}\n')

		elif args[1] == 'Memory':
			if  args[2] ==  'contextAdded': # E Memory contextAdded [{"ID":"Mem_prog_8","BigEndian":false,"AddressSize":2,"Name":"prog","StartBound":0,"EndBound":32767},{"ID":"Mem_signatures_9","BigEndian":false,"AddressSize":1,"Name":"signatures","StartBound":0,"EndBound":2},{"ID":"Mem_fuses_10","BigEndian":false,"AddressSize":1,"Name":"fuses","StartBound":0,"EndBound":2},{"ID":"Mem_lockbits_11","BigEndian":false,"AddressSize":1,"Name":"lockbits","StartBound":0,"EndBound":0},{"ID":"Mem_data_12","BigEndian":false,"AddressSize":2,"Name":"data","StartBound":0,"EndBound":2303},{"ID":"Mem_eeprom_13","BigEndian":false,"AddressSize":2,"Name":"eeprom","StartBound":0,"EndBound":1023},{"ID":"Mem_io_14","BigEndian":false,"AddressSize":1,"Name":"io","StartBound":0,"EndBound":63}]
				Device_for_debug.Memory_info =	give_mainkey_to_dd(
													give_key_to_ld( json.loads(args[3]), 'Name' ),
													'Name'
												)

				avr_logger.info(f'Memory contextAdded (Memory_info), but actually replaced:\n{Device_for_debug.Memory_info}')

		elif args[1] == 'Registers':
			if  args[2] ==  'contextAdded': # Registers contextAdded [{"ID":"Reg_CYCLE_COUNTER_1","ProcessID":"Proc_1","Name":"CYCLE_COUNTER","Size":8},{"ID":"Reg_PC_2","ProcessID":"Proc_1","Name":"PC","Size":4},{"ID":"Reg_SREG_3","ProcessID":"Proc_1","Name":"SREG","Size":1},{"ID":"Reg_FP_4","ProcessID":"Proc_1","Name":"FP","Size":2},{"ID":"Reg_X_5","ProcessID":"Proc_1","Name":"X","Size":2},{"ID":"Reg_Y_6","ProcessID":"Proc_1","Name":"Y","Size":2},{"ID":"Reg_Z_7","ProcessID":"Proc_1","Name":"Z","Size":2},{"ID":"Reg_SP_8","ProcessID":"Proc_1","Name":"SP","Size":2},{"ID":"Reg_R0_9","ProcessID":"Proc_1","Name":"R0","Size":1},{"ID":"Reg_R1_10","ProcessID":"Proc_1","Name":"R1","Size":1},{"ID":"Reg_R2_11","ProcessID":"Proc_1","Name":"R2","Size":1},{"ID":"Reg_R3_12","ProcessID":"Proc_1","Name":"R3","Size":1},{"ID":"Reg_R4_13","ProcessID":"Proc_1","Name":"R4","Size":1},{"ID":"Reg_R5_14","ProcessID":"Proc_1","Name":"R5","Size":1},{"ID":"Reg_R6_15","ProcessID":"Proc_1","Name":"R6","Size":1},{"ID":"Reg_R7_16","ProcessID":"Proc_1","Name":"R7","Size":1},{"ID":"...
				Device_for_debug.Registers_info = give_mainkey_to_dd(
													give_key_to_ld( json.loads(args[3]), 'Name' ),
													'Name'
												)

				avr_logger.info(f'Registers contextAdded (Reigstrs_info), but actually replaced:\n{Device_for_debug.Registers_info}')

		elif '"Description":"Launch complete"' in send: # P 8 {"Description":"Launch complete","ProgressComplete":0,"ProgressTotal":0}
			# Когда наконец-то инициализация программы закончилась

			Device_for_debug.board = AvrDevice(
													dataClass=Memory,FlashClass=Memory,eepromClass=Memory,
													isize = Device_for_debug.Memory_info["data"]["EndBound"]+1, fsize = Device_for_debug.Memory_info["prog"]["EndBound"]+1, esize = Device_for_debug.Memory_info["eeprom"]["EndBound"]+1,
													coreRegisterSpaceSize=0x020, ioSpaceSize=Device_for_debug.Memory_info["io"]["EndBound"]+1,	# !!!количество регистров при инициализации тоже не прописвывают. Нужно смотреть самому в пакетном файле, а затем в m328p.ini
													PC_step=2,
													COMPortName = Device_for_debug.COM,
													COMBaudRate = Device_for_debug.BAUDRATE
											  )

			avr_logger.info(f'Device initialized:\nBoard name:{Device_for_debug.board_name}\nBoard:\n{Device_for_debug.board}\nProgram:\n{Device_for_debug.prog}')
			avr_logger.info(f'Launch complete')

			print('Специально портим Регистры для проверки реализаци прерываний пакетов чтения-записи')
			#Device_for_debug.board.WriteArray('data', bytearray([(256-(i+1))%0xff for i in range(0xff)]), 0x00, 0x1f, 1)
			#Device_for_debug.board.regs.SetPC(b'\x0E\x00\x00\x00')


# def sync_breakpoints(send):
# 	# Так как после каждого изменения (внесение/удаление) точек останова
# 	#  atmel studio уже следующей командой запрашивает у atbackend инфомацию о точках останова
# 	#  а сам по себе atbackend не меняет точки останова
# 	# То дополнительно запрашивать информацию не имеет смысла - вся актуальная информация лежит в этих пакетах
# 	global Device_for_debug
# 	global Tglobals

# 	recv = Tglobals.LAST_RECV_PACKET
# 	recv_args = recv.split('\x00')

# 	if len(recv_args)>=3:
# 		if   recv_args[2] == 'Breakpoints':

# 			# Во время Memory get нам нужно
# 			# 0. Прервать приёмо-передачу
# 			# 1. Спарсить данные из пакета
# 			# 2. Самим получить данные с платы МК AVR
# 			# 3. Записать их в контекст atbackend
# 			# 4. Теперь с обновлёнными данными в СИМУЛЯТОРЕ (atbackend), передать ему запрос на получение этих обновлённых данных (то есть отпустить неизменённый запрос на чтение дальше по потоку)
# 			if  recv_args[3] ==  'get':



def listen_for_memory_change(send):
	# Проверяем дебаг на предмет пакетов, содержащих информацию об изменениях в Memory или в Registers во время дебага
	global Device_for_debug
	global Tglobals
	# Делаем копию, пока его не стёрли
	last_recv_packet = Tglobals.LAST_RECV_PACKET
	recv_args = last_recv_packet.split('\x00')

	#print(last_recv_packet, recv_args[2], recv_args[3])
	#print(send)
	#print()
	args = send.split('\x00')

	if len(recv_args)>=3:

		if   recv_args[2] == 'Memory':

			# Во время Memory get нам нужно
			# 0. попридержать передачу сообщения
			# 1. самим получать данные с МК AVR с интерисующих atmel studio ячеек
			# 2. записывать их в симулятор
			# 3. 
			if  recv_args[3] ==  'get':	# Memory get "Mem_data_145" 36 1 1 0
										# R 374 "AA=="  []
				...
				# avr_logger.info(f'Process Memory get from server packet:\n{last_recv_packet}')

				# # C N Memory get "[MEM_ID]" [start_address] 1 [number_of_elements] [count_id], count_id 1 - несколько, 0 - один байт. Не обращаем внимание, всё равно пишем в массив
				# # У нас ключ Memory_info это имя памяти, но поиск нужно осуществить по другому полю словаря.
				# # 	Поэтому, чтобы получить имя памяти Memory_info по её идентификатору MEM_ID с помощью функции find_by_another_key
				# #		нужно из итогового под-словарика (записи) выбрать поле 'IDKEY'
				# MEM_ID        = recv_args[4].replace('"','')
				# start_address      = int(recv_args[5])
				# number_of_elements = int(recv_args[7])
				# count_id           = int(recv_args[8])

				# memspace = find_by_another_key(Device_for_debug.Memory_info,'ID',MEM_ID)['IDKEY']	# Находим название адресного пространства по его 'ID'
				
				# print(MEM_ID,
				# 	  hex(start_address),
				# 	  hex(number_of_elements),
				# 	  hex(count_id),
				# 	  memspace)

				# max_address = find_by_another_key(Device_for_debug.Memory_info,'ID',MEM_ID)["EndBound"]	# Получаем максимально допустимый адрес в адресной сетке
				# start_address = start_address % max_address			# Урезаем лишнее, что вылезает за пределы адресной сетки (прокрутились)
				# number_of_elements = number_of_elements - count_id		# Находим реальное количество элементов: зависит от режима, выбранного в count_id

				# data = bytearray(b64decode( args[2].replace('"','') ))	# Декодируем даныне, которые нам отправил сервер-симулятор в ответ на просьбу о предоставлении данных из prog, data или eeprom

				# changed_memory = Device_for_debug.board.WriteArray_DifferentOnly(memspace, data, start_address, number_of_elements, 1) # Вносим изменения в память МК AVR в заданном диапазоне адресов и получаем новые значения ВСЕХ ячеек этого диапазона

				# if len(changed_memory)>0:
				# 	printf(f'Board Memory changed by simulator:\n{memspace}\n{changed_memory}\n')
				# 	avr_logger.info(f'Board Memory changed by simulator:\n{memspace}\n{changed_memory}\n')

				# #avr_logger.info(f'Device state: {Device_for_debug.board}')

			if True:
				pass


		elif recv_args[2] == 'Reigstrs':
			if  recv_args[3] ==  'set':	# Registers set "Reg_R0_89" "AQ=="
										# R 374 "AA=="  []
				reg_info = recv_args[4]
				data     = b64decode( recv_args[5].replace('"','') )

				#Device_for_debug.Memory_info
				...
			
			if  recv_args[3] ==  'set':  # R 374 "AA=="  []
				#recv_args[4]
				#Device_for_debug.Memory_info
				...

			if  recv_args[3] ==  'getm':  # R 24  "AAAAAAAAAAAAAAAAAAAAAAAAAAAA/wgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="
				# C 24 Registers getm [["Reg_CYCLE_COUNTER_1",0,8],["Reg_PC_2",0,4],["Reg_SREG_3",0,1],["Reg_FP_4",0,2],["Reg_X_5",0,2],["Reg_Y_6",0,2],["Reg_Z_7",0,2],["Reg_SP_8",0,2],["Reg_R0_9",0,1],["Reg_R1_10",0,1],["Reg_R2_11",0,1],["Reg_R3_12",0,1],["Reg_R4_13",0,1],["Reg_R5_14",0,1],["Reg_R6_15",0,1],["Reg_R7_16",0,1],["Reg_R8_17",0,1],["Reg_R9_18",0,1],["Reg_R10_19",0,1],["Reg_R11_20",0,1],["Reg_R12_21",0,1],["Reg_R13_22",0,1],["Reg_R14_23",0,1],["Reg_R15_24",0,1],["Reg_R16_25",0,1],["Reg_R17_26",0,1],["Reg_R18_27",0,1],["Reg_R19_28",0,1],["Reg_R20_29",0,1],["Reg_R21_30",0,1],["Reg_R22_31",0,1],["Reg_R23_32",0,1],["Reg_R24_33",0,1],["Reg_R25_34",0,1],["Reg_R26_35",0,1],["Reg_R27_36",0,1],["Reg_R28_37",0,1],["Reg_R29_38",0,1],["Reg_R30_39",0,1],["Reg_R31_40",0,1]]
				#Device_for_debug.Memory_info
				#for el in :
				...





# Должно
# 08 51 05 680: msg recv(c0):C 851 Memory get "Mem_prog_57" 65316 1 220 1
# 08 51 05 680: msg send(c0):R 851 "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="  []

# Есть сейчас
# 07 59 04 846: msg recv(b8):C 819 Memory set 65316 1 220 1 "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
# 07 59 04 846:  Exception: Code (3) Service:  :
# 07 59 04 847: msg send(b8):R 819 {"Code":3}




#-------------------------------------------------------------------------------------
# Есть сейчас
# 07 01 47 677: msg recv(d0):C 598 Expressions compute "Proc_12:0:0" "C" "0x0000,prog"
# 07 01 47 678: msg send(d0):R 598  "AAAAAA==" {"ID":"expr_16","ParentID":"Proc_12:0:0","Language":"C","Expression":"0x0000,prog","FormatString":"prog","Bits":0,"Size":4,"Type":"Sym17","CanAssign":false} {"Class":1,"Type":"Sym17","BigEndian":false} {"ID":"Sym17","ID":"Sym17","Name":"dword{prog}","Class":4,"TypeClass":1,"Size":4,"Length":0,"Offset":0,"Address":0,"MultiLocation":false}
# 07 01 47 687: msg recv(d0):C 599 Memory set 32549 1 219 0 "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
# 07 01 47 687:  Exception: Code (3) Service:  :
# 07 01 47 688: msg send(d0):R 599 {"Code":3}
# Должно



# должно
#Memory set 32549 1 219 0 "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
# А на самом деле
#Memory set 32549 1 219 0 "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
def auto_step_thread():
	...