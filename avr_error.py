import logging
import datetime

global LOGGING_register_size
LOGGING_register_size = 16 #32


logging.basicConfig(filename=f"logs/PyAVR_avr_log_{str(datetime.datetime.now()).split('.')[0].replace(' ','__').replace(':','.')}.log",
                    format=f"%(asctime)s - [%(levelname)-8s] - %(name)s - (%(filename)s).%(funcName)-25s(%(lineno)-d): %(message)s",
                    filemode='w')

avr_logger = logging.getLogger()
avr_logger.setLevel(logging.DEBUG)	# Пока что без изысков

logging.basicConfig(filename=f"logs/PyAVR_gdb_log_{str(datetime.datetime.now()).split('.')[0].replace(' ','__').replace(':','.')}.log",
                    format=f"%(asctime)s - [%(levelname)-8s] - %(name)s - (%(filename)s).%(funcName)-25s(%(lineno)-d): %(message)s",
                    filemode='w')
gdb_logger = logging.getLogger()
gdb_logger.setLevel(logging.DEBUG)

# logging.basicConfig(filename=f"logs/zPyAVR_COM_log_{str(datetime.datetime.now()).split('.')[0].replace(' ','__').replace(':','.')}.log",
#                     format=f"%(asctime)s - [%(levelname)-8s] - %(name)s - (%(filename)s).%(funcName)-25s(%(lineno)-d): %(message)s",
#                     filemode='w')
# COM_logger = logging.getLogger()
# COM_logger.setLevel(logging.DEBUG)

def avr_warning(msg):
	avr_logger.warning(msg)
def avr_error(msg):
	avr_logger.error(msg)
def avr_info(msg):
	avr_logger.info(msg)

def gdb_info(*args,**kwargs):
	print(*args,**kwargs)
	gdb_logger.info(*args,**kwargs)