'''
Замечания:
1) Из-за того, что информацию о необходимом файле мы получаем посредством чтения сообщений, а для кривых ASCII сообщений
   расшифровку автор данной программы ещё не придумал, то
   (!!!) Все файлы и пути к ним не должны содержать не ASCII символы
'''
import socket
# threading
import threading
from queue import Queue
import argparse
import sys
import socket
import sys

from avr_error import *
from DEBUG_HANDLER import *

ATMEL_STUDIO_ADDRESS = ("127.0.0.1",4711)
ATBACKDEN_ADDRESS    = ("127.0.0.1",4712)

GLOBAL_PRINT_DEBUG = True     # Выводим ли на экран побочную информацию?
GLOBAL_PRINT_DEBUG1= True     # Выводим ли на экран побочную информацию?
GLOBAL_RECV_MSG    = Queue()  # очередь сообщений, полученных от Atmel Studio
GLOBAL_SENT_MSG    = Queue()  # очередь сообщений, полученных от atbackand.exe


def printf(*args,**kwargs):
	# Функция вывода на экран строки, если в данный момент утверждение GLOBAL_PRINT_DEBUG справедливо
	if GLOBAL_PRINT_DEBUG:
		print(*args,**kwargs)

def printf1(*args,**kwargs):
	# Функция вывода на экран строки, если в данный момент утверждение GLOBAL_PRINT_DEBUG справедливо
	if GLOBAL_PRINT_DEBUG1:
		print(*args,**kwargs)



class atmel_studio_connection(socket.socket):
	def __init__(self,address):
		super().__init__(socket.AF_INET, socket.SOCK_STREAM)
		self.bind(address)
		self.listen(1)
		self.conn, self.addr = self.accept()
		self.setblocking(0)
		avr_logger.info("Connection to server estabilished")
		printf("Connection to server estabilished")


		# Разница между номером принимаемового пакета и отправляемового
		self.offset = int(0)


		self.bigbuff = Queue()		# Буфер принятых пакетов
		self.ImWritingDontFuckingInterruptMe = False
		self.DontFuckingStartToWriteImErasing = False

		def read_thread():
			while True:
				# считываем вплоть до TL;DR
				buf = bytearray(0)
				while not buf.endswith(b'\x00\x03\x01'):
					buf += self.conn.recv(1024)		# На удивления, он читает только до TL;DR (\x00\x03\x01)

				res = buf.replace(b'\x00\x03\x01',b'\n')[:-1].decode(errors='backslashreplace')	# переводим байты в строку и заменяем 3 символа TL;DR на \n. Последний TL;DR убираем

				for pkt_str in res.split('\n'):
					self.bigbuff.put_nowait(pkt_str) 		# Сохраняем принятые пакеты

				if not res=='':
					avr_logger.info(f"pre__recv {res}")
					printf(f"pre__recv {res}")


				if Globals_info.exit:	# Завершаем
					sys.exit(); print('EXITED')
					return False

		self.thread = threading.Thread(target=read_thread, daemon=False)
		self.thread.start()

	def read_packet_str(self):
		res = ''
		if not len(self.bigbuff.queue)==0:
			res = self.bigbuff.get()

			avr_logger.info(f"pop__recv {res}")
			printf(f"pop__recv {res}")
		return res

	"""
	def send(self, pkt_str):
		if not pkt_str=='':
			b = bytearray(0)
			for pkt in pkt_str.split('\n'):			# Может быть так, что мы считали одновременно несколько сообщений за раз в одном пакете, однако все они разделены символом \n
				b = pkt.encode()+b'\x00\x03\x01'
				self.conn.sendall(b)

			if not pkt_str=='':
				avr_logger.info(f"post_send {pkt_str}")
				printf(f"post_send {pkt_str}")
	"""

	def send(self, pkt_str):
		printf(f"send2 {pkt_str}")
		if not pkt_str=='':
			b = bytearray(0)
			for pkt in pkt_str.split('\n'):			# Может быть так, что мы считали одновременно несколько сообщений за раз в одном пакете, однако все они разделены символом \n
				# Добавляем смещение к номеру возвращаемового пакета
				args = pkt.split('\x00')
				try:
					args[1] = str(int(args[1])+self.offset)
					pkt = '\x00'.join(args)
				except Exception as e:
					print(f'Offset excepted: {e}')
				print('offsetted',pkt)

				b = pkt.encode()+b'\x00\x03\x01'
				self.conn.sendall(b)

				avr_logger.info(f"post_send {pkt}")
				printf(f"post_send {pkt}")

	def send_without_offset(self, pkt_str):
		printf(f"send2 {pkt_str}")
		if not pkt_str=='':
			b = bytearray(0)
			for pkt in pkt_str.split('\n'):			# Может быть так, что мы считали одновременно несколько сообщений за раз в одном пакете, однако все они разделены символом \n
				print('nonoffsetted',pkt)

				b = pkt.encode()+b'\x00\x03\x01'
				self.conn.sendall(b)

				avr_logger.info(f"post_send {pkt}")
				printf(f"post_send {pkt}")

