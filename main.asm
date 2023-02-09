.include "m328Pdef.inc"


; �������� ���������
call setup
main:
	inc r19
	nop
	nop
	call USB_debug		; ������ �������
	nop
	nop
	inc r19
	nop
	nop
	call USB_debug		; ������ �������
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

; ���� �������������� � �����������
USB_debug:
; ������������� ����������� ����������
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

; �������� ���� 
loop:
	;call recv
	;call send
	; ������ ��� �������
	; r = msg[0:1]
	call recv

	; ������ ���������
	read:
		; ���������, ���� �� �������. ���� ��� - �� ��������� � �������� ���������
		cpi r, 'r'			
		brne write

		; ������ ��������----
		; ������ �����
		call recv
		mov  Xh,r				; X[0:1] = msg[1:2]
		call recv
		mov  Xl,r

		; ��������� �������--
		; ������ ���� �� ������ msg[1:2]
		ld r, X
		call send

		rjmp loop

	write:
		; ���������, ���� �� �������. ���� ��� - �� ��������� � �������� ���������
		cpi r, 'w'			
		brne step

		; ������ ��������----
		; ������ �����
		call recv
		mov  Xh,r				; X[0:1] = msg[1:2]
		call recv
		mov  Xl,r
		; ������ ��������
		call recv

		; ��������� �������--
		; ���������� ���� �� ������ msg[1:2]
		st X, r
		ld r, X					; �������� ����� �������� � ���� ������
		call send

		rjmp loop

	step:
		; ���������, ���� �� ��� ���������, ���� ���, �� ��������� � �������� ���������
		cpi r, 's'
		brne getStatus
		
		; ������� �� ������������ � ��������� ��������� ������� �������� ���������
		rjmp exit

	getStatus:
		cpi r, 'u'
		brne setStatus
			
		mov r,StatusValue		; ���������� � r �������� �������� ������ SREG
		call send				; ���������� r, � ������� �������� SREG
			
		rjmp loop				;	������� �� ���������
	setStatus:
		; ���������, ���� �� ��� ���������, ���� ���, �� ��������� � �������� ���������
		cpi r, 'U'
		brne getStack
		
		call recv				; ������ ������������ �������� SREG
		mov StatusValue, r				; ���������� ����� �������� SREG 

		call send
		rjmp loop

	getStack:
		; ���������, ���� �� ��� ���������, ���� ���, �� ��������� � �������� ���������
		cpi r, 'a'
		brne setStack
			
		mov r, StackValueH		; ���������� � r �������� SPL
		call send				; ���������� r, � ������� �������� SPL
			
		mov r,StackValueL		; ���������� � r �������� SPH	
		call send				; ���������� r, � ������� �������� SPH
			
		rjmp loop

	setStack:
		; ���������, ���� �� ��� ���������, ���� ���, �� ��������� � �������� ���������
		cpi r, 'A'
		brne readProg

		; �������� ���������
		; ��������� �������� SPH
		call recv
		mov StackValueH, r

		call recv
		mov StackValueL, r

		; ������� ���������� ��������
		mov r, StackValueH
		call send
		mov r, StackValueL
		call send

		rjmp loop 
	readProg:
		; ���������, ���� �� ��� ���������, ���� ���, �� ��������� � �������� ���������
		cpi r, 'p'
		brne readEeprom

		; �������� ���������
		; ��������� ������ ������ Flash, �� ������� ��������� ������
		; ������� ����� �������� Z
		call recv
		mov ZH, r
		; ������� ����� �������� Z
		call recv
		mov ZL, r
		lpm r, Z ; ��������� �������� �� �����
		call send ; Serial.write (�������� ����������� ��������)

		rjmp loop
	readEeprom:
		; ���������, ���� �� ��� ���������, ���� ���, �� ��������� � �������� ���������
		cpi r, 'e'
		brne getPC

		; �������� ���������
		
		; ��������� ������ ������ EEPROM, �� ������� ��������� ������
		; ������� ����� �������� EEAR
		call recv
		;out EEARH, r
		; ������� ����� �������� EEAR
		call recv
		;out EEARL, r
		/*
		sbi EECR,EERE			; ���������� ��� ������
		in r, EEDR 				; �������� �� �������� ������ ���������
		call send				; Serial.write (�������� ����������� ��������)
		*/
		ldi r, 0
		call send
		rjmp loop

	getPC:
		; ���������, ���� �� ��� ���������, ���� ���, �� ��������� � �������� ���������
		cpi r, 'o'
		brne setPC

		; �������� ���������
		mov r, PCValueH			; ���������� � r �������� PCValueH
		call send				; ���������� r, � ������� �������� PCValueH
		mov r, PCValueL			; ���������� � r �������� PCValueL
		call send				; ���������� r, � ������� �������� PCValueL

		rjmp loop

	setPC:
		; ���������, ���� �� ��� ���������, ���� ���, �� ��������� � �������� ���������
		cpi r, 'O'
		brne skip
			

		; �������� ���������
		; ��������� �������� PCValue
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
	




; ������� USB (UART)
; �������������� ���������
setup:
		ldi tmp, 0x0C	; 0x67 - 6900, 0x0C - 76800
		sts UBRR0L, tmp
		ldi tmp, 0x00
		sts UBRR0H, tmp
		ldi tmp, (1  << RXEN0) | (1 << TXEN0)
		sts UCSR0B,tmp
		ldi tmp , (1 << UCSZ01) | (1 << UCSZ00)
		sts UCSR0C , tmp 

		; ����� � ����������
		ldi r, READY_BYTE
		call send
		ret

; ���� 1 �����
; ����:
; - r - ���� ��� ������
recv:
	; tmp = (UCSR0A & (1 << RXC0))
	lds tmp, UCSR0A
	andi tmp, (1 << RXC0)
	cpi  tmp , 0x00
	breq recv
	lds r, UDR0
	ret


; �������� 1 �����
; �����:
; - r - ���� ��� ������
send:
	; tmp = UCSR0A & (1<<UDRE0)
	lds tmp, UCSR0A
	andi tmp, (1 << UDRE0)
	cpi tmp, 0x00
	breq send
	sts UDR0,r
	ret


	