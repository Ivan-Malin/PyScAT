import fnmatch
import json
from   copy import deepcopy
from   avr_error import avr_logger

'''
Сокращения:
- ld - list of dicts
- dd - dict of dicts
'''

# НАШ ИССЛЕДУЕМЫЙ ТИП МАССИВОВ:
# 'E Memory contextAdded [{"ID":"Mem_prog_8","BigEndian":false,"AddressSize":2,"Name":"prog","StartBound":0,"EndBound":32767},{"ID":"Mem_signatures_9","BigEndian":false,"AddressSize":1,"Name":"signatures","StartBound":0,"EndBound":2},{"ID":"Mem_fuses_10","BigEndian":false,"AddressSize":1,"Name":"fuses","StartBound":0,"EndBound":2},{"ID":"Mem_lockbits_11","BigEndian":false,"AddressSize":1,"Name":"lockbits","StartBound":0,"EndBound":0},{"ID":"Mem_data_12","BigEndian":false,"AddressSize":2,"Name":"data","StartBound":0,"EndBound":2303},{"ID":"Mem_eeprom_13","BigEndian":false,"AddressSize":2,"Name":"eeprom","StartBound":0,"EndBound":1023},{"ID":"Mem_io_14","BigEndian":false,"AddressSize":1,"Name":"io","StartBound":0,"EndBound":63}]'

# поиск с фильтром по словарю исследуемуемого типа
def find_dict_by_key_in_dict_list(dict_list: list, key_for_search: str, key_filter: str) -> dict:
	'''
	Ввод:
	- лист вида
			[{"ID":"Mem_prog_8","BigEndian":false,"AddressSize":2,"Name":"prog","StartBound":0,"EndBound":32767},...]
		- ключ
			"EndBound"
		- как он должен выглядеть
			"32???"
	Вывод:
		- первый попавшийся словарик с ключом, который так выглядит
			{"ID":"Mem_prog_8","BigEndian":false,"AddressSize":2,"Name":"prog","StartBound":0,"EndBound":32767}
	'''
	#print("0000000000000",dict_list,key_for_search)
	for dic in dict_list:
		#print("AAAAAAAAAAA",dic[key_for_search],key_filter)
		if len(fnmatch.filter( [str(dic[key_for_search])] , key_filter))>0:
			return dic

# поиск нужного словаря в словаре_словарей, содержащего поле key_for_search со значением key_value
def find_by_another_key(dict_of_dicts: dict, key_for_search: str, key_value: str) -> dict:
	# find_dict_by_another_key_in_dict_of_dict
	'''
	Ввод:
		- словарик вида
			{
				"Mem_prog_8" : {"BigEndian":false,"AddressSize":2,"Name":"prog","StartBound":0,"EndBound":32767},
				...
			}
		- ключ
			"BigEndian"
		- его значение
			false
	Вывод:
		- первый попавшийся словарик (запись) с полем key_for_search значение которого равно key_value
		  Значение идентификатора этого словарика, под которым он записан в БОЛЬШОЙ словарик dict_of_dicts
		  будет записан в поле 'IDKEY'
			{
				"Mem_prog_8" : {"BigEndian":false,"AddressSize":2,"Name":"prog","StartBound":0,"EndBound":32767,"IDKEY":"Mem_prog_8"}
			}
	'''
	for dict_key in dict_of_dicts:
		if dict_of_dicts[dict_key][key_for_search] == key_value:
			big_dic = dict_of_dicts[dict_key]
			# PREVIOUS_ID
			big_dic['IDKEY'] = dict_key
			return big_dic

# Добавляет главный ключ строки внутрь самой строки
def give_mainkey_to_dd(dict_of_dicts: dict, main_key_name='IDKEY') -> dict:
	'''
	Ввод:
		- словарик вида
			{
				"Mem_prog_8" : {"BigEndian":false,"AddressSize":2,"Name":"prog","StartBound":0,"EndBound":32767},
				...
			}
	Вывод:
		- словарик вида
			{
				"Mem_prog_8" : {"BigEndian":false,"AddressSize":2,"Name":"prog","StartBound":0,"EndBound":32767,IDKEY:"Mem_prog_8"},
				...
			}
	'''
	dict_of_dicts_old = dict_of_dicts
	dict_of_dicts = deepcopy(dict_of_dicts)
	for dict_key in dict_of_dicts:
		dict_of_dicts[dict_key][main_key_name] = dict_key
	return dict_of_dicts