#global Tglobals.atmel_client
#!!!Tglobals.atmel_client = atmel_studio_connection(ATMEL_STUDIO_ADDRESS) # клиент, подключённый к Atmel Studio. Tglobals.atmel_client


class atbackend_connection(socket.socket):
	def __init__(self,address):
		super().__init__(socket.AF_INET, socket.SOCK_STREAM)
		self.connect(address)
		self.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
		avr_logger.info("Connection to client estabilished")
		printf("Connection to client estabilished")

		# Обратное смещение - излишне
		self.rev_offset = int(0)


		self.last_packet: str		# последний принятый, отформатированный в строку пакет

		self.bigbuff = Queue()		# Буфер принятых пакетов
		def read_thread():
			while True:
				# считываем вплоть до TL;DR
				buf = bytearray(0)
				while not buf.endswith(b'\x00\x03\x01'):
					buf += self.recv(1024)

				res = buf.replace(b'\x00\x03\x01',b'\n')[:-1].decode(errors='backslashreplace')	# переводим байты в строку и заменяем 3 символа TL;DR на \n. Последний TL;DR убираем

				for pkt_str in res.split('\n'):
					self.bigbuff.put_nowait(pkt_str)		# Сохраняем принятый пакет

				if not res=='':
					avr_logger.info(f"pre__send {res}")
					printf(f"pre__send {res}")

				if Globals_info.exit:	# Завершаем
					sys.exit(); print('EXITED')
					return False

		self.thread = threading.Thread(target=read_thread, daemon=False)
		self.thread.start()


	def read_packet_str(self):
		res = ''
		# Из-за долгой пересылки между тредами, таким операции лучше не делать лишний раз
		if not len(self.bigbuff.queue)==0:
			res = self.bigbuff.get()

			avr_logger.info(f"pop__send {res}")
			printf(f"pop__send {res}")
		return res

	def send(self, pkt_str):
		printf(f"recv2 {pkt_str}")
		if not pkt_str=='':
			b = bytearray(0)
			for pkt in pkt_str.split('\n'):			# Может быть так, что мы считали одновременно несколько сообщений за раз в одном пакете, однако все они разделены символом \n
				# Добавляем смещение к номеру возвращаемового пакета
				self.last_packet = pkt
				args = pkt.split('\x00')
				try:
					args[1] = str(int(args[1])+self.rev_offset)
					pkt = '\x00'.join(args)
				except Exception as e:
					print(f'Offset excepted: {e}')

				b = pkt.encode()+b'\x00\x03\x01'
				self.sendall(b)

				avr_logger.info(f"post_recv {pkt_str}")
				printf(f"post_recv {pkt_str}")

	"""
	def send_with_offset(self,
						 number,			# Номер строки, который сейчас стоит на месте {0}
						 pkt_to_format		# Строка формата "R {0} ..."
						):
		printf(f"recv2 {number} {pkt_to_format}")
		pkt = pkt_to_format.format(number+self.offset)
		printf(f"recv2_with_offset {pkt}")
		if not pkt=='':
			b = bytearray(0)
			for pkt in pkt_str.split('\n'):			# Может быть так, что мы считали одновременно несколько сообщений за раз в одном пакете, однако все они разделены символом \n
				b = pkt.encode()+b'\x00\x03\x01'
				self.sendall(b)

				avr_logger.info(f"post_recv_with_offset {pkt_str}")
				printf(f"post_recv_with_offset {pkt_str}")
	"""

