.include "m328Pdef.inc"


; Основная программа
call setup
main:
	inc r19
	nop
	nop
	call USB_debug		; Запуск отладки
	nop
	nop
	inc r19
	nop
	nop
	call USB_debug		; Запуск отладки
	rjmp main





































.equ SIGNAL_BYTE = 0x00
.equ START_BYTE = 0x00
.def tmp = r20
.def r = r18
.def a = r21
.equ READY_BYTE = '_'
.equ FINISH_BYTE = '\n'
.def StatusValue  = r22
.def StackValueH  = r23
.def StackValueL  = r24
.def PCValueH	  = r16
.def PCValueL     = r17

; Блок взаимодействия с компьютером
USB_debug:
; Инициализация виртуальных переменных
init:
	in StatusValue,SREG
	in StackValueH, SPH
	in StackValueL, SPL 
	in StackValueL, SPL
	pop PCValueH
	pop PCValueL
	push PCValueL
	push PCValueH

	rjmp loop

; Основной цикл 
loop:
	;call recv
	;call send
	; Читаем код команды
	; r = msg[0:1]
	call recv

	; Делаем ветвления
	read:
		; Проверяем, наша ли команда. Если нет - то периходим к проверке следующей
		cpi r, 'r'			
		brne write

		; Читаем операнды----
		; Читаем адрес
		call recv
		mov  Xh,r				; X[0:1] = msg[1:2]
		call recv
		mov  Xl,r

		; Исполняем команду--
		; Читаем байт по адресу msg[1:2]
		ld r, X
		call send

		rjmp loop

	write:
		; Проверяем, наша ли команда. Если нет - то периходим к проверке следующей
		cpi r, 'w'			
		brne step

		; Читаем операнды----
		; Читаем адрес
		call recv
		mov  Xh,r				; X[0:1] = msg[1:2]
		call recv
		mov  Xl,r
		; Читаем значение
		call recv

		; Исполняем команду--
		; Записываем байт по адресу msg[1:2]
		st X, r
		ld r, X					; Получаем новое значение в этой ячейке
		call send

		rjmp loop

	step:
		; проверяем, наша ли это программа, если нет, то переходим к проверке следующей
		cpi r, 's'
		brne getStatus
		
		; Выходим из подпрограммы и исполняем следующую команду основной программы
		rjmp exit

	getStatus:
		cpi r, 'u'
		brne setStatus
			
		mov r,StatusValue		; записываем в r значение регистра флагов SREG
		call send				; отправляем r, в котором хранится SREG
			
		rjmp loop				;	выходим из ветвления
	setStatus:
		; проверяем, наша ли это программа, если нет, то переходим к проверке следующей
		cpi r, 'U'
		brne getStack
		
		call recv				; Читаем отправленное значение SREG
		mov StatusValue, r				; Записываем новое значение SREG 

		call send
		rjmp loop

	getStack:
		; проверяем, наша ли это программа, если нет, то переходим к проверке следующей
		cpi r, 'a'
		brne setStack
			
		mov r, StackValueH		; записываем в r значение SPL
		call send				; отправляем r, в котором хранится SPL
			
		mov r,StackValueL		; записываем в r значение SPH	
		call send				; отправляем r, в котором хранится SPH
			
		rjmp loop

	setStack:
		; проверяем, наша ли это программа, если нет, то переходим к проверке следующей
		cpi r, 'A'
		brne readProg

		; Основная программа
		; Установка значений SPH
		call recv
		mov StackValueH, r

		call recv
		mov StackValueL, r

		; Выводим записанное значение
		mov r, StackValueH
		call send
		mov r, StackValueL
		call send

		rjmp loop 
	readProg:
		; проверяем, наша ли это программа, если нет, то переходим к проверке следующей
		cpi r, 'p'
		brne readEeprom

		; Основная программа
		; Установка адреса ячейки Flash, из которой считывать данные
		; Старшая часть регистра Z
		call recv
		mov ZH, r
		; Младшая часть регистра Z
		call recv
		mov ZL, r
		lpm r, Z ; Получение значения из флеша
		call send ; Serial.write (Отправка полученного значения)

		rjmp loop
	readEeprom:
		; проверяем, наша ли это программа, если нет, то переходим к проверке следующей
		cpi r, 'e'
		brne getPC

		; Основная программа
		
		; Установка адреса ячейки EEPROM, из которой считывать данные
		; Старшая часть регистра EEAR
		call recv
		;out EEARH, r
		; Младшая часть регистра EEAR
		call recv
		;out EEARL, r
		/*
		sbi EECR,EERE			; Выставляем бит чтения
		in r, EEDR 				; Забираем из регистра данных результат
		call send				; Serial.write (Отправка полученного значения)
		*/
		ldi r, 0
		call send
		rjmp loop

	getPC:
		; проверяем, наша ли это программа, если нет, то переходим к проверке следующей
		cpi r, 'o'
		brne setPC

		; Основная программа
		mov r, PCValueH			; записываем в r значение PCValueH
		call send				; отправляем r, в котором хранится PCValueH
		mov r, PCValueL			; записываем в r значение PCValueL
		call send				; отправляем r, в котором хранится PCValueL

		rjmp loop

	setPC:
		; проверяем, наша ли это программа, если нет, то переходим к проверке следующей
		cpi r, 'O'
		brne skip
			

		; Основная программа
		; Установка значений PCValue
		call recv
		mov  PCValueH ,r	
		call recv
		mov PCValueL, r


		; Serial.write
		; send b
		mov r, PCValueH
		call send
		mov r, PCValueL
		call send
		skip:
			rjmp loop

exit:
	sts SREG, StatusValue
	sts SPH, StackValueH
	sts SPL, StackValueL
	push PCValueL
	push PCValueH
	ret
	




; Команды USB (UART)
; Первоначальная настройка
setup:
		ldi tmp, 0x0C	; 0x67 - 6900, 0x0C - 76800
		sts UBRR0L, tmp
		ldi tmp, 0x00
		sts UBRR0H, tmp
		ldi tmp, (1  << RXEN0) | (1 << TXEN0)
		sts UCSR0B,tmp
		ldi tmp , (1 << UCSZ01) | (1 << UCSZ00)
		sts UCSR0C , tmp 

		; вывод о готовности
		ldi r, READY_BYTE
		call send
		ret

; Приём 1 байта
; Ввод:
; - r - байт для вывода
recv:
	; tmp = (UCSR0A & (1 << RXC0))
	lds tmp, UCSR0A
	andi tmp, (1 << RXC0)
	cpi  tmp , 0x00
	breq recv
	lds r, UDR0
	ret


; Отправка 1 байта
; Вывод:
; - r - байт для вывода
send:
	; tmp = UCSR0A & (1<<UDRE0)
	lds tmp, UCSR0A
	andi tmp, (1 << UDRE0)
	cpi tmp, 0x00
	breq send
	sts UDR0,r
	ret


	