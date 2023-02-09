"""
Общее описание
  COM_interface, avr_dude_interface 	- логика железа

  /\
  ||
  \/

  Memory, AdvancedRegisters				- логика отдельных элементов МК AVR

  /\
  ||
  \/

  AvrDevice 							- логика платы в целом



Содержит

Прямой интерфейс  для работы с платой МК AVR по шине USB через COM serial порт (COM_interface)
	- COM_interface
		- ...


Виртуальный интерфейс для работы с памятью платы МК AVR (адресуемая ячейка - 1 байт), который содержит
	- информацию об адресном пространстве памяти
		- size     - размер памяти в байтах
		- endian   - порядок байтов в памяти
		- memspace - название адресного пространства (data, eeprom, flash, ...)
	- буфер, хранящий копию массива данных с МК AVR
		- self
	- функции, реализующие взаимодействие программиста с памятью платы МК AVR по средством геттеров сеттеров
		- WriteArray(), WriteArray_DifferentOnly() - запись отдельного массива ячеек памяти
		- ReadArray() 							   - чтение отдельного массива ячеек памяти



Виртуальный интерфейс для работы со специальными регистрами МК AVR, который содержит
	- SREG, SP, PC   - копии последних данных о специальных регистрах с МК AVR
	- Get..., Set... - функции, реализующие взаимодействие программиста со специальными регистрами платы МК AVR по средством геттеров сеттеров


Интерфейс для работы с платой МК AVR, который содержит
	- name - название платы ("ATmega328P")

	- coreRegisterSpaceSize, ioSpaceSize - информацию о том, как разделена память data/SRAM (сколько байт ушло на РОН и сколько байт ушло на РВВ)
	- data, flash, eeprom, regs          - интерфейсы памяти с буферами данных;
										   виртуальная копию различных адресных пространств МК AVR (интерфейс для работы с ними),
										   а так же виртуальная копию служебных регистров МК AVR (интерфейс для работы с ними),
										   и информация о них
	- WriteArray(), WriteArray_DifferentOnly(), ReadArray() - интерфейсы, обобщающуе запросы интерфейсов памяти МК AVR
															  (в аргументах функции добавляется только название адресного пространства)

															  При обращении к памяти рекомендуется использовать именно эти функции
	- Reset() - запрос/функция перезапуска контроллера
	- Step()  - запрос/функция исполнения ровно 1й команды контроллера
				Проверка точек останова происходит в самом интерфейсе (на стороне программы-сервера avrdevice.py).
				То есть во время запуска Step()
					- сервер отсылает запрос на исполнения команды МК
					- сервер отсылает запрос на получение информации о текущем состоянии PC
					- сервер проверяет, находится ли текущий PC в точках дебага
					- если да, то запрещаем использовать Step(), пока не обработаем точку останова (поднимается флаг self.IsPaused)
				Замечание:
				- В отличие от обычной работы МК AVR,
				  МК AVR с прерыванием SuperDuperAvrDebbuger.asm после каждой команды будет ожидать разрешение на исполнение следующей (кроме тех случаев, когда прерывания запрещены)

	- InsertBP(), RemoveBP() - функции редактирования точек останова

"""

from numpy import *
from avr_error import *
from base64 import b64encode, b64decode
import serial
import time

# Общие функции и константы
MAX_ADDRES_SIZE_LEN = 4	# 4 цифры
def normalized_hex(a,LEN):
	return hex(a).replace('0x','0x'+'0'*(LEN+2-len(hex(a))))
def raw_hex(a):
	return hex(a).replace('0x','')

COM = 'COM3'
BAURDATE = 76800
START_BYTE = b'_'