#Tglobals.atbackend_server = atbackend_connection(ATBACKDEN_ADDRESS,timeout_regular=0.5,timeout_slow=3,timeout_fast=10**(-1))
#global Tglobals.atbackend_server
#!!!Tglobals.atbackend_server = atbackend_connection(ATBACKDEN_ADDRESS)



# И никаких глобальных переменных не надо!
def get_recv_from_atmel_studio():
	global Tglobals
	while True:
		#print(Tglobals.SOCKET_IO_INTERRUPTED)
		if not Tglobals.SOCKET_IO_INTERRUPTED:
			recv = Tglobals.atmel_client.read_packet_str()
			args = recv.split('\x00')

			Tglobals.LAST_RECV_PACKET = recv
			
			recv = handle_atmel_requests(recv)

			# Если сообщение похоже на сообщение сервиса 'runControl'
			#if len(args)>=3:
			#	if args[2]=='RunControl':
					


			if not recv=='':
				#avr_logger.info(f"recv {recv}")
				printf(f"recv1 {recv}")
				Tglobals.atbackend_server.send(recv)


			if Globals_info.exit:	# Завершаем
				sys.exit(); print('EXITED')
				return False



# atbackend_server -> atmel_client
def send_from_atbackend():
	while True:
		if not Tglobals.SOCKET_IO_INTERRUPTED:
			send = Tglobals.atbackend_server.read_packet_str()

			process_atbackend_info(send)

			if not send=='':
				#avr_logger.info(f"send {send}")
				#printf(f"send {send}")
				Tglobals.atmel_client.send(send)

			if Globals_info.exit:	# Завершаем
				sys.exit(); print('EXITED')
				print('EXITED')
				return False



def main():
	'''
	Главная функция запуска сервера и цикл обработки пакетов
	'''

	parser = argparse.ArgumentParser(description='Программа для связи с atmel studio через atbackend')
	parser.add_argument('--COM', type=str,
					help='COM порт к которому подключена отлаживаемая плата')
	parser.add_argument('--Baud_rate', type=int,
					help='Baud rate отлаживаемой платы для общения по Serial')
	parser.add_argument('--atbackend_path', type=str,
					help='Полный путь до симулятора atbackend.exe. Находится в папке приложения Atmel Studio. Как правило по адресу C\\...\\Atmel\\Studio\\7.0\\atbackend\\atbackend.exe')

	parser.add_argument('--atmel_port', type=int,
					help='TCP порт для общения с atmel studio')
	parser.add_argument('--atbackend_port', type=int,
					help='TCP порт для общения с atbackend')

	global Globals_info

	args = parser.parse_args()
	if args.COM is not None:
		Globals_info.COM	  = args.COM
		Globals_info.BAUDRATE = args.Baud_rate
		Globals_info.atmel_port		= args.atmel_port
		Globals_info.atbackend_port = args.atbackend_port
	print(f"Globals_info.COM {args.COM}")

	init_device()
	
	from subprocess import Popen, PIPE, CREATE_NEW_CONSOLE

	#print('Starting subprocess')
	#process = Popen([args.atbackend_path, f'/connection-port={args.atbackend_port}'], stdout=PIPE, stderr=PIPE, shell = True)
	#process = Popen([args.atbackend_path, f'/connection-port={args.atbackend_port}'], creationflags=CREATE_NEW_CONSOLE)
	#stdout, stderr = process.communicate()

	Tglobals.atmel_client     = atmel_studio_connection(("127.0.0.1",Globals_info.atmel_port)) # клиент, подключённый к Atmel Studio. Tglobals.atmel_client
	Tglobals.atbackend_server = atbackend_connection(("127.0.0.1",Globals_info.atbackend_port))



	recv_thread = threading.Thread(target=get_recv_from_atmel_studio, daemon=False)
	send_thread = threading.Thread(target=send_from_atbackend, daemon=False)
	recv_thread.start()
	send_thread.start()


	while True:
		if Globals_info.exit:	# Завершаем
			#Tglobals.atmel_client.shutdown(socket.SHUT_RDWR)	# socket.SHUT_RDWR
			#Tglobals.atmel_client.close()
			#Tglobals.atbackend_server.shutdown(socket.SHUT_RDWR)
			#Tglobals.atbackend_server.close()
			print('EXITED')
			sys.exit(); print('EXITED')
			return False

	


if __name__ == "__main__":
	main()