def give_key_to_ld(dict_list: list, main_key_name: str) -> dict:
	'''
	give_a_key_to_an_element_of_list_of_dicts

	Ввод:
		- лист вида
			[{"ID":"Mem_prog_8","BigEndian":false,"AddressSize":2,"Name":"prog","StartBound":0,"EndBound":32767},...]
		- главный ключ вида
			"ID"
	Вывод:
		- словарик словариков вида
			{
				"Mem_prog_8" : {"BigEndian":false,"AddressSize":2,"Name":"prog","StartBound":0,"EndBound":32767},
				...
			}
	'''
	dict_out  = {}
	dict_list = deepcopy(dict_list)

	for dic in dict_list:
		main_key = dic[main_key_name]
		del dic[main_key_name]

		dict_out[main_key] = dic
	return dict_out

def join_ld_to_list(
							LIST: list, LIST_OF_DICTS: dict,
							index: int, key_to_join: str,
							keys_to_give: list):
	'''
	К исходному листу LIST джойнит столбец листа LIST_OF_DICTS
								   так же разрешается джойнить DICT_OF_DICTS
	(Предполагается, что для каждого элемента LIST найдётся элемент LIST_OF_DICT)
	Джойнит по правилу
		R1 = LIST JOIN LIST_OF_DICT ON index=key_to_join
	
	И после этого делает выборку
		R = R1[все столбцы LIST, keys_to_give0, keys_to_give1, keys_to_give2, ...]

	Ввод:
		- лист вида
			[["Reg_CYCLE_COUNTER_481",0,8],["Reg_PC_482",0,4],["Reg_SREG_483",0,1],["Reg_FP_484",0,2],["Reg_X_485",0,2],["Reg_Y_486",0,2],["Reg_Z_487",0,2],["Reg_SP_488",0,2],["Reg_R0_489",0,1],["Reg_R1_490",0,1],["Reg_R2_491",0,1],["Reg_R3_492",0,1],["Reg_R4_493",0,1],["Reg_R5_494",0,1],["Reg_R6_495",0,1],["Reg_R7_496",0,1],["Reg_R8_497",0,1],["Reg_R9_498",0,1],["Reg_R10_499",0,1],["Reg_R11_500",0,1],["Reg_R12_501",0,1],["Reg_R13_502",0,1],["Reg_R14_503",0,1],["Reg_R15_504",0,1],["Reg_R16_505",0,1],["Reg_R17_506",0,1],["Reg_R18_507",0,1],["Reg_R19_508",0,1],["Reg_R20_509",0,1],["Reg_R21_510",0,1],["Reg_R22_511",0,1],["Reg_R23_512",0,1],["Reg_R24_513",0,1],["Reg_R25_514",0,1],["Reg_R26_515",0,1],["Reg_R27_516",0,1],["Reg_R28_517",0,1],["Reg_R29_518",0,1],["Reg_R30_519",0,1],["Reg_R31_520",0,1]]
		- номер столбца для джойна
			0
		- словарь вида
			[{"ID":"Reg_CYCLE_COUNTER_481","ProcessID":"Proc_13","Name":"CYCLE_COUNTER","Size":8},{"ID":"Reg_PC_482","ProcessID":"Proc_13","Name":"PC","Size":4},{"ID":"Reg_SREG_483","ProcessID":"Proc_13","Name":"SREG","Size":1},{"ID":"Reg_FP_484","ProcessID":"Proc_13","Name":"FP","Size":2},{"ID":"Reg_X_485","ProcessID":"Proc_13","Name":"X","Size":2},{"ID":"Reg_Y_486","ProcessID":"Proc_13","Name":"Y","Size":2},{"ID":"Reg_Z_487","ProcessID":"Proc_13","Name":"Z","Size":2},{"ID":"Reg_SP_488","ProcessID":"Proc_13","Name":"SP","Size":2},{"ID":"Reg_R0_489","ProcessID":"Proc_13","Name":"R0","Size":1},{"ID":"Reg_R1_490","ProcessID":"Proc_13","Name":"R1","Size":1},{"ID":"Reg_R2_491","ProcessID":"Proc_13","Name":"R2","Size":1},{"ID":"Reg_R3_492","ProcessID":"Proc_13","Name":"R3","Size":1},{"ID":"Reg_R4_493","ProcessID":"Proc_13","Name":"R4","Size":1},{"ID":"Reg_R5_494","ProcessID":"Proc_13","Name":"R5","Size":1},{"ID":"Reg_R6_495","ProcessID":"Proc_13","Name":"R6","Size":1},{"ID":"Reg_R7_496","ProcessID":"Proc_13","Name":"R7","Size":1},{"ID":"Reg_R8_497","ProcessID":"Proc_13","Name":"R8","Size":1},{"ID":"Reg_R9_498","ProcessID":"Proc_13","Name":"R9","Size":1},{"ID":"Reg_R10_499","ProcessID":"Proc_13","Name":"R10","Size":1},{"ID":"Reg_R11_500","ProcessID":"Proc_13","Name":"R11","Size":1},{"ID":"Reg_R12_501","ProcessID":"Proc_13","Name":"R12","Size":1},{"ID":"Reg_R13_502","ProcessID":"Proc_13","Name":"R13","Size":1},{"ID":"Reg_R14_503","ProcessID":"Proc_13","Name":"R14","Size":1},{"ID":"Reg_R15_504","ProcessID":"Proc_13","Name":"R15","Size":1},{"ID":"Reg_R16_505","ProcessID":"Proc_13","Name":"R16","Size":1},{"ID":"Reg_R17_506","ProcessID":"Proc_13","Name":"R17","Size":1},{"ID":"Reg_R18_507","ProcessID":"Proc_13","Name":"R18","Size":1},{"ID":"Reg_R19_508","ProcessID":"Proc_13","Name":"R19","Size":1},{"ID":"Reg_R20_509","ProcessID":"Proc_13","Name":"R20","Size":1},{"ID":"Reg_R21_510","ProcessID":"Proc_13","Name":"R21","Size":1},{"ID":"Reg_R22_511","ProcessID":"Proc_13","Name":"R22","Size":1},{"ID":"Reg_R23_512","ProcessID":"Proc_13","Name":"R23","Size":1},{"ID":"Reg_R24_513","ProcessID":"Proc_13","Name":"R24","Size":1},{"ID":"Reg_R25_514","ProcessID":"Proc_13","Name":"R25","Size":1},{"ID":"Reg_R26_515","ProcessID":"Proc_13","Name":"R26","Size":1},{"ID":"Reg_R27_516","ProcessID":"Proc_13","Name":"R27","Size":1},{"ID":"Reg_R28_517","ProcessID":"Proc_13","Name":"R28","Size":1},{"ID":"Reg_R29_518","ProcessID":"Proc_13","Name":"R29","Size":1},{"ID":"Reg_R30_519","ProcessID":"Proc_13","Name":"R30","Size":1},{"ID":"Reg_R31_520","ProcessID":"Proc_13","Name":"R31","Size":1}]
		- название столбца для джойна
			"ID"
		- какте столбцы словаря оставляем после этого
			["Name"]
	Вывод:
		- результат джойна
			'[["Reg_CYCLE_COUNTER_481",0,8,"CYCLE_COUNTER"],["Reg_PC_482",0,4,"PC"],...'
	'''
	LISTold = LIST
	LIST = deepcopy(LIST)
	if   type(LIST_OF_DICTS) == list:
		RANGE = range(len(LIST_OF_DICTS))
	elif type(LIST_OF_DICTS) == dict:
		RANGE = LIST_OF_DICTS.keys()
	else:
		avr_logger.error("Нельзя джойнить к листам подобный лист/словарь:\n[{0}]".format(",\n".join([str(el) for el in LIST_OF_DICTS])))
		return LIST

	for i in range(len(LIST)):
		for j in RANGE:
			if LIST[i][index] == LIST_OF_DICTS[j][key_to_join]:
				for key in keys_to_give:
					LIST[i].append(LIST_OF_DICTS[j][key])

	def check():
	# Проверяет, для всех ли нашлось соответствие
		LEN = len(LISTold[0])+len(keys_to_give)
		unmuchted_elements = []
		for i in range(len(LIST)):
			if len(LIST[i]) != LEN:
				unmuchted_elements.append(LIST[i])
		if not len(unmuchted_elements)==0:
			avr_logger.error(\
"""Во время джойна
листа словарей
[{0}]
к листу
[{1}]
к строкам
[{2}]
листа LIST не нашлось строки листа словарей LIST_OF_DICTS.
В результате получили:
[{3}]
""".format(
		",\n".join([str(el) for el in LIST_OF_DICTS]),
		",\n".join([str(el) for el in LISTold]),
		",\n".join([str(el) for el in unmuchted_elements]),
		",\n".join([str(el) for el in LIST])
	)
	)
	check()

	return LIST