class COM_interface():
	def __init__(self,
				 portname='None',
				 baudrate=76800,
				 isize=0x900,fsize=0x8000,esize=0x400
				):
		#self.portname = portname
		#self.baudrate = baudrate
		if portname != 'None':
			self.COM = serial.Serial(portname, baudrate)
			time.sleep(1)
			# Читаем 
			response = b'None'
			try:
				while not response==START_BYTE:
					response = self.COM.read(1)
					print(f'Ответ от платы на открытие порта: {response}')
			except Exception as e:
				assert False, f'По данному порту нет плат для отладки {e}'

		
		self.PC_size = 2
		...

		self.prog 	= bytearray(fsize)
		self.data 	= bytearray(isize)
		self.eeprom	= bytearray(esize)
		self.SREG   = bytearray(1)
		self.PC     = bytearray(10)
		self.SP     = bytearray(10)
		self.SW     = bytearray(10)
		self.CYCLE_COUNTER = bytearray(10)

	def _any_to_bytearray(
						  self,
						  val,				# - переменная
						  size=1,			# - её размер
						  endian='big'		# - порядок байт для перевода
						 ):
		"""
		Приводит int, bytes и bytearray к единому формату bytearray
		"""
		if type(val)==int:
			return bytearray(val.to_bytes(size, byteorder=endian))

		if type(val)==bytes:
			return bytearray(val[0:size])

		if type(val)==bytearray:
			return val[0:size]


	def WriteByte(
				  self,
				  memspace: str,		# - адресное пространство в которое происходит запись
				  addr: int,			# - адрес ячейки для записи в этом пространстве
				  val: bytearray 		# - 1 байт, который мы туда запишем
				 ):

		if   memspace=='prog':
			# !!!
			# !!! Запись в prog не реализована
			#     поэтому просто читаем
			# b'p\x00\x00'
			self.COM.write( bytearray([b'p'[0], (addr>>8)&0xff, addr&0xff ]) )
			val = self.COM.read(1)	# Ответ - 1 байт который прочитали
			
			self.prog[addr] = val[0]
			return self.prog[addr]

		elif memspace=='data':
			# !!!
			# b'w\x01\x00\xAA'
			self.COM.write( bytearray([b'w'[0], (addr>>8)&0xff, addr&0xff, val[0] ]) )
			val = self.COM.read(1)	# Ответ - 1 байт который записали

			self.data[addr] = val[0]
			return self.data[addr]

		elif memspace=='eeprom':
			# !!!
			# !!! Ни запись, ни чтение из eeprom не реализовано
			self.eeprom[addr] = val[0]
			return self.eeprom[addr]


	def ReadByte(
				 self,
				 memspace: str,			# - адресное пространство из которого читаем
				 addr: int 				# - адрес ячейки, которую читаем
				):

		if   memspace=='prog':
			# !!!
			# b'p\x00\x00'
			self.COM.write( bytearray([b'p'[0], (addr>>8)&0xff, addr&0xff ]) )
			prog = self.COM.read(1)	# Ответ - 1 байт который прочитали
			
			self.prog[addr] = prog[0]
			return prog[0]

		elif memspace=='data':
			# !!!
			# b'r\x01\x00'
			self.COM.write( bytearray([b'r'[0], (addr>>8)&0xff, addr&0xff ]) )
			data = self.COM.read(1)	# Ответ - 1 байт который прочитали
			
			self.data[addr] = data[0]
			return data[0]

		elif memspace=='eeprom':
			# !!!
			# !!! Чтение из eeprom не реализовано
			eeprom = self.eeprom[addr]
			return eeprom


	def WritePC(
				self,
				val: int,		#  сожалению так проще всего
				PC_size: int
			   ):
		# пока что на уровне МК AVR реализовано только для PC_size=2
		# !!!
		# Урезаем до размера, который сможем вместить
		#data_in = int.from_bytes(val[0:self.PC_size], val, byteorder=self.PC_endian, signed=False)
		# !!!
		print(val)
		val = val // 2
		bytes_in = int.to_bytes(val, self.PC_size, byteorder='big')		# Переводим исходное число в байт-массив требуемового формата
		# self.PC  = 	bytes_in
		#!!! Пока что реализуем только чтение
		# b'o'
		self.COM.write( bytearray([b'o'[0]]) )
		#self.PC = self.COM.read(2)

		PC = int.from_bytes(self.PC, byteorder='big')*2
		self.PC = bytearray( [(PC>>8)&0xff, PC&0xff] )

		print('\n\n\n')
		print("PC IS FAKE")
		print(self.PC)
		print('\n\n\n')

		#int_out   = int.from_bytes(self.PC, byteorder='big')	# Переводим PC в целое число
		#bytes_out = int.to_bytes(int_out, PC_size, byteorder='big')		# Переводим это целое число его в байт-массив требуемового формата
		bytes_out = bytearray( [self.PC[1], self.PC[0], 0, 0] )
		return bytes_out

	def ReadPC(
				self,
				PC_size: int
			  ):
		# !!!
		#PC = self.PC
		# b'o'
		self.COM.write( bytearray([b'o'[0]]) )
		self.PC = self.COM.read(2)
		print('\n\n\n')
		print("PC IS FAKE")
		print(self.PC)
		print('\n\n\n')

		PC = int.from_bytes(self.PC, byteorder='big')*2
		self.PC = bytearray( [(PC>>8)&0xff, PC&0xff] )

		#int_out   = int.from_bytes(self.PC, byteorder='big')	# Переводим PC в целое число
		#bytes_out = int.to_bytes(int_out, PC_size, byteorder='big')		# Переводим это целое число его в байт-массив требуемового формата
		bytes_out = bytearray( [self.PC[1], self.PC[0], 0, 0] )
		return bytes_out


	def WriteSREG(
				self,
				val: bytearray
			   ):
		# !!!
		# b'U\xab'
		self.COM.write( bytearray([b'U'[0], val[0]]) )
		val = self.COM.read(1)
		self.SREG = val
		return self.SREG

	def ReadSREG(
				self
			  ):
		# !!!
		# b'u'
		self.COM.write( bytearray([b'u'[0]]) )
		self.SREG = self.COM.read(1)
		SREG = self.SREG
		return SREG


	def WriteSP(
				self,
				val: bytearray
			   ):
		# !!!
		# b'A\xab\xcd'
		self.COM.write( bytearray([b'A'[0], val[1], val[0]]) )	# Перевели из little endian в big endian
		val = self.COM.read(2)						# в формате big endian
		val = bytearray( [val[1], val[0]] )	# перевели в формат little endian
		self.SP = val
		return self.SP

	def ReadSP(
				self
			  ):
		#!!!
		# b'a'
		self.COM.write( bytearray([b'a'[0]]) )
		SP = self.COM.read(2)				# в формате big endian
		SP = bytearray( [SP[1], SP[0]] )	# перевели в формат little endian
		self.SP = SP 	# Синхронизировали виртуальный контекст с контекстом МК AVR
		return SP


	def WriteSW(
				self,
				val: bytearray
			   ):
		# !!!
		#!!! Stop Watch пока что не реализовано
		self.SW = val
		return self.SW

	def ReadSW(
				self
			  ):
		# !!!
		#!!! Stop Watch пока что не реализовано
		SW = self.SW
		return SW


	def Reset(self):
		# Ничего не делаем - нужно для проверки
		pass

	def Step(self):
		# Step
		# !!!
		# b's'
		self.COM.write( b's' )
		return True		# просто возвращаем хоть что-то



	def get_str(self,FROM=-1,TO=-1,data_space="iRAM",columns=1,byte_interpretation="1-byte Integer",display="Hexadecimal Display"):
		"""
			Функция, возвращающая строку с ячейками памяти data_space в формате окна дебага Memory Atmel Studio.
			Во время вызова не синхронизируется с МК,
			синхронизацию с платой требуется выполнять отдельно (вызовом функции self.ReadArray())
			Можно не смотреть, если хотите понять код.
		"""
		"""
		if byte_interpretation=="1-byte Integer":
			size = 1
		elif byte_interpretation=="2-byte Integer":
			size = 2
		elif byte_interpretation=="4-byte Integer":
			size = 4
		elif byte_interpretation=="8-byte Integer":
			size = 8
		elif byte_interpretation=="32-bit Floating Point":
			pass
		elif byte_interpretation=="64-bit Floating Point":
			pass
		"""

		S = ""
		if data_space=="iRAM":
			arr = self.data
			prefix = 'data'
		elif data_space=="FLASH":
			arr = self.prog
			prefix = 'prog'
		elif data_space=="EEPROM":
			arr = self.eeprom
			prefix = 'eeprom'
		if FROM==-1:
			FROM = 0
		if TO==-1:
			TO = len(arr)

		for i in range(FROM,TO,columns):
			S += prefix+' '
			S += f'{normalized_hex(i,MAX_ADDRES_SIZE_LEN)} '
			for j in range(i,i+columns):
				if display=="Hexadecimal Display":
					# Количество нулей (пробелов) перед элементом зависит от количества символов в элементе в выходной строке
					el = raw_hex(arr[j])
					S += '0'*(2-len(el))+el+' '
				if display=="Signed Display":
					el = arr[j]
					if (arr[j])&(1<<7):
						# Если отрицательный, то из доп кода (суммы вычитов по модулю 256) получаем обычное число
						el = el-256
						el = str(el)
					else:
						el = '+'+str(el)
					S += ' '*(4-len(el))+el+' '
				if display=="Unsigned Display":
					el = str(arr[j])
					S += ' '*(3-len(el))+el+' '
			S += '\n'
		return S

	def __str__(self):
		return \
			f"{self.COM}\n" + \
			f"{self.get_str(data_space='FLASH',columns=LOGGING_register_size,display='Hexadecimal Display')}\n" + \
			f"{self.get_str(data_space='EEPROM',columns=LOGGING_register_size,display='Hexadecimal Display')}\n" + \
			f"{self.get_str(data_space='iRAM',columns=LOGGING_register_size,display='Hexadecimal Display')}\n"


