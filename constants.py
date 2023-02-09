MAX_BUF				= 400	# Максимальное количество байт в сообщении

# this are similar to unix signal numbers, but here used only as number, not
# as signal! See signum.h on unix systems for the values.
GDB_SIGHUP	= 1      # Hangup (POSIX).
GDB_SIGINT	= 2      # Interrupt (ANSI).
GDB_SIGILL	= 4      # Illegal instruction (ANSI).
GDB_SIGTRAP	= 5      # Trace trap (POSIX).

MAX_READ_RETRY	= 50         # Maximum number of retries if a read is incomplete. 
MEM_SPACE_MASK = 0x00ff0000  # mask to get bits which determine memory space 
FLASH_OFFSET   = 0x00000000  # Data in flash has this offset from gdb 
SRAM_OFFSET    = 0x00800000  # Data in sram has this offset from gdb 
EEPROM_OFFSET  = 0x00810000  # Data in eeprom has this offset from gdb 
SIGNATURE_OFFSET = 0x00840000# Present if application used "#include <avr/signature.h>" 

GDB_BLOCKING_OFF = 0         # Signify that a read is non-blocking. 
GDB_BLOCKING_ON  = 1         # Signify that a read will block. 

GDB_RET_NOTHING_RECEIVED = -5 # if the read in non blocking receives nothing, we have nothing todo  
GDB_RET_SINGLE_STEP = -4     # do one single step in gdb loop 
GDB_RET_CONTINUE    = -3     # step until another command from gdb is received 
GDB_RET_CTRL_C       = -2    # gdb has sent Ctrl-C to interrupt what is doing 
GDB_RET_KILL_REQUEST = -1    # gdb has requested that sim be killed 
GDB_RET_OK           =  0     # continue normal processing of gdb requests  
    # means that we should NOT execute any step!!!


# Закрываем сервер после команды выключения сервера?
exitOnKillRequest = True

EIO = b"I DON'T DUCKING KNOW THIS CONSTANT" #!!! I/O error constant




REPL_STATE_START_BYTE = 0
REPL_STATE_READ_DATA_LENGTH_FIRST_BYTE = 1
REPL_STATE_READ_DATA_LENGTH_SECOND_BYTE = 2
REPL_STATE_READ_DATA_LENGTH_THIRD_BYTE = 3
REPL_STATE_READ_DATA_LENGTH_FOURTH_BYTE = 4
REPL_STATE_READ_DATA_CRC_FIRST_BYTE = 5
REPL_STATE_READ_DATA_CRC_SECOND_BYTE = 6
REPL_STATE_READ_COMMAND = 7
REPL_STATE_READ_DATA = 8
REPL_STATE_READ_CRC_FIRST_BYTE = 9
REPL_STATE_READ_CRC_SECOND_BYTE = 10
REPL_STATE_PROCESSING = 11


REPL_COMMAND_NOP = 0
REPL_COMMAND_RUN = 1
REPL_COMMAND_WRITE_FLASH = 2
REPL_COMMAND_WRITE_RAM = 3
REPL_COMMAND_WRITE_EEPROM = 4
REPL_COMMAND_READ_FLASH = 5
REPL_COMMAND_READ_RAM = 6
REPL_COMMAND_READ_EEPROM = 7
REPL_COMMAND_PAUSE = 8
REPL_COMMAND_WRITE_AND_REWRITE_FLASH = 9
REPL_COMMAND_STEP = 10
REPL_COMMAND_SET_BREAKPOINT = 11
REPL_COMMAND_DELETE_ALL_BREAKPOINTS = 12
REPL_COMMAND_DELETE_BREAKPOINTS = 13
REPL_COMMAND_READ_NEAR_PC = 14
REPL_COMMAND_RUN_NOT_FROM_BREAKPOINT = 15
REPL_LAST_COMMAND = 15

REPL_START_BYTE = 0xb7
REPL_CRC_LENGTH = 2
REPL_CRC_START_VALUE = 0xffff
REPL_RESPONSE_BASE_PART_SIZE = 45
REPL_DATA_LENGTH = 2