def test():
	def test1():
		send = 'E\x00Memory\x00contextAdded\x00[{"ID":"Mem_prog_8","BigEndian":false,"AddressSize":2,"Name":"prog","StartBound":0,"EndBound":32767},{"ID":"Mem_signatures_9","BigEndian":false,"AddressSize":1,"Name":"signatures","StartBound":0,"EndBound":2},{"ID":"Mem_fuses_10","BigEndian":false,"AddressSize":1,"Name":"fuses","StartBound":0,"EndBound":2},{"ID":"Mem_lockbits_11","BigEndian":false,"AddressSize":1,"Name":"lockbits","StartBound":0,"EndBound":0},{"ID":"Mem_data_12","BigEndian":false,"AddressSize":2,"Name":"data","StartBound":0,"EndBound":2303},{"ID":"Mem_eeprom_13","BigEndian":false,"AddressSize":2,"Name":"eeprom","StartBound":0,"EndBound":1023},{"ID":"Mem_io_14","BigEndian":false,"AddressSize":1,"Name":"io","StartBound":0,"EndBound":63}]'
		args = send.split('\x00')

		list_of_dicts = json.loads( args[3] )
		print( find_dict_by_key_in_dict_list(list_of_dicts,'Name','prog') )
		memory_info = give_key_to_ld(list_of_dicts,'Name')
		print( find_by_another_key(memory_info,'ID','Mem_signatures_9') )
		for memory in memory_info:
			print(f'{memory} : {memory_info[memory]}')

	def test2():
		regs_raw = json.loads( '[["Reg_CYCLE_COUNTER_481",0,8],["Reg_PC_482",0,4],["Reg_SREG_483",0,1],["Reg_FP_484",0,2],["Reg_X_485",0,2],["Reg_Y_486",0,2],["Reg_Z_487",0,2],["Reg_SP_488",0,2],["Reg_R0_489",0,1],["Reg_R1_490",0,1],["Reg_R2_491",0,1],["Reg_R3_492",0,1],["Reg_R4_493",0,1],["Reg_R5_494",0,1],["Reg_R6_495",0,1],["Reg_R7_496",0,1],["Reg_R8_497",0,1],["Reg_R9_498",0,1],["Reg_R10_499",0,1],["Reg_R11_500",0,1],["Reg_R12_501",0,1],["Reg_R13_502",0,1],["Reg_R14_503",0,1],["Reg_R15_504",0,1],["Reg_R16_505",0,1],["Reg_R17_506",0,1],["Reg_R18_507",0,1],["Reg_R19_508",0,1],["Reg_R20_509",0,1],["Reg_R21_510",0,1],["Reg_R22_511",0,1],["Reg_R23_512",0,1],["Reg_R24_513",0,1],["Reg_R25_514",0,1],["Reg_R26_515",0,1],["Reg_R27_516",0,1],["Reg_R28_517",0,1],["Reg_R29_518",0,1],["Reg_R30_519",0,1],["Reg_R31_520",0,1]]' )
		regs_info = json.loads( '[{"ID":"Reg_CYCLE_COUNTER_481","ProcessID":"Proc_13","Name":"CYCLE_COUNTER","Size":8},{"ID":"Reg_PC_482","ProcessID":"Proc_13","Name":"PC","Size":4},{"ID":"Reg_SREG_483","ProcessID":"Proc_13","Name":"SREG","Size":1},{"ID":"Reg_FP_484","ProcessID":"Proc_13","Name":"FP","Size":2},{"ID":"Reg_X_485","ProcessID":"Proc_13","Name":"X","Size":2},{"ID":"Reg_Y_486","ProcessID":"Proc_13","Name":"Y","Size":2},{"ID":"Reg_Z_487","ProcessID":"Proc_13","Name":"Z","Size":2},{"ID":"Reg_SP_488","ProcessID":"Proc_13","Name":"SP","Size":2},{"ID":"Reg_R0_489","ProcessID":"Proc_13","Name":"R0","Size":1},{"ID":"Reg_R1_490","ProcessID":"Proc_13","Name":"R1","Size":1},{"ID":"Reg_R2_491","ProcessID":"Proc_13","Name":"R2","Size":1},{"ID":"Reg_R3_492","ProcessID":"Proc_13","Name":"R3","Size":1},{"ID":"Reg_R4_493","ProcessID":"Proc_13","Name":"R4","Size":1},{"ID":"Reg_R5_494","ProcessID":"Proc_13","Name":"R5","Size":1},{"ID":"Reg_R6_495","ProcessID":"Proc_13","Name":"R6","Size":1},{"ID":"Reg_R7_496","ProcessID":"Proc_13","Name":"R7","Size":1},{"ID":"Reg_R8_497","ProcessID":"Proc_13","Name":"R8","Size":1},{"ID":"Reg_R9_498","ProcessID":"Proc_13","Name":"R9","Size":1},{"ID":"Reg_R10_499","ProcessID":"Proc_13","Name":"R10","Size":1},{"ID":"Reg_R11_500","ProcessID":"Proc_13","Name":"R11","Size":1},{"ID":"Reg_R12_501","ProcessID":"Proc_13","Name":"R12","Size":1},{"ID":"Reg_R13_502","ProcessID":"Proc_13","Name":"R13","Size":1},{"ID":"Reg_R14_503","ProcessID":"Proc_13","Name":"R14","Size":1},{"ID":"Reg_R15_504","ProcessID":"Proc_13","Name":"R15","Size":1},{"ID":"Reg_R16_505","ProcessID":"Proc_13","Name":"R16","Size":1},{"ID":"Reg_R17_506","ProcessID":"Proc_13","Name":"R17","Size":1},{"ID":"Reg_R18_507","ProcessID":"Proc_13","Name":"R18","Size":1},{"ID":"Reg_R19_508","ProcessID":"Proc_13","Name":"R19","Size":1},{"ID":"Reg_R20_509","ProcessID":"Proc_13","Name":"R20","Size":1},{"ID":"Reg_R21_510","ProcessID":"Proc_13","Name":"R21","Size":1},{"ID":"Reg_R22_511","ProcessID":"Proc_13","Name":"R22","Size":1},{"ID":"Reg_R23_512","ProcessID":"Proc_13","Name":"R23","Size":1},{"ID":"Reg_R24_513","ProcessID":"Proc_13","Name":"R24","Size":1},{"ID":"Reg_R25_514","ProcessID":"Proc_13","Name":"R25","Size":1},{"ID":"Reg_R26_515","ProcessID":"Proc_13","Name":"R26","Size":1},{"ID":"Reg_R27_516","ProcessID":"Proc_13","Name":"R27","Size":1},{"ID":"Reg_R28_517","ProcessID":"Proc_13","Name":"R28","Size":1},{"ID":"Reg_R29_518","ProcessID":"Proc_13","Name":"R29","Size":1},{"ID":"Reg_R30_519","ProcessID":"Proc_13","Name":"R30","Size":1},{"ID":"Reg_R31_520","ProcessID":"Proc_13","Name":"R31","Size":1}]' )
		regs = join_ld_to_list(regs_raw, regs_info, 0, 'ID', ['Name'])
		print(regs)
		regs = [[reg[3],reg[1],reg[2]] for reg in regs]
		print(regs) # [['CYCLE_COUNTER', 0, 8], ['PC', 0, 4], ['SREG', 0, 1], ['FP', 0, 2], ['X', 0, 2], ['Y', 0, 2], ['Z', 0, 2], ['SP', 0, 2], ['R0', 0, 1], ['R1', 0, 1], ['R2', 0, 1], ['R3', 0, 1], ['R4', 0, 1], ['R5', 0, 1], ['R6', 0, 1], ['R7', 0, 1], ['R8', 0, 1], ['R9', 0, 1], ['R10', 0, 1], ['R11', 0, 1], ['R12', 0, 1], ['R13', 0, 1], ['R14', 0, 1], ['R15', 0, 1], ['R16', 0, 1], ['R17', 0, 1], ['R18', 0, 1], ['R19', 0, 1], ['R20', 0, 1], ['R21', 0, 1], ['R22', 0, 1], ['R23', 0, 1], ['R24', 0, 1], ['R25', 0, 1], ['R26', 0, 1], ['R27', 0, 1], ['R28', 0, 1], ['R29', 0, 1], ['R30', 0, 1], ['R31', 0, 1]]

	def test3():
		# Ожидание:
		#     Джойнит лист словарей к листу
		#     но у листа словарей нет некоторых элементов для джойна с листом
		#     Об этом должен сообщить avr_logger в файле логов
		regs_raw = json.loads( '[["Reg_CYCLE_COUNTER_481",0,8],["Reg_PC_482",0,4],["Reg_SREG_483",0,1],["Reg_FP_484",0,2],["Reg_X_485",0,2],["Reg_Y_486",0,2],["Reg_Z_487",0,2],["Reg_SP_488",0,2],["Reg_R0_489",0,1],["Reg_R1_490",0,1],["Reg_R2_491",0,1],["Reg_R3_492",0,1],["Reg_R4_493",0,1],["Reg_R5_494",0,1],["Reg_R6_495",0,1],["Reg_R7_496",0,1],["Reg_R8_497",0,1],["Reg_R9_498",0,1],["Reg_R10_499",0,1],["Reg_R11_500",0,1],["Reg_R12_501",0,1],["Reg_R13_502",0,1],["Reg_R14_503",0,1],["Reg_R15_504",0,1],["Reg_R16_505",0,1],["Reg_R17_506",0,1],["Reg_R18_507",0,1],["Reg_R19_508",0,1],["Reg_R20_509",0,1],["Reg_R21_510",0,1],["Reg_R22_511",0,1],["Reg_R23_512",0,1],["Reg_R24_513",0,1],["Reg_R25_514",0,1],["Reg_R26_515",0,1],["Reg_R27_516",0,1],["Reg_R28_517",0,1],["Reg_R29_518",0,1],["Reg_R30_519",0,1],["Reg_R31_520",0,1]]' )
		regs_info = json.loads( '[{"ID":"Reg_PC_482","ProcessID":"Proc_13","Name":"PC","Size":4},{"ID":"Reg_SREG_483","ProcessID":"Proc_13","Name":"SREG","Size":1},{"ID":"Reg_FP_484","ProcessID":"Proc_13","Name":"FP","Size":2},{"ID":"Reg_X_485","ProcessID":"Proc_13","Name":"X","Size":2},{"ID":"Reg_Y_486","ProcessID":"Proc_13","Name":"Y","Size":2},{"ID":"Reg_Z_487","ProcessID":"Proc_13","Name":"Z","Size":2},{"ID":"Reg_SP_488","ProcessID":"Proc_13","Name":"SP","Size":2},{"ID":"Reg_R0_489","ProcessID":"Proc_13","Name":"R0","Size":1},{"ID":"Reg_R1_490","ProcessID":"Proc_13","Name":"R1","Size":1},{"ID":"Reg_R2_491","ProcessID":"Proc_13","Name":"R2","Size":1},{"ID":"Reg_R3_492","ProcessID":"Proc_13","Name":"R3","Size":1},{"ID":"Reg_R4_493","ProcessID":"Proc_13","Name":"R4","Size":1},{"ID":"Reg_R5_494","ProcessID":"Proc_13","Name":"R5","Size":1},{"ID":"Reg_R6_495","ProcessID":"Proc_13","Name":"R6","Size":1},{"ID":"Reg_R7_496","ProcessID":"Proc_13","Name":"R7","Size":1},{"ID":"Reg_R8_497","ProcessID":"Proc_13","Name":"R8","Size":1},{"ID":"Reg_R9_498","ProcessID":"Proc_13","Name":"R9","Size":1},{"ID":"Reg_R10_499","ProcessID":"Proc_13","Name":"R10","Size":1},{"ID":"Reg_R11_500","ProcessID":"Proc_13","Name":"R11","Size":1},{"ID":"Reg_R12_501","ProcessID":"Proc_13","Name":"R12","Size":1},{"ID":"Reg_R13_502","ProcessID":"Proc_13","Name":"R13","Size":1},{"ID":"Reg_R14_503","ProcessID":"Proc_13","Name":"R14","Size":1},{"ID":"Reg_R15_504","ProcessID":"Proc_13","Name":"R15","Size":1},{"ID":"Reg_R16_505","ProcessID":"Proc_13","Name":"R16","Size":1},{"ID":"Reg_R17_506","ProcessID":"Proc_13","Name":"R17","Size":1},{"ID":"Reg_R18_507","ProcessID":"Proc_13","Name":"R18","Size":1},{"ID":"Reg_R19_508","ProcessID":"Proc_13","Name":"R19","Size":1},{"ID":"Reg_R20_509","ProcessID":"Proc_13","Name":"R20","Size":1},{"ID":"Reg_R21_510","ProcessID":"Proc_13","Name":"R21","Size":1},{"ID":"Reg_R22_511","ProcessID":"Proc_13","Name":"R22","Size":1},{"ID":"Reg_R23_512","ProcessID":"Proc_13","Name":"R23","Size":1},{"ID":"Reg_R24_513","ProcessID":"Proc_13","Name":"R24","Size":1},{"ID":"Reg_R25_514","ProcessID":"Proc_13","Name":"R25","Size":1},{"ID":"Reg_R26_515","ProcessID":"Proc_13","Name":"R26","Size":1},{"ID":"Reg_R27_516","ProcessID":"Proc_13","Name":"R27","Size":1},{"ID":"Reg_R28_517","ProcessID":"Proc_13","Name":"R28","Size":1},{"ID":"Reg_R29_518","ProcessID":"Proc_13","Name":"R29","Size":1},{"ID":"Reg_R30_519","ProcessID":"Proc_13","Name":"R30","Size":1},{"ID":"Reg_R31_520","ProcessID":"Proc_13","Name":"R31","Size":1}]' )
		regs = join_ld_to_list(regs_raw, regs_info, 0, 'ID', ['Name'])
		print(regs)
		try:
			regs = [[reg[3],reg[1],reg[2]] for reg in regs]	# Эта строка должна выдать ошибку, так как не у всех столбцов есть 4 элемент
		except:
			print('как и ожидалось, словили ошибку')
		print(regs)

	def test4():
		# Ожидание:
		#     Джойнит непонятно что к листу
		#     не продолжить работу, но при этом записать ошибку в логи
		regs_raw = json.loads( '[["Reg_CYCLE_COUNTER_481",0,8],["Reg_PC_482",0,4],["Reg_SREG_483",0,1],["Reg_FP_484",0,2],["Reg_X_485",0,2],["Reg_Y_486",0,2],["Reg_Z_487",0,2],["Reg_SP_488",0,2],["Reg_R0_489",0,1],["Reg_R1_490",0,1],["Reg_R2_491",0,1],["Reg_R3_492",0,1],["Reg_R4_493",0,1],["Reg_R5_494",0,1],["Reg_R6_495",0,1],["Reg_R7_496",0,1],["Reg_R8_497",0,1],["Reg_R9_498",0,1],["Reg_R10_499",0,1],["Reg_R11_500",0,1],["Reg_R12_501",0,1],["Reg_R13_502",0,1],["Reg_R14_503",0,1],["Reg_R15_504",0,1],["Reg_R16_505",0,1],["Reg_R17_506",0,1],["Reg_R18_507",0,1],["Reg_R19_508",0,1],["Reg_R20_509",0,1],["Reg_R21_510",0,1],["Reg_R22_511",0,1],["Reg_R23_512",0,1],["Reg_R24_513",0,1],["Reg_R25_514",0,1],["Reg_R26_515",0,1],["Reg_R27_516",0,1],["Reg_R28_517",0,1],["Reg_R29_518",0,1],["Reg_R30_519",0,1],["Reg_R31_520",0,1]]' )
		regs_info = ''
		regs = join_ld_to_list(regs_raw, regs_info, 0, 'ID', ['Name'])
		print(regs)
		try:
			regs = [[reg[3],reg[1],reg[2]] for reg in regs]	# Эта строка должна выдать ошибку, так как не у всех столбцов есть 4 элемент
		except:
			print('как и ожидалось, словили ошибку')
		print(regs)

	def test5():
		# Ожидание:
		#     Джойнит словарь к листу
		# Результат:
		#     тот же что и в тесте 3
		regs_raw = json.loads( '[["Reg_CYCLE_COUNTER_241",0,8],["Reg_PC_242",0,4],["Reg_SREG_243",0,1],["Reg_FP_244",0,2],["Reg_X_245",0,2],["Reg_Y_246",0,2],["Reg_Z_247",0,2],["Reg_SP_248",0,2],["Reg_R0_249",0,1],["Reg_R1_250",0,1],["Reg_R2_251",0,1],["Reg_R3_252",0,1],["Reg_R4_253",0,1],["Reg_R5_254",0,1],["Reg_R6_255",0,1],["Reg_R7_256",0,1],["Reg_R8_257",0,1],["Reg_R9_258",0,1],["Reg_R10_259",0,1],["Reg_R11_260",0,1],["Reg_R12_261",0,1],["Reg_R13_262",0,1],["Reg_R14_263",0,1],["Reg_R15_264",0,1],["Reg_R16_265",0,1],["Reg_R17_266",0,1],["Reg_R18_267",0,1],["Reg_R19_268",0,1],["Reg_R20_269",0,1],["Reg_R21_270",0,1],["Reg_R22_271",0,1],["Reg_R23_272",0,1],["Reg_R24_273",0,1],["Reg_R25_274",0,1],["Reg_R26_275",0,1],["Reg_R27_276",0,1],["Reg_R28_277",0,1],["Reg_R29_278",0,1],["Reg_R30_279",0,1],["Reg_R31_280",0,1]]' )
		regs_info = give_mainkey_to_dd({'CYCLE_COUNTER': {'ID': 'Reg_CYCLE_COUNTER_241', 'ProcessID': 'Proc_7', 'Size': 8}, 'PC': {'ID': 'Reg_PC_242', 'ProcessID': 'Proc_7', 'Size': 4}, 'SREG': {'ID': 'Reg_SREG_243', 'ProcessID': 'Proc_7', 'Size': 1}, 'FP': {'ID': 'Reg_FP_244', 'ProcessID': 'Proc_7', 'Size': 2}, 'X': {'ID': 'Reg_X_245', 'ProcessID': 'Proc_7', 'Size': 2}, 'Y': {'ID': 'Reg_Y_246', 'ProcessID': 'Proc_7', 'Size': 2}, 'Z': {'ID': 'Reg_Z_247', 'ProcessID': 'Proc_7', 'Size': 2}, 'SP': {'ID': 'Reg_SP_248', 'ProcessID': 'Proc_7', 'Size': 2}, 'R0': {'ID': 'Reg_R0_249', 'ProcessID': 'Proc_7', 'Size': 1}, 'R1': {'ID': 'Reg_R1_250', 'ProcessID': 'Proc_7', 'Size': 1}, 'R2': {'ID': 'Reg_R2_251', 'ProcessID': 'Proc_7', 'Size': 1}, 'R3': {'ID': 'Reg_R3_252', 'ProcessID': 'Proc_7', 'Size': 1}, 'R4': {'ID': 'Reg_R4_253', 'ProcessID': 'Proc_7', 'Size': 1}, 'R5': {'ID': 'Reg_R5_254', 'ProcessID': 'Proc_7', 'Size': 1}, 'R6': {'ID': 'Reg_R6_255', 'ProcessID': 'Proc_7', 'Size': 1}, 'R7': {'ID': 'Reg_R7_256', 'ProcessID': 'Proc_7', 'Size': 1}, 'R8': {'ID': 'Reg_R8_257', 'ProcessID': 'Proc_7', 'Size': 1}, 'R9': {'ID': 'Reg_R9_258', 'ProcessID': 'Proc_7', 'Size': 1}, 'R10': {'ID': 'Reg_R10_259', 'ProcessID': 'Proc_7', 'Size': 1}, 'R11': {'ID': 'Reg_R11_260', 'ProcessID': 'Proc_7', 'Size': 1}, 'R12': {'ID': 'Reg_R12_261', 'ProcessID': 'Proc_7', 'Size': 1}, 'R13': {'ID': 'Reg_R13_262', 'ProcessID': 'Proc_7', 'Size': 1}, 'R14': {'ID': 'Reg_R14_263', 'ProcessID': 'Proc_7', 'Size': 1}, 'R15': {'ID': 'Reg_R15_264', 'ProcessID': 'Proc_7', 'Size': 1}, 'R16': {'ID': 'Reg_R16_265', 'ProcessID': 'Proc_7', 'Size': 1}, 'R17': {'ID': 'Reg_R17_266', 'ProcessID': 'Proc_7', 'Size': 1}, 'R18': {'ID': 'Reg_R18_267', 'ProcessID': 'Proc_7', 'Size': 1}, 'R19': {'ID': 'Reg_R19_268', 'ProcessID': 'Proc_7', 'Size': 1}, 'R20': {'ID': 'Reg_R20_269', 'ProcessID': 'Proc_7', 'Size': 1}, 'R21': {'ID': 'Reg_R21_270', 'ProcessID': 'Proc_7', 'Size': 1}, 'R22': {'ID': 'Reg_R22_271', 'ProcessID': 'Proc_7', 'Size': 1}, 'R23': {'ID': 'Reg_R23_272', 'ProcessID': 'Proc_7', 'Size': 1}, 'R24': {'ID': 'Reg_R24_273', 'ProcessID': 'Proc_7', 'Size': 1}, 'R25': {'ID': 'Reg_R25_274', 'ProcessID': 'Proc_7', 'Size': 1}, 'R26': {'ID': 'Reg_R26_275', 'ProcessID': 'Proc_7', 'Size': 1}, 'R27': {'ID': 'Reg_R27_276', 'ProcessID': 'Proc_7', 'Size': 1}, 'R28': {'ID': 'Reg_R28_277', 'ProcessID': 'Proc_7', 'Size': 1}, 'R29': {'ID': 'Reg_R29_278', 'ProcessID': 'Proc_7', 'Size': 1}, 'R30': {'ID': 'Reg_R30_279', 'ProcessID': 'Proc_7', 'Size': 1}, 'R31': {'ID': 'Reg_R31_280', 'ProcessID': 'Proc_7', 'Size': 1}},
									   main_key_name='Name')
		print(regs_info)
		regs = join_ld_to_list(regs_raw, regs_info, 0, 'ID', ['Name'])
		print(regs)
		try:
			regs = [[reg[3],reg[1],reg[2]] for reg in regs]	# Эта строка должна выдать ошибку, так как не у всех столбцов есть 4 элемент
		except:
			print('Здесь ошибки быть не лолжно, исправляем код')
		print(regs)



	test5()

if __name__=='__main__':
	test()