# Симулирует общение по COM порту и просто копирует данные в свой контекст
class COM_interface_pseudo():
	def __init__(self,portname):
		self.COM = portname
		self.PC_size = 2
		...

		self.prog 	= bytearray(0x8000*2)
		self.data 	= bytearray(0x900*2)
		self.eeprom	= bytearray(0x400*2)
		self.SREG   = bytearray(1)
		self.PC     = bytearray(10)
		self.SP     = bytearray(10)
		self.SW     = bytearray(10)
		self.CYCLE_COUNTER = bytearray(10)

	def _any_to_bytearray(
						  self,
						  val,				# - переменная
						  size=1,			# - её размер
						  endian='big'		# - порядок байт для перевода
						 ):
		"""
		Приводит int, bytes и bytearray к единому формату bytearray
		"""
		if type(val)==int:
			return bytearray(val.to_bytes(size, byteorder=endian))

		if type(val)==bytes:
			return bytearray(val[0:size])

		if type(val)==bytearray:
			return val[0:size]


	def WriteByte(
				  self,
				  memspace: str,		# - адресное пространство в которое происходит запись
				  addr: int,			# - адрес ячейки для записи в этом пространстве
				  val: bytearray 		# - 1 байт, который мы туда запишем
				 ):

		if   memspace=='prog':
			# !!!
			self.prog[addr] = val[0]
			return self.prog[addr]

		elif memspace=='data':
			# !!!
			self.data[addr] = val[0]
			return self.data[addr]

		elif memspace=='eeprom':
			# !!!
			self.eeprom[addr] = val[0]
			return self.eeprom[addr]


	def ReadByte(
				 self,
				 memspace: str,			# - адресное пространство из которого читаем
				 addr: int 				# - адрес ячейки, которую читаем
				):

		if   memspace=='prog':
			# !!!
			prog = self.prog[addr]
			return prog

		elif memspace=='data':
			# !!!
			data = self.data[addr]
			return data

		elif memspace=='eeprom':
			# !!!
			eeprom = self.eeprom[addr]
			return eeprom


	def WritePC(
				self,
				val: int,		#  сожалению так проще всего
				PC_size: int
			   ):
		# пока что на уровне МК AVR реализовано только для PC_size=2
		# !!!
		# Урезаем до размера, который сможем вместить
		#data_in = int.from_bytes(val[0:self.PC_size], val, byteorder=self.PC_endian, signed=False)
		# !!!
		print(val)
		bytes_in = int.to_bytes(val, self.PC_size, byteorder='big')		# Переводим исходное число в байт-массив требуемового формата
		self.PC  = 	bytes_in

		int_out   = int.from_bytes(self.PC, byteorder='big')	# Переводим PC в целое число
		bytes_out = int.to_bytes(int_out, PC_size, byteorder='little')		# Переводим это целое число его в байт-массив требуемового формата
		return bytes_out

	def ReadPC(
				self,
				PC_size: int
			  ):
		# !!!
		PC = self.PC
		int_out   = int.from_bytes(PC, byteorder='big')	# Переводим PC в целое число
		bytes_out = int.to_bytes(int_out, PC_size, byteorder='little')		# Переводим это целое число его в байт-массив требуемового формата
		return bytes_out


	def WriteSREG(
				self,
				val: bytearray
			   ):
		# !!!
		self.SREG = val
		return self.SREG

	def ReadSREG(
				self
			  ):
		# !!!
		SREG = self.SREG
		return SREG


	def WriteSP(
				self,
				val: bytearray
			   ):
		# !!!
		self.SP = val
		return self.SP

	def ReadSP(
				self
			  ):
		#!!!
		SP = self.SP
		return SP


	def WriteSW(
				self,
				val: bytearray
			   ):
		# !!!
		self.SW = val
		return self.SW

	def ReadSW(
				self
			  ):
		# пока что на уровне МК AVR реализовано только для PC_size=2
		# !!!
		SW = self.SW
		return SW


	def Reset(self):
		# Ничего не делаем - нужно для проверки
		pass

	def Step(self):
		# Step
		# !!!
		return True		# просто возвращаем хоть что-то







