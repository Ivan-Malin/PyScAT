# Функции для рабоыт с выражениями
# EXPs =  [
#		    {
#				"ID":"expr_3",				- ID выражения
#				"Name":"byte{registers}@R16" - его содержание для последующего присвоения. 
#		    },
#		  ]


def remove_exp(EXPs_in, exp_id):
	# Удаляет точку останова из BPs_in
	# Ввод:
	# - EXPs_in	- лист выражений
	# - exp_id 	- ID выражения
	# Вывод:
	# - EXPs 	- лист выражений с удалённым выражением (с ID exp_id)

	return list(filter(lambda x: x['ID'] != exp_id, EXPs_in))

#def get_expr(EXPs_in, exp_id):
	# Получает выражение по по его ID
	#find_dict_by_key_in_dict_list