class Memory(bytearray):
	"""
	Класс, реализующий устройства памяти, хранящий упорядоченные ячейки памяти
	и операции чтения, записи
	"""
	def __init__(self,
				 size_in_bytes: uint, # размер всего массива в байтах
				 endian=None,         # 'big' или 'little'. Будет учитываться при чтении, если указано при инициализации
				 memspace='',          # хранит имя адрессного пространства (то есть данная память prog, или data, или eeprom)
				 COM = COM_interface('None')
				 ):
		self.size = size_in_bytes
		self.endian = endian
		self.memspace = memspace
		self._COM = COM
		super().__init__(size_in_bytes)

	def WriteArray(self, data: bytearray, start_index, element_count, element_size_in_bytes, endian="little"):
		# Переведено
		'''
		Вход:
		- data: bytearray - массив байтов - данных для записи
		- start_index     - адрес первого элемента
		- element_count   - количество элементов (все они идут по порядку)
		- element_size_in_bytes - размер элементарной ячейки памяти
		- endian          - порядок байтов в элементарной ячейке памяти
							Если он не совпадает с нашим, то для преобразования их в наши данные или обратно
							их нужно инвертировать
		'''

		#!!! Serial_send_write_array(self.memspace, data, start_index, element_count, element_size_in_bytes, endian)
		for i in range(0, element_count, element_size_in_bytes):
			for offset in range(element_size_in_bytes):
				if endian == self.endian:
					# 0,1,2,3,4 <- 0,1,2,3,4
					index_to   = (start_index+i + offset) % self.size # урезаем то, что выходит за границу массива нашего пространства
					index_from = i + offset							  # выход же за границу массива входных данных не допустил бы сам atbackend

					#!!!self[index_to] = data[index_from]
					#!!! Записываем байт в МК AVR
					self[index_to] = self._COM.WriteByte( self.memspace, index_to, bytearray([data[index_from]]) )

				else:
					# 0,1,2,3,4 <- 4,3,2,1,0
					index_to   = (start_index+i + offset) % self.size
					index_from = i+element_size_in_bytes - (offset+1)

					#!!!self[index_to] = data[index_from]
					#!!! Записываем байт в МК AVR
					self[index_to] = self._COM.WriteByte( self.memspace, index_to, bytearray([data[index_from]]) )

		return self.ReadArray(start_index, element_count, element_size_in_bytes, endian=endian)

	def WriteArray_DifferentOnly(self, data: bytearray, start_index, element_count, element_size_in_bytes, endian="little"):
		# Переведено
		'''
		Изменяет ячейку памяти, только если её новое значение отличается от старого
		Вход:
		- data: bytearray - массив байтов - данных для записи
		- start_index     - адрес первого элемента
		- element_count   - количество элементов (все они идут по порядку)
		- element_size_in_bytes - размер элементарной ячейки памяти
		- endian          - порядок байтов в элементарной ячейке памяти
							Если он не совпадает с нашим, то для преобразования их в наши данные или обратно
							их нужно инвертировать
		Выход:
		- changed_elements = {       - словарь с произвольным количеством элементов, хранит информацию об изменённых ячейках
			element_address :        - адрес элемента памяти, который мы изменили
			[element_value_before,   - его старое значение
			element_value_before]    - его новое значение
		  }
		'''

		changed_elements = {}

		for i in range(0, element_count, element_size_in_bytes):
			for offset in range(element_size_in_bytes):
				if endian == self.endian:
					# 0,1,2,3,4 <- 0,1,2,3,4
					index_to   = (start_index+i + offset) % self.size # урезаем то, что выходит за границу массива нашего пространства
					index_from = i + offset							  # выход же за границу массива входных данных не допустил бы сам atbackend
					# Проверяем, есть ли изменения
					if self[index_to] != data[index_from]:
						changed_elements[hex(index_to)] = [ hex(self[index_to]), hex(data[index_from]) ]
						
						#!!!self[index_to] = data[index_from]
						#!!!!!! Serial_send_write_byte(self.memspace, byte_addr, byte_val)
						#!!! то есть
						#!!!!!! Serial_send_write_byte(self.memspace, start_index+i+offset, data[i+offset])
						#!!! Записываем байт в МК AVR
						self[index_to] = self._COM.WriteByte( self.memspace, index_to, bytearray([data[index_from]]) )

				else:
					# 0,1,2,3,4 <- 4,3,2,1,0
					index_to   = (start_index+i + offset) % self.size
					index_from = i+element_size_in_bytes - (offset+1)
					# Проверяем, есть ли изменения
					if self[index_to] != data[index_from]:
						changed_elements[hex(index_to)] = [ hex(self[index_to]), hex(data[index_from]) ]
						
						#!!!self[index_to] = data[index_from]
						#!!!!!! Serial_send_write_byte(self.memspace, start_index+i+offset, data[i+element_size_in_bytes - (offset+1)])
						self[index_to] = self._COM.WriteByte( self.memspace, index_to, bytearray([data[index_from]]) )

		return changed_elements

	def ReadArray(self, start_index, element_count, element_size_in_bytes, endian="little") -> bytearray:
		# Переведено

		res = bytearray(element_count)
		#!!! self[start_index:start_index+element_count] = Serial_send_read_array(start_index, element_count, element_size_in_bytes, endian)
		for i in range(0, element_count, element_size_in_bytes):
			for offset in range(element_size_in_bytes):
				if endian == self.endian:
					# 0,1,2,3,4 <- 0,1,2,3,4
					index_to   = i + offset
					index_from = (start_index+i + offset) % self.size

					#!!! Предварительно читаем
					self[index_from] = self._COM.ReadByte( self.memspace, index_from )
					res[index_to] = self[index_from]
				else:
					# 0,1,2,3,4 <- 4,3,2,1,0
					index_to   = i + offset
					index_from = (start_index+i+element_size_in_bytes - (offset+1)) % self.size

					#!!! Предварительно читаем
					self[index_from] = self._COM.ReadByte( self.memspace, index_from )
					res[i + offset] = self[index_from]
		return res

	def Erase(self):
		# Ничего не делаем, т.к. стирать слишком дорого
		super().__init__(self.size_in_bytes)



class AdvancedRegisters:
	def __init__(self,
				 SREG_size=1,
				 SP_size=2,
				 PC_size=4,
				 SW_size=8,
				 endian='little',
				 COM = COM_interface('None')):
		self._COM = COM
		
		self.endian = endian

		self.SREG_size    = SREG_size
		self.SREG         = bytearray(SREG_size)

		self.SP_size      = SP_size
		self.SP           = bytearray(SP_size) # Stack Pointer

		self.PC_size	  = PC_size
		self.PC           = bytearray(PC_size)

		self.SW_size	  = SW_size
		self.SW           = bytearray(SW_size) # Stop Watch time

	def __repr__(self):
		return f'SREG {self.SREG}\nSP   {self.SP}\nPC   {self.PC}\nSW   {self.SW}'

	# 8 bit
	def SetSREG(self,val: bytearray):
		# Переведено
		self.SREG = self._COM.WriteSREG(val) #!!!
		#!!! self.SREG = Serial_send_SREG_write(val)
		return self.SREG

	def GetSREG(self)->bytearray:
		# Переведено
		self.SREG = self._COM.ReadSREG() #!!!
		#!!! self.SREG = Serial_send_SREG_read()
		return self.SREG


	# 16 bit
	def SetSP(self,val: bytearray):
		# Переведено
		self.SP = self._COM.WriteSP(val) #!!!
		#!!! self.SP = Serial_send_SP_write(val)
		return self.SP

	def GetSP(self)->bytearray:
		# Переведено
		self.SP = self._COM.ReadSP() #!!!
		#!!! self.SP = Serial_send_SP_read()
		return self.SP


	# 32 bit
	def SetPC(self,val: bytearray):		#!!! ПОЧЕМУ PC ХРАНИТСЯ В ФОРМАТЕ BIG ENDIAN?			# Должно быть 4, но в atmega328p всего 2 байта
		# Переведено
		int_in = int.from_bytes(val, byteorder='little')
		self.PC = self._COM.WritePC(int_in, self.PC_size) #!!!
		print('\n\n\n')
		print("PC IS REAL")
		print(self.PC)
		print('\n\n\n')
		#!!! self.PC = Serial_send_PC_write(val)
		return self.PC

	def GetPC(self)->bytearray:
		# Переведено
		self.PC = self._COM.ReadPC(self.PC_size)
		print('\n\n\n')
		print("PC IS REAL")
		print(self.PC)
		print('\n\n\n')
		#!!! self.PC = Serial_send_PC_read()
		return self.PC



class AvrDevice:
	"""
		fsize	- размер flash памяти
		esize	- размер eeprom памяти
		isize	- размер iRAM памяти
	"""
	def __init__(self,
				dataClass=Memory,FlashClass=Memory,eepromClass=Memory,
				isize=0x900,fsize=0x8000,esize=0x400,
				coreRegisterSpaceSize=0x020, ioSpaceSize=0x080,
				X_location=26,Y_location=28,Z_location=30,
				PC_step=2,
				endian='little',
				name='ATmega328P',COMPortName=COM,COMBaudRate=BAURDATE
				):
		self.name = name
		self._COM = COM_interface(COMPortName,
								  isize=isize,
								  fsize=fsize,
								  esize=esize)

		self.data 	= dataClass(isize, memspace='data', endian=endian, COM=self._COM)
		self.Flash	= FlashClass(fsize, memspace='prog', endian=endian, COM=self._COM)
		self.eeprom	= eepromClass(esize, memspace='eeprom', endian=endian, COM=self._COM)
		self.regs   = AdvancedRegisters(endian = endian, COM=self._COM)
		self.coreRegisterSpaceSize = coreRegisterSpaceSize	# Сколько байт выделяется на регистры в самом начале
		self.ioSpaceSize           = ioSpaceSize			# Сколько 
		self.PC_step = PC_step				# Указывает размер одной команды в байтах
		#self.IsProgramLoaded = True		# В реализованном классе этот флаг при инициализации должен быть равен False, и только после загрузки программы равен True

		self.X_location,self.Y_location,self.Z_location = X_location,Y_location,Z_location


		self.IsPaused = False 			# Показывает, простаивает ли данная машина или нет. Всегда будет поднят в ситуациях, когда PC заступил на точку останова (BP) или завершения дебага (EP)

		# Отладочная часть
		# Точки останова (Break Points)
		self.BP = []
		# Конечные точки (End Points)
		self.EP = []
		## Флаги останова
		#self.FLAGS = {'Break':False,'End':False}


	def ReadRegister(self, reg_info, endian='little') -> bytearray:
		'''
		Ввод:
			reg_info - 	лист, содержащий информацию о требуемом регистре
						Формат:
							["CYCLE_COUNTER",0,8]
			endian	 - порядок байтов в каждом из регистров
		Вывод:
			b: bytearray - массив даных одного регистра (записаны в порядке endian) формата bytes (НЕ BASE64!!!)
		'''
		reg_name = reg_info[0]					# ['X',1,2], где в регистре 'X' в памяти платы записано b'00AB'
		start_byte_inside_reg = reg_info[1]		# первый байт регистра, который нас интересует информация 

		if reg_info[1] is None:	# Если нам нужно получить все байты регистра
			end_byte_inside_reg = None
		else:					# Иначе реально считаем смещение на основе непустых данных
			end_byte_inside_reg   = start_byte_inside_reg+reg_info[2]		# последний байт = начало + количество байт

		b = bytearray()
		if   reg_name == 'CYCLE_COUNTER':
			# Cycle Counter
			#!!! Пока не знаем что давать

			# Если нужно вывести всё
			if reg_info[1] is None:
				b = bytearray(8)
			else:	# Иначе выводим как обычно
				b = bytearray(8)[ start_byte_inside_reg : end_byte_inside_reg ]	#!!! Пока не знаем что давать

		elif reg_name == 'SP':
			# Stack Pointer
			b = self.regs.GetSP()

		elif reg_name == 'SREG':
			# Status Register
			b = self.regs.GetSREG()

		elif reg_name == 'PC':
			# Program Counter
			b = self.regs.GetPC()

		elif reg_name == 'SW':
			# Stop Watch
			b = self.regs.GetSW()

		elif reg_name == 'FP':
			# Frame Pointer
			b = bytearray(2)	#!!! Пока не знаем что давать

		elif reg_name == 'X':
			# X pointer
			b = self.ReadArray('data', self.X_location, 2, 1, endian=endian)

		elif reg_name == 'Y':
			# Y pointer
			b = self.ReadArray('data', self.Y_location, 2, 1, endian=endian)

		elif reg_name == 'Z':
			# Z pointer
			b = self.ReadArray('data', self.Z_location, 2, 1, endian=endian)

		elif reg_name.startswith('R'):	# Rxx
			# Core Registers
			try:

				addr = int(reg_name[1:])
				b = self.ReadArray('data', addr, 1, 1, endian=endian)

			except Exception as e:

				avr_logger.error(f"Unknown register {reg_name} for board {self.name}",e)
				b = bytearray(0)

		else:
			avr_logger.error(f"Unknown register {reg_name} for board {self.name}",e)
			assert reg_info[1] is None, 'Your reg_info is fully incorrect'
			b = bytearray(end_byte_inside_reg-start_byte_inside_reg)		# Если нужно вывести всё, то прост выдаст ошибку, потому что данные некорректны

		if reg_info[1] is None:	# Если нужно вывести всё
			return b
		else:					# Иначе выводим как обычно
			return b[ start_byte_inside_reg : end_byte_inside_reg ]

	def ReadRegisters(self, regs_infos_list, endian='little') -> bytearray:
		'''
		Ввод:
			regs_infos_list - лист, содержащий информацию о требуемых регистрах
							  Формат:
								[["CYCLE_COUNTER",0,8],["PC",0,4],["SREG",0,1],["FP",0,2],["X",0,2],["Y",0,2],...,["R31",0,1]]
			endian			- порядок байтов в каждом из регистров
		Вывод:
			BYTES: bytearray - массив даных всех регистров (записаны в порядке endian) формата bytes (НЕ BASE64!!!)
		'''

		BYTES = bytearray()
		for reg_info in regs_infos_list:
			BYTES += self.ReadRegister(reg_info, endian=endian)

		return BYTES



	def WriteRegister(self, data, reg_name, endian='little'):
		'''
		Ввод:
			data: bytearray - массив даных для записи формата bytes (НЕ BASE64!!!)
			regsname - название регистра для записи
			endian			- порядок байтов в каждом из регистров
		Вывод:
			b: bytearray - массив даных одного регистра (записаны в порядке endian) формата bytes (НЕ BASE64!!!)
		'''

		b = bytearray()

		if   reg_name == 'CYCLE_COUNTER':
			# Cycle Counter
			b = bytearray(8)	#!!! Пока не знаем что давать

		elif reg_name == 'SP':
			# Stack Pointer
			UINT = int.from_bytes(data, byteorder=endian, signed=False)
			b = self.regs.SetSP(UINT.to_bytes(self.regs.SP_size, byteorder=endian))

		elif reg_name == 'SREG':
			# Status Register
			UINT = int.from_bytes(data, byteorder=endian, signed=False)
			b = self.regs.SetSREG(UINT.to_bytes(self.regs.SREG_size, byteorder=endian))

		elif reg_name == 'PC':
			# Program Counter
			UINT = int.from_bytes(data, byteorder=endian, signed=False)
			b = self.regs.SetPC(UINT.to_bytes(self.regs.PC_size, byteorder=endian))

		elif reg_name == 'SW':
			# Stop Watch
			UINT = int.from_bytes(data, byteorder=endian, signed=False)
			b = self.regs.SetSW(UINT.to_bytes(self.regs.SW_size, byteorder=endian))

		elif reg_name == 'FP':
			# Frame Pointer
			b = bytearray(2)	#!!! Пока не знаем что давать

		elif reg_name == 'X':
			# X pointer
			b = self.WriteArray('data', data, X_location, 2, 1, endian=endian)

		elif reg_name == 'Y':
			# Y pointer
			b = self.WriteArray('data', data, Y_location, 2, 1, endian=endian)

		elif reg_name == 'Z':
			# Z pointer
			b = self.WriteArray('data', data, Z_location, 2, 1, endian=endian)

		elif reg_name.startswith('R'):	# Rxx
			#!!! Нестабильный код - проверить в случае нарушения порядка (byteorder / endian error)
			#if len(data)==1:	# Не хватает
			#	data = bytearray([0x00])+data

			# Core Registers
			try:
				addr = int(reg_name[1:])
				b = self.WriteArray('data', data, addr, 1, 1, endian=endian)
				#print('ADDR!!!!!!!!!!!!!!!!!!!!!!!!!',int(reg_name[1:]))
				#print('data',data)
				#print('b',b)

			except Exception as e:

				avr_logger.error(f"Unknown register {reg_name} for board {self.name}",e)
				b = bytearray(0)

		else:
			avr_logger.error(f"Unknown register {reg_name} for board {self.name}",e)
			b = bytearray(0)

		return b
		



	def WriteArray(self, memspace: str, data: bytearray, start_index, element_count, element_size_in_bytes, endian="little"):
		if   memspace=='prog':
			return self.Flash.WriteArray(data, start_index, element_count, element_size_in_bytes, endian=endian)
		elif memspace=='data':
			return self.data.WriteArray(data, start_index, element_count, element_size_in_bytes, endian=endian)
		elif memspace=='eeprom':
			return self.eeprom.WriteArray(data, start_index, element_count, element_size_in_bytes, endian=endian)
		else:
			avr_logger.error('Unknown Memory space of AVR device: {memspace}')
			return bytes(element_count)


	def WriteArray_DifferentOnly(self, memspace: str, data: bytearray, start_index, element_count, element_size_in_bytes, endian="little"):
		if   memspace=='prog':
			return self.Flash.WriteArray_DifferentOnly(data, start_index, element_count, element_size_in_bytes, endian=endian)
		elif memspace=='data':
			return self.data.WriteArray_DifferentOnly(data, start_index, element_count, element_size_in_bytes, endian=endian)
		elif memspace=='eeprom':
			return self.eeprom.WriteArray_DifferentOnly(data, start_index, element_count, element_size_in_bytes, endian=endian)
		else:
			avr_logger.error('Unknown Memory space of AVR device: {memspace}')
			return bytes(element_count)

	def ReadArray(self, memspace: str, start_index, element_count, element_size_in_bytes, endian="little") -> bytearray:
		if   memspace=='prog':
			return self.Flash.ReadArray(start_index, element_count, element_size_in_bytes, endian=endian)
		elif memspace=='data':
			return self.data.ReadArray(start_index, element_count, element_size_in_bytes, endian=endian)
		elif memspace=='eeprom':
			return self.eeprom.ReadArray(start_index, element_count, element_size_in_bytes, endian=endian)
		else:
			avr_logger.error('Unknown Memory space of AVR device: {memspace}')
			return bytes(element_count)


	def Reset(self):
		# Переведено
		self.data.Erase()
		self.Flash.Erase()
		self.eeprom.Erase()
		self.regs.Erase()
		self.BP = []
		self.EP = []
		S = str(self)
		avr_logger.info(f'Resetted. The data on the system before the erasing was:\n{S}')
		#!!! Serial_send_reset
		self._COM.Reset()
		pass

	def InsertBP(self, BP_address):
		self.BP.append(BP_address)

	def RemoveBP(self, BP_address):
		if BP_address in BP:
			self.BP.remove(BP_address)

	def Step(self):
		# Переведено
		#if self.IsPaused:
		#	avr_logger.error(f'Cant step further, because the current state of ther board is: PC={self.regs.PC} BP={self.BP} EP={self.EP} IsPaused={self.IsPaused}')
		#	return False # Всё не ок

		#!!! Serial_send_step
		self._COM.Step()

		# self.regs.PC = int.to_bytes(
		# 							int.from_bytes(
		# 								self.regs.PC,
		# 								byteorder=self.regs.endian
		# 								)
		# 							+ self.PC_step,
		# 							length=self.regs.PC_size,
		# 							byteorder=self.regs.endian
		# 							)


		#!!! self.regs.PC = Serial_send_read_PC

		# if self.regs.PC in self.BP:
		# 	S = str(self)
		# 	avr_logger.info(f"Достигнута точка останова по адресу PC={self.regs.PC}\n{S}")
		# 	#self.FLAGS['Break'] = True
		# 	#!!! Serial_send_pause
		# 	self.IsPaused = True

		# elif self.regs.PC in self.EP:
		# 	S = str(self)
		# 	avr_logger.info(f"Достигнута точка окончания программы по адресу PC={self.regs.PC}\n{S}")
		# 	#self.FLAGS['End'] = True
		# 	#!!! Serial_send_reset
		# 	self.IsPaused = True

		return True # Всё ок



	# TODO - добавить красивый вывод byte_interpretation
	def get_str(self,FROM=-1,TO=-1,data_space="iRAM",columns=1,byte_interpretation="1-byte Integer",display="Hexadecimal Display"):
		"""
			Функция, возвращающая строку с ячейками памяти data_space в формате окна дебага Memory Atmel Studio.
			Во время вызова не синхронизируется с МК,
			синхронизацию с платой требуется выполнять отдельно (вызовом функции self.ReadArray())
			Можно не смотреть, если хотите понять код.
		"""
		"""
		if byte_interpretation=="1-byte Integer":
			size = 1
		elif byte_interpretation=="2-byte Integer":
			size = 2
		elif byte_interpretation=="4-byte Integer":
			size = 4
		elif byte_interpretation=="8-byte Integer":
			size = 8
		elif byte_interpretation=="32-bit Floating Point":
			pass
		elif byte_interpretation=="64-bit Floating Point":
			pass
		"""

		S = ""
		if data_space=="iRAM":
			arr = self.data
			prefix = 'data'
		elif data_space=="FLASH":
			arr = self.Flash
			prefix = 'prog'
		elif data_space=="EEPROM":
			arr = self.eeprom
			prefix = 'eeprom'
		if FROM==-1:
			FROM = 0
		if TO==-1:
			TO = len(arr)

		for i in range(FROM,TO,columns):
			S += prefix+' '
			S += f'{normalized_hex(i,MAX_ADDRES_SIZE_LEN)} '
			for j in range(i,i+columns):
				if display=="Hexadecimal Display":
					# Количество нулей (пробелов) перед элементом зависит от количества символов в элементе в выходной строке
					el = raw_hex(arr[j])
					S += '0'*(2-len(el))+el+' '
				if display=="Signed Display":
					el = arr[j]
					if (arr[j])&(1<<7):
						# Если отрицательный, то из доп кода (суммы вычитов по модулю 256) получаем обычное число
						el = el-256
						el = str(el)
					else:
						el = '+'+str(el)
					S += ' '*(4-len(el))+el+' '
				if display=="Unsigned Display":
					el = str(arr[j])
					S += ' '*(3-len(el))+el+' '
			S += '\n'
		return S

	def __str__(self):
		return \
			f"{self.name}\n" + \
			f"{self._COM}\n" + \
			f"{self.regs}\n" + \
			f"{self.get_str(data_space='FLASH',columns=LOGGING_register_size,display='Hexadecimal Display')}\n" + \
			f"{self.get_str(data_space='EEPROM',columns=LOGGING_register_size,display='Hexadecimal Display')}\n" + \
			f"{self.get_str(data_space='iRAM',columns=LOGGING_register_size,display='Hexadecimal Display')}\n"


def test():
	a = AvrDevice()
	def test1():
		#a.data[0x100] = 256-5
		a.WriteArray('data', bytearray([256-(i+1) for i in range(6)]), 0x100, 6, 1, endian="little") # l и h в выводе должны быть перепутаны местами
		print(a.get_str(data_space='iRAM',FROM=0x100,TO=0x200,columns=8,display="Signed Display"))
		a.BP.append(2)
		a.Step()
		a.Step()

	def test2():
		# Записывает регистры и выводит их с помощью отдельной функции
		# Тестирует функцию AvrDevice.ReadRegisters
		print([(256-(i+1))%0xff for i in range(0xff)])
		a.WriteArray('data', bytearray([(256-(i+1))%0xff for i in range(0xff)]), 0x00, 0x1f, 1, endian="little") # l и h в выводе должны быть перепутаны местами
		print(a.get_str(data_space='iRAM',FROM=0x00,TO=0x1f,columns=8,display="Hexadecimal Display"))
		req = [['CYCLE_COUNTER', 0, 8], ['PC', 0, 4], ['SREG', 0, 1], ['FP', 0, 2], ['X', 0, 2], ['Y', 0, 2], ['Z', 0, 2], ['SP', 0, 2], ['R0', 0, 1], ['R1', 0, 1], ['R2', 0, 1], ['R3', 0, 1], ['R4', 0, 1], ['R5', 0, 1], ['R6', 0, 1], ['R7', 0, 1], ['R8', 0, 1], ['R9', 0, 1], ['R10', 0, 1], ['R11', 0, 1], ['R12', 0, 1], ['R13', 0, 1], ['R14', 0, 1], ['R15', 0, 1], ['R16', 0, 1], ['R17', 0, 1], ['R18', 0, 1], ['R19', 0, 1], ['R20', 0, 1], ['R21', 0, 1], ['R22', 0, 1], ['R23', 0, 1], ['R24', 0, 1], ['R25', 0, 1], ['R26', 0, 1], ['R27', 0, 1], ['R28', 0, 1], ['R29', 0, 1], ['R30', 0, 1], ['R31', 0, 1]]
		print(a.ReadRegisters(req))

	def test3():
		# Записывает PC, выводит его, затем делает шаг и снова выводит
		# Тестирует функцию AvrDevice.ReadRegisters и AvrDevice.Step
		# Что должно делать
		#     1) Записать PC := 4
		#     2) Вывести PC в порядке little endian bytearray(b'\x04\x00\x00\x00')
		#     3) Сделать шаг PC += 2
		#     4) Вывести PC в порядке little endian bytearray(b'\x06\x00\x00\x00')
		a.regs.SetPC(b'\x04\x00\x00\x00')
		print(a.ReadRegisters([['PC', 0, 4]]))
		a.Step()
		print(a.ReadRegisters([['PC', 0, 4]]))


	test2()
		




if __name__=="__main__":
	test()